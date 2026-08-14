import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import Engine, and_, case, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from book_tracker.domain.normalization import normalize_text, shelf_slug
from book_tracker.domain.pagination import CursorError, CursorState, decode_cursor, encode_cursor
from book_tracker.infrastructure.attachments import (
    AttachmentError,
    delete_blob_if_unreferenced,
    store_blob,
)
from book_tracker.infrastructure.models import (
    AttachmentRow,
    EntryRow,
    EntryShelfRow,
    ItemIdentifierRow,
    ItemRow,
    ItemSourceRow,
    ShelfRow,
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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
            "sort_author": item.sort_author,
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

    def add_attachment(
        self, item_id: int, *, filename: str, content: bytes, data_dir: Path, max_bytes: int
    ) -> dict[str, Any]:
        """Store the bytes, then record the name against the item.

        The blob is written before the row so a crash between the two leaves an
        unreferenced file rather than a row pointing at nothing: one is reclaimable
        by a prune, the other is a broken download the owner discovers later.
        """
        if len(content) > max_bytes:
            raise LibraryError(
                "attachment_too_large",
                f"Attachments are limited to {max_bytes} bytes",
                status_code=413,
            )
        with Session(self.engine) as session:
            self._item(session, item_id)
        try:
            stored = store_blob(content, data_dir)
        except AttachmentError as error:
            raise LibraryError("invalid_attachment", str(error), status_code=422) from error
        now = _now()
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
    def _filter_key(statuses: Sequence[str] | None, shelves: Sequence[str], q: str | None) -> str:
        value = json.dumps(
            {"q": q or "", "shelves": sorted(shelves), "statuses": sorted(statuses or [])},
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _filtered_entries(
        self, statuses: Sequence[str] | None, shelves: Sequence[str], q: str | None
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
        if q:
            pattern = f"%{normalize_text(q)}%"
            # The stored projection holds exactly what `normalize_text` returns
            # (DEC-036), so filtering reads a column instead of invoking the UDF
            # once per row.
            query = query.where(
                or_(
                    ItemRow.title_normalized.like(pattern),
                    ItemRow.sort_author_normalized.like(pattern),
                )
            )
        return query

    def list_entries(
        self,
        *,
        statuses: Sequence[str] | None = None,
        shelves: Sequence[str] = (),
        q: str | None = None,
        sort: str = "date_added",
        order: Literal["asc", "desc"] = "desc",
        after: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        sort_expressions = {
            "date_added": EntryRow.date_added,
            "score": EntryRow.score,
            "title": ItemRow.title_normalized,
            "sort_author": ItemRow.sort_author_normalized,
            "year": ItemRow.year,
            "date_finished": EntryRow.date_finished,
        }
        expression = sort_expressions[sort]
        bucket = case((expression.is_(None), 1), else_=0)
        filter_key = self._filter_key(statuses, shelves, q)
        state = None
        if after:
            try:
                state = decode_cursor(after, sort=sort, order=order, filter_key=filter_key)
            except CursorError as error:
                raise LibraryError("invalid_cursor", str(error), status_code=400) from error

        query = self._filtered_entries(statuses, shelves, q)
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
                self._filtered_entries(statuses, shelves, q).order_by(None).subquery()
            )
            total = session.scalar(total_query) or 0
            facet_base = self._filtered_entries([], shelves, q).subquery()
            facet_rows = session.execute(
                select(facet_base.c.status, func.count()).group_by(facet_base.c.status)
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
                    "sort_author": item.sort_author_normalized,
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
                "facets": {"status_counts": {row[0]: row[1] for row in facet_rows}},
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
        query = self._filtered_entries(statuses, filters.get("shelf", []), filters.get("q"))
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
                if changes.get("status") is not None:
                    entry.status = changes["status"]
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
