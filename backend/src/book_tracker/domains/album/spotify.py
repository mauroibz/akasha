"""Spotify's account-data export, read into the album domain.

Measured against the owner's own two real bundles on 2026-09-02/03 rather than
against documentation (`docs/spotify-import-and-insights-viability.md`): Spotify
publishes **two** exports, and only one is a library.

- **Technical Log Information** (`my_spotify_data.zip`): **not usable.** 291
  `spotify:album:` URIs, but they sit under recommendation-carousel section names
  (`discover-weekly`, `release-radar`, `artist-mixes`) — things Spotify advertised,
  not chosen.
- **Account Data** (`my_spotify_data_2.zip`): **the library.** `YourLibrary.json`'s
  `albums` array is a deliberate "save this album" act — 157 rows in the owner's
  library, each an exact `spotify:album:` URI.

Both bundles nest every member one directory deep (`Spotify Account Data/…`,
`Spotify Technical Log Information/…`), so this reader matches members by their
own basename rather than assuming a fixed root — Spotify could rename that folder
in a future export without changing what is actually inside it.

Three things this reader deliberately does not do, all measured and out of scope
for this sprint (see the sprint file's "Explicit non-scope"):

- **`YourLibrary.tracks`** (1,362 rows) is never rolled up to albums by default.
  Rolling up the owner's own export yields 41 genuinely new albums, of which only
  9 have two or more saved tracks — mostly a statement about one song, not about an
  album. `records_from_library(..., rollup_min_tracks=...)` implements the roll-up,
  tested directly; no route wires a way to turn it on yet; it defaults to off.
- **`Playlist1.json`** (406 further albums, on the strength of one track appearing
  in a list), **`StreamingHistory_music_0.json`** and the follow graph are never
  opened.
- **Identity resolution against MusicBrainz** (the URL-relation and text-search
  passes) is `MusicBrainzProvider.fetch_by_identifier`'s job, reached through
  background enrichment once a row lands with a `spotify` identifier — not this
  reader's.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
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
from book_tracker.domains.album import DOMAIN as ALBUM

#: What the reader will expand the archive to before refusing it, the same shape
#: Trakt's reader bounds against (declared sizes checked before a byte is
#: decompressed; each member re-checked against its own bound as it is read).
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
_CHUNK = 64 * 1024

#: The one member this reader needs. Present only in the Account Data bundle.
LIBRARY_MEMBER = "YourLibrary.json"
#: A telltale member of the *other* bundle, present only there — used to name the
#: wrong-export refusal specifically rather than falling back to a generic one.
TECHNICAL_LOG_MARKER = "ReadMeFirst_TechnicalLogInformation.pdf"

#: A saved album's own URI shape: `spotify:album:<22-char base62 id>`.
_ALBUM_URI_PREFIX = "spotify:album:"


class SpotifyError(ImportReadError):
    """Every way a Spotify export can be unreadable, with the way out of each.

    The vocabulary is closed and declared on `SpotifyImporter.error_codes`.
    """

    ACTIONS = {
        "invalid_archive": (
            "This file is not a Spotify export.",
            "Request your data from spotify.com/account/privacy and upload the "
            "Account Data .zip exactly as it downloaded, without unpacking it.",
        ),
        "wrong_export": (
            "This is Spotify's Technical Log Information export, not your library.",
            'Spotify sends two separate exports. Request "Account data" — not '
            '"Extended streaming history" or the technical log — and upload '
            "that .zip instead.",
        ),
        "unsafe_archive": (
            "This archive contains entries Akasha will not open.",
            "Upload the .zip exactly as Spotify produced it. A rebuilt or edited "
            "archive is refused because Akasha cannot tell what was changed.",
        ),
        "export_too_large": (
            "This export expands to more than Akasha will read.",
            "Check you uploaded a Spotify data export and not something else.",
        ),
    }

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        user_message, action = self.ACTIONS.get(code, (None, None))
        super().__init__(code, message, details, user_message=user_message, action=action)


def _safe_member(name: str) -> bool:
    """Whether a member name is one this reader will even consider opening.

    Anything absolute, anything containing `..`, anything with a hidden or empty
    segment and anything with a backslash is refused before it is read — nothing is
    extracted to disk, so a name that tries to escape is evidence about the archive
    rather than a nuisance.
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
                raise SpotifyError(
                    "export_too_large",
                    "A member of the archive is larger than declared",
                    {"member": info.filename[:80]},
                )
    return bytes(body)


def _open_archive(data: bytes) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as error:
        raise SpotifyError("invalid_archive", "The upload is not a readable ZIP") from error


def _checked_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Every real (non-directory) member, refused early if any one is unsafe."""
    seen: set[str] = set()
    total = 0
    files: list[zipfile.ZipInfo] = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        if info.flag_bits & 0x1:
            raise SpotifyError(
                "unsafe_archive",
                "The archive contains an encrypted member",
                {"member": info.filename[:80]},
            )
        if not _safe_member(info.filename):
            raise SpotifyError(
                "unsafe_archive",
                "The archive contains an unsafe member name",
                {"member": info.filename[:80]},
            )
        if info.filename in seen:
            raise SpotifyError(
                "unsafe_archive", "The archive names a member twice", {"member": info.filename[:80]}
            )
        seen.add(info.filename)
        if info.file_size > MAX_MEMBER_BYTES:
            raise SpotifyError(
                "export_too_large",
                "A member of the archive is larger than Akasha will read",
                {"member": info.filename[:80]},
            )
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise SpotifyError(
                "export_too_large", "The archive expands to more than Akasha will read"
            )
        files.append(info)
    return files


def _find(files: list[zipfile.ZipInfo], basename: str) -> zipfile.ZipInfo | None:
    return next((info for info in files if PurePosixPath(info.filename).name == basename), None)


@dataclass(frozen=True)
class SpotifyAlbum:
    """One row of `YourLibrary.albums`, after Spotify's vocabulary stops leaking
    upward — a saved album's artist, title and exact URI, and nothing else."""

    artist: str
    title: str
    spotify_id: str


def _album_id(uri: object) -> str | None:
    value = str(uri).strip() if isinstance(uri, str) else ""
    return value[len(_ALBUM_URI_PREFIX) :] if value.startswith(_ALBUM_URI_PREFIX) else None


def _library_albums(library: Any) -> list[SpotifyAlbum]:
    if not isinstance(library, dict):
        raise SpotifyError("invalid_archive", "YourLibrary.json does not hold an object")
    rows = library.get("albums")
    if not isinstance(rows, list):
        raise SpotifyError("invalid_archive", "YourLibrary.json has no albums list")
    found: list[SpotifyAlbum] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        spotify_id = _album_id(row.get("uri"))
        artist = str(row.get("artist") or "").strip()
        title = str(row.get("album") or "").strip()
        if spotify_id and artist and title:
            found.append(SpotifyAlbum(artist=artist, title=title, spotify_id=spotify_id))
    return found


def _track_rollup_albums(
    library: Any, already_saved: frozenset[str], min_tracks: int
) -> list[SpotifyAlbum]:
    """Albums implied by `YourLibrary.tracks`, threshold-gated and never a default.

    Measured on the owner's own export: rolling up 1,362 saved tracks yields 128
    distinct albums, of which 87 are already in `albums` — the genuinely new ones
    number 41, and only 9 of those have two or more saved tracks. Below the
    threshold, one saved song is a statement about a song, not about an album.
    """
    rows = library.get("tracks") if isinstance(library, dict) else None
    if not isinstance(rows, list):
        return []
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        artist = str(row.get("artist") or "").strip()
        title = str(row.get("album") or "").strip()
        if artist and title:
            counts[(artist, title)] = counts.get((artist, title), 0) + 1
    found: list[SpotifyAlbum] = []
    for (artist, title), count in counts.items():
        if count < min_tracks:
            continue
        # Tracks carry no album URI (measured: only saved *albums* do), so a
        # roll-up row has no exact identity — it is named by title and artist
        # alone and never merges with an exactly-identified saved album.
        key = f"{artist}␟{title}"
        if key in already_saved:
            continue
        found.append(SpotifyAlbum(artist=artist, title=title, spotify_id=""))
    return found


def records_from_library(
    library: Any, *, rollup: bool = False, rollup_min_tracks: int = 3
) -> list[NormalizedImportRecord]:
    """`YourLibrary.json`'s parsed body, turned into the album domain's rows.

    Roll-up is off by default (see the module docstring) and, when enabled, adds
    rows the same way a saved album does except for the identity: a rolled-up
    album carries no `spotify` identifier, so it is never queued for enrichment
    either — matching a search-added album (AC4's rule applies here too).
    """
    albums = _library_albums(library)
    records = [
        NormalizedImportRecord(
            row_number=index,
            item=ImportItem(
                title=album.title,
                subtitle=None,
                year=None,
                identifiers={"spotify": album.spotify_id},
                metadata={"creators": [album.artist]},
            ),
            entry=ImportEntry(score=None, notes=None, date_added=None, values={}),
            shelves=(),
            errors=(),
            source_fields={"spotify_uri": f"{_ALBUM_URI_PREFIX}{album.spotify_id}"},
        )
        for index, album in enumerate(albums)
    ]
    if rollup:
        saved = {f"{album.artist}␟{album.title}" for album in albums}
        rolled = _track_rollup_albums(library, frozenset(saved), rollup_min_tracks)
        records.extend(
            NormalizedImportRecord(
                row_number=len(records) + index,
                item=ImportItem(
                    title=album.title,
                    subtitle=None,
                    year=None,
                    identifiers={},
                    metadata={"creators": [album.artist]},
                ),
                entry=ImportEntry(score=None, notes=None, date_added=None, values={}),
                shelves=(),
                errors=(),
                source_fields={"from_saved_tracks": True},
            )
            for index, album in enumerate(rolled)
        )
    return records


class SpotifyImporter:
    name = "spotify"
    label = "Spotify"
    item_types: tuple[str, ...] = (ALBUM.item_type,)
    input = ImportInputSpec(
        kind="upload",
        label="Spotify export",
        field="file",
        accept=".zip,application/zip",
        guide=(
            "On spotify.com, open Account, then Privacy settings, and request "
            '"Account data" — not "Extended streaming history".',
            "Spotify emails you a download link within a few days. Download the "
            ".zip and upload it exactly as it downloaded, without unpacking it.",
            'Only your saved albums come across — a deliberate "save this '
            'album" act. Playlists, streaming history and podcasts are not read.',
            "Each album is looked up on MusicBrainz in the background for its "
            "cover, label, tracklist and other details. That can take a few "
            "minutes for a full library.",
            "This is a snapshot, not a sync. Importing again later adds "
            "whatever is new and changes nothing it already holds.",
            "Everything lands in Triage rather than in the library, so nothing "
            "appears until you have looked at it.",
        ),
        empty_state="Drop your Spotify account data export .zip here, or choose a file.",
        help_url="https://www.spotify.com/account/privacy/",
    )
    identity_kinds = frozenset({"spotify"})
    error_codes = frozenset(
        {"invalid_archive", "wrong_export", "unsafe_archive", "export_too_large"}
    )

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.data is None:
            raise SpotifyError("invalid_archive", "A Spotify export file is required")
        archive = _open_archive(source.data)
        files = _checked_members(archive)
        library_info = _find(files, LIBRARY_MEMBER)
        if library_info is None:
            if _find(files, TECHNICAL_LOG_MARKER) is not None:
                raise SpotifyError(
                    "wrong_export",
                    "This is the Technical Log Information export, not Account Data",
                )
            raise SpotifyError("invalid_archive", "The archive holds no YourLibrary.json")
        try:
            text = _body(archive, library_info).decode("utf-8-sig")
            library = json.loads(text)
        except UnicodeDecodeError as error:
            raise SpotifyError(
                "invalid_archive", "YourLibrary.json is not UTF-8", {"member": LIBRARY_MEMBER}
            ) from error
        except json.JSONDecodeError as error:
            raise SpotifyError(
                "invalid_archive",
                "YourLibrary.json is not readable JSON",
                {"member": LIBRARY_MEMBER},
            ) from error
        records = records_from_library(library)
        return ImportSnapshot(
            fingerprint=hashlib.sha256(source.data).hexdigest(),
            filename=source.filename or "spotify.zip",
            source_descriptor={"filename": source.filename or "spotify.zip"},
            records=tuple(records),
        )

    def stage(self, snapshot: ImportSnapshot, _directory: Any, _data_dir: Any) -> ImportSnapshot:
        """Nothing to stage: a JSON archive carries no assets and commit never
        re-reads it."""
        return snapshot

    def match(self, record: NormalizedImportRecord, matcher: ImportMatcher) -> MatchDecision:
        """Exact on the Spotify id (AC5's re-import idempotency), scoped to albums.

        A rolled-up row carries no `spotify` identifier at all — the same "title
        plus exact year" ambiguity path every other importer offers is not
        available either, since Spotify supplies no year — so it always arrives
        as a fresh candidate rather than a match.
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
            item_type=ALBUM.item_type,
        )


IMPORTER = SpotifyImporter()
