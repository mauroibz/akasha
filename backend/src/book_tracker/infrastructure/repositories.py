import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from book_tracker.domain.identity import Identifier
from book_tracker.domain.matching import MatchDecision, MatchKind, decide_match
from book_tracker.domain.merge import fill_empty
from book_tracker.domain.normalization import normalize_text, shelf_slug
from book_tracker.infrastructure.models import (
    EntryRow,
    EntryShelfRow,
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
