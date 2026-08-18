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
field, the format needs a v2 for the second domain (DEC-052 seam 3). The
Goodreads CSV beside it is allowed to be book-shaped because it is one domain's
export view rather than the export.

**Flat memory, whatever the library size.** The deployment target is a ZimaBoard.
Rows stream in bounded batches and each one is serialized and yielded on its own,
so peak memory tracks the batch size rather than the corpus. Child rows are
fetched one query per batch rather than one per item, which keeps that promise
without an N+1.
"""

import csv
import io
import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from book_tracker.domain.registry import DEFAULT_DOMAIN
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


#: Product spec 5.1, in Goodreads' own order. This view is allowed to be
#: book-shaped: it is one domain's export view, not the export (DEC-052 seam 3).
GOODREADS_COLUMNS = (
    "Book Id",
    "Title",
    "Author",
    "Additional Authors",
    "ISBN",
    "ISBN13",
    "My Rating",
    "Publisher",
    "Number of Pages",
    "Year Published",
    "Original Publication Year",
    "Date Read",
    "Date Added",
    "Bookshelves",
    "Exclusive Shelf",
    "My Review",
    "Read Count",
)

#: The inverse of the import's suggestion map (product spec 5.1). Goodreads has no
#: wishlist or dropped concept, so those statuses -- and `unsorted` -- have no
#: Goodreads spelling and are written verbatim rather than flattened into a
#: neighbouring shelf, which would silently move a row.
_EXCLUSIVE_SHELF = {"read": "read", "reading": "currently-reading", "to_read": "to-read"}

#: Leading characters a spreadsheet treats as the start of a formula rather than
#: as text. Excel's DDE behaviour makes this a real hazard in a file whose whole
#: purpose is to be opened in a spreadsheet, and notes are free text.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: object) -> str:
    """Render a cell that a spreadsheet will read as text.

    Neutralizing changes the bytes, which is why it happens *here* and not in the
    JSON: the JSON export is the lossless artifact and carries the value exactly
    as typed, while the CSV is the convenience view and is made safe to open.
    """
    text_value = "" if value is None else str(value)
    if text_value.startswith(_FORMULA_PREFIXES):
        return "'" + text_value
    return text_value


def _goodreads_date(value: str | None) -> str:
    """ISO `2026-01-05` to Goodreads' `2026/01/05`; timestamps lose their time."""
    if not value:
        return ""
    return value[:10].replace("-", "/")


def _row(entry: Any, item: Any, identifiers: dict[str, str], shelves: list[str]) -> dict[str, Any]:
    metadata = json.loads(item.metadata_json or "{}")
    authors = metadata.get("creators")
    authors = [str(name) for name in authors] if isinstance(authors, list) else []
    # Goodreads rates 1-5 and the importer doubled it (product spec 5.1). Halving
    # rounds a hand-set odd score up rather than down; the exact 1-10 value is in
    # the JSON export, which is the lossless one. `0` is Goodreads for unrated.
    rating = (entry.score + 1) // 2 if entry.score else 0
    return {
        "Book Id": item.id,
        "Title": item.title,
        "Author": authors[0] if authors else "",
        "Additional Authors": ", ".join(authors[1:]),
        "ISBN": identifiers.get("isbn10", ""),
        "ISBN13": identifiers.get("isbn", identifiers.get("isbn13", "")),
        "My Rating": rating,
        "Publisher": metadata.get("publisher") or "",
        "Number of Pages": metadata.get("page_count") or "",
        "Year Published": item.year if item.year is not None else "",
        "Original Publication Year": metadata.get("original_year") or "",
        "Date Read": _goodreads_date(entry.date_finished),
        "Date Added": _goodreads_date(entry.date_added),
        "Bookshelves": ", ".join(shelves),
        "Exclusive Shelf": _EXCLUSIVE_SHELF.get(entry.status, entry.status),
        "My Review": entry.notes or "",
        # We store rereads; Goodreads counts total reads, and the importer took
        # `Read Count - 1`. This is that inverse.
        "Read Count": (entry.reread_count or 0) + 1,
    }


def export_csv(engine: Engine) -> Iterator[str]:
    """Yield the Goodreads-shaped CSV a row at a time, for books alone."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(GOODREADS_COLUMNS), lineterminator="\r\n")

    def flush() -> str:
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    writer.writeheader()
    yield flush()

    with Session(engine) as session:
        for batch in _batches(session, _ENTRY_COLUMNS):
            item_ids = [entry.item_id for entry in batch]
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
            shelves = _shelves_for(session, [entry.id for entry in batch])
            for entry in batch:
                item = items.get(entry.item_id)
                if item is None:  # pragma: no cover - the foreign key guarantees this
                    continue
                # One domain's export view, not the export. A Goodreads CSV describes
                # books: an album emitted into it would arrive somewhere else as a book
                # with no author, no ISBN and a page count. The JSON beside it is the
                # lossless artifact and carries every type (DEC-052 seam 3).
                if item.type != DEFAULT_DOMAIN.item_type:
                    continue
                row_values = _row(
                    entry, item, identifiers.get(item.id, {}), shelves.get(entry.id, [])
                )
                writer.writerow({key: _safe_cell(value) for key, value in row_values.items()})
                yield flush()
