"""TMDB as a recommendation source (Sprint 134, DEC-183 point 6, DEC-189).

One round is at most two requests and usually one: the seed's TMDB id is read from
its stored identifiers (Wikidata carries it for most films and series), or found once
through `/find/{imdb_id}` and handed back on the `Selection` so the round keeps it on
the item; then `/{media}/{id}/recommendations` chooses. Nothing here asks TMDB about a
candidate: the domain resolves the few it enriches through its own providers.

Shared, not a domain's: which TMDB media a library is (`movie`, `tv`) comes from the
domain's `RecommendationSpec.source_options`, handed over on the seed, so this adapter
never asks which library it holds.

Terms (DEC-183 point 6 amends DEC-103 for recommendations only): rows from here carry
TMDB's attribution wherever they are shown, and are deleted after `retention`, TMDB's
six-month cache window, by the job runner's idle pass. No poster path is kept: a
suggestion is shown with the cover its domain's providers found, never an image
hotlinked from TMDB.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

import httpx

from book_tracker.domain.recommendations import (
    Candidate,
    Seed,
    Selection,
    SourceError,
    TasteProfile,
)
from book_tracker.infrastructure.providers import (
    INTERACTIVE_ATTEMPTS,
    ProviderPayloadError,
    bounded_json_object,
    parse_year,
)

TMDB_API = "https://api.themoviedb.org/3"
NAME = "tmdb"
#: TMDB's own wording, required beside anything its API supplied.
TMDB_ATTRIBUTION = "This product uses the TMDB API but is not endorsed or certified by TMDB."
#: TMDB's terms allow caching its content for six months.
RETENTION = timedelta(days=182)
#: What a round's reason says; the signal beside it is the source's name.
REASON = "TMDB: often watched together"
NOT_CONFIGURED_HINT = (
    "TMDB is not configured. Set TMDB_READ_TOKEN (a TMDB API read access token, free"
    " from themoviedb.org's API settings) in the server's environment and restart."
)
#: The media a domain may name, which are TMDB's path segments.
MEDIA = frozenset({"movie", "tv"})
#: How much of an overview is kept for the sheet.
OVERVIEW_CHARACTERS = 600

_TMDB_ID = re.compile(r"[0-9]{1,12}")
_IMDB_ID = re.compile(r"tt[0-9]{7,10}")


class TmdbRecommendations:
    """`/recommendations` for one film or series, in one request."""

    name = NAME
    label = "TMDB"
    retention = RETENTION
    attribution = TMDB_ATTRIBUTION

    def __init__(
        self,
        client: httpx.AsyncClient,
        read_token: str,
        *,
        attempts: int = INTERACTIVE_ATTEMPTS,
    ) -> None:
        self.client = client
        self.read_token = read_token
        self.attempts = attempts

    async def select(self, seed: Seed, profile: TasteProfile, limit: int) -> Selection:
        media = seed.options.get("media")
        if media not in MEDIA:
            raise SourceError("TMDB does not cover this library", code="unsupported")
        title = seed.title or "this"
        learned: dict[str, str] = {}
        tmdb_id = str(seed.external_ids.get("tmdb") or "").strip()
        if not _TMDB_ID.fullmatch(tmdb_id):
            imdb_id = str(seed.external_ids.get("imdb") or "").strip()
            if not _IMDB_ID.fullmatch(imdb_id):
                raise SourceError(
                    f"TMDB needs an IMDb or TMDB id to find {title}; this one carries neither",
                    code="no_identity",
                )
            tmdb_id = await self._find(media, imdb_id, title)
            learned["tmdb"] = tmdb_id
        body = await self._get(f"/{media}/{tmdb_id}/recommendations", {"page": 1}, title)
        results = body.get("results")
        rows = results if isinstance(results, list) else []
        candidates: list[Candidate] = []
        for row in rows:
            candidate = self._candidate(media, row, tmdb_id)
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) == limit:
                break
        return Selection(candidates=candidates, seed_ids=learned)

    async def _find(self, media: str, imdb_id: str, title: str) -> str:
        body = await self._get(f"/find/{imdb_id}", {"external_source": "imdb_id"}, title)
        found = body.get(f"{media}_results")
        for row in found if isinstance(found, list) else []:
            value = str(row.get("id") or "") if isinstance(row, Mapping) else ""
            if _TMDB_ID.fullmatch(value):
                return value
        raise SourceError(f"TMDB has no record of {title} ({imdb_id})", code="not_found")

    async def _get(
        self, path: str, params: Mapping[str, str | int], title: str
    ) -> Mapping[str, Any]:
        try:
            return await bounded_json_object(
                self.client,
                f"{TMDB_API}{path}",
                params=params,
                headers={
                    "Authorization": f"Bearer {self.read_token}",
                    "Accept": "application/json",
                },
                attempts=self.attempts,
            )
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status == 404:
                raise SourceError(f"TMDB has no record of {title}", code="not_found") from None
            if status in (401, 403):
                raise SourceError(
                    "TMDB refused the token; check TMDB_READ_TOKEN", code="unauthorized"
                ) from None
            if status == 429:
                raise SourceError(
                    "TMDB asked us to slow down; try again later", code="busy"
                ) from None
            raise SourceError(f"TMDB answered {status}", code="unavailable") from None
        except (httpx.TransportError, httpx.TimeoutException):
            raise SourceError("TMDB could not be reached", code="unavailable") from None
        except ProviderPayloadError:
            raise SourceError("TMDB answered something unreadable", code="malformed") from None

    @staticmethod
    def _candidate(media: str, row: object, seed_id: str) -> Candidate | None:
        if not isinstance(row, Mapping) or row.get("adult") is True:
            return None
        value = str(row.get("id") or "")
        title = row.get("title") or row.get("name")
        if not _TMDB_ID.fullmatch(value) or value == seed_id or not isinstance(title, str):
            return None
        title = title.strip()
        if not title:
            return None
        year = parse_year(row.get("release_date") or row.get("first_air_date"))
        display: dict[str, Any] = {"url": f"https://www.themoviedb.org/{media}/{value}"}
        overview = row.get("overview")
        if isinstance(overview, str) and overview.strip():
            display["overview"] = overview.strip()[:OVERVIEW_CHARACTERS]
        original = row.get("original_title") or row.get("original_name")
        if isinstance(original, str) and original.strip() and original.strip() != title:
            display["original_title"] = original.strip()
        score = row.get("vote_average")
        return Candidate(
            title=title,
            year=year,
            external_ids={"tmdb": value},
            reason=REASON,
            source_score=float(score) if isinstance(score, int | float) else None,
            display=display,
        )
