"""What the application is doing, and whether its providers answer (Sprint 101).

Provider health was *configured*, never *working*: an outage showed only as a thin
search. Every provider call is observed now, search answers are kept for a day so
the same question costs one request, and `/metrics` says all of it when asked to.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.domain.providers import SearchCandidate, SourceRef
from book_tracker.infrastructure.observed import (
    ObservedProvider,
    ProviderObservations,
    ResponseCache,
)
from book_tracker.infrastructure.providers import ProviderPayloadError
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _candidate(title: str) -> SearchCandidate:
    return SearchCandidate(
        source="openlibrary",
        source_id="OL1M",
        source_refs=(SourceRef("openlibrary", "OL1M"),),
        title=title,
        subtitle=None,
        creators=("Julio Cortázar",),
        year=1963,
        cover_url=None,
        identifiers={"isbn13": "9788437604572"},
        language="es",
        metadata={"subjects": ["Novela"]},
    )


class Flaky:
    name = "openlibrary"
    item_type = "book"

    def __init__(self) -> None:
        self.failing = False
        self.searches = 0

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        self.searches += 1
        if self.failing:
            raise httpx.ConnectError("down")
        return [_candidate(query)]

    async def fetch(self, source_id: str):  # type: ignore[no-untyped-def]
        raise ProviderPayloadError("gone", code="record_not_found")


@pytest.mark.anyio
async def test_health_follows_the_last_calls_and_recovers() -> None:
    observations = ProviderObservations()
    flaky = Flaky()
    provider = ObservedProvider(flaky, observations)
    assert observations.state("openlibrary") == "working"

    flaky.failing = True
    for _ in range(3):
        with pytest.raises(httpx.ConnectError):
            await provider.search(f"q{_}")
    assert observations.state("openlibrary") == "down"

    flaky.failing = False
    for index in range(10):
        await provider.search(f"ok{index}")
    assert observations.state("openlibrary") == "working"


@pytest.mark.anyio
async def test_a_record_the_provider_does_not_have_is_not_an_outage() -> None:
    observations = ProviderObservations()
    provider = ObservedProvider(Flaky(), observations)
    for _ in range(5):
        with pytest.raises(ProviderPayloadError):
            await provider.fetch("missing")
    assert observations.state("openlibrary") == "working"


@pytest.mark.anyio
async def test_the_same_search_reaches_the_provider_once_within_a_day(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        clock = [datetime(2026, 10, 21, tzinfo=UTC)]
        cache = ResponseCache(app.state.engine, now=lambda: clock[0])
        flaky = Flaky()
        provider = ObservedProvider(flaky, ProviderObservations(), cache=cache)

        first = await provider.search("Rayuela")
        again = await provider.search("  rayuela ")
        assert flaky.searches == 1
        assert again == first

        await provider.search("Ficciones")
        assert flaky.searches == 2

        clock[0] += timedelta(hours=25)
        await provider.search("Rayuela")
        assert flaky.searches == 3

        flaky.failing = True
        with pytest.raises(httpx.ConnectError):
            await provider.search("Bestiario")
        flaky.failing = False
        await provider.search("Bestiario")
        assert flaky.searches == 5


@pytest.mark.anyio
async def test_health_reports_a_provider_that_stopped_answering(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        flaky = Flaky()
        flaky.failing = True
        provider = ObservedProvider(flaky, app.state.provider_observations)
        for index in range(3):
            with pytest.raises(httpx.ConnectError):
                await provider.search(f"q{index}")
        body = (await client.get("/api/health/providers")).json()
    row = next(row for row in body["providers"] if row["name"] == "openlibrary")
    assert row["available"] is True
    assert row["state"] == "down"
    assert body["degraded"] is True


@pytest.mark.anyio
async def test_metrics_answer_only_when_enabled(tmp_path: Path) -> None:
    off = create_app(Settings(data_dir=tmp_path / "off", user_agent_contact="t@example.invalid"))
    async with (
        off.router.lifespan_context(off),
        httpx.AsyncClient(transport=httpx.ASGITransport(off), base_url="http://test") as client,
    ):
        assert (await client.get("/metrics")).status_code == 404

    on = create_app(
        Settings(data_dir=tmp_path / "on", user_agent_contact="t@example.invalid", metrics="on")
    )
    async with (
        on.router.lifespan_context(on),
        httpx.AsyncClient(transport=httpx.ASGITransport(on), base_url="http://test") as client,
    ):
        await client.get("/api/entries")
        await ObservedProvider(Flaky(), on.state.provider_observations).search("Rayuela")
        response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    for family in (
        "akasha_job_queue_depth",
        "akasha_jobs",
        "akasha_provider_calls_total",
        "akasha_provider_call_seconds",
        "akasha_request_seconds",
    ):
        assert f"# TYPE {family}" in body, family
    assert 'akasha_provider_calls_total{provider="openlibrary",outcome="ok"} 1' in body
    assert 'route="/api/entries"' in body
