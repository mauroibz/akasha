"""Albums' adapter: MusicBrainz, plus the Cover Art Archive.

It sits in this domain's package rather than in `infrastructure/`, so the album's
adapter, vocabulary and identity rule are one directory (technical spec 6.6).

The album domain's provider: MusicBrainz for the record, Cover Art Archive for the art.

Three things here are not how the book providers work, and each one is measured rather
than assumed (DEC-052, `docs/domain-architecture-proposal.md` section 2):

- **A release group is the work and a release is the edition.** Search answers release
  groups, because that is what a person types; the label, catalogue number, country,
  language and track count exist only on a release, so `fetch` reaches one.
- **The source knows how its creators sort.** `artist-credit[].artist.sort-name` is
  curated and arrives in the search response itself, so no artist lookup is needed and
  the DEC-051 heuristic never runs on a name MusicBrainz already answered.
- **Pacing lives here.** Albums declare no background enrichment, so MusicBrainz is
  reached only from interactive paths, which never touch the job runner's shared
  `RateLimiter`. ~1 request/second is the documented ceiling and throttling arrives as
  **503**, not 429.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import httpx

from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef
from book_tracker.infrastructure.providers import (
    INTERACTIVE_ATTEMPTS,
    ProviderPayloadError,
    bounded_json,
    parse_year,
)

MUSICBRAINZ_BASE = "https://musicbrainz.org/ws/2"
# The documented ceiling is one request per second averaged; a little over one second
# keeps a burst inside it without needing a token bucket. Breaching the terms of a free
# service on a pilot is a real cost with no upside.
MUSICBRAINZ_MIN_INTERVAL_SECONDS = 1.1
# `MAX_COVER_EDGE` is 600, so the full image (811 KiB measured) is downscaled to 600
# anyway and the 500px thumbnail would upscale. The 1200 is 244 KiB.
COVER_ART_THUMBNAIL = "https://coverartarchive.org/release-group/{release_group}/front-1200"
USER_AGENT = "Akasha/1.1 ({contact})"


def _credit(artist_credit: Sequence[Any]) -> tuple[tuple[str, ...], str, str | None]:
    """The ordered creators, the credit as rendered, and the first sort name.

    `["Dean Blunt", "James Ferraro"]` joined by ", " is not
    `Dean Blunt Meets James Ferraro`: the joinphrase between two credits is part of
    what the record is called, so the rendered string is stored beside the list.
    """
    names: list[str] = []
    rendered: list[str] = []
    sort_name: str | None = None
    for index, entry in enumerate(artist_credit):
        if not isinstance(entry, Mapping):
            continue
        candidate = entry.get("artist")
        artist: Mapping[str, Any] = candidate if isinstance(candidate, Mapping) else {}
        name = str(entry.get("name") or artist.get("name") or "").strip()
        if not name:
            continue
        names.append(name)
        rendered.append(name + str(entry.get("joinphrase") or ""))
        if index == 0:
            curated = artist.get("sort-name")
            sort_name = (
                str(curated).strip() if isinstance(curated, str) and curated.strip() else None
            )
    return tuple(names), "".join(rendered).strip(), sort_name


def _tracklist(media: Sequence[Any]) -> list[dict[str, Any]]:
    """Every track on the release, in the order the response lists them.

    Two numbers arrive per track and they are not the same string: `position` is the
    sequential index and `number` is what is printed — `A1`, `A2` on a record. The
    printed one is what a person reads off the sleeve, so it is what is stored, and
    a multi-disc release qualifies it with the medium ("2-A1") rather than repeating
    bare numbers that no longer identify a track.

    The order is the response's own. Deriving one here would reshuffle a tracklist on
    the next refresh, which overwrites metadata wholesale.
    """
    usable = [medium for medium in media if isinstance(medium, Mapping)]
    rows: list[dict[str, Any]] = []
    for medium in usable:
        for track in medium.get("tracks") or []:
            if not isinstance(track, Mapping):
                continue
            title = _text(track.get("title"))
            if not title:
                continue
            number = _text(track.get("number")) or str(track.get("position") or len(rows) + 1)
            if len(usable) > 1:
                number = f"{medium.get('position') or 1}-{number}"
            length = track.get("length")
            rows.append(
                {
                    "number": number,
                    "title": title,
                    "length_ms": length if isinstance(length, int) else None,
                }
            )
    return rows


def _text(value: object) -> str | None:
    text = str(value).strip() if isinstance(value, str) else ""
    return text or None


class MusicBrainzProvider:
    name = "musicbrainz"
    item_type = "album"

    def __init__(
        self,
        client: httpx.AsyncClient,
        contact: str,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        min_interval_seconds: float = MUSICBRAINZ_MIN_INTERVAL_SECONDS,
    ) -> None:
        self.client = client
        self.contact = contact
        self._sleep = sleep
        self._min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last_request: float | None = None

    async def _json(self, path: str, params: Mapping[str, str | int]) -> Mapping[str, Any]:
        """One paced, retrying request. Every call to MusicBrainz goes through here."""
        async with self._lock:
            now = time.monotonic()
            if self._last_request is not None:
                waiting = self._last_request + self._min_interval - now
                if waiting > 0:
                    await self._sleep(waiting)
            self._last_request = time.monotonic()
        return await bounded_json(
            self.client,
            f"{MUSICBRAINZ_BASE}{path}",
            params={**params, "fmt": "json"},
            headers={"User-Agent": USER_AGENT.format(contact=self.contact)},
            attempts=INTERACTIVE_ATTEMPTS,
        )

    def _candidate(self, group: Mapping[str, Any]) -> SearchCandidate | None:
        release_group_id = _text(group.get("id"))
        title = _text(group.get("title"))
        if not release_group_id or not title:
            return None
        creators, credit, sort_name = _credit(group.get("artist-credit") or [])
        return SearchCandidate(
            source=self.name,
            source_id=release_group_id,
            source_refs=(SourceRef(self.name, release_group_id),),
            title=title,
            subtitle=None,
            creators=creators,
            year=parse_year(group.get("first-release-date")),
            cover_url=COVER_ART_THUMBNAIL.format(release_group=release_group_id),
            # A barcode is not an edition key (obs. 3) and a release group has no
            # global identifier at all, so nothing here is offered as one.
            identifiers={},
            language=None,
            metadata={"creators": list(creators), "credit": credit},
            credit=credit or None,
            creator_sort=sort_name,
        )

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        body = await self._json("/release-group", {"query": query, "limit": limit})
        groups = body.get("release-groups")
        if not isinstance(groups, list):
            raise ProviderPayloadError("MusicBrainz returned no release groups")
        rows = [self._candidate(group) for group in groups if isinstance(group, Mapping)]
        return [row for row in rows if row is not None][:limit]

    @staticmethod
    def _preferred_release(
        releases: Sequence[Any], first_release_date: str | None
    ) -> Mapping[str, Any] | None:
        """The original official pressing, which is what a person means by the album.

        A group holds 25 releases for *Kind of Blue*, so the first one the API happens
        to return would file a 2013 Japanese reissue as the record. The group states
        its own `first-release-date`, so an official release carrying that exact date is
        the original; failing that, the earliest date wins. Several pressings can share
        the day — mono and stereo here — and which of those is chosen is arbitrary but
        stable, because they differ only in the catalogue number.
        """
        usable = [row for row in releases if isinstance(row, Mapping) and row.get("id")]
        if not usable:
            return None
        official = [row for row in usable if row.get("status") == "Official"] or usable
        original = [row for row in official if row.get("date") == first_release_date]
        return min(
            original or official,
            key=lambda row: (str(row.get("date") or "9999"), str(row.get("id"))),
        )

    async def fetch(self, source_id: str) -> ItemPayload:
        group = await self._json(f"/release-group/{source_id}", {"inc": "releases+artist-credits"})
        release_stub = self._preferred_release(
            group.get("releases") or [], _text(group.get("first-release-date"))
        )
        if release_stub is None:
            raise ProviderPayloadError("MusicBrainz release group has no releases")
        release = await self._json(
            f"/release/{release_stub['id']}",
            # `recordings` is what turns `media` into a tracklist. Measured
            # 2026-08-14 and again on re-recording: 6.5 KB for *Kind of Blue*, in
            # the same request, so it costs no extra rate-limit budget.
            {"inc": "artist-credits+labels+media+release-groups+recordings"},
        )
        # DEC-044: a record that cannot be tied to the one that was asked for is
        # refused rather than partially merged.
        belongs_to = release.get("release-group")
        if not isinstance(belongs_to, Mapping) or belongs_to.get("id") != source_id:
            raise ProviderPayloadError(
                "MusicBrainz release does not belong to the requested release group",
                code="provider_edition_mismatch",
            )

        creators, credit, sort_name = _credit(group.get("artist-credit") or [])
        label_info: Mapping[str, Any] = next(
            (row for row in release.get("label-info") or [] if isinstance(row, Mapping)), {}
        )
        named = label_info.get("label")
        label: Mapping[str, Any] = named if isinstance(named, Mapping) else {}
        medium: Mapping[str, Any] = next(
            (row for row in release.get("media") or [] if isinstance(row, Mapping)), {}
        )
        representation = release.get("text-representation")
        language = (
            _text(representation.get("language")) if isinstance(representation, Mapping) else None
        )
        track_count = medium.get("track-count")
        metadata: dict[str, Any] = {
            "creators": list(creators),
            "credit": credit,
            "label": _text(label.get("name")),
            "catalog_number": _text(label_info.get("catalog-number")),
            "country": _text(release.get("country")),
            "language": language,
            "format": _text(medium.get("format")),
            "track_count": track_count if isinstance(track_count, int) else None,
            "tracklist": _tracklist(release.get("media") or []) or None,
        }
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title=str(group.get("title") or release.get("title") or ""),
            subtitle=None,
            creators=creators,
            year=parse_year(group.get("first-release-date")) or parse_year(release.get("date")),
            cover_url=COVER_ART_THUMBNAIL.format(release_group=source_id),
            identifiers={},
            language=language,
            metadata={key: value for key, value in metadata.items() if value is not None},
            credit=credit or None,
            creator_sort=sort_name,
        )
