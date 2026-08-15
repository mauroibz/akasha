import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from sqlalchemy import Engine, and_, case, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from book_tracker.domain.domains import (
    DOMAINS,
    Domain,
    InvalidEntryField,
    InvalidFormat,
    InvalidStatus,
    validate_entry_fields,
    validate_formats,
    validate_status,
)
from book_tracker.domain.normalization import normalize_text, shelf_slug
from book_tracker.domain.pagination import CursorError, CursorState, decode_cursor, encode_cursor
from book_tracker.infrastructure.attachments import (
    StoredBlob,
    delete_blob_if_unreferenced,
)
from book_tracker.infrastructure.models import (
    AttachmentRow,
    EntryFormatRow,
    EntryRow,
    EntryShelfRow,
    ItemIdentifierRow,
    ItemRow,
    ItemSourceRow,
    ShelfRow,
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


MAX_FILENAME_LENGTH = 255


def clean_attachment_filename(raw: str) -> str | None:
    """The one rule for an attachment's name, wherever it arrives from.

    A name never becomes a path component (DEC-048), so this is not what stops
    traversal — the digest being the path is. It runs anyway because the name is
    echoed straight back out in a `Content-Disposition`, and a name carrying
    directories is a name that reads as a path to whatever receives it next.

    Returns `None` for anything that is not a name, so upload can fall back to a
    default and rename can refuse: a file with no name at all is worse than the
    name it already had.
    """
    name = PurePosixPath(raw.strip()).name.strip()
    if not name or name in {".", ".."}:
        return None
    return name[:MAX_FILENAME_LENGTH]


class LibraryError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 409,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = dict(details or {})
        super().__init__(message)


class LibraryService:
    def __init__(self, engine: Engine, user_id: int = 1) -> None:
        self.engine = engine
        self.user_id = user_id

    @contextmanager
    def _write(self) -> Iterator[Session]:
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            session = Session(bind=connection)
            try:
                yield session
                session.flush()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                session.close()

    def _entry(self, session: Session, entry_id: int) -> EntryRow:
        entry = session.scalar(
            select(EntryRow).where(EntryRow.id == entry_id, EntryRow.user_id == self.user_id)
        )
        if entry is None:
            raise LibraryError("entry_not_found", "Entry was not found", status_code=404)
        return entry

    def _item(self, session: Session, item_id: int) -> ItemRow:
        item = session.get(ItemRow, item_id)
        if item is None:
            raise LibraryError("item_not_found", "Item was not found", status_code=404)
        return item

    def _domain(self, session: Session, entry: EntryRow) -> Domain:
        """The domain of the item this entry hangs on.

        Every per-entry rule in this module is keyed on this rather than on a
        parameter, so a caller cannot pass the wrong one and no path can forget to
        ask (DEC-052 seam 5b).
        """
        item_type = str(self._item(session, entry.item_id).type)
        domain = DOMAINS.get(item_type)
        if domain is None:
            raise LibraryError("unknown_item_type", f"No domain describes {item_type!r}")
        return domain

    def _validated(self, domain: Domain, changes: Mapping[str, Any]) -> dict[str, Any]:
        """Check a set of entry changes against the domain that owns the item.

        One place rather than three, because `update_entry`, `bulk_update` and the
        add path all write the same fields and a rule enforced in two of them is a
        rule the third quietly breaks.
        """
        try:
            validated = validate_entry_fields(domain, changes)
            if changes.get("status") is not None:
                validate_status(domain, changes["status"])
            if changes.get("formats") is not None:
                validated["formats"] = validate_formats(domain, changes["formats"])
            for key in ("add_formats", "remove_formats"):
                if changes.get(key):
                    validated[key] = validate_formats(domain, changes[key])
        except InvalidStatus as error:
            raise LibraryError("invalid_status", str(error), status_code=422) from error
        except InvalidFormat as error:
            raise LibraryError("invalid_format", str(error), status_code=422) from error
        except InvalidEntryField as error:
            raise LibraryError("invalid_entry_field", str(error), status_code=422) from error
        return validated

    def _formats_for_entry(self, session: Session, entry_id: int, domain: Domain) -> list[str]:
        """The entry's formats in the domain's declared order, not the row order.

        `Vinyl, Digital` reads the way the control offers them; alphabetical would
        put "CD" first for no reason a reader could name.
        """
        held = set(
            session.scalars(
                select(EntryFormatRow.format).where(EntryFormatRow.entry_id == entry_id)
            )
        )
        return [row.value for row in domain.formats if row.value in held]

    def _set_formats(self, session: Session, entry_id: int, values: Sequence[str]) -> None:
        session.execute(delete(EntryFormatRow).where(EntryFormatRow.entry_id == entry_id))
        session.add_all(EntryFormatRow(entry_id=entry_id, format=value) for value in values)

    def _shelf(self, session: Session, shelf_id: int) -> ShelfRow:
        shelf = session.scalar(
            select(ShelfRow).where(ShelfRow.id == shelf_id, ShelfRow.user_id == self.user_id)
        )
        if shelf is None:
            raise LibraryError("shelf_not_found", "Shelf was not found", status_code=404)
        return shelf

    def _shelves_for_entry(self, session: Session, entry_id: int) -> list[dict[str, Any]]:
        rows = session.execute(
            select(ShelfRow)
            .join(EntryShelfRow, EntryShelfRow.shelf_id == ShelfRow.id)
            .where(EntryShelfRow.entry_id == entry_id)
            .order_by(ShelfRow.name.collate("NOCASE"), ShelfRow.id)
        ).scalars()
        return [self._shelf_dict(row) for row in rows]

    @staticmethod
    def _shelf_dict(shelf: ShelfRow) -> dict[str, Any]:
        return {"id": shelf.id, "name": shelf.name, "slug": shelf.slug}

    def _entry_dict(self, session: Session, entry: EntryRow) -> dict[str, Any]:
        item = self._item(session, entry.item_id)
        domain = self._domain(session, entry)
        return {
            "id": entry.id,
            "item_id": entry.item_id,
            "status": entry.status,
            "score": entry.score,
            "notes": entry.notes,
            "date_added": entry.date_added,
            "date_started": entry.date_started,
            "date_finished": entry.date_finished,
            "reread_count": entry.reread_count,
            "score_provisional": bool(entry.score_provisional),
            "suggested_status": entry.suggested_status,
            "item": self._item_dict(session, item),
            "shelves": self._shelves_for_entry(session, entry.id),
            "formats": self._formats_for_entry(session, entry.id, domain),
        }

    @staticmethod
    def _item_dict(session: Session, item: ItemRow) -> dict[str, Any]:
        identifiers = session.execute(
            select(ItemIdentifierRow.kind, ItemIdentifierRow.normalized_value).where(
                ItemIdentifierRow.item_id == item.id
            )
        ).all()
        sources = session.execute(
            select(ItemSourceRow.source, ItemSourceRow.source_id, ItemSourceRow.is_primary).where(
                ItemSourceRow.item_id == item.id
            )
        ).all()
        metadata = json.loads(item.metadata_json)
        legacy_publishers = metadata.pop("publishers", None)
        if not metadata.get("publisher") and isinstance(legacy_publishers, list):
            metadata["publisher"] = next(
                (str(value).strip() for value in legacy_publishers if str(value).strip()), None
            )
        metadata = {key: value for key, value in metadata.items() if value is not None}
        cover_version = item.updated_at.replace(":", "").replace("-", "")
        return {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "subtitle": item.subtitle,
            "year": item.year,
            # The credit as the source rendered it, and the first creator's name when
            # nobody rendered one: "Dean Blunt Meets James Ferraro" is not the join of
            # the ordered list, and a book's single author is both.
            "creator": metadata.get("credit") or item.creator_primary,
            "creator_sort": item.creator_sort,
            "creator_sort_override": item.creator_sort_override,
            "cover_url": f"/api/items/{item.id}/cover?v={cover_version}"
            if item.cover_path
            else None,
            "metadata": metadata,
            "identifiers": {row.kind: row.normalized_value for row in identifiers},
            "sources": [
                {
                    "source": row.source,
                    "source_id": row.source_id,
                    "is_primary": bool(row.is_primary),
                }
                for row in sources
            ],
        }

    def get_entry(self, entry_id: int) -> dict[str, Any]:
        with Session(self.engine) as session:
            return self._entry_dict(session, self._entry(session, entry_id))

    def update_entry(self, entry_id: int, changes: Mapping[str, Any]) -> dict[str, Any]:
        with self._write() as session:
            entry = self._entry(session, entry_id)
            changes = self._validated(self._domain(session, entry), changes)
            for field in (
                "status",
                "score",
                "notes",
                "date_started",
                "date_finished",
                "reread_count",
            ):
                if field in changes:
                    setattr(entry, field, changes[field])
            if "score" in changes:
                entry.score_provisional = 0
            if "formats" in changes:
                self._set_formats(session, entry.id, changes["formats"])
            if "shelf_ids" in changes:
                shelf_ids = set(changes["shelf_ids"])
                found = set(
                    session.scalars(
                        select(ShelfRow.id).where(
                            ShelfRow.user_id == self.user_id, ShelfRow.id.in_(shelf_ids)
                        )
                    )
                )
                if found != shelf_ids:
                    raise LibraryError(
                        "shelf_not_found", "One or more shelves were not found", status_code=404
                    )
                session.execute(delete(EntryShelfRow).where(EntryShelfRow.entry_id == entry.id))
                session.add_all(
                    EntryShelfRow(entry_id=entry.id, shelf_id=value) for value in shelf_ids
                )
            entry.updated_at = _now()
            session.flush()
            return self._entry_dict(session, entry)

    def delete_entry(self, entry_id: int) -> None:
        with self._write() as session:
            session.delete(self._entry(session, entry_id))

    def get_item(self, item_id: int) -> dict[str, Any]:
        with Session(self.engine) as session:
            return self._item_dict(session, self._item(session, item_id))

    def update_item(self, item_id: int, changes: Mapping[str, Any]) -> dict[str, Any]:
        with self._write() as session:
            item = self._item(session, item_id)
            for field in ("title", "subtitle", "year"):
                if field in changes:
                    setattr(item, field, changes[field])
            if "creator_sort_override" in changes:
                # Blank means "go back to the automatic value", which is why this
                # stores NULL rather than an empty string: the mapper event reads
                # the override to decide whether the heuristic still applies.
                override = (changes["creator_sort_override"] or "").strip()
                item.creator_sort_override = override or None
            if "metadata" in changes:
                metadata = json.loads(item.metadata_json)
                legacy_publishers = metadata.pop("publishers", None)
                if not metadata.get("publisher") and isinstance(legacy_publishers, list):
                    publisher = next(
                        (str(value).strip() for value in legacy_publishers if str(value).strip()),
                        None,
                    )
                    if publisher:
                        metadata["publisher"] = publisher
                for key, value in changes["metadata"].items():
                    if value is None:
                        metadata.pop(key, None)
                    else:
                        metadata[key] = value
                item.metadata_json = json.dumps(metadata, ensure_ascii=False)
            item.updated_at = _now()
            session.flush()
            return self._item_dict(session, item)

    def list_attachments(self, item_id: int) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            self._item(session, item_id)
            rows = session.execute(
                select(AttachmentRow)
                .where(AttachmentRow.item_id == item_id)
                .order_by(AttachmentRow.created_at, AttachmentRow.id)
            ).scalars()
            return [self._attachment_dict(row) for row in rows]

    def ensure_item(self, item_id: int) -> None:
        """Cheap existence check. Called before an upload is read, so a request
        for an item that is not here costs nothing rather than 25 MiB."""
        with Session(self.engine) as session:
            self._item(session, item_id)

    def record_attachment(
        self, item_id: int, *, filename: str, sha256: str, byte_size: int
    ) -> dict[str, Any]:
        """Record an already-stored blob against the item.

        The blob is written before this row on purpose, so a crash between the
        two leaves an unreferenced file rather than a row pointing at nothing:
        one is collectable by `reclaim`, the other is a broken download the owner
        discovers much later.
        """
        now = _now()
        stored = StoredBlob(sha256=sha256, byte_size=byte_size)
        with self._write() as session:
            existing = session.execute(
                select(AttachmentRow).where(
                    AttachmentRow.item_id == item_id, AttachmentRow.sha256 == stored.sha256
                )
            ).scalar_one_or_none()
            if existing is not None:
                # Same bytes on the same item. Refresh the name the owner chose and
                # return the row that already exists rather than duplicating it.
                existing.filename = filename
                existing.updated_at = now
                session.flush()
                return self._attachment_dict(existing)
            row = AttachmentRow(
                item_id=item_id,
                filename=filename,
                byte_size=stored.byte_size,
                sha256=stored.sha256,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return self._attachment_dict(row)

    def rename_attachment(
        self, item_id: int, attachment_id: int, *, filename: str
    ) -> dict[str, Any]:
        """Change what the file is called, and nothing else.

        The name has only ever been metadata (DEC-048), so this touches no file,
        keeps the digest and the row identity, and leaves every backup that has
        already linked the blob correct. What it does change is the download
        response, which is why the validator on that response covers the name as
        well as the bytes.
        """
        cleaned = clean_attachment_filename(filename)
        if cleaned is None:
            raise LibraryError("invalid_attachment_name", "A file needs a name", status_code=422)
        with self._write() as session:
            row = session.execute(
                select(AttachmentRow).where(
                    AttachmentRow.id == attachment_id, AttachmentRow.item_id == item_id
                )
            ).scalar_one_or_none()
            if row is None:
                raise LibraryError(
                    "attachment_not_found", "Attachment was not found", status_code=404
                )
            row.filename = cleaned
            row.updated_at = _now()
            session.flush()
            return self._attachment_dict(row)

    def get_attachment(self, item_id: int, attachment_id: int) -> dict[str, Any]:
        """Scoped by item on purpose: an id alone must not reach another item's file."""
        with Session(self.engine) as session:
            row = session.execute(
                select(AttachmentRow).where(
                    AttachmentRow.id == attachment_id, AttachmentRow.item_id == item_id
                )
            ).scalar_one_or_none()
            if row is None:
                raise LibraryError(
                    "attachment_not_found", "Attachment was not found", status_code=404
                )
            return self._attachment_dict(row)

    def delete_attachment(self, item_id: int, attachment_id: int, *, data_dir: Path) -> None:
        """Drop the row, then the blob only if no other row still points at it."""
        with self._write() as session:
            row = session.execute(
                select(AttachmentRow).where(
                    AttachmentRow.id == attachment_id, AttachmentRow.item_id == item_id
                )
            ).scalar_one_or_none()
            if row is None:
                raise LibraryError(
                    "attachment_not_found", "Attachment was not found", status_code=404
                )
            digest = row.sha256
            session.delete(row)
            session.flush()
            remaining = session.scalar(
                select(func.count())
                .select_from(AttachmentRow)
                .where(AttachmentRow.sha256 == digest)
            )
        delete_blob_if_unreferenced(data_dir, digest, references=int(remaining or 0))

    @staticmethod
    def _attachment_dict(row: AttachmentRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "filename": row.filename,
            "byte_size": row.byte_size,
            "sha256": row.sha256,
            "created_at": row.created_at,
        }

    def primary_source(self, item_id: int) -> tuple[str, str]:
        with Session(self.engine) as session:
            self._item(session, item_id)
            source = session.execute(
                select(ItemSourceRow.source, ItemSourceRow.source_id).where(
                    ItemSourceRow.item_id == item_id, ItemSourceRow.is_primary == 1
                )
            ).first()
            if source is None:
                raise LibraryError(
                    "refresh_unavailable", "This item has no provider source", status_code=422
                )
            return source.source, source.source_id

    def cover_lookup(self, item_id: int) -> tuple[str | None, str | None]:
        """The two handles a cover chooser can reach Open Library's editions by.

        An Open Library edition id when the item has one — primary or not, since a
        Google-primary item merged with an Open Library match still carries the ref —
        and otherwise an ISBN, which is the only handle a Google-only item has.
        """
        with Session(self.engine) as session:
            self._item(session, item_id)
            edition_id = session.scalar(
                select(ItemSourceRow.source_id).where(
                    ItemSourceRow.item_id == item_id, ItemSourceRow.source == "openlibrary"
                )
            )
            isbn = session.scalar(
                select(ItemIdentifierRow.normalized_value).where(
                    ItemIdentifierRow.item_id == item_id, ItemIdentifierRow.kind == "isbn"
                )
            )
            return edition_id, isbn

    def overwrite_provider_fields(self, item_id: int, values: Mapping[str, Any]) -> dict[str, Any]:
        with self._write() as session:
            item = self._item(session, item_id)
            for field in ("title", "subtitle", "year"):
                if field in values and values[field] is not None:
                    setattr(item, field, values[field])
            metadata = json.loads(item.metadata_json)
            metadata.update(values.get("metadata", {}))
            item.metadata_json = json.dumps(metadata, ensure_ascii=False)
            item.updated_at = _now()
            session.flush()
            return self._item_dict(session, item)

    def list_shelves(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            count_subq = (
                select(EntryShelfRow.shelf_id, func.count().label("cnt"))
                .group_by(EntryShelfRow.shelf_id)
                .subquery()
            )
            rows = session.execute(
                select(ShelfRow, func.coalesce(count_subq.c.cnt, 0).label("entry_count"))
                .outerjoin(count_subq, count_subq.c.shelf_id == ShelfRow.id)
                .where(ShelfRow.user_id == self.user_id)
                .order_by(ShelfRow.name.collate("NOCASE"), ShelfRow.id)
            ).all()
            return [{**self._shelf_dict(row[0]), "entry_count": row[1]} for row in rows]

    def create_shelf(self, name: str) -> dict[str, Any]:
        try:
            with self._write() as session:
                now = _now()
                shelf = ShelfRow(
                    user_id=self.user_id,
                    name=name.strip(),
                    slug=shelf_slug(name),
                    created_at=now,
                    updated_at=now,
                )
                session.add(shelf)
                session.flush()
                return self._shelf_dict(shelf)
        except (IntegrityError, ValueError) as error:
            raise LibraryError("shelf_slug_conflict", "Shelf name is already in use") from error

    def rename_shelf(self, shelf_id: int, name: str) -> dict[str, Any]:
        try:
            with self._write() as session:
                shelf = self._shelf(session, shelf_id)
                shelf.name = name.strip()
                shelf.slug = shelf_slug(name)
                shelf.updated_at = _now()
                session.flush()
                return self._shelf_dict(shelf)
        except IntegrityError as error:
            raise LibraryError("shelf_slug_conflict", "Shelf name is already in use") from error

    def delete_shelf(self, shelf_id: int) -> None:
        with self._write() as session:
            session.delete(self._shelf(session, shelf_id))

    @staticmethod
    def _filter_key(
        statuses: Sequence[str] | None,
        shelves: Sequence[str],
        q: str | None,
        formats: Sequence[str] = (),
    ) -> str:
        """What a cursor is bound to. Every filter has to be in here.

        A key that omits one lets a cursor cut for one filter be accepted under
        another, which skips or repeats a page silently rather than failing.
        """
        value = json.dumps(
            {
                "q": q or "",
                "shelves": sorted(shelves),
                "statuses": sorted(statuses or []),
                "formats": sorted(formats),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _filtered_entries(
        self,
        statuses: Sequence[str] | None,
        shelves: Sequence[str],
        q: str | None,
        formats: Sequence[str] = (),
    ) -> Any:
        query = (
            select(EntryRow)
            .join(ItemRow, ItemRow.id == EntryRow.item_id)
            .where(EntryRow.user_id == self.user_id)
        )
        if statuses is None:
            query = query.where(EntryRow.status != "unsorted")
        elif statuses:
            query = query.where(EntryRow.status.in_(statuses))
        if shelves:
            query = query.where(
                EntryRow.id.in_(
                    select(EntryShelfRow.entry_id)
                    .join(ShelfRow, ShelfRow.id == EntryShelfRow.shelf_id)
                    .where(ShelfRow.user_id == self.user_id, ShelfRow.slug.in_(shelves))
                    .group_by(EntryShelfRow.entry_id)
                    .having(func.count(func.distinct(ShelfRow.slug)) == len(set(shelves)))
                )
            )
        if formats:
            # The shelf filter's shape: an entry must carry every value asked for,
            # so two of them narrows rather than widens.
            query = query.where(
                EntryRow.id.in_(
                    select(EntryFormatRow.entry_id)
                    .where(EntryFormatRow.format.in_(formats))
                    .group_by(EntryFormatRow.entry_id)
                    .having(func.count(func.distinct(EntryFormatRow.format)) == len(set(formats)))
                )
            )
        if q:
            pattern = f"%{normalize_text(q)}%"
            # The stored projection holds exactly what `normalize_text` returns
            # (DEC-036), so filtering reads a column instead of invoking the UDF
            # once per row.
            query = query.where(
                or_(
                    ItemRow.title_normalized.like(pattern),
                    ItemRow.creator_primary_normalized.like(pattern),
                )
            )
        return query

    def list_entries(
        self,
        *,
        statuses: Sequence[str] | None = None,
        shelves: Sequence[str] = (),
        q: str | None = None,
        formats: Sequence[str] = (),
        sort: str = "date_added",
        order: Literal["asc", "desc"] = "desc",
        after: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        sort_expressions = {
            "date_added": EntryRow.date_added,
            "score": EntryRow.score,
            "title": ItemRow.title_normalized,
            # Ordering reads the creator sort name; the `q` filter above stays on
            # `creator_primary_normalized`, because search matches the name as it is
            # written and "gabriel garcia" must keep finding García Márquez.
            "creator": ItemRow.creator_sort_normalized,
            "year": ItemRow.year,
            "date_finished": EntryRow.date_finished,
        }
        expression = sort_expressions[sort]
        bucket = case((expression.is_(None), 1), else_=0)
        filter_key = self._filter_key(statuses, shelves, q, formats)
        state = None
        if after:
            try:
                state = decode_cursor(after, sort=sort, order=order, filter_key=filter_key)
            except CursorError as error:
                raise LibraryError("invalid_cursor", str(error), status_code=400) from error

        query = self._filtered_entries(statuses, shelves, q, formats)
        if state is not None:
            id_comparison = (
                EntryRow.id > state.entry_id if order == "asc" else EntryRow.id < state.entry_id
            )
            if state.null_bucket:
                query = query.where(and_(bucket == 1, id_comparison))
            else:
                value_comparison = (
                    expression > state.value if order == "asc" else expression < state.value
                )
                query = query.where(
                    or_(
                        bucket > 0,
                        and_(
                            bucket == 0,
                            or_(value_comparison, and_(expression == state.value, id_comparison)),
                        ),
                    )
                )
        direction = expression.asc if order == "asc" else expression.desc
        id_direction = EntryRow.id.asc if order == "asc" else EntryRow.id.desc
        query = query.order_by(bucket.asc(), direction(), id_direction()).limit(limit + 1)

        with Session(self.engine) as session:
            entries = list(session.scalars(query))
            has_more = len(entries) > limit
            entries = entries[:limit]
            total_query = select(func.count()).select_from(
                self._filtered_entries(statuses, shelves, q, formats).order_by(None).subquery()
            )
            total = session.scalar(total_query) or 0
            # Each facet clears its own dimension, so a count reads as "what you would
            # get if you clicked this" rather than as a count of the current page.
            facet_base = self._filtered_entries([], shelves, q, formats).subquery()
            # Grouped by the item's type as well as the status, because a status two
            # domains share is not one number on a screen that lists them separately:
            # a wishlisted record counted under "Book · Wishlist" is a wrong answer
            # the walkthrough caught. `status_counts` stays the whole-library total,
            # which is what the inbox badge means.
            facet_rows = session.execute(
                select(facet_base.c.status, ItemRow.type, func.count())
                .join(ItemRow, ItemRow.id == facet_base.c.item_id)
                .group_by(facet_base.c.status, ItemRow.type)
            ).all()
            status_counts: dict[str, int] = {}
            by_type: dict[str, dict[str, int]] = {}
            for status_value, item_type, count in facet_rows:
                status_counts[status_value] = status_counts.get(status_value, 0) + count
                by_type.setdefault(item_type, {})[status_value] = count
            format_base = self._filtered_entries(statuses, shelves, q).subquery()
            format_rows = session.execute(
                select(EntryFormatRow.format, func.count())
                .join(format_base, format_base.c.id == EntryFormatRow.entry_id)
                .group_by(EntryFormatRow.format)
            ).all()
            next_cursor = None
            if has_more and entries:
                last = entries[-1]
                item = self._item(session, last.item_id)
                values: dict[str, Any] = {
                    "date_added": last.date_added,
                    "score": last.score,
                    # Read back the stored projection rather than recomputing it:
                    # the cursor is compared against that column in SQL, so any
                    # divergence between the two would silently skip or repeat a
                    # page.
                    "title": item.title_normalized,
                    "creator": item.creator_sort_normalized,
                    "year": item.year,
                    "date_finished": last.date_finished,
                }
                last_value = values[sort]
                next_cursor = encode_cursor(
                    CursorState(
                        sort=sort,
                        order=order,
                        filter_key=filter_key,
                        value=last_value,
                        entry_id=last.id,
                        null_bucket=int(last_value is None),
                    )
                )
            return {
                "items": [self._entry_dict(session, entry) for entry in entries],
                "next_cursor": next_cursor,
                "total": total,
                "facets": {
                    "status_counts": status_counts,
                    "status_counts_by_type": by_type,
                    "format_counts": {row[0]: row[1] for row in format_rows},
                },
            }

    def _selection(
        self,
        session: Session,
        entry_ids: Sequence[int] | None,
        filters: Mapping[str, Any] | None,
        excluded_entry_ids: Sequence[int],
    ) -> list[EntryRow]:
        if entry_ids is not None:
            unique_ids = set(entry_ids)
            entries = list(
                session.scalars(
                    select(EntryRow).where(
                        EntryRow.user_id == self.user_id, EntryRow.id.in_(unique_ids)
                    )
                )
            )
            if len(entries) != len(unique_ids):
                raise LibraryError(
                    "entry_not_found", "One or more entries were not found", status_code=404
                )
            return entries
        assert filters is not None
        statuses = filters.get("status")
        query = self._filtered_entries(
            statuses,
            filters.get("shelf", []),
            filters.get("q"),
            filters.get("format", []),
        )
        if excluded_entry_ids:
            query = query.where(EntryRow.id.not_in(excluded_entry_ids))
        return list(session.scalars(query))

    def bulk_update(
        self,
        *,
        entry_ids: Sequence[int] | None,
        filters: Mapping[str, Any] | None,
        excluded_entry_ids: Sequence[int],
        changes: Mapping[str, Any],
    ) -> int:
        with self._write() as session:
            entries = self._selection(session, entry_ids, filters, excluded_entry_ids)
            # Validated against every selected entry's own domain *before* anything is
            # written: a selection can legitimately span domains, and half-applying a
            # mixed write is worse than refusing it, because nothing shows which half
            # landed and the undo ledger does not cover a manual edit.
            per_entry = {
                entry.id: self._validated(self._domain(session, entry), changes)
                for entry in entries
            }
            add_shelves = set(changes.get("add_shelves", []))
            remove_shelves = set(changes.get("remove_shelves", []))
            requested_shelves = add_shelves | remove_shelves
            if requested_shelves:
                found = set(
                    session.scalars(
                        select(ShelfRow.id).where(
                            ShelfRow.user_id == self.user_id,
                            ShelfRow.id.in_(requested_shelves),
                        )
                    )
                )
                if found != requested_shelves:
                    raise LibraryError(
                        "shelf_not_found", "One or more shelves were not found", status_code=404
                    )
            now = _now()
            for entry in entries:
                validated = per_entry[entry.id]
                if changes.get("status") is not None:
                    entry.status = changes["status"]
                if validated.get("add_formats"):
                    for value in validated["add_formats"]:
                        if session.get(EntryFormatRow, (entry.id, value)) is None:
                            session.add(EntryFormatRow(entry_id=entry.id, format=value))
                if validated.get("remove_formats"):
                    session.execute(
                        delete(EntryFormatRow).where(
                            EntryFormatRow.entry_id == entry.id,
                            EntryFormatRow.format.in_(validated["remove_formats"]),
                        )
                    )
                if "score" in changes:
                    entry.score = changes["score"]
                    entry.score_provisional = 0
                if changes.get("clear_provisional"):
                    entry.score_provisional = 0
                for shelf_id in add_shelves:
                    if session.get(EntryShelfRow, (entry.id, shelf_id)) is None:
                        session.add(EntryShelfRow(entry_id=entry.id, shelf_id=shelf_id))
                if remove_shelves:
                    session.execute(
                        delete(EntryShelfRow).where(
                            EntryShelfRow.entry_id == entry.id,
                            EntryShelfRow.shelf_id.in_(remove_shelves),
                        )
                    )
                entry.updated_at = now
            return len(entries)

    def accept_suggested(self, filters: Mapping[str, Any]) -> int:
        with self._write() as session:
            selection_filters = dict(filters)
            if selection_filters.get("status") is None:
                selection_filters["status"] = ["unsorted"]
            entries = self._selection(session, None, selection_filters, ())
            affected = 0
            now = _now()
            for entry in entries:
                if entry.suggested_status is not None:
                    entry.status = entry.suggested_status
                    entry.suggested_status = None
                    entry.updated_at = now
                    affected += 1
            return affected
