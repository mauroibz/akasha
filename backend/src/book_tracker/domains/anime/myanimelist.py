"""The MyAnimeList export, read into this domain's vocabulary.

Measured against the owner's real file on 2026-08-27 rather than against MyAnimeList's
documentation: 81 rows, 3,102 bytes gzipped expanding to 78,210 (**25x**), every text
field CDATA-wrapped, `series_animedb_id` distinct on every row.

Three things about the source that a reasonable implementation would get wrong:

- **`my_score` of `0` means unrated**, not a score of zero. And the scale is already
  1–10, so unlike a Goodreads star rating there is nothing to double and nothing to mark
  provisional — a score arrives as the number the owner chose.
- **`0000-00-00` is absence, not a date.** It is every `my_start_date` in the owner's
  file and 76 of 81 finish dates.
- **`my_watched_episodes` is the point.** It differs from `series_episodes` on 7 of the
  owner's rows; without it a dropped series says only "dropped" (DEC-077, Sprint 040).
"""

import gzip
import hashlib
import io
import re
import xml.etree.ElementTree as ElementTree
from dataclasses import replace
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
from book_tracker.domains.anime import DOMAIN as ANIME

DOMAIN = ANIME

#: MyAnimeList's five states, mapped onto the statuses of the domain this importer
#: serves. Stated against `DOMAIN` rather than left to the accident that anime is the
#: only domain with these words, and asserted over `DOMAIN.status(...)` in
#: `test_myanimelist_import.py`, so a status renamed out from under it fails a test
#: rather than silently suggesting nothing.
SUGGESTED_STATUS = {
    "Watching": "watching",
    "Completed": "completed",
    "On-Hold": "on_hold",
    "Dropped": "dropped",
    "Plan to Watch": "plan_to_watch",
}

#: What the reader will expand a gzip to before refusing it.
#:
#: The upload route admits 5 MiB of *compressed* bytes and never consults this
#: connector's `max_bytes`, so this is the only thing standing between a crafted
#: archive and memory. At the measured 965 bytes per row this admits roughly 34,000
#: entries — past any real MyAnimeList list, and still a hard bound.
MAX_DECOMPRESSED_BYTES = 32 * 1024 * 1024
_CHUNK = 512 * 1024

#: A date MyAnimeList writes when it has none.
_NO_DATE = "0000-00-00"
_GZIP_MAGIC = b"\x1f\x8b"
_DOCTYPE = re.compile(rb"<!DOCTYPE", re.IGNORECASE)


class MyAnimeListError(ImportReadError):
    """Every way a MyAnimeList export can be unreadable, with the way out of each.

    The vocabulary is closed and declared on `MyAnimeListImporter.error_codes`. The
    `action` is the point: "the XML is malformed" tells a reader nothing they can do,
    and "export again from MyAnimeList" does (DEC-080).
    """

    ACTIONS = {
        "invalid_xml": (
            "This file is not a MyAnimeList export.",
            "Export again from myanimelist.net/panel.php?go=export and upload the file "
            "unchanged, gzipped as it downloads.",
        ),
        "not_an_anime_export": (
            "This is a manga export, and Akasha holds anime.",
            "Choose Anime List rather than Manga List on the export panel and try again.",
        ),
        "export_too_large": (
            "This export expands to more than Akasha will read.",
            "Check you exported a list and not something else; if your list really is "
            "this large, say so and the limit can be raised.",
        ),
    }

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        user_message, action = self.ACTIONS.get(code, (None, None))
        super().__init__(code, message, details, user_message=user_message, action=action)


def _decoded(data: bytes) -> bytes:
    """The XML behind an upload, whether or not it arrived gzipped.

    Sniffed by magic bytes rather than by filename: MyAnimeList serves the export
    gzipped and a reader may or may not have unpacked it before uploading, and a name
    is not evidence of anything.

    Read in chunks against a ceiling rather than through `gzip.decompress`, which is
    unbounded — a few hundred kilobytes of crafted archive expands to gigabytes.
    """
    if not data.startswith(_GZIP_MAGIC):
        return data
    read = bytearray()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            while chunk := stream.read(_CHUNK):
                read.extend(chunk)
                if len(read) > MAX_DECOMPRESSED_BYTES:
                    raise MyAnimeListError(
                        "export_too_large",
                        f"The export expands beyond {MAX_DECOMPRESSED_BYTES} bytes",
                        {"limit_bytes": MAX_DECOMPRESSED_BYTES},
                    )
    # `BadGzipFile` subclasses `OSError`; `EOFError` is what a truncated stream raises.
    except (OSError, EOFError) as error:
        raise MyAnimeListError("invalid_xml", "The archive could not be decompressed") from error
    return bytes(read)


def _text(element: ElementTree.Element, tag: str) -> str:
    found = element.findtext(tag)
    return (found or "").strip()


def _integer(element: ElementTree.Element, tag: str, errors: list[dict[str, str]]) -> int | None:
    """A whole number, or `None` plus a note on the row that it could not be read."""
    raw = _text(element, tag)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        errors.append({"field": tag, "code": "invalid_integer", "value": raw})
        return None


def _date(element: ElementTree.Element, tag: str) -> str | None:
    """A date, or `None` for the all-zero one MyAnimeList writes when it has none."""
    raw = _text(element, tag)
    return None if not raw or raw == _NO_DATE else raw


def parse_myanimelist(data: bytes) -> list[dict[str, Any]]:
    """Every row of an export, in the source's own words.

    A malformed **file** raises; a malformed **row** carries its complaint in `errors`
    and still comes through, so one bad row does not cost the other eighty and the
    owner can see on the preview screen what did not arrive.
    """
    decoded = _decoded(data)
    # Refused before the parser sees it. Measured on Python 3.12: ElementTree expands
    # internal entities, so billion laughs is live — and it expands *in* the parser,
    # where the decompression ceiling above cannot reach it. External entities are
    # already refused, so there is no file disclosure to worry about. A real export
    # carries no DOCTYPE at all, which is what makes a flat refusal free.
    if _DOCTYPE.search(decoded):
        raise MyAnimeListError("invalid_xml", "A MyAnimeList export declares no DOCTYPE")
    try:
        root = ElementTree.fromstring(decoded)
    except ElementTree.ParseError as error:
        raise MyAnimeListError("invalid_xml", "The XML structure is malformed") from error
    if root.tag != "myanimelist":
        raise MyAnimeListError("invalid_xml", f"The root element is {root.tag!r}")

    info = root.find("myinfo")
    export_type = _text(info, "user_export_type") if info is not None else ""
    if export_type == "2" or root.find("manga") is not None:
        raise MyAnimeListError("not_an_anime_export", "This export holds manga, not anime")

    records: list[dict[str, Any]] = []
    for row_number, anime in enumerate(root.findall("anime"), 1):
        errors: list[dict[str, str]] = []
        mal_id = _text(anime, "series_animedb_id")
        if not mal_id.isdigit():
            errors.append({"field": "series_animedb_id", "code": "required", "value": mal_id})
            mal_id = ""
        title = _text(anime, "series_title")
        if not title:
            errors.append({"field": "series_title", "code": "required", "value": ""})
        score = _integer(anime, "my_score", errors)
        shelves: list[str] = []
        for value in _text(anime, "my_tags").split(","):
            # `shelf_slug` refuses a name with no letters or digits rather than
            # returning an empty one, so a trailing comma is filtered before the call.
            if not value.strip():
                continue
            slug = shelf_slug(value.strip())
            if slug and slug not in shelves:
                shelves.append(slug)
        records.append(
            {
                "row_number": row_number,
                "mal_id": mal_id or None,
                "title": title,
                "kind": _text(anime, "series_type") or None,
                "episodes": _integer(anime, "series_episodes", errors),
                # `0` is unrated on MyAnimeList, and unrated is not a score of zero.
                "score": score or None,
                # Nothing to double and nothing to mark: the scale is already 1-10.
                "score_provisional": False,
                "date_started": _date(anime, "my_start_date"),
                "date_finished": _date(anime, "my_finish_date"),
                "reread_count": _integer(anime, "my_times_watched", errors) or 0,
                "progress": _integer(anime, "my_watched_episodes", errors),
                "notes": _text(anime, "my_comments") or None,
                "suggested_status": SUGGESTED_STATUS.get(_text(anime, "my_status")),
                "shelves": shelves,
                "errors": errors,
            }
        )
    return records


class MyAnimeListImporter:
    name = "myanimelist"
    label = "MyAnimeList"
    item_type = DOMAIN.item_type
    input = ImportInputSpec(
        kind="upload",
        label="MyAnimeList export",
        field="file",
        accept=".xml,.gz,application/gzip,text/xml",
        # Where the file comes from and what happens to it. Two of these exist because
        # they are things to know *before* uploading rather than to discover after.
        guide=(
            "On myanimelist.net, open your profile and choose Export "
            "(myanimelist.net/panel.php?go=export). Pick Anime List, not Manga List.",
            "Download the file. It arrives gzipped; upload it exactly as it "
            "downloaded, or unpacked — either is read.",
            "Scores come across unchanged, because MyAnimeList already scores out of "
            "ten. Nothing is doubled and nothing is marked provisional.",
            "Watched-episode counts come across too, so a series you dropped halfway "
            "still says how far you got.",
            "This is a snapshot, not a sync. Importing again later adds whatever is "
            "new and changes nothing it already holds, so a count that has moved on "
            "stays as it was.",
            "Everything lands in Triage rather than in the library, so nothing appears "
            "until you have looked at it.",
        ),
        empty_state="Drop your MyAnimeList export here, or choose a file.",
        help_url="https://myanimelist.net/panel.php?go=export",
        # `max_bytes` is deliberately absent. The upload route hard-caps the body at its
        # own 5 MiB and never reads this value, while the client *is* shown it — so
        # declaring one would advertise a limit the server does not keep. What actually
        # protects the reader is `MAX_DECOMPRESSED_BYTES`.
    )
    identity_kinds = frozenset({"mal"})
    error_codes = frozenset({"invalid_xml", "not_an_anime_export", "export_too_large"})

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.data is None:
            raise MyAnimeListError("invalid_xml", "A MyAnimeList export file is required")
        records = []
        for payload in parse_myanimelist(source.data):
            metadata = {
                key: payload[key]
                for key in ("kind", "episodes")
                if payload.get(key) not in (None, "", [], {})
            }
            records.append(
                NormalizedImportRecord(
                    row_number=payload["row_number"],
                    item=ImportItem(
                        title=payload["title"],
                        subtitle=None,
                        # The air date is the provider's to supply; the export has none.
                        year=None,
                        identifiers={"mal": payload["mal_id"]} if payload["mal_id"] else {},
                        metadata=metadata,
                    ),
                    entry=ImportEntry(
                        score=payload["score"],
                        notes=payload["notes"],
                        date_added=None,
                        values={
                            "date_started": payload["date_started"],
                            "date_finished": payload["date_finished"],
                            "reread_count": payload["reread_count"],
                            "progress": payload["progress"],
                        },
                        score_provisional=payload["score_provisional"],
                        suggested_status=payload["suggested_status"],
                    ),
                    shelves=tuple(payload["shelves"]),
                    errors=tuple(payload["errors"]),
                    source_fields={"series_animedb_id": payload["mal_id"] or ""},
                )
            )
        return ImportSnapshot(
            fingerprint=hashlib.sha256(source.data).hexdigest(),
            filename=source.filename or "animelist.xml",
            # The filename and nothing else. A MyAnimeList export names its owner in
            # `myinfo`, and none of that is Akasha's to keep.
            source_descriptor={"filename": source.filename or "animelist.xml"},
            records=tuple(records),
            archive_name="source.xml",
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
        return matcher.match(
            identifiers=identifiers,
            title=record.item.title,
            # The export names no studio; only the provider knows one, so a title-only
            # near match is all this connector can offer.
            first_author="",
        )


IMPORTER = MyAnimeListImporter()
