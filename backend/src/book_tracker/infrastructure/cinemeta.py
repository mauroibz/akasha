"""Cinemeta's shared transport and response reader, for the movie and series domains.

Stremio's Cinemeta addon answers two endpoints, identical in shape for `movie` and
`series` — only the field mapping differs, which is the domain's job. It lives in
infrastructure rather than in either domain's package because two domains need it and
a domain package may not import another (technical spec 6.6); `infrastructure/posters.py`
is the standing precedent for exactly this split. Unlike that module, this one does make
requests, so it also owns the pacing, bounding and retry every other adapter's transport
owns.

Two endpoints, measured live 2026-09-03 (`docs/movie-domain-viability.md`,
`docs/series-domain-viability.md`):

| Operation | Endpoint |
|---|---|
| search | `GET /catalog/<kind>/top/search=<query>.json` → `{"metas": [...]}` |
| fetch | `GET /meta/<kind>/<imdb id>.json` → `{"meta": {...}}` |

Three shapes an implementation would otherwise guess wrong:

- **`/meta/` sometimes answers `307`** to `cinemeta-live.strem.io` rather than serving
  from `v3-cinemeta.strem.io` directly. The shared provider client already follows
  redirects (`create_provider_client`), so this needs no handling here — only noting,
  since a client built without `follow_redirects=True` would silently break.
- **The catalog search's `poster` is `m.media-amazon.com`; the `/meta/` response's own
  `poster` is `images.metahub.space` at the `small` size.** Neither is read. Both domain
  adapters build the medium-size metahub URL from the IMDb id instead, through the
  existing `metahub_poster_url` helper — the same one Wikidata and TVmaze call.
- **A well-formed but unassigned `tt` id is not reliably a miss.** Cinemeta appears to
  resolve almost any plausibly-shaped id live rather than answering 404, which is why no
  "record not found" fixture exists here: none could be produced during measurement. The
  404 branch below is kept for the shape every other adapter in this codebase defends
  against, not because this sprint observed it.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any
from urllib.parse import quote

import httpx

from book_tracker.infrastructure.providers import (
    INTERACTIVE_ATTEMPTS,
    ProviderPayloadError,
    bounded_json_object,
)

CINEMETA_BASE = "https://v3-cinemeta.strem.io"
USER_AGENT = "Akasha/1.6 ({contact})"

# Cinemeta publishes no rate limit. Paced the same as TVmaze's conservative interval
# (Sprint 050): nothing in this sprint's ~30-request measurement run answered a 429 or
# looked throttled, and a courtesy pace costs nothing an interactive search would notice.
MIN_INTERVAL_SECONDS = 0.5

_RUNTIME_MINUTES = re.compile(r"(\d+)")


def parse_runtime_minutes(value: object) -> int | None:
    """`"207 min"` becomes `207`. A missing or malformed value becomes `None`.

    Cinemeta's runtime is always a string with a trailing unit in every response this
    build has seen, but nothing about the contract guarantees the unit is minutes or
    that the field is present at all, so this reads the leading integer and nothing else.
    """
    if not isinstance(value, str):
        return None
    match = _RUNTIME_MINUTES.search(value)
    return int(match.group(1)) if match else None


class _Paced:
    """One request at a time, no faster than the source asked to be called."""

    def __init__(
        self,
        interval: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._interval = interval
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._last: float | None = None

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._last is not None:
                remaining = self._last + self._interval - now
                if remaining > 0:
                    await self._sleep(remaining)
            self._last = time.monotonic()


def _http_failure(error: httpx.HTTPStatusError) -> ProviderPayloadError:
    """A provider's HTTP status as a reason the layer above can act on.

    A 404 is an answer — this record does not exist — while anything else is the
    provider being unwell. Cinemeta's 404 body is HTML, not JSON, so this is reached
    through `raise_for_status` before any JSON decode is attempted.
    """
    status = error.response.status_code
    if status == 404:
        return ProviderPayloadError("Cinemeta has no record for this id", code="record_not_found")
    return ProviderPayloadError(f"Cinemeta returned HTTP {status}", code="provider_http_error")


class CinemetaClient:
    """The transport both domain adapters share: pacing, bounding and the two envelopes.

    One instance per domain adapter, exactly like `WikidataMovieProvider` and
    `TvmazeSeriesProvider` each own their own `_Paced` — the two domains must not share a
    pacing budget, since one asking for time should not make the other wait.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        contact: str,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        min_interval_seconds: float = MIN_INTERVAL_SECONDS,
    ) -> None:
        self.client = client
        self.contact = contact
        self._paced = _Paced(min_interval_seconds, sleep)

    async def _read(self, path: str) -> Any:
        await self._paced.wait()
        try:
            return await bounded_json_object(
                self.client,
                f"{CINEMETA_BASE}{path}",
                params={},
                headers={
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT.format(contact=self.contact),
                },
                attempts=INTERACTIVE_ATTEMPTS,
            )
        except httpx.HTTPStatusError as error:
            raise _http_failure(error) from error
        except httpx.HTTPError as error:
            raise ProviderPayloadError(
                "Cinemeta could not be reached", code="provider_unreachable"
            ) from error

    async def search(self, kind: str, query: str) -> Sequence[Mapping[str, Any]]:
        """The catalog search. Carries no `year` — every field beyond title and id needs
        the `/meta/` fetch below, exactly like every other adapter here."""
        body = await self._read(f"/catalog/{kind}/top/search={quote(query, safe='')}.json")
        metas = body.get("metas")
        if not isinstance(metas, list):
            raise ProviderPayloadError("Cinemeta returned no search results block")
        return [row for row in metas if isinstance(row, Mapping)]

    async def meta(self, kind: str, imdb_id: str) -> Mapping[str, Any]:
        """One full record by IMDb id — the id the catalog is keyed on."""
        body = await self._read(f"/meta/{kind}/{imdb_id}.json")
        meta = body.get("meta")
        if not isinstance(meta, Mapping):
            raise ProviderPayloadError(
                "Cinemeta returned no record for this id", code="record_not_found"
            )
        return meta
