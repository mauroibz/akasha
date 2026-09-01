"""Series' second adapter: TVmaze's official API, keyless and CC BY-SA.

Three endpoints and nothing else (Sprint 050, measured live 2026-08-31):

| Operation | Endpoint |
|---|---|
| search | `GET api.tvmaze.com/search/shows?q=` |
| resolve by IMDb id | `GET api.tvmaze.com/lookup/shows?imdb=tt…` |
| fetch | `GET api.tvmaze.com/shows/<id>` |

What this source is for: a real synopsis (Wikidata's `synopsis` holds a one-line
identification sentence), a real airing status, and the shows Wikidata's title
search misses — `Los Simuladores` and `Okupas` are the measured pair. What it is
deliberately **not** for:

- **`episodes` is never emitted.** TVmaze's count and Wikidata's `P1113` disagree
  (44 against 38 for one measured series, 76 against 77 for another), and the
  shared `fill_empty` merge would let whichever provider answered second win a
  field that drives a progress control. Wikidata is the declared source for the
  total; the only reliable way to keep TVmaze's out is not to emit it.
- **Covers are never emitted.** TVmaze's `medium_portrait` measured 210×295, which
  the pipeline would upscale, and its `original_untouched` is 2000×3000 at 1.3 MB.
  Stremio's 500×750 is already the right variant, so `static.tvmaze.com` never
  joins `ALLOWED_COVER_HOSTS`.

Two measured shapes an implementation would otherwise guess wrong:

- `/lookup/shows?imdb=` answers a hit with **301 → /shows/<id>** and a `null`
  body; the shared client follows the redirect, so a hit *is* the show record.
  A miss answers **404** with a `null` body — an answer (`record_not_found`),
  never an outage.
- `summary` arrives as HTML. It is parsed to plain text the way the Letterboxd
  reader parses a review, and no markup is ever stored.

TVmaze is English-only; Spanish labels and descriptions remain Wikidata's job.
The licence is CC BY-SA and asks that TVmaze be properly credited as source —
the credit line is a sprint deliverable and DEC-105 records the decision.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef
from book_tracker.infrastructure.providers import (
    INTERACTIVE_ATTEMPTS,
    ProviderPayloadError,
    bounded_json,
)

TVMAZE_BASE = "https://api.tvmaze.com"
USER_AGENT = "Akasha/1.4 ({contact})"

# TVmaze publishes "at least 20 calls every 10 seconds per IP address", with an
# HTTP 429 on breach. A series search is one call, so pacing to half the published
# floor means nobody ever waits for this unless they are searching forty times a
# minute. The 429 itself is retried under the shared `bounded_json` policy — the
# existing quota and retry machinery, not a second one.
MIN_INTERVAL_SECONDS = 0.5

_TAG = re.compile(r"<[^>]+>")
_BLANK_LINES = re.compile(r"\n{3,}")
_IMDB_ID = re.compile(r"tt[0-9]{7,10}")


def _text(value: object) -> str | None:
    text = str(value).strip() if isinstance(value, str) else ""
    return text or None


def _whole(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _year(value: object) -> int | None:
    """`premiered` is an ISO date; the neutral year is its leading four digits."""
    text = _text(value)
    if text is None:
        return None
    try:
        return int(text[:4])
    except ValueError:
        return None


def _plain(value: object) -> str | None:
    """A synopsis with the markup taken out.

    TVmaze's `summary` is HTML (`<p><b>Breaking Bad</b> follows…`), and no renderer
    here interprets markup — so a tag left in would be shown to the reader verbatim.
    Parsed as text rather than trusted, and never stored as source markup: the same
    rule the Letterboxd reader applies to a review.
    """
    raw = _text(value)
    if raw is None:
        return None
    stripped = _TAG.sub("", raw).replace("&nbsp;", " ").replace("&amp;", "&")
    stripped = stripped.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return _BLANK_LINES.sub("\n\n", stripped).strip() or None


def _names(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [name for name in (_text(value) for value in values) if name]


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
    provider being unwell, which is what the enrichment job's retry and the health
    notice read. TVmaze answers a lookup miss with 404 and a `null` body (measured).
    """
    status = error.response.status_code
    if status == 404:
        return ProviderPayloadError("TVmaze has no record for this id", code="record_not_found")
    return ProviderPayloadError(f"TVmaze returned HTTP {status}", code="provider_http_error")


class TvmazeSeriesProvider:
    """TVmaze's REST API. The series domain's second source (DEC-104, DEC-105)."""

    name = "tvmaze"
    item_type = "series"

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

    # -- the boundary ---------------------------------------------------------------

    async def _read(self, path: str, params: Mapping[str, str]) -> Any:
        """One paced, retrying, bounded read. Every call to TVmaze goes through here.

        Returns the decoded body unvalidated: a lookup miss is 404 with a literal
        `null` body, which is an answer rather than malformed JSON, so the non-object
        shape is the caller's to judge. The 429 is retried inside `bounded_json`
        under the shared policy (AC8).
        """
        await self._paced.wait()
        try:
            return await bounded_json(
                self.client,
                f"{TVMAZE_BASE}{path}",
                params=params,
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
                "TVmaze could not be reached", code="provider_unreachable"
            ) from error

    # -- turning a show into a candidate ---------------------------------------------

    @staticmethod
    def _candidate(show: Mapping[str, Any]) -> SearchCandidate | None:
        show_id = _whole(show.get("id"))
        title = _text(show.get("name"))
        if show_id is None or title is None:
            return None
        externals = show.get("externals")
        externals_map: Mapping[str, Any] = externals if isinstance(externals, Mapping) else {}
        imdb = _text(externals_map.get("imdb"))
        if imdb is not None and not _IMDB_ID.fullmatch(imdb):
            imdb = None
        thetvdb = _whole(externals_map.get("thetvdb"))
        network = show.get("network")
        network_name = _text(network.get("name")) if isinstance(network, Mapping) else None
        if network_name is None:
            web_channel = show.get("webChannel")
            network_name = (
                _text(web_channel.get("name")) if isinstance(web_channel, Mapping) else None
            )
        # `averageRuntime` is the measured steadier value; `runtime` is the fallback.
        # Both are legitimately null on some records, and a null is not a zero.
        episode_minutes = _whole(show.get("averageRuntime")) or _whole(show.get("runtime"))
        metadata: dict[str, Any] = {
            "genres": _names(show.get("genres")) or None,
            "network": network_name,
            "episode_minutes": episode_minutes,
            "airing_status": _text(show.get("status")),
            "synopsis": _plain(show.get("summary")),
        }
        identifiers: dict[str, str] = {"tvmaze": str(show_id)}
        if imdb is not None:
            identifiers["imdb"] = imdb
        if thetvdb is not None:
            identifiers["thetvdb"] = str(thetvdb)
        return SearchCandidate(
            source=TvmazeSeriesProvider.name,
            source_id=str(show_id),
            source_refs=(SourceRef(TvmazeSeriesProvider.name, str(show_id)),),
            title=title,
            subtitle=None,
            creators=(),
            year=_year(show.get("premiered")),
            # No cover: Stremio's 500×750 is already the right variant, and TVmaze's
            # would be upscaled or a 1.3 MB original (measured 2026-08-31).
            cover_url=None,
            identifiers=identifiers,
            language="en",
            metadata={key: value for key, value in metadata.items() if value not in (None, [], "")},
            creator_sort=None,
        )

    # -- the Provider protocol --------------------------------------------------------

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        body = await self._read("/search/shows", {"q": query})
        if not isinstance(body, list):
            raise ProviderPayloadError("TVmaze returned no search results")
        rows = [
            self._candidate(row["show"])
            for row in body
            if isinstance(row, Mapping) and isinstance(row.get("show"), Mapping)
        ]
        return [row for row in rows if row is not None][:limit]

    async def fetch(self, source_id: str) -> ItemPayload:
        """A series by TVmaze id — how a pasted `tvmaze.com/shows/<id>` link resolves."""
        value = source_id.strip()
        if not value.isdigit():
            raise ProviderPayloadError(f"{source_id!r} is not a TVmaze id")
        body = await self._read(f"/shows/{value}", {})
        if not isinstance(body, Mapping):
            raise ProviderPayloadError("TVmaze returned no record for this id")
        candidate = self._candidate(body)
        if candidate is None:
            raise ProviderPayloadError("TVmaze returned a record with no usable title")
        return ItemPayload(**vars(candidate))

    async def fetch_by_identifier(self, kind: str, value: str) -> ItemPayload:
        """Background enrichment's entry point (DEC-067 row 3).

        The series domain's declared key is `imdb`, and TVmaze resolves it through
        `/lookup/shows?imdb=` — a hit is a 301 to the show record, which the shared
        client follows, so the answer *is* the record. A miss is a 404, which
        `_http_failure` reads as `record_not_found`: an answer, not an outage.
        """
        if kind != "imdb":
            raise ProviderPayloadError(
                f"TVmaze cannot look a series up by {kind!r}",
                code="unsupported_identity_kind",
            )
        raw = value.strip()
        if not _IMDB_ID.fullmatch(raw):
            raise ProviderPayloadError(f"{raw!r} is not an IMDb id")
        body = await self._read("/lookup/shows", {"imdb": raw})
        if not isinstance(body, Mapping):
            raise ProviderPayloadError(f"TVmaze has no record for {raw}", code="record_not_found")
        candidate = self._candidate(body)
        if candidate is None:
            raise ProviderPayloadError("TVmaze returned a record with no usable title")
        return ItemPayload(**vars(candidate))
