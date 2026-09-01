"""The Trakt data archive, read into two libraries at once.

Measured against the owner's real archive on 2026-08-31 rather than against
documentation: a ZIP of 43 verbatim API-response members, 26 of them the two
bytes `[]`, one watched film, two watched shows, 115 history events — and
nothing from it reproduced here, in the fixtures or in the logs. The archive
names its owner in `user-settings.json` and `user-profile.json`, which carry
an **email address**; this reader never opens either, and no fixture is cut
from them.

A Trakt export is **six tables about the same films and shows**, keyed on the
`ids` block every object carries. Four things a reasonable implementation would
get wrong:

- **`watched-history.json` is the only member with episode detail, and progress
  means episodes, not plays.** A rewatch is a second event for the same
  episode; counting events would put progress above the total for no reason a
  person would recognise. Distinct `(show, season, number)` with
  `action == "watch"`, excluding season 0 — specials are not part of the run.
- **`plays` is a fallback, and a row that used it should say so.** In the
  owner's archive the two agree exactly (76 and 38), which is precisely why the
  fallback needs its own synthetic fixture: the real archive will not exercise
  it. `plays` counts rewatches, so it is an upper bound rather than the same
  number, and the row carries the fact in its notes where the library shows it.
- **The reader cannot know whether a series has ended.** That is a provider
  fact, not an export fact, so the status suggestion stops at what the archive
  proves: below `aired_episodes` suggests `watching`, equal or above suggests
  `completed`. Triage is where a person decides.
- **Season and episode ratings change no score.** A series holds one score —
  DEC-077's line — so `ratings-seasons.json` and `ratings-episodes.json` are
  counted in the report and never read into a record.

`rated_at` is available but the score is the score; the earliest of
`last_watched_at` / `rated_at` / `listed_at` becomes `date_added`; and the
`plex` sub-object inside every `ids` block is never read. Trakt's 1–10 integer
maps 1:1 with nothing lost, so no score is marked provisional.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
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

#: The six members this reader consumes. Everything else in the archive is
#: either counted below or ignored outright; a member that is absent is absent
#: — the owner's own archive has 26 empty members and no watchlist — and the
#: reader never requires one it does not need.
MEMBERS = (
    "watched-movies.json",
    "ratings-movies.json",
    "watched-shows.json",
    "ratings-shows.json",
    "watched-history.json",
    "lists-watchlist.json",
)

#: Members whose rows are counted in the report rather than read, because this
#: application deliberately does not hold what they carry. The reason is the
#: source's own word, so the preview names the thing rather than a code
#: (DEC-112) — a series holds one score, which is DEC-077's line restated.
COUNTED_MEMBERS: dict[str, str] = {
    "ratings-seasons.json": "season rating",
    "ratings-episodes.json": "episode rating",
    "collection-movies.json": "collection entry",
    "collection-shows.json": "collection entry",
    "collection-episodes.json": "collection entry",
    "comments-movies.json": "comment",
    "comments-shows.json": "comment",
    "comments-seasons.json": "comment",
    "comments-episodes.json": "comment",
    "comments-lists.json": "comment",
    "notes-movies.json": "note",
    "notes-shows.json": "note",
    "notes-seasons.json": "note",
    "notes-episodes.json": "note",
    "notes-people.json": "note",
    "notes-activities.json": "note",
    "notes-collection_items.json": "note",
    "notes-ratings.json": "note",
    "likes-comments.json": "like",
    "likes-lists.json": "like",
    "network-followers.json": "follower",
    "network-followers-requests.json": "follower",
    "network-following.json": "followed",
    "network-friends.json": "friend",
    "hidden-calendar.json": "hidden item",
    "hidden-progress-watched.json": "hidden item",
    "hidden-progress-watched-reset.json": "hidden item",
    "hidden-progress-collected.json": "hidden item",
    "hidden-recommendations.json": "hidden item",
    "watched-playback.json": "playback progress",
}

#: Never opened, on any path. These two carry the owner's **email address**, and
#: a test asserts it: an archive whose copies are deliberately malformed imports
#: cleanly, which is only possible if nothing read them. `user-last-activities.json`
#: and `user-stats.json` are account telemetry rather than library data, and are
#: not read either.
NEVER_OPENED = (
    "user-settings.json",
    "user-profile.json",
    "user-last-activities.json",
    "user-stats.json",
)

#: What the reader will expand the archive to before refusing it. The upload
#: route caps the *compressed* body and never consults the connector, so this is
#: the only thing between a crafted archive and memory. The declared sizes are
#: checked before a byte is decompressed (deflate reaches about 1,000:1), and
#: each member is still read against its own bound in case it lied.
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
_CHUNK = 64 * 1024

#: Ceilings that exist because the *database* has them: `ck_entries_score` allows
#: 1–10 and `ck_entries_progress` refuses negatives, and nothing between this
#: reader and the commit re-checks. The episode total is deliberately *not*
#: bounded against progress — DEC-092's floor-and-no-ceiling — but the metadata
#: field itself declares a maximum, so the same number applies here.
_MAX_SCORE = 10
_MIN_SCORE = 1
_MAX_EPISODES = 100_000
_MAX_PROGRESS = 100_000
_MAX_TITLE = 500

_IMDB_ID = re.compile(r"tt[0-9]{7,10}")
_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")

#: The warning a `plays`-derived row carries, so it does not look identical to
#: one whose progress was counted from history. It rides the entry's notes
#: because a row *error* would block the commit of a healthy row (the pipeline
#: refuses every row with errors), and the shared screens — which this sprint
#: does not touch — already render notes.
_PLAYS_NOTE = (
    "Watched-episode count is Trakt's play count, which includes rewatches, "
    "because this archive carries no watch history for this show."
)


class TraktError(ImportReadError):
    """Every way a Trakt archive can be unreadable, with the way out of each.

    The vocabulary is closed and declared on `TraktImporter.error_codes`. The
    `action` is the point: "the archive is malformed" tells a reader nothing they
    can do, and "export again from Trakt" does (DEC-080).
    """

    ACTIONS = {
        "invalid_archive": (
            "This file is not a Trakt export.",
            "Export again from trakt.tv — your profile's Settings → Export Data "
            "(a VIP feature) — and upload the .zip exactly as it downloaded, "
            "without unpacking it.",
        ),
        "unsafe_archive": (
            "This archive contains entries Akasha will not open.",
            "Upload the .zip exactly as Trakt produced it. A rebuilt or edited "
            "archive is refused because Akasha cannot tell what was changed.",
        ),
        "export_too_large": (
            "This export expands to more than Akasha will read.",
            "Check you uploaded a Trakt export and not something else; if your "
            "history really is this large, say so and the limit can be raised.",
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

    A Trakt export is flat, so anything absolute, anything containing `..`,
    anything with a hidden or empty segment and anything with a backslash is
    refused before it is read. Nothing is extracted to disk; a name that tries
    to escape is evidence about the archive rather than a nuisance.
    """
    if not name or name.startswith("/") or "\\" in name:
        return False
    parts = name.split("/")
    return all(part and part != ".." and not part.startswith(".") for part in parts)


def _body(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    """One member's bytes, bounded while read in case it lied about its size."""
    with archive.open(info) as member:
        body = bytearray()
        while chunk := member.read(_CHUNK):
            body.extend(chunk)
            if len(body) > MAX_MEMBER_BYTES:
                raise TraktError(
                    "export_too_large",
                    "A member of the archive is larger than declared",
                    {"member": info.filename[:80]},
                )
    return bytes(body)


def _members(data: bytes) -> tuple[dict[str, list[Any]], list[ImportSkip]]:
    """The six work members, parsed, plus the tally of everything counted.

    The private members are never opened — not for parsing, not for counting:
    their existence is the only thing this reader ever learns about them, which
    is nothing.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as error:
        raise TraktError("invalid_archive", "The upload is not a readable ZIP") from error

    seen: set[str] = set()
    total = 0
    for info in archive.infolist():
        if info.flag_bits & 0x1:
            raise TraktError(
                "unsafe_archive",
                "The archive contains an encrypted member",
                {"member": info.filename[:80]},
            )
        if not _safe_member(info.filename):
            raise TraktError(
                "unsafe_archive",
                "The archive contains an unsafe member name",
                {"member": info.filename[:80]},
            )
        if info.filename in seen:
            # Two members with one name: whichever is read, the other was ignored.
            raise TraktError(
                "unsafe_archive", "The archive names a member twice", {"member": info.filename[:80]}
            )
        seen.add(info.filename)
        if info.file_size > MAX_MEMBER_BYTES:
            raise TraktError(
                "export_too_large",
                "A member of the archive is larger than Akasha will read",
                {"member": info.filename[:80]},
            )
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            # Declared sizes, before a byte is decompressed.
            raise TraktError(
                "export_too_large", "The archive expands to more than Akasha will read"
            )

    tables: dict[str, list[Any]] = {}
    skipped: dict[str, int] = {}
    for name in (*MEMBERS, *COUNTED_MEMBERS):
        if name not in seen:
            # Absent is absent. The owner's own archive has 26 empty members and
            # no watchlist, and requiring one this row does not need is how a
            # healthy import fails.
            continue
        info = archive.getinfo(name)
        try:
            text = _body(archive, info).decode("utf-8-sig")
            rows = json.loads(text)
        except UnicodeDecodeError as error:
            raise TraktError("invalid_archive", f"{name} is not UTF-8", {"member": name}) from error
        except json.JSONDecodeError as error:
            raise TraktError(
                "invalid_archive", f"{name} is not readable JSON", {"member": name}
            ) from error
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise TraktError(
                "invalid_archive", f"{name} does not hold a list of entries", {"member": name}
            )
        if name in COUNTED_MEMBERS:
            # Counted, never read: a series holds one score (DEC-077), and
            # collection, comments, notes, likes, the follower graph, hidden
            # items and playback progress are not this application's to hold.
            if rows:
                skipped[COUNTED_MEMBERS[name]] = skipped.get(COUNTED_MEMBERS[name], 0) + len(rows)
        else:
            tables[name] = rows
    if not tables:
        raise TraktError("invalid_archive", "The archive holds no Trakt tables")
    return tables, [ImportSkip(reason, count) for reason, count in skipped.items()]


# --------------------------------------------------------------------------------------
# Reading one value
# --------------------------------------------------------------------------------------


def _imdb(row: dict[str, Any], key: str) -> str | None:
    """The `imdb` id from an object's `ids` block — the identity both target
    domains resolve, and the only one this connector declares.

    Everything else in the block (`trakt`, `slug`, `tmdb`, `tvdb`, and the
    `plex` sub-object) is deliberately not read: an identifier nobody can
    resolve is worse than none, and `identity_kinds` is the promise that the
    ones emitted are authoritative.
    """
    value = str(((row.get(key) or {}).get("ids") or {}).get("imdb") or "").strip()
    return value if _IMDB_ID.fullmatch(value) else None


def _title(row: dict[str, Any], key: str) -> str:
    return " ".join(str((row.get(key) or {}).get("title") or "").split())[:_MAX_TITLE]


def _year(row: dict[str, Any], key: str) -> int | None:
    year = (row.get(key) or {}).get("year")
    return int(year) if isinstance(year, int) and 1000 <= year <= 2999 else None


def _aired(row: dict[str, Any], key: str) -> int | None:
    """The episode total at export time, bounded by the metadata field's own
    declared maximum rather than by anything about progress (DEC-092)."""
    aired = (row.get(key) or {}).get("aired_episodes")
    if isinstance(aired, bool) or not isinstance(aired, int):
        return None
    return aired if 1 <= aired <= _MAX_EPISODES else None


def _timestamp(value: Any) -> str | None:
    """An ISO date from Trakt's `…Z` timestamps, or nothing.

    Stored as the bare `YYYY-MM-DD` the entry columns hold. A malformed
    timestamp is absence, not an error: Trakt wrote it, this reader did not.
    """
    if not isinstance(value, str):
        return None
    match = _ISO_DATE.match(value)
    if match is None:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _rating(row: dict[str, Any], errors: list[dict[str, Any]]) -> int | None:
    """Trakt's 1–10 integer, mapped 1:1. Blank or absent is unscored.

    Out of range is a row error rather than a stored value: `ck_entries_score`
    would otherwise pass preview and raise an `IntegrityError` half way through
    the commit.
    """
    rating = row.get("rating")
    if rating is None or rating == "":
        return None
    if isinstance(rating, bool) or not isinstance(rating, int):
        errors.append({"field": "rating", "code": "rating_not_a_number", "value": str(rating)[:50]})
        return None
    if not _MIN_SCORE <= rating <= _MAX_SCORE:
        errors.append({"field": "rating", "code": "rating_out_of_range", "value": str(rating)[:50]})
        return None
    return int(rating)


# --------------------------------------------------------------------------------------
# Aggregating six members into one record per title
# --------------------------------------------------------------------------------------


@dataclass
class _Record:
    """Everything the archive says about one title, in the row's own library."""

    row_number: int
    item_type: str
    title: str
    year: int | None = None
    imdb_id: str | None = None
    aired_episodes: int | None = None
    score: int | None = None
    dates: list[str] = field(default_factory=list)
    watched_dates: list[str] = field(default_factory=list)
    episode_dates: list[str] = field(default_factory=list)
    episodes: set[tuple[int, int]] = field(default_factory=set)
    plays: int | None = None
    watched: bool = False
    listed: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)

    def note(self, field_name: str, code: str, value: Any = "") -> None:
        row = {"field": field_name, "code": code, "value": str(value)[:50]}
        if row not in self.errors:
            self.errors.append(row)

    @property
    def progress(self) -> int:
        """Distinct episodes watched — never events, never season 0."""
        return len(self.episodes)

    @property
    def date_added(self) -> str | None:
        return min(self.dates) if self.dates else None

    @property
    def suggested_status(self) -> str:
        if self.item_type == MOVIE.item_type:
            return "watched" if self.watched else "watchlist"
        if self.listed and not self.watched:
            return "plan_to_watch"
        # Equal-or-above suggests completed; below suggests watching. Whether the
        # show has ended is a provider fact this archive cannot know, so the
        # suggestion stops here and Triage is where a person decides. The count
        # is the row's own progress — which for a `plays`-derived row is `plays`,
        # an upper bound that still answers "did they see it all".
        count = self.progress or (self.plays if self.plays is not None else 0)
        if self.aired_episodes is not None:
            return "completed" if count >= self.aired_episodes else "watching"
        return "completed" if self.watched else "plan_to_watch"

    @property
    def date_finished(self) -> str | None:
        """A movie finishes when it was last watched; a series only when every
        aired episode at export time has been watched."""
        if self.item_type == MOVIE.item_type:
            return max(self.watched_dates) if self.watched_dates else None
        if self.aired_episodes is not None and 0 < self.progress >= self.aired_episodes:
            return max(self.episode_dates) if self.episode_dates else None
        return None


def parse_trakt(data: bytes) -> tuple[list[_Record], list[ImportSkip]]:
    """One record per title, from however many members mention it."""
    tables, skipped = _members(data)
    records: dict[str, _Record] = {}

    def _count(tally: list[ImportSkip], reason: str) -> None:
        """A row the source never gave an identity: counted, never a record —
        there is nothing to key one on and nothing a later enrichment could
        resolve (DEC-112)."""
        for index, skip in enumerate(tally):
            if skip.reason == reason:
                tally[index] = ImportSkip(reason, skip.count + 1)
                return
        tally.append(ImportSkip(reason, 1))

    def record_for(
        row: dict[str, Any],
        key: str,
        item_type: str,
        errors_owner: list[dict[str, Any]] | None = None,
    ) -> _Record | None:
        imdb_id = _imdb(row, key)
        if imdb_id is None:
            # Without an identity there is nothing to key the record on and
            # nothing a later enrichment could resolve. Counted rather than a
            # row error: the source did not describe a thing this tracks.
            return None
        found = records.get(imdb_id)
        if found is None:
            found = _Record(
                row_number=len(records) + 1,
                item_type=item_type,
                title=_title(row, key) or f"Trakt row {len(records) + 1}",
                year=_year(row, key),
                imdb_id=imdb_id,
            )
            records[imdb_id] = found
            if errors_owner:
                found.errors.extend(errors_owner)
        return found

    # Watched and rated films.
    for row in tables.get("watched-movies.json", ()):
        film = record_for(row, "movie", MOVIE.item_type)
        if film is None:
            _count(skipped, "unidentifiable row")
            continue
        film.watched = True
        film.plays = row.get("plays") if isinstance(row.get("plays"), int) else None
        when = _timestamp(row.get("last_watched_at"))
        if when:
            film.dates.append(when)
            film.watched_dates.append(when)
    for row in tables.get("ratings-movies.json", ()):
        film = record_for(row, "movie", MOVIE.item_type)
        if film is None:
            _count(skipped, "unidentifiable row")
            continue
        film.watched = True
        score = _rating(row, film.errors)
        if score is not None:
            film.score = score
        when = _timestamp(row.get("rated_at"))
        if when:
            film.dates.append(when)

    # Watched and rated shows.
    for row in tables.get("watched-shows.json", ()):
        show = record_for(row, "show", SERIES.item_type)
        if show is None:
            _count(skipped, "unidentifiable row")
            continue
        show.watched = True
        show.aired_episodes = _aired(row, "show")
        plays = row.get("plays")
        show.plays = plays if isinstance(plays, int) and 0 <= plays <= _MAX_PROGRESS else None
        when = _timestamp(row.get("last_watched_at"))
        if when:
            show.dates.append(when)
    for row in tables.get("ratings-shows.json", ()):
        show = record_for(row, "show", SERIES.item_type)
        if show is None:
            _count(skipped, "unidentifiable row")
            continue
        show.watched = True
        show.aired_episodes = show.aired_episodes or _aired(row, "show")
        score = _rating(row, show.errors)
        if score is not None:
            show.score = score
        when = _timestamp(row.get("rated_at"))
        if when:
            show.dates.append(when)

    # The watchlist: a thing ahead of you, not behind you. Its populated shape
    # is declared from Trakt's published API and not measured — the owner's
    # archive holds only `[]` — so the reader treats it as optional throughout.
    for row in tables.get("lists-watchlist.json", ()):
        for key, item_type in (("movie", MOVIE.item_type), ("show", SERIES.item_type)):
            if row.get(key) is None:
                continue
            record = record_for(row, key, item_type)
            if record is None:
                _count(skipped, "unidentifiable row")
                continue
            record.listed = True
            when = _timestamp(row.get("listed_at"))
            if when:
                record.dates.append(when)
            break

    # The history: episodes and films the other members may have missed. A
    # `checkin` or a `scrobble` is not a completed watch, so only
    # `action == "watch"` counts — and a rewatch is a second event for an
    # episode already counted, which is why progress is a set, not a tally.
    for row in tables.get("watched-history.json", ()):
        if row.get("action") != "watch":
            continue
        watched_on = _timestamp(row.get("watched_at"))
        if row.get("type") == "movie":
            film = record_for(row, "movie", MOVIE.item_type)
            if film is None:
                _count(skipped, "unidentifiable row")
                continue
            film.watched = True
            if watched_on:
                film.dates.append(watched_on)
                film.watched_dates.append(watched_on)
        elif row.get("type") == "episode":
            show = record_for(row, "show", SERIES.item_type)
            if show is None:
                _count(skipped, "unidentifiable row")
                continue
            show.watched = True
            episode = row.get("episode") or {}
            season = episode.get("season")
            number = episode.get("number")
            if isinstance(season, int) and isinstance(number, int) and season != 0:
                # Season 0 is specials; counting them would put progress above
                # the total for no reason a person would recognise.
                show.episodes.add((season, number))
                if watched_on:
                    show.episode_dates.append(watched_on)
            aired = _aired(row, "show")
            if aired is not None and show.aired_episodes is None:
                show.aired_episodes = aired

    ordered = sorted(records.values(), key=lambda record: record.row_number)
    for position, record in enumerate(ordered, 1):
        record.row_number = position
    return ordered, skipped


class TraktImporter:
    name = "trakt"
    label = "Trakt"
    #: Films first, matching the declaration order of the connector this one
    #: mirrors. Every record names its own type; the default is never used.
    item_types: tuple[str, ...] = (MOVIE.item_type, SERIES.item_type)
    input = ImportInputSpec(
        kind="upload",
        label="Trakt export",
        field="file",
        accept=".zip,application/zip",
        guide=(
            "On trakt.tv, open your profile's Settings and choose Export Data. "
            "This is a VIP feature — the option is not there on a free account.",
            "Download the .zip and upload it exactly as it downloaded, without unpacking it.",
            "Films go to your Movies library and shows to your Series library, "
            "and you choose above which of the two this import brings in.",
            "A show's progress is counted from its watch history — episodes "
            "you actually watched, rewatches counted once, specials left out.",
            "Season and episode ratings are counted and skipped: a series "
            "holds one score, and you will see how many were left behind on "
            "the preview screen.",
            "Your ratings come across exactly: Trakt's 1-10 is already Akasha's "
            "scale, so nothing is doubled and nothing is marked as a guess.",
            "This is a snapshot, not a sync. Importing again later adds "
            "whatever is new and changes nothing it already holds.",
            "Everything lands in Triage rather than in the library, so nothing "
            "appears until you have looked at it.",
        ),
        empty_state="Drop your Trakt export .zip here, or choose a file.",
        help_url="https://trakt.tv/settings/export",
    )
    identity_kinds = frozenset({"imdb"})
    error_codes = frozenset({"invalid_archive", "unsafe_archive", "export_too_large"})

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.data is None:
            raise TraktError("invalid_archive", "A Trakt export file is required")
        records: list[NormalizedImportRecord] = []
        parsed, skipped = parse_trakt(source.data)
        for record in parsed:
            metadata: dict[str, Any] = {}
            values: dict[str, Any] = {}
            notes: str | None = None
            plays_used = False
            if record.item_type == SERIES.item_type:
                if record.aired_episodes is not None:
                    metadata["episodes"] = record.aired_episodes
                # The roll-up: distinct episodes, excluding season 0. When the
                # archive carries no history for this show, `plays` stands in —
                # an upper bound rather than the same number, so the row says
                # so in its notes rather than looking identical to one that
                # was counted. `plays` is never clamped to the total: the total
                # is display only and never a bound (DEC-092).
                if record.progress:
                    values["progress"] = min(record.progress, _MAX_PROGRESS)
                elif record.plays:
                    values["progress"] = record.plays
                    notes = _PLAYS_NOTE
                if record.date_finished:
                    values["date_finished"] = record.date_finished
                # A marker the row's own data can be checked against, in the
                # source's word for the row and never a stored entry value:
                # the shared entry-value allowlist owns that vocabulary.
                plays_used = notes is not None
            elif record.date_finished:
                values["date_finished"] = record.date_finished

            records.append(
                NormalizedImportRecord(
                    row_number=record.row_number,
                    item=ImportItem(
                        title=record.title,
                        subtitle=None,
                        year=record.year,
                        identifiers={"imdb": record.imdb_id} if record.imdb_id else {},
                        # Everything a person wants to look at — creators,
                        # genres, runtime — is the provider's to supply, and
                        # the archive carries none of it. Inventing a field here
                        # would block the fill.
                        metadata=metadata,
                    ),
                    entry=ImportEntry(
                        score=record.score,
                        notes=notes,
                        date_added=record.date_added,
                        values=values,
                        # Trakt's scale is Akasha's scale: nothing to hedge.
                        score_provisional=False,
                        suggested_status=record.suggested_status,
                    ),
                    shelves=(),
                    errors=tuple(record.errors),
                    # The row's own word for how its progress was counted, and
                    # nothing out of the members themselves. The archive names
                    # its owner in the members this reader never opens.
                    source_fields={"plays_used": plays_used},
                    item_type=record.item_type,
                )
            )
        return ImportSnapshot(
            fingerprint=hashlib.sha256(source.data).hexdigest(),
            filename=source.filename or "trakt.zip",
            source_descriptor={"filename": source.filename or "trakt.zip"},
            records=tuple(records),
            skipped=tuple(skipped),
        )

    def stage(self, snapshot: ImportSnapshot, _directory: Any, _data_dir: Any) -> ImportSnapshot:
        """Nothing to stage: a JSON archive carries no assets and commit never
        re-reads it."""
        return snapshot

    def match(self, record: NormalizedImportRecord, matcher: ImportMatcher) -> MatchDecision:
        """Exact on the IMDb id, scoped to **this row's** library.

        Both target domains resolve an `imdb` identity, so a re-import matches
        every row with no provider traffic, and a film already in the library
        from a Letterboxd or IMDb import matches exactly. Title plus exact year
        is offered only as an ambiguity, never as a match, and scoped to the
        row's own type — a series and the film made from it share both
        (DEC-101).
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


IMPORTER = TraktImporter()
