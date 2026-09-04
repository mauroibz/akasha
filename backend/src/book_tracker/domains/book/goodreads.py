import csv
import hashlib
import io
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from book_tracker.domain.exports import ExportRow, safe_cell
from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.importers import (
    ImportEntry,
    ImportInputSpec,
    ImportItem,
    ImportMatcher,
    ImportReadContext,
    ImportReadError,
    ImportSnapshot,
    ImportSource,
    NormalizedImportRecord,
)
from book_tracker.domain.matching import MatchDecision
from book_tracker.domain.normalization import shelf_slug
from book_tracker.domains.book import DOMAIN as BOOK

REQUIRED_COLUMNS = {
    "Book Id",
    "Title",
    "Author",
    "ISBN",
    "ISBN13",
    "My Rating",
    "Date Read",
    "Date Added",
    "Bookshelves",
    "Exclusive Shelf",
}


#: Goodreads' exclusive shelf, mapped onto the statuses of the domain this importer
#: serves (product spec 5.1). Stated against `BOOK` rather than left to the accident
#: that books are the only domain with an importer: a `pending` record has no Goodreads
#: spelling, and a future importer for another domain declares its own map or none.
#: `DOMAIN.status(...)` is asserted over this in `test_goodreads_import.py`, so a
#: status renamed out from under it fails a test rather than silently suggesting
#: nothing.
DOMAIN = BOOK
SUGGESTED_STATUS = {"read": "read", "currently-reading": "reading", "to-read": "to_read"}


class GoodreadsCSVError(ImportReadError):
    """Every way a Goodreads export can be unreadable, with the way out of each.

    The vocabulary is closed and declared on `GoodreadsImporter.error_codes`. The
    `action` is the point: "the CSV structure is malformed" tells a reader nothing they
    can do, and "export again from goodreads.com" does (DEC-080).
    """

    ACTIONS = {
        "invalid_csv": (
            "This file is not a Goodreads export.",
            "Export again from goodreads.com/review/import and upload the file unchanged.",
        ),
        "missing_columns": (
            "This export is missing columns Akasha needs.",
            "Use Export Library on goodreads.com rather than a spreadsheet you edited.",
        ),
    }

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        user_message, action = self.ACTIONS.get(code, (None, None))
        super().__init__(code, message, details, user_message=user_message, action=action)


def _unarmor(value: str) -> str:
    value = value.strip()
    return value[2:-1] if value.startswith('="') and value.endswith('"') else value


def _date(value: str, field: str, errors: list[dict[str, str]]) -> str | None:
    if not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y/%m/%d").date().isoformat()
    except ValueError:
        errors.append({"field": field, "code": "invalid_date", "value": value.strip()})
        return None


def parse_goodreads(data: bytes) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        columns = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise GoodreadsCSVError(
                "missing_columns", "Required Goodreads columns are missing", {"columns": missing}
            )
        rows = list(reader)
    except UnicodeDecodeError as error:
        raise GoodreadsCSVError("invalid_csv", "The file must be UTF-8 CSV") from error
    except csv.Error as error:
        raise GoodreadsCSVError("invalid_csv", "The CSV structure is malformed") from error
    records: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, 2):
        errors: list[dict[str, str]] = []
        title = (row.get("Title") or "").strip()
        author = (row.get("Author") or "").strip()
        if not title:
            errors.append({"field": "title", "code": "required", "value": ""})
        isbn = None
        for raw in (_unarmor(row.get("ISBN13") or ""), _unarmor(row.get("ISBN") or "")):
            if not raw:
                continue
            try:
                isbn = normalize_identifier("isbn", raw).normalized_value
                break
            except InvalidIdentifier:
                errors.append({"field": "isbn", "code": "invalid_isbn", "value": raw})
        rating_raw = (row.get("My Rating") or "").strip()
        score = None
        if rating_raw:
            try:
                rating = int(rating_raw)
                if rating not in range(6):
                    raise ValueError
                score = rating * 2 if rating else None
            except ValueError:
                errors.append({"field": "my_rating", "code": "invalid_rating", "value": rating_raw})
        exclusive = (row.get("Exclusive Shelf") or "").strip()
        suggested = SUGGESTED_STATUS.get(exclusive)
        shelves = []
        for value in (row.get("Bookshelves") or "").split(","):
            value = value.strip()
            if value and value != exclusive:
                slug = shelf_slug(value)
                if slug and slug not in shelves:
                    shelves.append(slug)

        def integer(
            name: str,
            current_row: dict[str, str | None] = row,
            current_errors: list[dict[str, str]] = errors,
        ) -> int | None:
            raw = (current_row.get(name) or "").strip()
            if not raw:
                return None
            try:
                return int(raw)
            except ValueError:
                current_errors.append(
                    {
                        "field": name.lower().replace(" ", "_"),
                        "code": "invalid_integer",
                        "value": raw,
                    }
                )
                return None

        records.append(
            {
                "row_number": row_number,
                "goodreads_book_id": (row.get("Book Id") or "").strip(),
                "title": title,
                "creators": [
                    value
                    for value in [author, *((row.get("Additional Authors") or "").split(","))]
                    if value.strip()
                ],
                "isbn": isbn,
                "publisher": (row.get("Publisher") or "").strip() or None,
                "page_count": integer("Number of Pages"),
                "year": integer("Year Published"),
                "original_year": integer("Original Publication Year"),
                "date_finished": _date(row.get("Date Read") or "", "date_read", errors),
                "date_added": _date(row.get("Date Added") or "", "date_added", errors),
                "suggested_status": suggested,
                "score": score,
                "score_provisional": score is not None,
                "shelves": shelves,
                "review": (row.get("My Review") or "").strip() or None,
                "reread_count": max((integer("Read Count") or 1) - 1, 0),
                "errors": errors,
            }
        )
    return records


class GoodreadsImporter:
    name = "goodreads"
    label = "Goodreads"
    item_types: tuple[str, ...] = (DOMAIN.item_type,)
    input = ImportInputSpec(
        kind="upload",
        label="Goodreads CSV",
        field="file",
        accept=".csv,text/csv",
        # Where the file comes from, and what happens to it. Product spec §5.1 is
        # the source of every claim here; a reader should not have to find that
        # document to know why their four-star book arrived as an 8.
        guide=(
            "On goodreads.com, open My Books → Import and export "
            "(goodreads.com/review/import). Desktop web only — the apps cannot export.",
            "Press Export Library, wait for the file to be generated, and download "
            "goodreads_library_export.csv.",
            "Drop it below. This is a snapshot, not a sync: Goodreads stops being "
            "authoritative the moment it lands.",
            "Ratings are doubled onto Akasha's 1–10 scale and marked provisional, "
            "because a 3\u2605 is not a 6 you chose. Editing a score clears the mark.",
            "Your shelves become tags, and every row lands in Triage rather than in "
            "the library, so nothing appears until you have looked at it.",
        ),
        empty_state="Drop goodreads_library_export.csv here, or choose a file.",
        help_url="https://www.goodreads.com/review/import",
    )
    identity_kinds = frozenset({"isbn"})
    error_codes = frozenset({"invalid_csv", "missing_columns"})

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.data is None:
            raise GoodreadsCSVError("invalid_csv", "A Goodreads CSV file is required")
        records = []
        for payload in parse_goodreads(source.data):
            metadata = {
                "creators": payload["creators"],
                **{
                    key: payload[key]
                    for key in ("publisher", "page_count", "original_year")
                    if payload.get(key) not in (None, "", [], {})
                },
            }
            records.append(
                NormalizedImportRecord(
                    row_number=payload["row_number"],
                    item=ImportItem(
                        title=payload["title"],
                        subtitle=None,
                        year=payload.get("year"),
                        identifiers={"isbn": payload["isbn"]} if payload.get("isbn") else {},
                        metadata=metadata,
                    ),
                    entry=ImportEntry(
                        score=payload.get("score"),
                        notes=payload.get("review"),
                        date_added=payload.get("date_added"),
                        values={
                            "date_finished": payload.get("date_finished"),
                            "reread_count": payload.get("reread_count", 0),
                        },
                        score_provisional=bool(payload.get("score_provisional")),
                        suggested_status=payload.get("suggested_status"),
                    ),
                    shelves=tuple(payload.get("shelves", ())),
                    errors=tuple(payload.get("errors", ())),
                    source_fields={"goodreads_book_id": payload["goodreads_book_id"]},
                )
            )
        return ImportSnapshot(
            fingerprint=hashlib.sha256(source.data).hexdigest(),
            filename=source.filename or "goodreads.csv",
            source_descriptor={"filename": source.filename or "goodreads.csv"},
            records=tuple(records),
            archive_name="source.csv",
            archive_data=source.data,
        )

    def stage(self, snapshot: ImportSnapshot, directory: Path, _data_dir: Path) -> ImportSnapshot:
        if snapshot.archive_name and snapshot.archive_data is not None:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / snapshot.archive_name).write_bytes(snapshot.archive_data)
        return replace(snapshot, archive_data=None)

    def match(self, record: NormalizedImportRecord, matcher: ImportMatcher) -> MatchDecision:
        identifiers = [
            normalize_identifier(kind, value)
            for kind, value in record.item.identifiers.items()
            if kind in self.identity_kinds
        ]
        creators = record.item.metadata.get("creators", ())
        first_creator = str(creators[0]) if isinstance(creators, list) and creators else ""
        return matcher.match(
            identifiers=identifiers,
            title=record.item.title,
            first_author=first_creator,
        )


IMPORTER = GoodreadsImporter()


#: Product spec 5.1, in Goodreads' own order. Moved here from `application/export.py`
#: (Sprint 068): this view is allowed to be book-shaped because it is one domain's
#: export view, not the export (DEC-052 seam 3), and it now sits beside the reader
#: of the same file it writes.
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


def _goodreads_date(value: str | None) -> str:
    """ISO `2026-01-05` to Goodreads' `2026/01/05`; timestamps lose their time."""
    if not value:
        return ""
    return value[:10].replace("-", "/")


class GoodreadsExportView:
    """The mirror of `GoodreadsImporter`: writes the same file it reads.

    Holds no session and writes no SQL — `application/export.py`'s shared walk hands
    it one `ExportRow` at a time, already joined and filtered to books. Round-tripped
    through `parse_goodreads` above by `test_export.py`, per DEC-025.
    """

    name = "goodreads"
    label = "Goodreads"
    item_types: tuple[str, ...] = (DOMAIN.item_type,)
    media_type = "text/csv; charset=utf-8"
    #: The 1-10 score halves to Goodreads' 1-5 and the exact value survives only in
    #: the lossless JSON export (proposal §2.6/finding 6).
    lossless = False
    #: Kept from the pre-sprint route so `?format=csv` stays a byte-identical alias
    #: (Sprint 068 AC4) rather than a rename dressed up as a deprecation.
    filename = "akasha-export.csv"
    guide: tuple[str, ...] = (
        "On goodreads.com, open My Books → Import and export "
        "(goodreads.com/review/import) and choose Import Library.",
        "Upload this file. Goodreads reads it as its own export, because it is one.",
    )
    help_url: str | None = "https://www.goodreads.com/review/import"
    carries: tuple[str, ...] = (
        "title",
        "author",
        "ISBN",
        "rating",
        "publisher",
        "page count",
        "year published",
        "date read",
        "date added",
        "shelves",
        "review",
        "read count",
    )

    def write(self, rows: Iterator[ExportRow]) -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(GOODREADS_COLUMNS), lineterminator="\r\n")

        def flush() -> str:
            value = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return value

        writer.writeheader()
        yield flush()
        for row in rows:
            authors = row.metadata.get("creators")
            authors = [str(name) for name in authors] if isinstance(authors, list) else []
            # Goodreads rates 1-5 and the importer doubled it (product spec 5.1).
            # Halving rounds a hand-set odd score up rather than down; the exact
            # 1-10 value is in the JSON export, which is the lossless one. `0` is
            # Goodreads for unrated.
            rating = (row.score + 1) // 2 if row.score else 0
            values = {
                "Book Id": row.item_id,
                "Title": row.title,
                "Author": authors[0] if authors else "",
                "Additional Authors": ", ".join(authors[1:]),
                "ISBN": row.identifiers.get("isbn10", ""),
                "ISBN13": row.identifiers.get("isbn", row.identifiers.get("isbn13", "")),
                "My Rating": rating,
                "Publisher": row.metadata.get("publisher") or "",
                "Number of Pages": row.metadata.get("page_count") or "",
                "Year Published": row.year if row.year is not None else "",
                "Original Publication Year": row.metadata.get("original_year") or "",
                "Date Read": _goodreads_date(row.date_finished),
                "Date Added": _goodreads_date(row.date_added),
                "Bookshelves": ", ".join(row.shelves),
                "Exclusive Shelf": _EXCLUSIVE_SHELF.get(row.status, row.status),
                "My Review": row.notes or "",
                # We store rereads; Goodreads counts total reads, and the importer
                # took `Read Count - 1`. This is that inverse.
                "Read Count": (row.reread_count or 0) + 1,
            }
            writer.writerow({key: safe_cell(value) for key, value in values.items()})
            yield flush()


EXPORT = GoodreadsExportView()
