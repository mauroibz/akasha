"""The StoryGraph import (Sprint 099, proposal §7): a CSV keyed on ISBN, the
Goodreads shape.

Written from StoryGraph's published export header, not from a recorded file (none was
available). The reader requires only the columns it maps and ignores every other, so a
column StoryGraph adds, drops or reorders around them does not refuse the file.

- **`ISBN/UID` is an ISBN or StoryGraph's own id.** Only a valid ISBN becomes an
  identifier; a UID is silently not one (it is not a broken ISBN).
- **`Star Rating` has quarter stars.** 4.25 is doubled and rounded onto 1–10 (9),
  and marked provisional exactly as Goodreads' are.
- **`Read Status` is a closed set**: read, currently-reading, to-read,
  did-not-finish. Anything else suggests nothing and lands unsorted.
"""

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
from book_tracker.domain.sniffing import csv_header
from book_tracker.domains.book import DOMAIN as BOOK

REQUIRED_COLUMNS = {"Title", "Authors", "Read Status"}

DOMAIN = BOOK
SUGGESTED_STATUS = {
    "read": "read",
    "currently-reading": "reading",
    "to-read": "to_read",
    "did-not-finish": "dropped",
}


class StoryGraphCSVError(ImportReadError):
    """Every way a StoryGraph export can be unreadable, with the way out of each."""

    ACTIONS = {
        "invalid_csv": (
            "This file is not a StoryGraph export.",
            "Export again from StoryGraph and upload the file unchanged.",
        ),
        "missing_columns": (
            "This export is missing columns Akasha needs.",
            "Use StoryGraph's own export rather than a spreadsheet you edited.",
        ),
    }

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        user_message, action = self.ACTIONS.get(code, (None, None))
        super().__init__(code, message, details, user_message=user_message, action=action)


def _date(value: str, field: str, errors: list[dict[str, str]]) -> str | None:
    value = value.strip()
    if not value:
        return None
    for pattern in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    errors.append({"field": field, "code": "invalid_date", "value": value})
    return None


def _split(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def parse_storygraph(data: bytes) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        columns = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise StoryGraphCSVError(
                "missing_columns",
                "Required StoryGraph columns are missing",
                {"columns": missing},
            )
        rows = list(reader)
    except UnicodeDecodeError as error:
        raise StoryGraphCSVError("invalid_csv", "The file must be UTF-8 CSV") from error
    except csv.Error as error:
        raise StoryGraphCSVError("invalid_csv", "The CSV structure is malformed") from error
    records: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, 2):
        errors: list[dict[str, str]] = []
        title = (row.get("Title") or "").strip()
        if not title:
            errors.append({"field": "title", "code": "required", "value": ""})
        isbn = None
        raw_isbn = (row.get("ISBN/UID") or "").strip()
        if raw_isbn:
            try:
                isbn = normalize_identifier("isbn", raw_isbn).normalized_value
            except InvalidIdentifier:
                isbn = None
        rating_raw = (row.get("Star Rating") or "").strip()
        score = None
        if rating_raw:
            try:
                rating = float(rating_raw)
                if not 0 <= rating <= 5:
                    raise ValueError
                # Half up: Python's round() is banker's, and 4.25 stars is a 9, not an 8.
                score = int(rating * 2 + 0.5) or None
            except ValueError:
                errors.append(
                    {"field": "star_rating", "code": "invalid_rating", "value": rating_raw}
                )
        count_raw = (row.get("Read Count") or "").strip()
        try:
            reads = int(count_raw) if count_raw else 0
        except ValueError:
            errors.append({"field": "read_count", "code": "invalid_integer", "value": count_raw})
            reads = 0
        shelves: list[str] = []
        for value in _split(row.get("Tags")):
            slug = shelf_slug(value)
            if slug and slug not in shelves:
                shelves.append(slug)
        records.append(
            {
                "row_number": row_number,
                "title": title,
                "creators": _split(row.get("Authors")),
                "isbn": isbn,
                "date_added": _date(row.get("Date Added") or "", "date_added", errors),
                "date_finished": _date(row.get("Last Date Read") or "", "last_date_read", errors),
                "suggested_status": SUGGESTED_STATUS.get(
                    (row.get("Read Status") or "").strip().lower()
                ),
                "score": score,
                "score_provisional": score is not None,
                "shelves": shelves,
                "review": (row.get("Review") or "").strip() or None,
                "reread_count": max(reads - 1, 0),
                "errors": errors,
            }
        )
    return records


class StoryGraphImporter:
    name = "storygraph"
    label = "StoryGraph"
    item_types: tuple[str, ...] = (DOMAIN.item_type,)
    input = ImportInputSpec(
        kind="upload",
        label="StoryGraph CSV",
        field="file",
        accept=".csv,text/csv",
        guide=(
            "On app.thestorygraph.com, open your profile's Manage Account page and "
            "choose Export StoryGraph Library.",
            "Download the CSV when it is ready, and drop it below.",
            "Star ratings are doubled onto Akasha's 1–10 scale (quarter stars round) "
            "and marked provisional. Your tags become shelves.",
            "Every row lands in your Inbox first, so nothing appears in the library "
            "until you have looked at it.",
        ),
        empty_state="Drop your StoryGraph export here, or choose a file.",
        help_url="https://app.thestorygraph.com/",
    )
    identity_kinds = frozenset({"isbn"})
    error_codes = frozenset({"invalid_csv", "missing_columns"})

    def sniff(self, head: bytes, name: str) -> float:
        """StoryGraph's export carries `ISBN/UID` and `Read Status` (Sprint 099)."""
        header = set(csv_header(head) or ())
        return 0.95 if {"ISBN/UID", "Read Status", "Title"} <= header else 0.0

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.data is None:
            raise StoryGraphCSVError("invalid_csv", "A StoryGraph CSV file is required")
        records = []
        for payload in parse_storygraph(source.data):
            records.append(
                NormalizedImportRecord(
                    row_number=payload["row_number"],
                    item=ImportItem(
                        title=payload["title"],
                        subtitle=None,
                        year=None,
                        identifiers={"isbn": payload["isbn"]} if payload.get("isbn") else {},
                        metadata={"creators": payload["creators"]},
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
                    source_fields={},
                )
            )
        return ImportSnapshot(
            fingerprint=hashlib.sha256(source.data).hexdigest(),
            filename=source.filename or "storygraph.csv",
            source_descriptor={"filename": source.filename or "storygraph.csv"},
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
            identifiers=identifiers, title=record.item.title, first_author=first_creator
        )


IMPORTER = StoryGraphImporter()
