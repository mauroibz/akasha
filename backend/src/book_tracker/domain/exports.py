"""The per-domain export boundary.

Mirrors `domain/importers.py` exactly, pointed the other way: an export view owns only
how a row is spelled, and the shared walk in `application/export.py` owns the streaming,
the keyset batching and the child-row joins, handing the view one `ExportRow` at a time.
The view holds no session and writes no SQL — a view that sorted or buffered rows to
write them would undo the flat-memory discipline the walk exists to keep.

Registration is the fifth shared registration point (`domain/registry.py`), derived from
what each view declares rather than hand-maintained, the same way `IMPORTERS_BY_DOMAIN`
is derived from `REGISTERED_IMPORTERS`.
"""

import csv
import io
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from book_tracker.domain.spec import Domain, FieldSpec

#: Leading characters a spreadsheet treats as the start of a formula rather than as
#: text. Every view that writes a spreadsheet format inherits this rule (Sprint 068
#: AC5) — a notes field is free text and these are files whose whole purpose is to be
#: opened in a spreadsheet.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: object) -> str:
    """Render a cell that a spreadsheet will read as text, never as a formula."""
    text_value = "" if value is None else str(value)
    if text_value.startswith(FORMULA_PREFIXES):
        return "'" + text_value
    return text_value


@dataclass(frozen=True)
class ExportRow:
    """One entry, joined and neutral, before a view decides how to spell it.

    Everything a view could need to write any format without touching SQL: the item's
    neutral columns and opaque `metadata`, the entry's own values, and the two child
    collections (`shelves`, `formats`) already resolved for this row. `identifiers` is
    keyed by kind (`"isbn"`, `"isbn13"`, ...), the same vocabulary import and the
    library API already use.
    """

    item_id: int
    item_type: str
    title: str
    subtitle: str | None
    year: int | None
    metadata: Mapping[str, Any]
    identifiers: Mapping[str, str]
    status: str
    score: int | None
    notes: str | None
    date_added: str | None
    date_started: str | None
    date_finished: str | None
    reread_count: int
    progress: int | None
    shelves: tuple[str, ...]
    formats: tuple[str, ...]


@runtime_checkable
class ExportView(Protocol):
    """A connector registered by the domains it can write — the export analogue of `Importer`."""

    name: str
    label: str
    item_types: tuple[str, ...]
    media_type: str
    #: Whether this view can reconstruct the full record, or is a lossy convenience.
    #: The lossless path is `GET /api/export`'s JSON, which is not a registered view.
    lossless: bool
    filename: str
    #: Ordered steps: where this file goes, in the target application. Never markup,
    #: for the reason `ImportInputSpec.guide` is not (DEC-080).
    guide: tuple[str, ...]
    help_url: str | None
    #: The entry fields this view can express, in words, for a screen to render.
    carries: tuple[str, ...]

    def write(self, rows: Iterator[ExportRow]) -> Iterator[str]: ...


#: The neutral entry layer every table view carries, regardless of domain
#: (proposal §2.2). `Creator` is drawn from `metadata["creators"]`, the one metadata
#: key every domain's own field declares (DEC-036's `creator_primary` generated column
#: is defined against the same key) — carried here rather than through the per-field
#: loop below so it is never duplicated under the domain's own label for it.
_NEUTRAL_COLUMNS = (
    "Title",
    "Creator",
    "Year",
    "Status",
    "Score",
    "Shelves",
    "Formats",
    "Date added",
    "Date started",
    "Date finished",
    "Progress",
    "Notes",
)


def _rendered_field(value: Any, field: FieldSpec) -> str:
    """One metadata field, rendered from its own declaration rather than its name.

    Driven entirely by `type`/`multiplicity`/`columns` so a domain nobody has written
    yet renders correctly by declaring itself, the same promise `fields_are_described_
    completely` holds the rest of the contract to.
    """
    if value is None:
        return ""
    if field.type == "rows":
        if not isinstance(value, Sequence) or isinstance(value, str):
            return ""
        parts = []
        for entry in value:
            if not isinstance(entry, Mapping):
                continue
            cells = [
                str(entry[column.name])
                for column in field.columns
                if entry.get(column.name) not in (None, "")
            ]
            if cells:
                parts.append(" ".join(cells))
        return "; ".join(parts)
    if field.multiplicity == "many":
        if isinstance(value, Sequence) and not isinstance(value, str):
            return ", ".join(str(item) for item in value)
        return str(value)
    return str(value)


class _TableExportView:
    """The floor every domain gets (proposal §2.2): a CSV rendered from its declaration.

    One instance per domain, built generically by `make_table_view` from that domain's
    own `Domain` object — no branch here names a domain, so a domain registered after
    this module is written is exportable the moment it is registered.
    """

    name = "table"
    media_type = "text/csv; charset=utf-8"
    #: Identifiers, attachments and exact timestamps are not columns here; the JSON
    #: export is the lossless artifact (proposal §2.6/finding 6).
    lossless = False
    help_url: str | None = None

    def __init__(self, domain: Domain) -> None:
        self._domain = domain
        self.label = f"Table ({domain.label})"
        self.item_types: tuple[str, ...] = (domain.item_type,)
        self.filename = f"akasha-{domain.item_type}-table.csv"
        self.guide: tuple[str, ...] = (
            f"Open this file in any spreadsheet application. Every {domain.label.lower()} "
            "entry in your library is one row.",
        )
        self._fields = tuple(field for field in domain.fields if field.name != "creators")
        self.carries: tuple[str, ...] = _NEUTRAL_COLUMNS + tuple(
            field.label for field in self._fields
        )
        self._columns = self.carries

    def write(self, rows: Iterator[ExportRow]) -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")

        def flush() -> str:
            value = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return value

        writer.writerow(self._columns)
        yield flush()
        for row in rows:
            creators = row.metadata.get("creators")
            creator = (
                ", ".join(str(name) for name in creators) if isinstance(creators, list) else ""
            )
            neutral_values = (
                row.title,
                creator,
                row.year if row.year is not None else "",
                row.status,
                row.score if row.score is not None else "",
                ", ".join(row.shelves),
                ", ".join(row.formats),
                row.date_added or "",
                row.date_started or "",
                row.date_finished or "",
                row.progress if row.progress is not None else "",
                row.notes or "",
            )
            metadata_values = tuple(
                _rendered_field(row.metadata.get(field.name), field) for field in self._fields
            )
            writer.writerow([safe_cell(value) for value in neutral_values + metadata_values])
            yield flush()


def make_table_view(domain: Domain) -> ExportView:
    """The generic `table` view for one domain (proposal §2.2, deliverable 4)."""
    return _TableExportView(domain)
