"""Movies' third adapter: Cinemeta, Stremio's keyless, IMDb-keyed metadata service.

Complementary and a fallback, never primary (`source_preference` ranks it last): it
fills what Wikidata left empty and never displaces it (Sprint 063, DEC-098, DEC-103,
DEC-104, DEC-109). Measured live 2026-09-03 at 15/15 films with full field coverage in
`docs/movie-domain-viability.md` — parity with Wikidata's own filter on the same sample,
which is why Sprint 063 proceeded rather than stopping at that gate.

Maps to `MOVIE_FIELDS`: `director` → `creators`, `country` → `countries`, `genres`,
`runtime`, `cast`, `description`. `original_title` and `languages` are left empty —
Cinemeta carries neither, and `fill_empty` means Wikidata still supplies them when it
has them.

The search response carries no `year` beyond a display string and no usable field
beyond a title and an id, so this is search-then-fetch like every other adapter here:
`search` fetches each candidate's `/meta/` record to build a real `SearchCandidate`,
bounded by `MAX_SEARCH_RESULTS` for the same reason Wikidata's search is bounded — a
result nobody will look past is not worth a request.
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

KIND = "movie"
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
    text = _text(value)
    if text is None:
        return None
    match = _YEAR.search(text)
    return int(match.group(0)) if match else None


class CinemetaMovieProvider:
    """Cinemeta's `movie` catalog, registered as `cinemeta`."""

    name = "cinemeta"
    item_type = "movie"

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
        metadata: dict[str, Any] = {
            "creators": _names(meta.get("director")),
            "countries": [country] if country else [],
            "genres": _names(meta.get("genre")),
            "runtime": parse_runtime_minutes(meta.get("runtime")),
            "cast": _names(meta.get("cast")),
            "description": _text(meta.get("description")),
        }
        return SearchCandidate(
            source=self.name,
            source_id=imdb_id,
            source_refs=(SourceRef(self.name, imdb_id),),
            title=title,
            subtitle=None,
            creators=tuple(metadata["creators"]),
            year=_year(meta.get("year")),
            # Built from the id already in hand, exactly as TVmaze does: no request,
            # and a title Cinemeta answers with no IMDb id (never observed live) would
            # get no cover, which is the same "no identity, no cover" rule AC gives it.
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
        """A film by IMDb id — the catalog's own key."""
        value = source_id.strip()
        if not _IMDB_ID.fullmatch(value):
            raise ProviderPayloadError(f"{source_id!r} is not an IMDb id")
        meta = await self._cinemeta.meta(KIND, value)
        candidate = self._candidate(meta)
        if candidate is None:
            raise ProviderPayloadError("Cinemeta returned a record with no usable title")
        return ItemPayload(**vars(candidate))

    async def fetch_by_identifier(self, kind: str, value: str) -> ItemPayload:
        """Background enrichment's entry point (DEC-067 row 3).

        Cinemeta's catalog is IMDb-keyed, so `imdb` is the only kind it answers — unlike
        Wikidata, which also resolves `letterboxd`.
        """
        if kind != "imdb":
            raise ProviderPayloadError(
                f"Cinemeta cannot look a film up by {kind!r}", code="unsupported_identity_kind"
            )
        return await self.fetch(value.strip())
