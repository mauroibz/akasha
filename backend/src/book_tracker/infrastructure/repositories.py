import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from book_tracker.domain.identity import Identifier
from book_tracker.domain.matching import MatchDecision, MatchKind, decide_match
from book_tracker.domain.merge import fill_empty
from book_tracker.domain.normalization import normalize_text, shelf_slug
from book_tracker.infrastructure.models import (
    EntryRow,
    EntryShelfRow,
    ImportBatchRow,
    ImportEffectRow,
    ImportRecordRow,
    ItemIdentifierRow,
    ItemRow,
    ItemSourceRow,
    ShelfRow,
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SourceIdentity:
    source: str
    source_id: str
    is_primary: bool = False


@dataclass(frozen=True)
class EntryResult:
    item_id: int
    entry_id: int
    already_exists: bool


class IdentityConflict(Exception):
    def __init__(self, decision: MatchDecision) -> None:
        self.decision = decision
        super().__init__(MatchKind.IDENTITY_CONFLICT)


class DomainRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

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

    def _exact_ids(
        self,
        session: Session,
        identifiers: Sequence[Identifier],
        sources: Sequence[SourceIdentity] = (),
    ) -> set[int]:
        ids: set[int] = set()
        for identifier in identifiers:
            found = session.scalar(
                select(ItemIdentifierRow.item_id).where(
                    ItemIdentifierRow.kind == identifier.kind,
                    ItemIdentifierRow.normalized_value == identifier.normalized_value,
                )
            )
            if found is not None:
                ids.add(found)
        for source in sources:
            found = session.scalar(
                select(ItemSourceRow.item_id).where(
                    ItemSourceRow.source == source.source,
                    ItemSourceRow.source_id == source.source_id,
                )
            )
            if found is not None:
                ids.add(found)
        return ids

    def match(
        self,
        *,
        identifiers: Sequence[Identifier] = (),
        sources: Sequence[SourceIdentity] = (),
        title: str = "",
        first_author: str = "",
    ) -> MatchDecision:
        with Session(self.engine) as session:
            exact = self._exact_ids(session, identifiers, sources)
            suggestions: set[int] = set()
            if title and first_author:
                for item_id, candidate_title, candidate_author in session.execute(
                    select(ItemRow.id, ItemRow.title, ItemRow.sort_author)
                ):
                    if (
                        candidate_author
                        and normalize_text(candidate_title) == normalize_text(title)
                        and normalize_text(candidate_author) == normalize_text(first_author)
                    ):
                        suggestions.add(item_id)
            return decide_match(exact, suggestions)

    def create_or_get_entry(
        self,
        *,
        title: str,
        subtitle: str | None = None,
        authors: Sequence[str] = (),
        identifiers: Sequence[Identifier] = (),
        sources: Sequence[SourceIdentity] = (),
        user_id: int = 1,
    ) -> EntryResult:
        with self._write() as session:
            exact = self._exact_ids(session, identifiers, sources)
            decision = decide_match(exact, set())
            if decision.kind is MatchKind.IDENTITY_CONFLICT:
                raise IdentityConflict(decision)
            now = _now()
            if decision.item_id is None:
                item = ItemRow(
                    type="book",
                    title=title,
                    subtitle=subtitle,
                    year=None,
                    cover_path=None,
                    identifiers="{}",
                    metadata_json=json.dumps({"authors": list(authors)}),
                    created_at=now,
                    updated_at=now,
                )
                session.add(item)
                session.flush()
                item_id = item.id
                for identifier in identifiers:
                    session.add(
                        ItemIdentifierRow(
                            item_id=item_id,
                            kind=identifier.kind,
                            normalized_value=identifier.normalized_value,
                            value=identifier.value,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                for source in sources:
                    session.add(
                        ItemSourceRow(
                            item_id=item_id,
                            source=source.source,
                            source_id=source.source_id,
                            is_primary=int(source.is_primary),
                            created_at=now,
                            updated_at=now,
                        )
                    )
            else:
                item_id = decision.item_id
            existing = session.scalar(
                select(EntryRow).where(EntryRow.user_id == user_id, EntryRow.item_id == item_id)
            )
            if existing is not None:
                return EntryResult(item_id, existing.id, True)
            entry = EntryRow(
                user_id=user_id,
                item_id=item_id,
                status="unsorted",
                score=None,
                notes=None,
                date_added=now,
                date_started=None,
                date_finished=None,
                reread_count=0,
                score_provisional=0,
                suggested_status=None,
                created_at=now,
                updated_at=now,
            )
            session.add(entry)
            session.flush()
            return EntryResult(item_id, entry.id, False)

    def near_entry_ids(self, title: str, first_author: str, user_id: int = 1) -> list[int]:
        decision = self.match(title=title, first_author=first_author)
        if decision.kind is not MatchKind.AMBIGUOUS:
            return []
        with Session(self.engine) as session:
            return list(
                session.scalars(
                    select(EntryRow.id)
                    .where(
                        EntryRow.user_id == user_id,
                        EntryRow.item_id.in_(decision.candidates),
                    )
                    .order_by(EntryRow.id)
                )
            )

    def create_cached_entry(
        self,
        *,
        title: str,
        subtitle: str | None,
        year: int | None,
        metadata: Mapping[str, Any],
        identifiers: Sequence[Identifier],
        sources: Sequence[SourceIdentity],
        status: str,
        score: int | None,
        shelf_ids: Sequence[int] = (),
        user_id: int = 1,
    ) -> EntryResult:
        with self._write() as session:
            exact = self._exact_ids(session, identifiers, sources)
            decision = decide_match(exact, set())
            if decision.kind is MatchKind.IDENTITY_CONFLICT:
                raise IdentityConflict(decision)
            now = _now()
            if decision.item_id is None:
                item = ItemRow(
                    type="book",
                    title=title,
                    subtitle=subtitle,
                    year=year,
                    cover_path=None,
                    identifiers=json.dumps(
                        {value.kind: value.normalized_value for value in identifiers}
                    ),
                    metadata_json=json.dumps(dict(metadata), ensure_ascii=False),
                    created_at=now,
                    updated_at=now,
                )
                session.add(item)
                session.flush()
                item_id = item.id
                session.add_all(
                    ItemIdentifierRow(
                        item_id=item_id,
                        kind=value.kind,
                        normalized_value=value.normalized_value,
                        value=value.value,
                        created_at=now,
                        updated_at=now,
                    )
                    for value in identifiers
                )
                session.add_all(
                    ItemSourceRow(
                        item_id=item_id,
                        source=value.source,
                        source_id=value.source_id,
                        is_primary=int(value.is_primary),
                        created_at=now,
                        updated_at=now,
                    )
                    for value in sources
                )
            else:
                item_id = decision.item_id
            existing = session.scalar(
                select(EntryRow).where(EntryRow.user_id == user_id, EntryRow.item_id == item_id)
            )
            if existing is not None:
                return EntryResult(item_id, existing.id, True)
            shelves = set(shelf_ids)
            if shelves:
                found = set(
                    session.scalars(
                        select(ShelfRow.id).where(
                            ShelfRow.user_id == user_id, ShelfRow.id.in_(shelves)
                        )
                    )
                )
                if found != shelves:
                    raise LookupError("shelf_not_found")
            entry = EntryRow(
                user_id=user_id,
                item_id=item_id,
                status=status,
                score=score,
                notes=None,
                date_added=now,
                date_started=None,
                date_finished=None,
                reread_count=0,
                score_provisional=0,
                suggested_status=None,
                created_at=now,
                updated_at=now,
            )
            session.add(entry)
            session.flush()
            session.add_all(
                EntryShelfRow(entry_id=entry.id, shelf_id=shelf_id) for shelf_id in shelves
            )
            return EntryResult(item_id, entry.id, False)

    def fill_empty_item(
        self, item_id: int, values: Mapping[str, Any], identifiers: Sequence[Identifier] = ()
    ) -> None:
        with self._write() as session:
            item = session.get(ItemRow, item_id)
            if item is None:
                raise LookupError(item_id)
            exact = self._exact_ids(session, identifiers)
            if exact - {item_id}:
                raise IdentityConflict(decide_match(exact | {item_id}, set()))
            merged = fill_empty({"title": item.title, "subtitle": item.subtitle}, values)
            item.title = merged["title"]
            item.subtitle = merged.get("subtitle")
            item.updated_at = _now()
            for identifier in identifiers:
                if (
                    session.get(
                        ItemIdentifierRow, (item_id, identifier.kind, identifier.normalized_value)
                    )
                    is None
                ):
                    now = _now()
                    session.add(
                        ItemIdentifierRow(
                            item_id=item_id,
                            kind=identifier.kind,
                            normalized_value=identifier.normalized_value,
                            value=identifier.value,
                            created_at=now,
                            updated_at=now,
                        )
                    )

    def set_cover_path(self, item_id: int, cover_path: str) -> None:
        with self._write() as session:
            item = session.get(ItemRow, item_id)
            if item is None:
                raise LookupError(item_id)
            item.cover_path = cover_path
            item.updated_at = _now()

    def create_shelf(self, name: str, user_id: int = 1) -> int:
        now = _now()
        try:
            with self._write() as session:
                shelf = ShelfRow(
                    user_id=user_id,
                    name=name.strip(),
                    slug=shelf_slug(name),
                    created_at=now,
                    updated_at=now,
                )
                session.add(shelf)
                session.flush()
                return shelf.id
        except IntegrityError as error:
            raise ValueError("shelf slug already exists") from error

    def attach_shelf(self, entry_id: int, shelf_id: int) -> None:
        with self._write() as session:
            if session.get(EntryShelfRow, (entry_id, shelf_id)) is None:
                session.add(EntryShelfRow(entry_id=entry_id, shelf_id=shelf_id))

    def rename_shelf(self, shelf_id: int, name: str) -> ShelfRow:
        try:
            with self._write() as session:
                shelf = session.get(ShelfRow, shelf_id)
                if shelf is None:
                    raise LookupError(shelf_id)
                shelf.name = name.strip()
                shelf.slug = shelf_slug(name)
                shelf.updated_at = _now()
                session.flush()
                session.expunge(shelf)
                return shelf
        except IntegrityError as error:
            raise ValueError("shelf slug already exists") from error

    def delete_shelf(self, shelf_id: int) -> None:
        with self._write() as session:
            session.execute(delete(ShelfRow).where(ShelfRow.id == shelf_id))


def _count_unsorted(session: Session, user_id: int) -> int:
    """How many entries are waiting in triage.

    A committed import lands its rows `unsorted`, and a library list with no
    `status` filter excludes `unsorted` (see `LibraryService`), so an import
    that reports only its own counters looks like an import that did nothing.
    """
    return (
        session.scalar(
            select(func.count())
            .select_from(EntryRow)
            .where(EntryRow.user_id == user_id, EntryRow.status == "unsorted")
        )
        or 0
    )


class ImportRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get_batch_by_fingerprint(self, kind: str, fingerprint: str) -> str | None:
        with Session(self.engine) as session:
            return session.scalar(
                select(ImportBatchRow.id).where(
                    ImportBatchRow.kind == kind, ImportBatchRow.fingerprint == fingerprint
                )
            )

    def create_preview(
        self,
        batch_id: str,
        fingerprint: str,
        filename: str,
        summary: Mapping[str, Any],
        records: Sequence[Mapping[str, Any]],
        *,
        kind: str = "goodreads",
        source_descriptor: Mapping[str, Any] | None = None,
    ) -> None:
        now = _now()
        with DomainRepository(self.engine)._write() as session:
            session.add(
                ImportBatchRow(
                    id=batch_id,
                    kind=kind,
                    fingerprint=fingerprint,
                    state="previewed",
                    source_descriptor=json.dumps(source_descriptor or {"filename": filename}),
                    preview_summary=json.dumps(summary),
                    counters="{}",
                    error=None,
                    committed_at=None,
                    undo_expires_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            for value in records:
                payload = dict(value)
                action = str(payload.pop("planned_action"))
                match_kind = str(payload.pop("match_kind"))
                matched_item_id = payload.pop("matched_item_id")
                candidates = payload.pop("candidates")
                errors = payload.pop("errors")
                session.add(
                    ImportRecordRow(
                        batch_id=batch_id,
                        row_number=int(payload["row_number"]),
                        normalized_payload=json.dumps(payload, ensure_ascii=False),
                        matched_item_id=matched_item_id,
                        matched_entry_id=None,
                        match_kind=match_kind,
                        planned_action=action,
                        conflicts=json.dumps({"candidates": candidates}),
                        validation_errors=json.dumps(errors, ensure_ascii=False),
                        ambiguity_resolution=None,
                        created_at=now,
                        updated_at=now,
                    )
                )

    def commit(
        self,
        batch_id: str,
        choices: Mapping[int, Mapping[str, Any]],
        user_id: int = 1,
        *,
        kind: str = "goodreads",
    ) -> dict[str, Any]:
        with DomainRepository(self.engine)._write() as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None or batch.kind != kind:
                raise LookupError("import_batch_not_found")
            if batch.state == "committed":
                return {
                    "batch_id": batch.id,
                    "state": batch.state,
                    **json.loads(batch.counters),
                    "unsorted_entries": _count_unsorted(session, user_id),
                }
            if batch.state != "previewed":
                raise ValueError("import_batch_not_committable")
            rows = list(
                session.scalars(
                    select(ImportRecordRow)
                    .where(ImportRecordRow.batch_id == batch_id)
                    .order_by(ImportRecordRow.row_number)
                )
            )
            unresolved = [
                row.id
                for row in rows
                if row.planned_action == "ambiguous" and row.id not in choices
            ]
            if unresolved:
                raise ValueError(json.dumps(unresolved))
            created_items = created_entries = unchanged = 0
            now = _now()
            for row in rows:
                if row.planned_action in {"error", "identity_conflict"}:
                    continue
                payload = json.loads(row.normalized_payload)
                choice = choices.get(row.id, {})
                item_id = row.matched_item_id
                if row.planned_action == "ambiguous":
                    candidates = set(json.loads(row.conflicts).get("candidates", []))
                    selected = choice.get("item_id")
                    if selected is not None and selected not in candidates:
                        raise ValueError("invalid_ambiguity_choice")
                    item_id = int(selected) if selected is not None else None
                    row.ambiguity_resolution = json.dumps(
                        {"action": "use_existing", "item_id": item_id}
                        if item_id is not None
                        else {"action": "create_new"}
                    )
                identity_values = {
                    key: payload.get(key) for key in ("isbn", "calibre_uuid") if payload.get(key)
                }
                isbn = identity_values.get("isbn")
                for identity_kind, identity_value in identity_values.items():
                    exact = session.scalar(
                        select(ItemIdentifierRow.item_id).where(
                            ItemIdentifierRow.kind == identity_kind,
                            ItemIdentifierRow.normalized_value == identity_value,
                        )
                    )
                    if exact is not None and item_id is not None and exact != item_id:
                        raise ValueError("identity_conflict")
                    item_id = exact or item_id
                if item_id is None:
                    metadata = {
                        "authors": payload["authors"],
                        **({"publisher": payload["publisher"]} if payload.get("publisher") else {}),
                        **(
                            {"page_count": payload["page_count"]}
                            if payload.get("page_count")
                            else {}
                        ),
                        **(
                            {"original_year": payload["original_year"]}
                            if payload.get("original_year")
                            else {}
                        ),
                        **(
                            {"description": payload["description"]}
                            if payload.get("description")
                            else {}
                        ),
                        **({"series": payload["series"]} if payload.get("series") else {}),
                    }
                    item = ItemRow(
                        type="book",
                        title=payload["title"],
                        subtitle=None,
                        year=payload.get("year"),
                        cover_path=None,
                        identifiers=json.dumps({"isbn": isbn} if isbn else {}),
                        metadata_json=json.dumps(metadata, ensure_ascii=False),
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(item)
                    session.flush()
                    item_id = item.id
                    created_items += 1
                    session.add(
                        ImportEffectRow(
                            batch_id=batch_id,
                            record_id=row.id,
                            effect_type="create",
                            entity_type="item",
                            entity_id=str(item_id),
                            before_values="{}",
                            after_values=json.dumps({"created": True}),
                        )
                    )
                    for identity_kind, identity_value in identity_values.items():
                        session.add(
                            ItemIdentifierRow(
                                item_id=item_id,
                                kind=identity_kind,
                                normalized_value=identity_value,
                                value=identity_value,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                else:
                    existing_item = session.get(ItemRow, item_id)
                    assert existing_item is not None
                    before: dict[str, Any] = {}
                    after: dict[str, Any] = {}
                    if existing_item.year is None and payload.get("year") is not None:
                        before["year"] = None
                        existing_item.year = payload["year"]
                        after["year"] = existing_item.year
                    metadata = json.loads(existing_item.metadata_json)
                    incoming = {
                        "authors": payload.get("authors"),
                        "publisher": payload.get("publisher"),
                        "page_count": payload.get("page_count"),
                        "original_year": payload.get("original_year"),
                        "description": payload.get("description"),
                        "series": payload.get("series"),
                    }
                    for key, value in incoming.items():
                        if value not in (None, "", [], {}) and metadata.get(key) in (
                            None,
                            "",
                            [],
                            {},
                        ):
                            before[f"metadata.{key}"] = metadata.get(key)
                            metadata[key] = value
                            after[f"metadata.{key}"] = value
                    if after:
                        existing_item.metadata_json = json.dumps(metadata, ensure_ascii=False)
                        existing_item.updated_at = now
                        session.add(
                            ImportEffectRow(
                                batch_id=batch_id,
                                record_id=row.id,
                                effect_type="fill_empty",
                                entity_type="item",
                                entity_id=str(item_id),
                                before_values=json.dumps(before, ensure_ascii=False),
                                after_values=json.dumps(after, ensure_ascii=False),
                            )
                        )
                    for identity_kind, identity_value in identity_values.items():
                        present = session.scalar(
                            select(ItemIdentifierRow.item_id).where(
                                ItemIdentifierRow.item_id == item_id,
                                ItemIdentifierRow.kind == identity_kind,
                                ItemIdentifierRow.normalized_value == identity_value,
                            )
                        )
                        if present is None:
                            identifier = ItemIdentifierRow(
                                item_id=item_id,
                                kind=identity_kind,
                                normalized_value=identity_value,
                                value=identity_value,
                                created_at=now,
                                updated_at=now,
                            )
                            session.add(identifier)
                            session.flush()
                            session.add(
                                ImportEffectRow(
                                    batch_id=batch_id,
                                    record_id=row.id,
                                    effect_type="create",
                                    entity_type="item_identifier",
                                    entity_id=f"{item_id}:{identity_kind}:{identity_value}",
                                    before_values="{}",
                                    after_values=json.dumps(
                                        {"kind": identity_kind, "value": identity_value}
                                    ),
                                )
                            )
                row.matched_item_id = item_id
                existing = session.scalar(
                    select(EntryRow).where(EntryRow.user_id == user_id, EntryRow.item_id == item_id)
                )
                if existing is not None:
                    row.matched_entry_id = existing.id
                    unchanged += 1
                    continue
                entry = EntryRow(
                    user_id=user_id,
                    item_id=item_id,
                    status="unsorted",
                    score=payload.get("score"),
                    notes=payload.get("review"),
                    date_added=payload.get("date_added") or now,
                    date_started=None,
                    date_finished=payload.get("date_finished"),
                    reread_count=payload.get("reread_count", 0),
                    score_provisional=int(payload.get("score_provisional", False)),
                    suggested_status=payload.get("suggested_status"),
                    created_at=now,
                    updated_at=now,
                )
                session.add(entry)
                session.flush()
                row.matched_entry_id = entry.id
                created_entries += 1
                session.add(
                    ImportEffectRow(
                        batch_id=batch_id,
                        record_id=row.id,
                        effect_type="create",
                        entity_type="entry",
                        entity_id=str(entry.id),
                        before_values="{}",
                        after_values=json.dumps({"created": True}),
                    )
                )
                for slug in payload.get("shelves", []):
                    shelf = session.scalar(
                        select(ShelfRow).where(ShelfRow.user_id == user_id, ShelfRow.slug == slug)
                    )
                    if shelf is None:
                        shelf = ShelfRow(
                            user_id=user_id, name=slug, slug=slug, created_at=now, updated_at=now
                        )
                        session.add(shelf)
                        session.flush()
                        session.add(
                            ImportEffectRow(
                                batch_id=batch_id,
                                record_id=row.id,
                                effect_type="create",
                                entity_type="shelf",
                                entity_id=str(shelf.id),
                                before_values="{}",
                                after_values=json.dumps({"created": True}),
                            )
                        )
                    session.add(EntryShelfRow(entry_id=entry.id, shelf_id=shelf.id))
                    session.flush()
                    session.add(
                        ImportEffectRow(
                            batch_id=batch_id,
                            record_id=row.id,
                            effect_type="attach",
                            entity_type="entry_shelf",
                            entity_id=f"{entry.id}:{shelf.id}",
                            before_values="{}",
                            after_values=json.dumps({"entry_id": entry.id, "shelf_id": shelf.id}),
                        )
                    )
            counters = {
                "created_items": created_items,
                "created_entries": created_entries,
                "unchanged_entries": unchanged,
            }
            batch.state = "committed"
            batch.counters = json.dumps(counters)
            batch.committed_at = now
            batch.undo_expires_at = (
                (datetime.now(UTC) + timedelta(hours=24)).isoformat().replace("+00:00", "Z")
            )
            batch.updated_at = now
            # Deliberately not part of `counters`: the persisted counters are facts
            # about this batch, and this is how many rows are waiting in triage
            # right now, including whatever an earlier import left there.
            return {
                "batch_id": batch.id,
                "state": "committed",
                **counters,
                "unsorted_entries": _count_unsorted(session, user_id),
            }
