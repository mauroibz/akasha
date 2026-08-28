"""The Letterboxd data export, read into this domain's vocabulary.

Measured against the owner's real archive on 2026-08-27 rather than against
documentation: sixteen CSV members, 1,022 uncompressed bytes, two watched films that are
the same two rated films, and every other live table empty. Nothing from it is
reproduced here, in the fixtures or in the logs.

An export is **five tables about the same films**, not one table. A film can appear in
`watched.csv`, in `ratings.csv`, several times in `diary.csv` and once more in
`reviews.csv`, and all of those are one record keyed on the Letterboxd URI. Four things
about the source that a reasonable implementation would get wrong:

- **A repeated diary row is a second viewing, not a duplicate item.** Collapsing them
  loses the rewatch count, which is the only reason the file has more than one row.
- **The scale really is exact.** Letterboxd's 0.5–5 half-stars double onto Akasha's
  1–10 with nothing lost, so unlike a Goodreads three-star this is *not* provisional —
  a 3.5 was a 7 and marking it a guess would be a lie about the owner's own data.
- **`Date` is not a viewing date.** `watched.csv.Date` is when the row was created; only
  `Watched Date` in the diary says when the film was seen. Relabelling the first as the
  second invents a viewing.
- **The export identifies films by a short `boxd.it` URI**, while the movie domain's
  provider publishes Letterboxd's *slug*. Both are stored under the same `letterboxd`
  kind and the adapter resolves either (DEC-100), so nothing here follows a redirect:
  a preview that made one network request per row would be unusable.

Deleted and orphaned content, comments, likes, lists and the profile are ignored on
purpose. Silently restoring something the owner deleted is not import fidelity.
"""

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from book_tracker.domain.identity import normalize_identifier
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
from book_tracker.domains.movie import DOMAIN as MOVIE

DOMAIN = MOVIE

#: The five live tables this reader consumes, and the columns each must carry. Anything
#: else in the archive — `profile.csv`, `comments.csv`, `likes/`, `deleted/`,
#: `orphaned/` — is ignored rather than refused: an export legitimately contains them.
REQUIRED_COLUMNS: dict[str, frozenset[str]] = {
    "watched.csv": frozenset({"Date", "Name", "Year", "Letterboxd URI"}),
    "ratings.csv": frozenset({"Date", "Name", "Year", "Letterboxd URI", "Rating"}),
    "diary.csv": frozenset(
        {"Date", "Name", "Year", "Letterboxd URI", "Rating", "Rewatch", "Tags", "Watched Date"}
    ),
    "reviews.csv": frozenset(
        {
            "Date",
            "Name",
            "Year",
            "Letterboxd URI",
            "Rating",
            "Rewatch",
            "Review",
            "Tags",
            "Watched Date",
        }
    ),
    "watchlist.csv": frozenset({"Date", "Name", "Year", "Letterboxd URI"}),
}

#: The tables whose presence means the film was seen. `watchlist.csv` deliberately is
#: not one of them: a film on the list has not been watched, and that is the difference
#: the two statuses exist to record.
WATCHED_EVIDENCE = ("watched.csv", "ratings.csv", "diary.csv", "reviews.csv")

#: What the reader will expand the archive to before refusing it. The upload route caps
#: the *compressed* body and never consults this connector, so this is the only thing
#: between a crafted archive and memory. At the owner's measured ~64 bytes per row this
#: admits well over a hundred thousand rows, which is orders of magnitude past any real
#: film diary, while a zip bomb that lied about its size is refused before it is read.
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
_CHUNK = 64 * 1024

# Ceilings that exist because the *database* has them: `ck_entries_score` allows 1-10
# and `ck_entries_reread_count` refuses negatives, and nothing between this reader and
# the commit re-checks.
_MAX_SCORE = 10
_MAX_REWATCHES = 10_000
_MAX_TITLE = 500
_MAX_NOTES = 20_000
#: Letterboxd's own documented rating scale.
_MIN_RATING = 0.5
_MAX_RATING = 5.0

_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_SHORT_URI = re.compile(r"https://boxd\.it/[A-Za-z0-9]{2,12}/?")
_FILM_URI = re.compile(r"https://(?:www\.)?letterboxd\.com/film/[a-z0-9][a-z0-9-]*/?")
_TAG = re.compile(r"<[^>]+>")
_BLANK_LINES = re.compile(r"\n{3,}")
_TRUTHY = {"yes", "true", "1"}


class LetterboxdError(ImportReadError):
    """Every way a Letterboxd export can be unreadable, with the way out of each.

    The vocabulary is closed and declared on `LetterboxdImporter.error_codes`. The
    `action` is the point: "the archive is malformed" tells a reader nothing they can
    do, and "export again from Letterboxd" does (DEC-080).
    """

    ACTIONS = {
        "invalid_archive": (
            "This file is not a Letterboxd export.",
            "Download your export again from letterboxd.com/settings/data/ and upload "
            "the .zip exactly as it downloaded, without unpacking it.",
        ),
        "unsafe_archive": (
            "This archive contains entries Akasha will not open.",
            "Upload the .zip exactly as Letterboxd produced it. A rebuilt or edited "
            "archive is refused because Akasha cannot tell what was changed.",
        ),
        "missing_columns": (
            "This export is missing columns Akasha needs.",
            "Download a fresh export from letterboxd.com/settings/data/ — an older or "
            "hand-edited file can be missing the columns this reads.",
        ),
        "export_too_large": (
            "This export expands to more than Akasha will read.",
            "Check you uploaded a Letterboxd export and not something else; if your "
            "diary really is this large, say so and the limit can be raised.",
        ),
    }

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        user_message, action = self.ACTIONS.get(code, (None, None))
        super().__init__(code, message, details, user_message=user_message, action=action)


# --------------------------------------------------------------------------------------
# Reading the archive
# --------------------------------------------------------------------------------------


def _safe_member(name: str) -> bool:
    """Whether a member name is one this reader will even consider opening.

    A Letterboxd export is flat plus two known subdirectories, so anything absolute,
    anything containing `..`, anything with a hidden or empty segment and anything with
    a backslash is refused before it is read. Nothing here is extracted to disk, but a
    name that tries to escape is evidence about the archive rather than a nuisance.
    """
    if not name or name.startswith("/") or "\\" in name:
        return False
    parts = name.split("/")
    return all(part and part != ".." and not part.startswith(".") for part in parts)


def _members(data: bytes) -> dict[str, str]:
    """The five live tables, decoded, with the whole archive checked on the way in."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as error:
        raise LetterboxdError("invalid_archive", "The upload is not a readable ZIP") from error

    seen: set[str] = set()
    total = 0
    for info in archive.infolist():
        if info.flag_bits & 0x1:
            raise LetterboxdError(
                "unsafe_archive",
                "The archive contains an encrypted member",
                {"member": info.filename[:80]},
            )
        if not _safe_member(info.filename):
            raise LetterboxdError(
                "unsafe_archive",
                "The archive contains an unsafe member name",
                {"member": info.filename[:80]},
            )
        if info.filename in seen:
            # Two members with one name: whichever is read, the other was ignored, and
            # nothing here can say which one the owner meant.
            raise LetterboxdError(
                "unsafe_archive",
                "The archive names a member twice",
                {"member": info.filename[:80]},
            )
        seen.add(info.filename)
        if info.file_size > MAX_MEMBER_BYTES:
            raise LetterboxdError(
                "export_too_large",
                "A member of the archive is larger than Akasha will read",
                {"member": info.filename[:80]},
            )
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            # The declared sizes, before a byte is decompressed. Compressed size is not
            # a bound: deflate reaches about 1,000:1.
            raise LetterboxdError(
                "export_too_large", "The archive expands to more than Akasha will read"
            )

    tables: dict[str, str] = {}
    for name in REQUIRED_COLUMNS:
        if name not in seen:
            continue
        with archive.open(name) as member:
            body = bytearray()
            while chunk := member.read(_CHUNK):
                body.extend(chunk)
                if len(body) > MAX_MEMBER_BYTES:
                    raise LetterboxdError(
                        "export_too_large",
                        "A member of the archive is larger than declared",
                        {"member": name},
                    )
        try:
            tables[name] = body.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise LetterboxdError(
                "invalid_archive", "A member of the archive is not UTF-8", {"member": name}
            ) from error
    if not tables:
        raise LetterboxdError("invalid_archive", "The archive holds no Letterboxd tables")
    return tables


def _rows(name: str, text: str) -> list[dict[str, str]]:
    """One table's rows, with its columns checked before any of them are read."""
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        header = frozenset(reader.fieldnames or ())
        missing = REQUIRED_COLUMNS[name] - header
        if missing:
            raise LetterboxdError(
                "missing_columns",
                f"{name} is missing columns",
                {"member": name, "missing": sorted(missing)},
            )
        return [{key: (value or "") for key, value in row.items() if key} for row in reader]
    except csv.Error as error:
        raise LetterboxdError(
            "invalid_archive", f"{name} is not readable CSV", {"member": name}
        ) from error


# --------------------------------------------------------------------------------------
# Reading one value
# --------------------------------------------------------------------------------------


def _uri(value: str) -> str | None:
    """The film identity in a row, or `None` for anything this will not store.

    Strict about scheme and host on purpose: this value becomes an exact identifier that
    a later enrichment will resolve by following it, and an identity nobody can check is
    worse than no identity at all.
    """
    candidate = value.strip()
    if _SHORT_URI.fullmatch(candidate) or _FILM_URI.fullmatch(candidate):
        return candidate.rstrip("/") if _SHORT_URI.fullmatch(candidate) else candidate
    return None


def _date(value: str) -> str | None:
    """An ISO date, or `None`. Blank is absence; a malformed one is the caller's error."""
    candidate = value.strip()
    if not candidate or not _ISO_DATE.fullmatch(candidate):
        return None
    try:
        date.fromisoformat(candidate)
    except ValueError:
        return None
    return candidate


def _year(value: str) -> int | None:
    candidate = value.strip()
    if not candidate.isdigit():
        return None
    year = int(candidate)
    return year if 1000 <= year <= 2999 else None


def _rating(value: str) -> tuple[int | None, str | None]:
    """A Letterboxd half-star as an Akasha score, and the reason it was refused.

    `0.5` to `5` doubles exactly onto `1` to `10`. Blank is unrated, which is a fact and
    not an error. Zero is neither: Letterboxd has no zero-star rating, so a `0` in this
    column is a file that was edited or generated by something else, and passing it
    through would violate `ck_entries_score` half way through the commit.
    """
    candidate = value.strip()
    if not candidate:
        return None, None
    try:
        stars = float(candidate)
    except ValueError:
        return None, "invalid_rating"
    if not _MIN_RATING <= stars <= _MAX_RATING:
        return None, "rating_out_of_range"
    score = int(round(stars * 2))
    if not 1 <= score <= _MAX_SCORE:
        return None, "rating_out_of_range"
    return score, None


def _plain(value: str) -> str | None:
    """A review with the markup taken out.

    Letterboxd's own import documentation says review text may be HTML, and no renderer
    here interprets markup — so a tag left in would be shown to the reader verbatim.
    Parsed as text rather than trusted, and never stored as source markup.
    """
    raw = value.strip()
    if not raw:
        return None
    stripped = _TAG.sub("", raw).replace("&nbsp;", " ").replace("&amp;", "&")
    stripped = stripped.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    text = _BLANK_LINES.sub("\n\n", stripped).strip()
    return text[:_MAX_NOTES] or None


def _tags(value: str) -> list[str]:
    """Live tags as shelf slugs, skipping the ones there was nothing in."""
    found: list[str] = []
    for part in value.split(","):
        if not part.strip():
            continue
        try:
            slug = shelf_slug(part)
        except ValueError:
            # A tag of pure punctuation slugs to nothing and `shelf_slug` says so by
            # raising. Skipped rather than reported: there was nothing in it to lose.
            continue
        if slug and slug not in found:
            found.append(slug)
    return found


# --------------------------------------------------------------------------------------
# Aggregating five tables into one record per film
# --------------------------------------------------------------------------------------


class _Film:
    """Everything the five tables say about one Letterboxd URI."""

    def __init__(self, uri: str, row_number: int) -> None:
        self.uri = uri
        self.row_number = row_number
        self.title = ""
        self.year: int | None = None
        self.dates: list[str] = []
        self.watched_dates: list[str] = []
        self.current_score: tuple[str, int] | None = None
        self.event_scores: list[tuple[str, int]] = []
        self.reviews: list[tuple[str, str]] = []
        self.rewatches = 0
        self.shelves: list[str] = []
        self.watched = False
        self.listed = False
        self.errors: list[dict[str, str]] = []
        self.sources: list[str] = []

    def note(self, field: str, code: str, value: str = "") -> None:
        row = {"field": field, "code": code, "value": value[:50]}
        if row not in self.errors:
            self.errors.append(row)

    def name(self, title: str, year: int | None, member: str) -> None:
        """The film's own title and year, with a disagreement made visible.

        Two tables naming one URI differently is not something to average or to take the
        first of: it means the export is inconsistent about which film this is, and the
        reader should see that rather than have one silently chosen.
        """
        cleaned = " ".join(title.split())
        if cleaned and not self.title:
            self.title = cleaned[:_MAX_TITLE]
        elif cleaned and cleaned[:_MAX_TITLE] != self.title:
            self.note("Name", "conflicting_title", member)
        if year is not None and self.year is None:
            self.year = year
        elif year is not None and year != self.year:
            self.note("Year", "conflicting_year", member)

    @property
    def score(self) -> int | None:
        """The current rating if there is one, otherwise the latest one recorded.

        `ratings.csv` is the owner's rating *now*; a diary rating is what they gave it
        that night. The first wins when both exist, which is the difference between "how
        I feel about this film" and "how I felt walking out".
        """
        if self.current_score is not None:
            return self.current_score[1]
        if self.event_scores:
            return max(self.event_scores, key=lambda row: row[0])[1]
        return None

    @property
    def notes(self) -> str | None:
        return max(self.reviews, key=lambda row: row[0])[1] if self.reviews else None

    @property
    def date_added(self) -> str | None:
        return min(self.dates) if self.dates else None

    @property
    def date_finished(self) -> str | None:
        """Only a `Watched Date` may become this. See the module docstring."""
        return max(self.watched_dates) if self.watched_dates else None

    @property
    def suggested_status(self) -> str:
        return "watched" if self.watched else "watchlist"


def parse_letterboxd(data: bytes) -> list[_Film]:
    """One record per film, from however many tables mention it."""
    tables = _members(data)
    films: dict[str, _Film] = {}

    def film_for(row: dict[str, str], member: str, index: int) -> _Film | None:
        uri = _uri(row.get("Letterboxd URI", ""))
        if uri is None:
            # Without an identity there is nothing to key the record on and nothing a
            # later enrichment could resolve, so the row is dropped with a reason rather
            # than stored under a made-up key.
            broken = films.setdefault(f"__unusable__{member}:{index}", _Film("", len(films) + 1))
            broken.name(row.get("Name", ""), _year(row.get("Year", "")), member)
            broken.note("Letterboxd URI", "unusable_uri", row.get("Letterboxd URI", ""))
            broken.sources.append(member)
            return None
        film = films.get(uri)
        if film is None:
            film = _Film(uri, len(films) + 1)
            films[uri] = film
        film.name(row.get("Name", ""), _year(row.get("Year", "")), member)
        if member not in film.sources:
            film.sources.append(member)
        when = _date(row.get("Date", ""))
        if when is not None:
            film.dates.append(when)
        elif row.get("Date", "").strip():
            film.note("Date", "invalid_date", row.get("Date", ""))
        if member in WATCHED_EVIDENCE:
            film.watched = True
        else:
            film.listed = True
        return film

    for member in ("watched.csv", "watchlist.csv"):
        for index, row in enumerate(
            _rows(member, tables.get(member, "")) if member in tables else []
        ):
            film_for(row, member, index)

    for index, row in enumerate(
        _rows("ratings.csv", tables["ratings.csv"]) if "ratings.csv" in tables else []
    ):
        film = film_for(row, "ratings.csv", index)
        if film is None:
            continue
        score, problem = _rating(row.get("Rating", ""))
        if problem is not None:
            film.note("Rating", problem, row.get("Rating", ""))
        elif score is not None:
            # Two current ratings for one film should not happen; if they do, the later
            # row is the owner's later opinion.
            stamp = _date(row.get("Date", "")) or ""
            if film.current_score is None or stamp >= film.current_score[0]:
                film.current_score = (stamp, score)

    for member in ("diary.csv", "reviews.csv"):
        for index, row in enumerate(
            _rows(member, tables.get(member, "")) if member in tables else []
        ):
            film = film_for(row, member, index)
            if film is None:
                continue
            stamp = _date(row.get("Watched Date", "")) or _date(row.get("Date", "")) or ""
            watched_on = _date(row.get("Watched Date", ""))
            if watched_on is not None:
                film.watched_dates.append(watched_on)
            elif row.get("Watched Date", "").strip():
                film.note("Watched Date", "invalid_date", row.get("Watched Date", ""))
            score, problem = _rating(row.get("Rating", ""))
            if problem is not None:
                film.note("Rating", problem, row.get("Rating", ""))
            elif score is not None:
                film.event_scores.append((stamp, score))
            if row.get("Rewatch", "").strip().casefold() in _TRUTHY:
                film.rewatches = min(film.rewatches + 1, _MAX_REWATCHES)
            for slug in _tags(row.get("Tags", "")):
                if slug not in film.shelves:
                    film.shelves.append(slug)
            review = _plain(row.get("Review", ""))
            if review is not None:
                film.reviews.append((stamp, review))

    ordered = sorted(films.values(), key=lambda row: row.row_number)
    for position, film in enumerate(ordered, 1):
        film.row_number = position
    return ordered


class LetterboxdImporter:
    name = "letterboxd"
    label = "Letterboxd"
    item_type = DOMAIN.item_type
    input = ImportInputSpec(
        kind="upload",
        label="Letterboxd export",
        field="file",
        accept=".zip,application/zip",
        guide=(
            "On letterboxd.com, open Settings → Data and choose Export your data. "
            "The download is a .zip.",
            "Upload the .zip exactly as it downloaded, without unpacking it.",
            "Your watched films, ratings, diary entries, reviews and watchlist are "
            "read. Deleted entries, comments, likes and lists are deliberately not.",
            "Ratings come across exactly: Letterboxd's half-stars double onto Akasha's "
            "1–10, so 3½ stars is a 7 and nothing is marked as a guess.",
            "Titles and years come from the export; the rest of each film's details "
            "are looked up afterwards and fill only what is still empty.",
            "This is a snapshot, not a sync. Importing again later adds whatever is "
            "new and changes nothing it already holds.",
            "Everything lands in Triage rather than in the library, so nothing appears "
            "until you have looked at it.",
        ),
        empty_state="Drop your Letterboxd export .zip here, or choose a file.",
        help_url="https://letterboxd.com/settings/data/",
    )
    identity_kinds = frozenset({"letterboxd"})
    error_codes = frozenset(
        {"invalid_archive", "unsafe_archive", "missing_columns", "export_too_large"}
    )

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.data is None:
            raise LetterboxdError("invalid_archive", "A Letterboxd export file is required")
        records = []
        for film in parse_letterboxd(source.data):
            title = film.title or (f"Letterboxd row {film.row_number}")
            if not film.title:
                film.note("Name", "required")
            records.append(
                NormalizedImportRecord(
                    row_number=film.row_number,
                    item=ImportItem(
                        title=title,
                        subtitle=None,
                        year=film.year,
                        identifiers={"letterboxd": film.uri} if film.uri else {},
                        # Everything a person wants to look at — director, runtime,
                        # genres — is the provider's to supply. The export has none of
                        # it, and inventing a field here would block the fill.
                        metadata={},
                    ),
                    entry=ImportEntry(
                        score=film.score,
                        notes=film.notes,
                        date_added=film.date_added,
                        values={
                            "date_finished": film.date_finished,
                            "reread_count": film.rewatches,
                        },
                        # Nothing to mark: a half-star doubles exactly. See `_rating`.
                        score_provisional=False,
                        suggested_status=film.suggested_status,
                    ),
                    shelves=tuple(film.shelves),
                    errors=tuple(film.errors),
                    # Which tables this film came from, and nothing out of them. The
                    # export names its owner in `profile.csv`, which is never read.
                    source_fields={"tables": ",".join(film.sources)},
                )
            )
        return ImportSnapshot(
            fingerprint=hashlib.sha256(source.data).hexdigest(),
            filename=source.filename or "letterboxd.zip",
            source_descriptor={"filename": source.filename or "letterboxd.zip"},
            records=tuple(records),
            archive_name="source.zip",
            archive_data=source.data,
        )

    def stage(self, snapshot: ImportSnapshot, directory: Path, _data_dir: Path) -> ImportSnapshot:
        if snapshot.archive_name and snapshot.archive_data is not None:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / snapshot.archive_name).write_bytes(snapshot.archive_data)
        return replace(snapshot, archive_data=None)

    def match(self, record: NormalizedImportRecord, matcher: ImportMatcher) -> MatchDecision:
        """Exact on the Letterboxd URI; title and year only as something to be offered.

        The export names no director, so there is no strong near match to make. What
        there is instead is the case this connector exists inside: the same film may
        already be in the library from a Wikidata search, carrying the *slug* rather than
        this export's short URI, and those two are not equal until something resolves
        one into the other. Title plus exact year, scoped to this domain, is offered as
        an ambiguity so the owner can say "that one" — and never merged automatically,
        because two films can share a title and a year and remakes share the title alone.
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
            item_type=self.item_type,
        )


IMPORTER = LetterboxdImporter()
