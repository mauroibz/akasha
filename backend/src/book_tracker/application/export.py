"""Stream the whole library as entity-shaped JSON.

Three rules shape this module.

**Owner data in, derived data out.** `creator_sort_override` (DEC-051) and an
attachment's `filename` (DEC-050) are values a person typed and no algorithm can
reconstruct, so an export that drops either loses something real. The projections
beside them -- `creator_primary`, `creator_sort`, and the `*_normalized` columns
-- rebuild themselves on every write through the DEC-036 mapper event. Exporting
them would present a cache as authority to whoever reads the dump later, so they
are omitted deliberately and a test asserts their absence.

**The entity shape, not a book shape.** An item is `type`, identifiers, sources
and an opaque `metadata` object, exactly as the row stores it. `metadata` is
passed through untransformed: the moment this module knows that `creators` is a
field, the format needs a v2 for the second domain (DEC-052 seam 3). A registered
`ExportView` (`domain/exports.py`) is allowed to be domain-shaped, because it is
one domain's export view rather than the export — `iter_export_rows` below is the
shared walk behind every one of them, and this module's own JSON path never uses it.

**Flat memory, whatever the library size.** The deployment target is a ZimaBoard.
Rows stream in bounded batches and each one is serialized and yielded on its own,
so peak memory tracks the batch size rather than the corpus. Child rows are
fetched one query per batch rather than one per item, which keeps that promise
without an N+1.
"""

import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from book_tracker.domain.exports import ExportRow, ExportView
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

EXPORT_KIND = "akasha-export"
EXPORT_VERSION = 1
#: Rows held in memory at once. Small enough that peak RSS is flat against a
#: library of any size, large enough that child lookups stay one query per batch.
BATCH = 200


def _grouped(rows: Sequence[Any], key: str) -> dict[int, list[Any]]:
    out: dict[int, list[Any]] = {}
    for row in rows:
        out.setdefault(getattr(row, key), []).append(row)
    return out


def _item_payload(
    item: Any,
    identifiers: list[Any],
    sources: list[Any],
    attachments: list[Any],
) -> dict[str, Any]:
    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "subtitle": item.subtitle,
        "year": item.year,
        # The owner's correction, and the only creator field that is not derived.
        "creator_sort_override": item.creator_sort_override,
        # Opaque on purpose: this module must not learn any domain's field names.
        "metadata": json.loads(item.metadata_json or "{}"),
        "identifiers": {row.kind: row.normalized_value for row in identifiers},
        "sources": [
            {
                "source": row.source,
                "source_id": row.source_id,
                "is_primary": bool(row.is_primary),
            }
            for row in sources
        ],
        # References, not bytes (DEC-054): the blob is already held twice -- once
        # live and once hardlinked into every nightly backup (DEC-048) -- and a
        # third copy would turn a file you can read into a multi-gigabyte archive.
        # The digest is what makes the reference resolvable, because the blob's
        # path *is* its digest, so a backup can be searched by it with no running
        # instance.
        "attachments": [
            {
                "filename": row.filename,
                "byte_size": row.byte_size,
                "sha256": row.sha256,
                "path": f"/api/items/{item.id}/attachments/{row.id}",
                "created_at": row.created_at,
            }
            for row in attachments
        ],
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


#: Columns are selected individually rather than as mapped entities throughout
#: this module. An ORM entity is retained by the `Session` identity map for as
#: long as the session lives, so streaming entities would hold the whole library
#: in memory however small the batch was -- which is precisely the regression the
#: memory test catches.
_ITEM_COLUMNS = (
    ItemRow.id,
    ItemRow.type,
    ItemRow.title,
    ItemRow.subtitle,
    ItemRow.year,
    ItemRow.creator_sort_override,
    ItemRow.metadata_json,
    ItemRow.created_at,
    ItemRow.updated_at,
)


def _batches(session: Session, columns: tuple[Any, ...]) -> Iterator[list[Any]]:
    """Walk a table in keyset batches, holding one batch at a time.

    `yield_per` is not enough here. SQLite's driver has no server-side cursor, so
    a streamed result is still materialized in full by the DBAPI and peak memory
    tracks the library rather than the batch -- which the memory test caught. A
    keyset walk issues one bounded query per batch instead, the same technique the
    library list already uses (technical spec 7.2). The key must be the first
    column and must be unique and ordered.
    """
    key = columns[0]
    last: Any = None
    while True:
        statement = select(*columns).order_by(key).limit(BATCH)
        if last is not None:
            statement = statement.where(key > last)
        rows = session.execute(statement).all()
        if not rows:
            return
        yield list(rows)
        if len(rows) < BATCH:
            return
        last = rows[-1][0]


def iter_items(session: Session) -> Iterator[dict[str, Any]]:
    for batch in _batches(session, _ITEM_COLUMNS):
        ids = [item.id for item in batch]
        identifiers = _grouped(
            session.execute(
                select(
                    ItemIdentifierRow.item_id,
                    ItemIdentifierRow.kind,
                    ItemIdentifierRow.normalized_value,
                )
                .where(ItemIdentifierRow.item_id.in_(ids))
                .order_by(ItemIdentifierRow.item_id, ItemIdentifierRow.kind)
            ).all(),
            "item_id",
        )
        sources = _grouped(
            session.execute(
                select(
                    ItemSourceRow.item_id,
                    ItemSourceRow.source,
                    ItemSourceRow.source_id,
                    ItemSourceRow.is_primary,
                )
                .where(ItemSourceRow.item_id.in_(ids))
                .order_by(ItemSourceRow.item_id, ItemSourceRow.source, ItemSourceRow.source_id)
            ).all(),
            "item_id",
        )
        attachments = _grouped(
            session.execute(
                select(
                    AttachmentRow.item_id,
                    AttachmentRow.id,
                    AttachmentRow.filename,
                    AttachmentRow.byte_size,
                    AttachmentRow.sha256,
                    AttachmentRow.created_at,
                )
                .where(AttachmentRow.item_id.in_(ids))
                .order_by(AttachmentRow.item_id, AttachmentRow.id)
            ).all(),
            "item_id",
        )
        for item in batch:
            yield _item_payload(
                item,
                identifiers.get(item.id, []),
                sources.get(item.id, []),
                attachments.get(item.id, []),
            )


_ENTRY_COLUMNS = (
    EntryRow.id,
    EntryRow.item_id,
    EntryRow.status,
    EntryRow.score,
    EntryRow.score_provisional,
    EntryRow.suggested_status,
    EntryRow.notes,
    EntryRow.date_added,
    EntryRow.date_started,
    EntryRow.date_finished,
    EntryRow.reread_count,
    EntryRow.progress,
)


def _shelves_for(session: Session, entry_ids: list[int]) -> dict[int, list[str]]:
    shelves: dict[int, list[str]] = {}
    for entry_id, name in session.execute(
        select(EntryShelfRow.entry_id, ShelfRow.name)
        .join(ShelfRow, ShelfRow.id == EntryShelfRow.shelf_id)
        .where(EntryShelfRow.entry_id.in_(entry_ids))
        .order_by(EntryShelfRow.entry_id, ShelfRow.name.collate("NOCASE"))
    ).all():
        shelves.setdefault(entry_id, []).append(name)
    return shelves


def _formats_for(session: Session, entry_ids: list[int]) -> dict[int, list[str]]:
    """One query per batch, like the shelves beside it.

    A format is owner data in exactly the sense DEC-054 means: nothing derives "I have
    this on vinyl" from the item, because the item describes a release and this
    describes your copy. An export that dropped it would lose a fact only you knew.
    """
    formats: dict[int, list[str]] = {}
    for entry_id, value in session.execute(
        select(EntryFormatRow.entry_id, EntryFormatRow.format)
        .where(EntryFormatRow.entry_id.in_(entry_ids))
        .order_by(EntryFormatRow.entry_id, EntryFormatRow.format)
    ).all():
        formats.setdefault(entry_id, []).append(value)
    return formats


def iter_entries(session: Session) -> Iterator[dict[str, Any]]:
    for batch in _batches(session, _ENTRY_COLUMNS):
        entry_ids = [entry.id for entry in batch]
        shelves = _shelves_for(session, entry_ids)
        formats = _formats_for(session, entry_ids)
        for entry in batch:
            yield {
                "id": entry.id,
                "item_id": entry.item_id,
                "status": entry.status,
                "score": entry.score,
                "score_provisional": bool(entry.score_provisional),
                "suggested_status": entry.suggested_status,
                "notes": entry.notes,
                "date_added": entry.date_added,
                "date_started": entry.date_started,
                "date_finished": entry.date_finished,
                "reread_count": entry.reread_count,
                # `None` where the domain records none, which is the honest shape:
                # an export that dropped it would lose owner data silently.
                "progress": entry.progress,
                # Names rather than ids: an id means nothing outside this database,
                # and the name is what the owner typed.
                "shelves": shelves.get(entry.id, []),
                "formats": formats.get(entry.id, []),
            }


def export_json(engine: Engine, *, now: datetime | None = None) -> Iterator[str]:
    """Yield the export document in pieces, never holding the whole of it."""
    generated = (now or datetime.now(UTC)).isoformat()
    with Session(engine) as session:
        header = {
            "kind": EXPORT_KIND,
            "version": EXPORT_VERSION,
            "generated_at": generated,
        }
        yield json.dumps(header, ensure_ascii=False)[:-1]
        for name, rows in (("items", iter_items(session)), ("entries", iter_entries(session))):
            yield f', "{name}": ['
            for index, row in enumerate(rows):
                yield ("," if index else "") + json.dumps(row, ensure_ascii=False)
            yield "]"
        yield "}"


def _entry_batches_for_type(session: Session, item_type: str) -> Iterator[list[Any]]:
    """`_batches`, joined and filtered to one domain's entries.

    A registered export view's rows are always one domain at a time — `type` is a
    required parameter of `GET /api/export/{view}` because a view's columns are
    themselves domain-shaped (the `table` view's header, the Goodreads writer's
    presence at all). Filtering here, at the query, keeps the walk from fetching a
    row only to discard it in Python.
    """
    key = EntryRow.id
    last: int | None = None
    while True:
        statement = (
            select(*_ENTRY_COLUMNS)
            .join(ItemRow, ItemRow.id == EntryRow.item_id)
            .where(ItemRow.type == item_type)
            .order_by(key)
            .limit(BATCH)
        )
        if last is not None:
            statement = statement.where(key > last)
        rows = session.execute(statement).all()
        if not rows:
            return
        yield list(rows)
        if len(rows) < BATCH:
            return
        last = rows[-1][0]


def iter_export_rows(session: Session, item_type: str) -> Iterator[ExportRow]:
    """The shared walk behind every registered `ExportView` (proposal §2.1).

    One domain's entries, joined to their item, identifiers, shelves and formats,
    the same batched-then-discarded shape `export_csv` used before this sprint. A
    view built on this never opens a session and never writes SQL — it receives one
    `ExportRow` at a time and decides only how to spell it.
    """
    for batch in _entry_batches_for_type(session, item_type):
        item_ids = [entry.item_id for entry in batch]
        entry_ids = [entry.id for entry in batch]
        items = {
            item.id: item
            for item in session.execute(
                select(*_ITEM_COLUMNS).where(ItemRow.id.in_(item_ids))
            ).all()
        }
        identifiers: dict[int, dict[str, str]] = {}
        for row in session.execute(
            select(
                ItemIdentifierRow.item_id,
                ItemIdentifierRow.kind,
                ItemIdentifierRow.normalized_value,
            ).where(ItemIdentifierRow.item_id.in_(item_ids))
        ).all():
            identifiers.setdefault(row.item_id, {})[row.kind] = row.normalized_value
        shelves = _shelves_for(session, entry_ids)
        formats = _formats_for(session, entry_ids)
        for entry in batch:
            item = items.get(entry.item_id)
            if item is None:  # pragma: no cover - the foreign key guarantees this
                continue
            yield ExportRow(
                item_id=item.id,
                item_type=item.type,
                title=item.title,
                subtitle=item.subtitle,
                year=item.year,
                metadata=json.loads(item.metadata_json or "{}"),
                identifiers=identifiers.get(item.id, {}),
                status=entry.status,
                score=entry.score,
                notes=entry.notes,
                date_added=entry.date_added,
                date_started=entry.date_started,
                date_finished=entry.date_finished,
                reread_count=entry.reread_count or 0,
                progress=entry.progress,
                shelves=tuple(shelves.get(entry.id, [])),
                formats=tuple(formats.get(entry.id, [])),
            )


def stream_export_view(engine: Engine, view: ExportView, item_type: str) -> Iterator[str]:
    """Stream one registered view for one domain — `GET /api/export/{view}`'s walk.

    The session is opened here and stays open across the view's own generator: both
    are lazy, so nothing runs until the `StreamingResponse` above this pulls a chunk,
    and the session lives exactly as long as the walk it backs (the same pattern
    `export_json` and the pre-sprint `export_csv` both used).
    """
    with Session(engine) as session:
        yield from view.write(iter_export_rows(session, item_type))
