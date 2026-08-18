import csv
import io
from datetime import datetime
from typing import Any

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
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


class GoodreadsCSVError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)


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
