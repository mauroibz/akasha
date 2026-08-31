"""An IMDb export, read into two libraries at once.

Measured against the owner's real exports on 2026-08-31 rather than against
documentation: two files, three rows between them, and nothing from either reproduced
here or in the fixtures. What the measurement gave is the *shape*, and the shape is the
reason this connector exists in the multi-domain form Sprint 052 built.

**An IMDb account exports in two different shapes, not one.** A ratings export begins
`Const, Your Rating, Date Rated, …`; a list export — and a Watchlist export is a list
export — begins `Position, Const, Created, Modified, Description, …` and moves the
rating columns to the end, where they are routinely blank. They share a core of columns
and mean the same things by them, so the header decides which shape is in hand and the
mappings below are written once.

**A television tracker tracks films too.** One export carries both, so this connector
declares `("movie", "series")` and every row names its own target through
`Title Type`. Four things a reasonable implementation would get wrong:

- **`Title Type` is IMDb's vocabulary and it changes.** The table below is a
  declaration whose default is *skip and count* — never a guess, and never an error. A
  title type IMDb has not published yet must appear as a number on the preview screen;
  somebody who exports their whole account should not meet forty red rows for podcasts
  they once rated (DEC-112).
- **`Runtime (mins)` means two different things.** It is the film's length for a film
  and one *episode's* length for a series, which is why it lands in `runtime` for one
  target and `episode_minutes` for the other. The routing is where that is written down.
- **The scale is already the scale.** IMDb's `Your Rating` is a 1–10 integer and maps
  1:1 with nothing lost. Letterboxd's half-stars doubled; doubling here would invent an
  opinion the owner never had.
- **Neither date column is a viewing date.** `Date Rated` is when a rating was written
  and `Created` is when a list row was added. IMDb does not record when you watched
  anything, and relabelling either as a viewing date invents one.

`IMDb Rating`, `Num Votes`, `Position`, `Modified`, `Description`, `Release Date` and
`URL` are deliberately not imported. The first two are the crowd's opinion rather than
the owner's, and `URL` is `Const` with decoration.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from typing import Any

from book_tracker.domain.identity import normalize_identifier
from book_tracker.domain.importers import (
    ImportEntry,
    ImportInputSpec,
    ImportItem,
    ImportMatcher,
    ImportReadContext,
    ImportReadError,
    ImportSkip,
    ImportSnapshot,
    ImportSource,
    NormalizedImportRecord,
)
from book_tracker.domain.matching import MatchDecision
from book_tracker.domains.movie import DOMAIN as MOVIE
from book_tracker.domains.series import DOMAIN as SERIES

#: Which library each of IMDb's title types belongs in. **The default is skip and
#: count**, which is what stops IMDb publishing a new type from being an outage.
TITLE_TYPES: dict[str, str] = {
    "movie": MOVIE.item_type,
    "tv movie": MOVIE.item_type,
    "video": MOVIE.item_type,
    "tv series": SERIES.item_type,
    "tv mini series": SERIES.item_type,
}

#: What a row with no `Title Type` at all is called on the preview screen. IMDb does
#: not write one, so this is what a hand-edited file looks like.
NO_TITLE_TYPE = "(no title type)"

#: The columns both shapes carry and this reader needs. A file without them is the
#: wrong file, which is one of the few things worth refusing whole.
CORE_COLUMNS = frozenset(
    {"Const", "Title", "Title Type", "Runtime (mins)", "Year", "Genres", "Directors"}
)
#: What tells the two shapes apart, checked on the header rather than by position.
RATINGS_COLUMNS = frozenset({"Your Rating", "Date Rated"})
LIST_COLUMNS = frozenset({"Position", "Created", "Modified", "Description"})

#: Where `date_added` comes from in each shape. A list export also carries
#: `Date Rated`, but `Created` is when the row arrived and is the one that means
#: "added to my library".
ARRIVAL_COLUMN = {"ratings": "Date Rated", "list": "Created"}

#: The reader's own ceilings. The upload route caps the request body but never
#: consults `ImportInputSpec.max_bytes` for `kind="upload"`, so advertising a limit
#: the server does not keep would be worse than declaring none (DEC-093).
MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 50_000

# Ceilings that exist because the *database* has them: `ck_entries_score` allows 1-10,
# and `items.title` is bounded. Nothing between this reader and the commit re-checks.
_MAX_SCORE = 10
_MIN_SCORE = 1
_MAX_TITLE = 500

_IMDB_ID = re.compile(r"tt[0-9]{7,10}")
_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})$")
_YEAR = re.compile(r"[0-9]{4}$")


class ImdbError(ImportReadError):
    """Every way an IMDb export can be unreadable, with the way out of each.

    The vocabulary is closed and declared on `ImdbImporter.error_codes`. `action` is
    the point: "the file is not an IMDb export" tells a reader nothing they can do,
    while naming the two pages the exports come from does (DEC-080).
    """


@dataclass
class ImdbRow:
    """One export row after IMDb's vocabulary has stopped leaking upward."""

    row_number: int
    item_type: str
    title: str
    #: What the export itself called this row, kept verbatim for the preview.
    title_type: str = ""
    original_title: str | None = None
    year: int | None = None
    imdb_id: str | None = None
    score: int | None = None
    date_added: str | None = None
    runtime: int | None = None
    genres: list[str] = field(default_factory=list)
    creators: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def note(self, column: str, code: str, value: str = "") -> None:
        row = {"field": column, "code": code, "value": value[:50]}
        if row not in self.errors:
            self.errors.append(row)

    @property
    def suggested_status(self) -> str:
        """A scored row was watched; an unscored one is still ahead of you.

        Each target's own word, because "watched" is a film's and "completed" is a
        series'. Persistence stays `unsorted` until Triage, as for every connector.
        """
        watched = {MOVIE.item_type: "watched", SERIES.item_type: "completed"}
        planned = {MOVIE.item_type: "watchlist", SERIES.item_type: "plan_to_watch"}
        table = watched if self.score is not None else planned
        return table[self.item_type]

    @property
    def metadata(self) -> dict[str, Any]:
        """This row's fields, under the names its own target domain declares.

        The `Runtime (mins)` divergence lives here: one column, two meanings, decided
        by which library the row is going to.
        """
        values: dict[str, Any] = {}
        if self.creators:
            values["creators"] = self.creators
        if self.genres:
            values["genres"] = self.genres
        if self.original_title:
            values["original_title"] = self.original_title
        if self.runtime is not None:
            key = "runtime" if self.item_type == MOVIE.item_type else "episode_minutes"
            values[key] = self.runtime
        return values


@dataclass
class ImdbExport:
    """What one file yielded: rows to import, and a tally of what it did not."""

    shape: str
    rows: list[ImdbRow]
    skipped: list[ImportSkip]


def _shape(columns: frozenset[str]) -> str:
    """Which export this is, decided by its header and never by position."""
    if not columns >= CORE_COLUMNS:
        raise ImdbError(
            "unknown_export_shape",
            f"Missing columns {sorted(CORE_COLUMNS - columns)}",
            {"missing": sorted(CORE_COLUMNS - columns)},
            user_message="That file is not an IMDb export.",
            action=(
                "Export again from IMDb — Your Ratings → Export for ratings, or a list's "
                "own ⋯ → Export for a list or your Watchlist — and upload the .csv "
                "unchanged."
            ),
        )
    if columns >= LIST_COLUMNS:
        return "list"
    if columns >= RATINGS_COLUMNS:
        return "ratings"
    raise ImdbError(
        "unknown_export_shape",
        "The header matches neither the ratings nor the list export",
        user_message="That IMDb file is not a shape Akasha knows how to read.",
        action="Upload a ratings export or a list export, exactly as IMDb downloaded it.",
    )


def _text(row: dict[str, str], column: str) -> str:
    return " ".join((row.get(column) or "").split())


def _int(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def _split(value: str) -> list[str]:
    """IMDb writes multi-valued columns as one comma-separated cell."""
    return [part for part in (piece.strip() for piece in value.split(",")) if part]


def _date(value: str) -> str | None:
    """An ISO date IMDb actually wrote, or nothing.

    Rejecting a half-known date like `2021-05-00` is the point: stored verbatim in a
    text column with no CHECK, it reads as a date for ever after (DEC-093).
    """
    match = _ISO_DATE.match(value)
    if match is None:
        return None
    year, month, day = (int(part) for part in match.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1800 <= year <= 2999):
        return None
    return value


def _score(row: ImdbRow, value: str) -> None:
    """`Your Rating` is IMDb's 1-10 integer, mapped 1:1. Blank is unscored.

    Out of range is a row error rather than a stored value: `ck_entries_score` would
    otherwise pass preview and raise an `IntegrityError` half way through the commit.
    """
    if not value:
        return
    number = _int(value)
    if number is None or not (_MIN_SCORE <= number <= _MAX_SCORE):
        row.note("Your Rating", "out_of_range", value)
        return
    row.score = number


def parse_imdb(data: bytes) -> ImdbExport:
    """One export file, normalized. Row problems stay on their row."""
    if len(data) > MAX_BYTES:
        raise ImdbError(
            "export_too_large",
            f"The export is larger than the {MAX_BYTES // (1024 * 1024)} MiB Akasha reads",
            user_message="That export is larger than Akasha will read.",
            action="Export a single list rather than your whole account, and upload that.",
        )
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ImdbError(
            "unreadable_export",
            f"The export is not UTF-8: {error}",
            user_message="That file is not readable as text.",
            action="Download the export again from IMDb and upload it without editing it.",
        ) from error

    reader = csv.DictReader(io.StringIO(text))
    columns = frozenset(reader.fieldnames or ())
    shape = _shape(columns)
    arrival = ARRIVAL_COLUMN[shape]

    rows: list[ImdbRow] = []
    skipped: dict[str, int] = {}
    seen: dict[str, int] = {}
    for source_row in reader:
        if len(rows) + sum(skipped.values()) >= MAX_ROWS:
            raise ImdbError(
                "export_too_large",
                f"The export holds more than the {MAX_ROWS} rows Akasha reads",
                user_message="That export holds more rows than Akasha will read.",
                action="Export a single list rather than your whole account, and upload that.",
            )
        # Three different things, kept apart on purpose. A row IMDb wrote about a kind
        # no library here holds is healthy and gets counted; a row that is structurally
        # short is *damaged*, and counting it as "not a kind this tracks" would hide
        # file damage inside a number nobody reads twice (DEC-112).
        if source_row.get("Title Type") is None:
            rows.append(_malformed(source_row, len(rows) + 1))
            continue
        title_type = _text(source_row, "Title Type")
        target = TITLE_TYPES.get(title_type.casefold())
        if target is None:
            # Skip and count, in the source's own words. Never a guess, never an error.
            reason = title_type or NO_TITLE_TYPE
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        rows.append(_row(source_row, len(rows) + 1, target, title_type, arrival, seen))
    return ImdbExport(shape=shape, rows=rows, skipped=[ImportSkip(*row) for row in skipped.items()])


def _malformed(source: dict[str, str], number: int) -> ImdbRow:
    """A row too short to carry the columns the header promised.

    It becomes a **visible** row error rather than a count: something is wrong with the
    file, and the reader should see that rather than have it absorbed into the tally of
    kinds this application deliberately does not hold. It is routed to the first
    declared library only so that it has somewhere to be seen.
    """
    row = ImdbRow(
        row_number=number, item_type=MOVIE.item_type, title=f"IMDb row {number}", title_type=""
    )
    row.note("Title Type", "malformed_row", _text(source, "Const"))
    return row


def _row(
    source: dict[str, str],
    number: int,
    target: str,
    title_type: str,
    arrival: str,
    seen: dict[str, int],
) -> ImdbRow:
    row = ImdbRow(row_number=number, item_type=target, title="", title_type=title_type)

    title = _text(source, "Title")
    if not title:
        row.note("Title", "required")
    row.title = title[:_MAX_TITLE] or f"IMDb row {number}"

    original = _text(source, "Original Title")
    if original and original != title:
        row.original_title = original[:_MAX_TITLE]

    const = _text(source, "Const")
    if _IMDB_ID.fullmatch(const):
        if const in seen:
            # Collapsing the second row would discard its score under a success, which
            # is how a duplicate loses data in silence (DEC-093).
            row.note("Const", "duplicate_identifier", const)
        else:
            seen[const] = number
            row.imdb_id = const
    elif const:
        row.note("Const", "invalid_identifier", const)
    else:
        row.note("Const", "required")

    year = _text(source, "Year")
    if year:
        if _YEAR.fullmatch(year):
            row.year = int(year)
        else:
            row.note("Year", "invalid_year", year)

    runtime = _text(source, "Runtime (mins)")
    if runtime:
        minutes = _int(runtime)
        # Both target domains declare a minimum of 1 on their minute field, and a 0
        # reaching the shared validator refuses the whole batch under a code no screen
        # has copy for — DEC-093's `series_episodes` of 0, one source over.
        if minutes is None or minutes < 1:
            row.note("Runtime (mins)", "out_of_range", runtime)
        else:
            row.runtime = minutes

    row.genres = _split(_text(source, "Genres"))
    row.creators = _split(_text(source, "Directors"))

    _score(row, _text(source, "Your Rating"))

    stamp = _text(source, arrival)
    if stamp:
        row.date_added = _date(stamp)
        if row.date_added is None:
            row.note(arrival, "invalid_date", stamp)
    return row


class ImdbImporter:
    name = "imdb"
    label = "IMDb"
    #: Films first, so a row naming no type of its own would be a film — though none
    #: does: every row routes through `Title Type` or is skipped.
    item_types: tuple[str, ...] = (MOVIE.item_type, SERIES.item_type)
    input = ImportInputSpec(
        kind="upload",
        label="IMDb export",
        field="file",
        accept=".csv,text/csv",
        guide=(
            "On imdb.com, open Your Ratings from your account menu, then ⋯ → Export. "
            "The download is a .csv.",
            "For your Watchlist or any list you made, open the list itself and use its "
            "own ⋯ → Export. Both shapes are read here.",
            "Upload the .csv exactly as it downloaded. IMDb emails you a link when the "
            "file is ready, which can take a few minutes.",
            "Films go to your Movies library and shows to your Series library, and you "
            "choose above which of the two this import brings in.",
            "Episodes, shorts, podcasts and video games are counted and skipped rather "
            "than imported — you will see how many on the preview screen.",
            "Your ratings come across exactly: IMDb's 1-10 is already Akasha's scale, "
            "so nothing is doubled and nothing is marked as a guess.",
            "This is a snapshot, not a sync. Importing again later adds whatever is new "
            "and changes nothing it already holds.",
            "Everything lands in Triage rather than in the library, so nothing appears "
            "until you have looked at it.",
        ),
        empty_state="Drop your IMDb .csv export here, or choose a file.",
        help_url="https://www.imdb.com/list/ratings",
    )
    identity_kinds = frozenset({"imdb"})
    error_codes = frozenset({"unknown_export_shape", "unreadable_export", "export_too_large"})

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.data is None:
            raise ImdbError(
                "unreadable_export",
                "An IMDb export file is required",
                user_message="No file was uploaded.",
                action="Choose the .csv IMDb exported for you and try again.",
            )
        export = parse_imdb(source.data)
        records = tuple(
            NormalizedImportRecord(
                row_number=row.row_number,
                item=ImportItem(
                    title=row.title,
                    subtitle=None,
                    year=row.year,
                    identifiers={"imdb": row.imdb_id} if row.imdb_id else {},
                    metadata=row.metadata,
                ),
                entry=ImportEntry(
                    score=row.score,
                    notes=None,
                    date_added=row.date_added,
                    values={},
                    # IMDb's scale is Akasha's scale, so there is nothing to hedge.
                    score_provisional=False,
                    suggested_status=row.suggested_status,
                ),
                shelves=(),
                errors=tuple(row.errors),
                # The source's own word for the row, kept so the preview can show what
                # the export called this. Nothing from it reaches an item's metadata.
                source_fields={"title_type": row.title_type},
                item_type=row.item_type,
            )
            for row in export.rows
        )
        return ImportSnapshot(
            fingerprint=hashlib.sha256(source.data).hexdigest(),
            filename=source.filename or "imdb.csv",
            source_descriptor={"filename": source.filename or "imdb.csv", "shape": export.shape},
            records=records,
            skipped=tuple(export.skipped),
        )

    def stage(self, snapshot: ImportSnapshot, _directory: Any, _data_dir: Any) -> ImportSnapshot:
        """Nothing to stage: a CSV carries no assets and commit never re-reads it."""
        return snapshot

    def match(self, record: NormalizedImportRecord, matcher: ImportMatcher) -> MatchDecision:
        """Exact on the IMDb id, scoped to **this row's** library.

        Both target domains resolve an `imdb` identity, so a re-import matches every row
        with no provider traffic, and a film already in the library from a Letterboxd
        import matches exactly once Wikidata enrichment has added its `imdb` claim.

        Title plus exact year is offered only as an ambiguity, never as a match, and
        scoped to the row's own type — a novel and the film of it share both, and so do
        a series and the film made from it (DEC-101).
        """
        identifiers = [
            normalize_identifier(kind, value)
            for kind, value in record.item.identifiers.items()
            if kind in self.identity_kinds
        ]
        return matcher.match(
            identifiers=identifiers,
            title=record.item.title,
            first_author="",
            year=record.item.year,
            item_type=record.item_type,
        )


IMPORTER = ImdbImporter()
