"""Series' third adapter: Cinemeta, registered as `cinemeta-series`.

The registry is keyed by name, so a second adapter answering to `cinemeta` would
silently replace the movie domain's — the same reason `wikidata-series` is named as it
is (DEC-104). Complementary and a fallback, ranked behind Wikidata and TVmaze
(`("wikidata-series", "tvmaze", "cinemeta-series")`): it fills what the other two left
empty and never displaces either. Measured live 2026-09-03 at 10/10 series with full
field coverage in `docs/series-domain-viability.md`.

Maps to `SERIES_FIELDS`: `country` → `countries`, `genre` → `genres`, `runtime` (an
episode length here, not a film's) → `episode_minutes`, `cast`, `description` →
`synopsis`. `creators` reads `writer`: Cinemeta's `director` measured `null` on every
recorded series row, where `writer` carried the real showrunner (`Vince Gilligan` for
Breaking Bad) — the same creator → screenwriter fallback the Wikidata series adapter
already makes.

Two fields are **deliberately never emitted**, both for the reason DEC-125 fixed for
TVmaze's `episodes`: the `/meta/series/` envelope carries no `network`, `episodes` or
`seasons` field of its own, and the only way to derive one — counting the per-episode
`videos` array — would be a second count for a field the domain already has a declared
canonical source (Wikidata's `P1113`/`P2437`) for, disagreeing with it silently. `videos`
is read by nothing here.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef
from book_tracker.infrastructure.cinemeta import CinemetaClient, parse_runtime_minutes
from book_tracker.infrastructure.posters import metahub_poster_url
from book_tracker.infrastructure.providers import ProviderPayloadError

KIND = "series"
MAX_SEARCH_RESULTS = 6

_IMDB_ID = re.compile(r"tt[0-9]{7,10}")
_YEAR = re.compile(r"[0-9]{4}")


def _text(value: object) -> str | None:
    text = str(value).strip() if isinstance(value, str) else ""
    return text or None


def _names(value: object) -> list[str]:
    return (
        [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if isinstance(value, list)
        else []
    )


def _year(value: object) -> int | None:
    """The earliest four digits of Cinemeta's `year`, which for a series is a range
    (`"2008–2013"`) rather than a single value."""
    text = _text(value)
    if text is None:
        return None
    match = _YEAR.search(text)
    return int(match.group(0)) if match else None


class CinemetaSeriesProvider:
    """Cinemeta's `series` catalog, registered as `cinemeta-series`."""

    name = "cinemeta-series"
    item_type = "series"

    def __init__(
        self,
        client: httpx.AsyncClient,
        contact: str,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._cinemeta = CinemetaClient(client, contact, sleep=sleep)

    def _candidate(self, meta: Mapping[str, Any]) -> SearchCandidate | None:
        imdb_id = _text(meta.get("imdb_id"))
        title = _text(meta.get("name"))
        if imdb_id is None or not _IMDB_ID.fullmatch(imdb_id) or title is None:
            return None
        country = _text(meta.get("country"))
        # `director` measured null on every recorded series row; `writer` is the real
        # showrunner and is the same fallback the Wikidata series adapter makes.
        creators = _names(meta.get("director")) or _names(meta.get("writer"))
        metadata: dict[str, Any] = {
            "creators": creators,
            "countries": [country] if country else [],
            "genres": _names(meta.get("genre")),
            "episode_minutes": parse_runtime_minutes(meta.get("runtime")),
            "cast": _names(meta.get("cast")),
            "synopsis": _text(meta.get("description")),
        }
        return SearchCandidate(
            source=self.name,
            source_id=imdb_id,
            source_refs=(SourceRef(self.name, imdb_id),),
            title=title,
            subtitle=None,
            creators=tuple(creators),
            year=_year(meta.get("year")),
            cover_url=metahub_poster_url(imdb_id),
            identifiers={"imdb": imdb_id},
            language=None,
            metadata={
                key: value for key, value in metadata.items() if value not in (None, "", [], {})
            },
            creator_sort=None,
        )

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        wanted = max(1, min(limit, MAX_SEARCH_RESULTS))
        rows = await self._cinemeta.search(KIND, query)
        candidates: list[SearchCandidate] = []
        for row in rows:
            imdb_id = _text(row.get("imdb_id"))
            if imdb_id is None or not _IMDB_ID.fullmatch(imdb_id):
                continue
            try:
                meta = await self._cinemeta.meta(KIND, imdb_id)
            except ProviderPayloadError:
                continue
            candidate = self._candidate(meta)
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) >= wanted:
                break
        return candidates

    async def fetch(self, source_id: str) -> ItemPayload:
        """A series by IMDb id — the catalog's own key."""
        value = source_id.strip()
        if not _IMDB_ID.fullmatch(value):
            raise ProviderPayloadError(f"{source_id!r} is not an IMDb id")
        meta = await self._cinemeta.meta(KIND, value)
        candidate = self._candidate(meta)
        if candidate is None:
            raise ProviderPayloadError("Cinemeta returned a record with no usable title")
        return ItemPayload(**vars(candidate))

    async def fetch_by_identifier(self, kind: str, value: str) -> ItemPayload:
        """Background enrichment's entry point (DEC-067 row 3). IMDb only, like the
        movie adapter — Cinemeta's catalog knows no other identity kind."""
        if kind != "imdb":
            raise ProviderPayloadError(
                f"Cinemeta cannot look a series up by {kind!r}", code="unsupported_identity_kind"
            )
        return await self.fetch(value.strip())
