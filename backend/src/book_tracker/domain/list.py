"""The custom-list reader: a hand-made list as an import source, any domain.

Born in Sprint 083 as the book domain's `list` connector and generalized in
Sprint 084: the file a person typed has no identity and no domain either, so
the reader takes its vocabulary from the chosen domain's `ListColumnSpec` —
which header words point at the title and the creator column, and whether a
creator is required at all (a film list is often one column). Everything else
is the Sprint 083 contract unchanged: read the columns the owner pointed at
(or the ones that smell like them), keep every row visible including the
malformed ones, preserve the original cells in `source_fields`, and resolve
nothing itself — the provider search in `application/import_search.py` is
the only matcher; `match` here is always `MatchKind.NEW`, because a source
with no identity should not guess (DEC-082).
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


def listable_domains() -> tuple[str, ...]:
    """The domains the list connector serves: every one that declared its
    list vocabulary.

    Derived, never hand-written — a domain that declares `list_columns`
    becomes list-importable with zero connector changes, and a domain that has
    not is not importable rather than silently borrowing another domain's
    words. Read at call time (not import time) because the registry imports
    this module to register the connector: a module-level read would be the
    circular import.
    """
    from book_tracker.domain.registry import DOMAINS

    return tuple(
        item_type for item_type, domain in DOMAINS.items() if domain.list_columns is not None
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
            "A list needs at least two columns: the title and the creator.",
            "Add a second column, even one that says nothing, and try again.",
        ),
        "column_not_mapped": (
            "The columns chosen do not exist in this file.",
            "Pick columns between 1 and the file's column count, or leave them unset.",
        ),
        "invalid_import_target": (
            "This list did not say which library it is for.",
            "Choose the library this list belongs to, then preview again.",
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


def sniff_mapping(
    headers: Sequence[str],
    *,
    title_words: Sequence[str] = (),
    creator_words: Sequence[str] = (),
) -> tuple[Sequence[str], dict[str, int]]:
    """Where title and creator live, by header name or by position.

    Headers are trimmed (the owner's `Editorial ` proves they must be) and
    folded before matching. No header match means the first two columns —
    which is what a plain two-column list means, and the honest default for a
    file nobody labelled. A domain that declares no creator words still gets
    `author` mapped (the second column, when the file has one) so a list that
    carries one anyway reads it — but the row treats an empty creator as a
    fact, not an error.
    """
    folded = [_fold(header) for header in headers]
    title_words = tuple(_fold(word) for word in title_words)
    creator_words = tuple(_fold(word) for word in creator_words)
    title_index = next(
        (index for index, header in enumerate(folded) if header in title_words), None
    )
    author_index = next(
        (index for index, header in enumerate(folded) if header in creator_words), None
    )
    mapping: dict[str, int] = {}
    mapping["title"] = title_index if title_index is not None else 0
    if len(headers) >= 2:
        mapping["author"] = author_index if author_index is not None else 1
    if len(headers) >= 2 and title_index is None and author_index == 0:
        # A single creator header that matched column 0: title falls back to
        # the first column too, which would make title and creator the same
        # column.
        mapping["title"] = 0
        mapping["author"] = 1
    return headers, mapping


def _mapping_from_options(
    options: Mapping[str, Any] | None, width: int, requires_creator: bool
) -> dict[str, int] | None:
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
    if "author" not in mapping and requires_creator and width >= 2:
        # A domain that expects a creator column and a client that only chose
        # a title one: the auto-detected creator (or the second column) keeps
        # its place rather than silently vanishing.
        pass
    return mapping or None


def _chosen_domain(options: Mapping[str, Any] | None) -> str:
    """The library this list is for, from the `targets` the screen sent.

    The choice is required — a connector serving five domains cannot guess
    which library a row belongs in, and guessing would put rows in the wrong
    one confidently. One value names one domain; the service's target filter
    enforces the same rule above this reader.
    """
    from book_tracker.domain.registry import DOMAINS

    raw = (options or {}).get("targets")
    if not isinstance(raw, str) or not raw.strip():
        raise ListCSVError(
            "invalid_import_target",
            "The list did not say which library it is for",
        )
    choices = raw.split()
    if len(choices) != 1:
        raise ListCSVError(
            "invalid_import_target",
            "A list is for exactly one library; a row cannot land in several",
            {"targets": choices},
        )
    item_type = choices[0]
    if item_type not in DOMAINS or DOMAINS[item_type].list_columns is None:
        raise ListCSVError(
            "invalid_import_target",
            f"No list importer serves {item_type!r}",
            {"target": item_type},
        )
    return item_type


class ListImporter:
    name = "list"
    label = "Custom list"

    @property
    def item_types(self) -> tuple[str, ...]:
        """Every domain that declared its list vocabulary — read at access
        time, because the registry imports this module to register the
        connector and the domains are only all-registered after."""
        return listable_domains()

    input = ImportInputSpec(
        kind="upload",
        label="Your list (CSV or text)",
        field="file",
        accept=".csv,.txt,.tsv,text/csv,text/plain",
        # The two columns are a choice the reader makes, published to the
        # screen through the catalog so the mapping UI renders from a
        # declaration.
        fields=("title_column", "author_column"),
        # Written for a person who typed this file themselves: there is no
        # platform to re-export from, so every step is about the file they hold.
        guide=(
            "Save your list as CSV or plain text — one row per line, the title "
            "in one column and the creator in another. Semicolons and tabs work too.",
            "Choose the library this list belongs to, then drop it below. Akasha "
            "reads the title and creator columns by their headers, or the first "
            "two columns when there are no headers.",
            "Nothing is added until you look at it: Akasha searches for each row "
            "in the background, proposes the matches it found, and you confirm "
            "or discard each one before the import lands in Triage.",
            "The other columns are kept exactly as you typed them, visible on "
            "each row, but are not read as data.",
        ),
        empty_state="Drop your list here, or choose a file.",
    )
    identity_kinds: frozenset[str] = frozenset()
    error_codes = frozenset(
        {"invalid_csv", "missing_columns", "column_not_mapped", "invalid_import_target"}
    )
    #: The search-then-confirm opt-in (Sprint 083 D3): preview stages this
    #: connector's batches in `matching` with one search job enqueued, and
    #: commit waits until the job drains. Reached by declaration, never by a
    #: shared-layer branch on the connector's name.
    search_job: Literal["search_import_rows"] = "search_import_rows"

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.data is None:
            raise ListCSVError("invalid_csv", "A list file is required")
        from book_tracker.domain.registry import DOMAINS

        item_type = _chosen_domain(source.options)
        columns = DOMAINS[item_type].list_columns
        assert columns is not None
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
        if width < 2 and columns.requires_creator:
            raise ListCSVError(
                "missing_columns",
                "The file needs at least two columns",
                {"columns": width},
            )
        if width < 1:
            raise ListCSVError(
                "missing_columns",
                "The file needs at least a title column",
                {"columns": width},
            )
        explicit = _mapping_from_options(source.options, width, columns.requires_creator)
        if explicit is not None:
            mapping = explicit
        else:
            _, mapping = sniff_mapping(
                headers,
                title_words=columns.title_headers,
                creator_words=columns.creator_headers,
            )

        records: list[NormalizedImportRecord] = []
        source_row = 1  # the header, if any
        for row in rows[1:]:
            source_row += 1
            records.append(self._record(row, mapping, headers, source_row, item_type, columns))
        if not records:
            raise ListCSVError("invalid_csv", "The file holds a header and no rows")

        fingerprint = hashlib.sha256(source.data).hexdigest()
        # The domain choice is part of the import's identity (Sprint 084): one
        # list, one library per batch — the same file for two domains is two
        # imports, never a stale replay (DEC-106's rule applied to the target).
        fingerprint = f"{fingerprint}#{item_type}"
        if explicit is not None:
            # The mapping is part of the import's identity: the same file read
            # with different columns is a different import, never a stale
            # replay (DEC-106's rule applied to interpretation, Sprint 083
            # D1.7).
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
                "item_type": item_type,
                "mapping": {key: mapping[key] for key in mapping},
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
        item_type: str,
        columns: Any,
    ) -> NormalizedImportRecord:
        def cell(index: int) -> str:
            return row[index].strip() if index < len(row) else ""

        title = cell(mapping["title"])
        author = cell(mapping["author"]) if "author" in mapping else ""
        errors: list[dict[str, Any]] = []
        if not title:
            errors.append({"field": "title", "code": "required", "value": ""})
        # A domain that declared creator words expects the column; one that
        # declared none treats an empty creator as an empty fact (Sprint 084:
        # a film list is often one column).
        if columns.requires_creator and not author:
            errors.append({"field": "author", "code": "missing"})
        # The original cells ride uninterpreted: the columns this connector
        # does not map are the owner's own words, and triage shows them
        # verbatim.
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
            item_type=item_type,
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
