"""Stream the whole library as entity-shaped JSON.

Three rules shape this module.

**Owner data in, derived data out.** `creator_sort_override` (DEC-051) and an
attachment's `filename` (DEC-050) are values a person typed and no algorithm can
reconstruct, so an export that drops either loses something real. The projections
beside them -- `sort_author`, `creator_sort`, and the three `*_normalized` columns
-- rebuild themselves on every write through the DEC-036 mapper event. Exporting
them would present a cache as authority to whoever reads the dump later, so they
are omitted deliberately and a test asserts their absence.

**The entity shape, not a book shape.** An item is `type`, identifiers, sources
and an opaque `metadata` object, exactly as the row stores it. `metadata` is
passed through untransformed: the moment this module knows that `authors` is a
field, the format needs a v2 for the second domain (DEC-052 seam 3). The
Goodreads CSV beside it is allowed to be book-shaped because it is one domain's
export view rather than the export.

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

from book_tracker.infrastructure.models import (
    AttachmentRow,
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
    item: ItemRow,
    identifiers: list[ItemIdentifierRow],
    sources: list[ItemSourceRow],
    attachments: list[AttachmentRow],
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
        # References, not bytes: the blob is already held twice -- once live and
        # once hardlinked into every nightly backup (DEC-048) -- and a third copy
        # would turn a file you can read into a multi-gigabyte archive. The digest
        # is what makes the reference resolvable, because the blob's path *is* its
        # digest, so a backup can be searched by it without a running instance.
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


def iter_items(session: Session) -> Iterator[dict[str, Any]]:
    stream = session.scalars(select(ItemRow).order_by(ItemRow.id)).yield_per(BATCH)
    for batch in stream.partitions(BATCH):
        ids = [item.id for item in batch]
        identifiers = _grouped(
            session.scalars(
                select(ItemIdentifierRow)
                .where(ItemIdentifierRow.item_id.in_(ids))
                .order_by(ItemIdentifierRow.item_id, ItemIdentifierRow.kind)
            ).all(),
            "item_id",
        )
        sources = _grouped(
            session.scalars(
                select(ItemSourceRow)
                .where(ItemSourceRow.item_id.in_(ids))
                .order_by(ItemSourceRow.item_id, ItemSourceRow.source, ItemSourceRow.source_id)
            ).all(),
            "item_id",
        )
        attachments = _grouped(
            session.scalars(
                select(AttachmentRow)
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


def iter_entries(session: Session) -> Iterator[dict[str, Any]]:
    stream = session.scalars(select(EntryRow).order_by(EntryRow.id)).yield_per(BATCH)
    for batch in stream.partitions(BATCH):
        ids = [entry.id for entry in batch]
        rows = session.execute(
            select(EntryShelfRow.entry_id, ShelfRow.name)
            .join(ShelfRow, ShelfRow.id == EntryShelfRow.shelf_id)
            .where(EntryShelfRow.entry_id.in_(ids))
            .order_by(EntryShelfRow.entry_id, ShelfRow.name.collate("NOCASE"))
        ).all()
        shelves: dict[int, list[str]] = {}
        for entry_id, name in rows:
            shelves.setdefault(entry_id, []).append(name)
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
                # Names rather than ids: an id means nothing outside this database,
                # and the name is what the owner typed.
                "shelves": shelves.get(entry.id, []),
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
