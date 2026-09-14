"""A list you wrote yourself: a hand-made spreadsheet as an import source (Sprint 083).

Every other connector reads an export a platform produced, and leans on that
platform's identifiers. This one reads a file a person typed — the owner's
`exports/Libros.csv`, columns for title and author and nothing trustworthy — so
its whole contract is honesty: read the two columns the owner pointed at (or
the two that smell like them), keep every row visible including the malformed
ones, preserve the original cells in `source_fields`, and resolve nothing
itself. The provider search in `application/import_search.py` is the only
matcher; `match` here is always `MatchKind.NEW`, because a source with no
identity should not guess (DEC-082).
"""

import csv
import hashlib
import io
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

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
from book_tracker.domain.matching import MatchDecision, MatchKind
from book_tracker.domains.book import DOMAIN as BOOK

DOMAIN = BOOK

#: Headers a person plausibly wrote over a title column, Spanish and English,
#: compared after casefolding and accent folding. Trailing spaces are trimmed
#: before matching — the owner's own CSV carries `Editorial ` — and a header
#: that matches nothing falls back to position, not guesswork.
TITLE_HEADERS = (
    "titulo",
    "titulo del libro",
    "libro",
    "nombre",
    "nombre del libro",
    "title",
    "book name",
    "book title",
)
AUTHOR_HEADERS = (
    "autor",
    "autora",
    "autor del libro",
    "author",
    "writer",
    "escritor",
    "escritora",
)


class ListCSVError(ImportReadError):
    """Every way a hand-made list can be unreadable, with the way out of each.

    The vocabulary is closed and declared on `ListImporter.error_codes`. The
    `action` is one imperative sentence naming the thing to do (DEC-080): the
    person reading it typed this file themselves, so "re-export from the
    platform" is exactly the sentence this connector must never say.
    """

    ACTIONS = {
        "invalid_csv": (
            "This file could not be read as a text list.",
            "Save it again as CSV or plain text (UTF-8) and upload it unchanged.",
        ),
        "missing_columns": (
            "A list needs at least two columns: the title and the author.",
            "Add an author column, even one that says nothing, and try again.",
        ),
        "column_not_mapped": (
            "The columns chosen do not exist in this file.",
            "Pick columns between 1 and the file's column count, or leave them unset.",
        ),
    }

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        user_message, action = self.ACTIONS.get(code, (None, None))
        super().__init__(code, message, details, user_message=user_message, action=action)


def _fold(value: str) -> str:
    """Casefold and strip accents, so `Título` matches `titulo`."""
    lowered = unicodedata.normalize("NFD", value.strip().casefold())
    return "".join(char for char in lowered if unicodedata.category(char) != "Mn")


def detect_delimiter(text: str) -> str:
    """Comma, semicolon or tab — whichever the first data line holds most of.

    The header may be a data-poor row (two single-word columns), so the first
    *data* line decides; a quoted comma inside a title must not make a
    semicolon file read as comma-delimited, and counting only the lines after
    the first is the cheapest way to keep it that way.
    """
    lines = text.splitlines()
    sample = lines[1] if len(lines) > 1 else (lines[0] if lines else "")
    counts = {",": sample.count(","), ";": sample.count(";"), "\t": sample.count("\t")}
    best = max(counts, key=lambda key: counts[key])
    return best if counts[best] > 0 else ","


def sniff_mapping(headers: Sequence[str]) -> tuple[Sequence[str], dict[str, int]]:
    """Where title and author live, by header name or by position.

    Headers are trimmed (the owner's `Editorial ` proves they must be) and
    folded before matching. No header match means the first two columns —
    which is what a plain two-column list means, and the honest default for a
    file nobody labelled.
    """
    folded = [_fold(header) for header in headers]
    title_index = next(
        (index for index, header in enumerate(folded) if header in TITLE_HEADERS), None
    )
    author_index = next(
        (index for index, header in enumerate(folded) if header in AUTHOR_HEADERS), None
    )
    mapping: dict[str, int] = {}
    mapping["title"] = title_index if title_index is not None else 0
    mapping["author"] = author_index if author_index is not None else 1
    if len(headers) >= 2 and title_index is None and author_index == 0:
        # A single `Autor` header that matched column 0: title falls back to the
        # first column too, which would make title and author the same column.
        mapping["title"] = 0
        mapping["author"] = 1
    return headers, mapping


def _mapping_from_options(options: Mapping[str, Any] | None, width: int) -> dict[str, int] | None:
    """The client's explicit mapping, validated against the file's width.

    Returns `None` when the client sent nothing (auto-detect applies). A value
    that is not a small non-negative integer below the file's width is
    `column_not_mapped` — a refusal that names the thing to fix, not a silent
    fall-back that would import the wrong columns confidently. Form fields
    arrive as strings ("2"), so both strings and integers are accepted and
    anything that is not a plain base-10 integer is refused.
    """
    if options is None:
        return None
    mapping: dict[str, int] = {}
    for key in ("title_column", "author_column"):
        if key not in options:
            continue
        raw = options[key]
        if isinstance(raw, bool):
            value: int | None = None
        elif isinstance(raw, int):
            value = raw
        elif isinstance(raw, str) and raw.strip().isdigit():
            value = int(raw.strip())
        else:
            value = None
        if value is None or not 0 <= value < width:
            raise ListCSVError(
                "column_not_mapped",
                f"The chosen {key.replace('_', ' ')} does not exist in this file",
                {"key": key, "value": raw, "columns": width},
            )
        mapping["title" if key == "title_column" else "author"] = value
    return mapping or None


class ListImporter:
    name = "list"
    label = "Custom list"
    item_types: tuple[str, ...] = (DOMAIN.item_type,)
    input = ImportInputSpec(
        kind="upload",
        label="Your list (CSV or text)",
        field="file",
        accept=".csv,.txt,.tsv,text/csv,text/plain",
        # The two columns are a choice the reader makes, published to the screen
        # through the catalog so the mapping UI renders from a declaration.
        fields=("title_column", "author_column"),
        # Written for a person who typed this file themselves: there is no
        # platform to re-export from, so every step is about the file they hold.
        guide=(
            "Save your list as CSV or plain text — one book per line, the title "
            "in one column and the author in another. Semicolons and tabs work too.",
            "Drop it below. Akasha reads the title and author columns by their "
            "headers, or the first two columns when there are no headers.",
            "Nothing is added until you look at it: Akasha searches for each row "
            "in the background, proposes the matches it found, and you confirm "
            "or discard each one before the import lands in Triage.",
            "The other columns are kept exactly as you typed them, visible on "
            "each row, but are not read as data.",
        ),
        empty_state="Drop your list here, or choose a file.",
    )
    identity_kinds: frozenset[str] = frozenset()
    error_codes = frozenset({"invalid_csv", "missing_columns", "column_not_mapped"})
    #: The search-then-confirm opt-in (Sprint 083 D3): preview stages this
    #: connector's batches in `matching` with one search job enqueued, and
    #: commit waits until the job drains. Reached by declaration, never by a
    #: shared-layer branch on the connector's name.
    search_job: Literal["search_import_rows"] = "search_import_rows"

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.data is None:
            raise ListCSVError("invalid_csv", "A list file is required")
        try:
            text = source.data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ListCSVError("invalid_csv", "The file must be UTF-8 text") from error
        delimiter = detect_delimiter(text)
        try:
            reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
            rows = list(reader)
        except csv.Error as error:
            raise ListCSVError("invalid_csv", "The file's structure could not be parsed") from error
        rows = [row for row in rows if any(cell.strip() for cell in row)]
        if not rows:
            raise ListCSVError("invalid_csv", "The file holds no rows")
        headers = [cell.strip() for cell in rows[0]]
        width = max(len(row) for row in rows)
        if width < 2:
            raise ListCSVError(
                "missing_columns",
                "The file needs at least two columns",
                {"columns": width},
            )
        explicit = _mapping_from_options(source.options, width)
        if explicit is not None:
            mapping = explicit
        else:
            _, mapping = sniff_mapping(headers)

        records: list[NormalizedImportRecord] = []
        source_row = 1  # the header, if any
        for row in rows[1:]:
            source_row += 1
            records.append(self._record(row, mapping, headers, source_row, width))
        if not records:
            raise ListCSVError("invalid_csv", "The file holds a header and no rows")

        fingerprint = hashlib.sha256(source.data).hexdigest()
        if explicit is not None:
            # The mapping is part of the import's identity: the same file read
            # with different columns is a different import, never a stale
            # replay (DEC-106's rule applied to interpretation, D1.7).
            suffix = "".join(
                f"{letter}{mapping[key]}" for key, letter in (("title", "t"), ("author", "a"))
            )
            fingerprint = f"{fingerprint}#{suffix}"
        return ImportSnapshot(
            fingerprint=fingerprint,
            filename=source.filename or "list.csv",
            source_descriptor={
                "filename": source.filename or "list.csv",
                "delimiter": delimiter,
                "mapping": {key: mapping[key] for key in ("title", "author")},
            },
            records=tuple(records),
            archive_name="source.csv",
            archive_data=source.data,
        )

    def _record(
        self,
        row: Sequence[str],
        mapping: Mapping[str, int],
        headers: Sequence[str],
        row_number: int,
        width: int,
    ) -> NormalizedImportRecord:
        def cell(index: int) -> str:
            return row[index].strip() if index < len(row) else ""

        title = cell(mapping["title"])
        author = cell(mapping["author"]) if "author" in mapping else ""
        errors: list[dict[str, Any]] = []
        if not title:
            errors.append({"field": "title", "code": "required", "value": ""})
        # No author cell (a short row) and an empty one are the same honest
        # fact about the spreadsheet: it said nothing there.
        if not author:
            errors.append({"field": "author", "code": "missing"})
        # The original cells ride uninterpreted: the columns this sprint does
        # not map are the owner's own words, and triage shows them verbatim.
        source_fields: dict[str, Any] = {}
        for index, header in enumerate(headers):
            if index == mapping.get("title") or index == mapping.get("author"):
                continue
            value = cell(index)
            if value:
                source_fields[header or f"column_{index + 1}"] = value
        return NormalizedImportRecord(
            row_number=row_number,
            item=ImportItem(
                title=title,
                subtitle=None,
                year=None,
                identifiers={},
                metadata={"creators": [author]} if author else {},
            ),
            entry=ImportEntry(score=None, notes=None, date_added=None, values={}),
            shelves=(),
            errors=tuple(errors),
            source_fields=source_fields,
        )

    def stage(self, snapshot: ImportSnapshot, directory: Path, _data_dir: Path) -> ImportSnapshot:
        if snapshot.archive_name and snapshot.archive_data is not None:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / snapshot.archive_name).write_bytes(snapshot.archive_data)
        return replace(snapshot, archive_data=None)

    def match(self, _record: NormalizedImportRecord, _matcher: ImportMatcher) -> MatchDecision:
        # With no identities and no trusted text key, this connector never
        # resolves a library match: the provider search (D3) is the only
        # matcher, and a wrong-but-confident local match is exactly what the
        # confirm flow exists to prevent.
        return MatchDecision(kind=MatchKind.NEW)


IMPORTER = ListImporter()
