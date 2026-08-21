import csv
import hashlib
import io
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

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
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, details)


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
    item_type = DOMAIN.item_type
    input = ImportInputSpec(
        kind="upload", label="Goodreads CSV", field="file", accept=".csv,text/csv"
    )
    identity_kinds = frozenset({"isbn"})

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
