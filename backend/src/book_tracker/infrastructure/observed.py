"""Every provider call observed, and search answers kept for a day (Sprint 101).

Provider health used to say *configured*, never *working*: an outage showed only as
a thin search (proposal R6). `ObservedProvider` wraps any provider without knowing
which one it holds. Each coroutine it delegates is timed into a window per provider,
which `/api/health/providers` and `/metrics` read, and `search` answers go through a
SQLite cache with a TTL.

`fetch` is not cached on purpose: *Refresh from provider* means "ask again", and an
answer from yesterday would be a refresh that refreshed nothing.
"""

import asyncio
import json
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from sqlalchemy import Engine, text

from book_tracker.domain.normalization import normalize_text
from book_tracker.domain.providers import SearchCandidate, SourceRef
from book_tracker.infrastructure.offload import off_loop
from book_tracker.infrastructure.providers import ProviderPayloadError

HealthState = Literal["working", "degraded", "down"]

#: Answers that are the provider working: it was reached and said "no such record".
_ANSWERS = frozenset({"record_not_found", "unsupported_identity_kind"})
WINDOW = 20
#: This many failures in a row, most recent first, is down rather than degraded.
DOWN_AFTER = 3
DEGRADED_RATE = 0.3
CACHE_TTL = timedelta(hours=24)


def is_outage(error: BaseException) -> bool:
    """Whether a raised error means the provider did not answer."""
    if isinstance(error, ProviderPayloadError):
        return error.code not in _ANSWERS
    return isinstance(error, httpx.HTTPError | TimeoutError | OSError)


@dataclass
class _Totals:
    ok: int = 0
    error: int = 0
    seconds: float = 0.0
    recent: deque[bool] = field(default_factory=lambda: deque(maxlen=WINDOW))


class ProviderObservations:
    """Outcomes and latency per provider, since start and over the last calls."""

    def __init__(self) -> None:
        self._providers: dict[str, _Totals] = {}

    def record(self, provider: str, *, ok: bool, seconds: float) -> None:
        totals = self._providers.setdefault(provider, _Totals())
        totals.recent.append(ok)
        totals.seconds += seconds
        if ok:
            totals.ok += 1
        else:
            totals.error += 1

    def state(self, provider: str) -> HealthState:
        totals = self._providers.get(provider)
        if totals is None or not totals.recent:
            return "working"
        recent = list(totals.recent)
        if len(recent) >= DOWN_AFTER and not any(recent[-DOWN_AFTER:]):
            return "down"
        if recent.count(False) / len(recent) >= DEGRADED_RATE:
            return "degraded"
        return "working"

    def totals(self) -> dict[str, tuple[int, int, float]]:
        """`(ok, error, seconds)` per provider since the process started."""
        return {
            name: (totals.ok, totals.error, totals.seconds)
            for name, totals in self._providers.items()
        }


def _encode(candidates: list[SearchCandidate]) -> str:
    return json.dumps([asdict(candidate) for candidate in candidates])


def _decode(body: str) -> list[SearchCandidate]:
    names = {item.name for item in fields(SearchCandidate)}
    rows = []
    for raw in json.loads(body):
        values = {key: value for key, value in raw.items() if key in names}
        values["source_refs"] = tuple(SourceRef(**ref) for ref in values["source_refs"])
        values["creators"] = tuple(values["creators"])
        values["cover_fallback_urls"] = tuple(values.get("cover_fallback_urls", ()))
        rows.append(SearchCandidate(**values))
    return rows


class ResponseCache:
    def __init__(
        self,
        engine: Engine,
        *,
        ttl: timedelta = CACHE_TTL,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.engine = engine
        self.ttl = ttl
        self.now = now

    def get(self, provider: str, key: str) -> list[SearchCandidate] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT body FROM provider_responses WHERE provider = :provider"
                    " AND request_key = :key AND expires_at > :now"
                ),
                {"provider": provider, "key": key, "now": self.now().isoformat()},
            ).first()
        return _decode(row[0]) if row is not None else None

    def put(self, provider: str, key: str, candidates: list[SearchCandidate]) -> None:
        # Only the plain shape is kept: a subclass carries fields this cache would drop.
        if any(type(candidate) is not SearchCandidate for candidate in candidates):
            return
        now = self.now()
        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM provider_responses WHERE expires_at <= :now"),
                {"now": now.isoformat()},
            )
            connection.execute(
                text(
                    "INSERT OR REPLACE INTO provider_responses"
                    " (provider, request_key, body, expires_at)"
                    " VALUES (:provider, :key, :body, :expires)"
                ),
                {
                    "provider": provider,
                    "key": key,
                    "body": _encode(candidates),
                    "expires": (now + self.ttl).isoformat(),
                },
            )


class ObservedProvider:
    """A provider, with each call timed and its searches cached. Knows no provider."""

    def __init__(
        self,
        inner: Any,
        observations: ProviderObservations,
        *,
        cache: ResponseCache | None = None,
    ) -> None:
        self._inner = inner
        self._observations = observations
        self._cache = cache
        # Protocol checks read attributes statically (`isinstance(x, EnrichingProvider)`
        # never reaches `__getattr__`), so what the inner provider has is put on this
        # instance: its identity, and an observed twin of each coroutine method.
        self.name = inner.name
        self.item_type = getattr(inner, "item_type", None)
        for attribute in dir(type(inner)):
            if attribute.startswith("_") or attribute == "search":
                continue
            value = getattr(inner, attribute, None)
            if asyncio.iscoroutinefunction(value):
                setattr(self, attribute, self._observed(value))

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._inner, name)
        return self._observed(value) if asyncio.iscoroutinefunction(value) else value

    def _observed(self, call: Callable[..., Any]) -> Callable[..., Any]:
        async def observed(*args: Any, **kwargs: Any) -> Any:
            return await self._observe(call, *args, **kwargs)

        return observed

    async def _observe(self, call: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            result = await call(*args, **kwargs)
        except BaseException as error:
            self._observations.record(
                self._inner.name,
                ok=not is_outage(error),
                seconds=time.perf_counter() - started,
            )
            raise
        self._observations.record(self._inner.name, ok=True, seconds=time.perf_counter() - started)
        return result

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        if self._cache is None:
            return await self._observe(self._inner.search, query, limit)  # type: ignore[no-any-return]
        key = f"{normalize_text(query)}|{limit}"
        cached = await off_loop(self._cache.get, self._inner.name, key)
        if cached is not None:
            return cached
        answer = await self._observe(self._inner.search, query, limit)
        await off_loop(self._cache.put, self._inner.name, key, list(answer))
        return answer  # type: ignore[no-any-return]
