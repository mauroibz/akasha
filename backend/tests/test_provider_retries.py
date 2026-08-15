"""Surviving a provider that is temporarily unwell.

Open Library's JSON API answers 503 under load, repeatedly and for minutes at a time,
while their website stays up. Sprint 020's walkthrough ran into it throughout, and two
things made it worse than it had to be:

* nothing retried a request that failed transiently; and
* `JobRepository.fail` scheduled its retry for *now*, so an enrichment job spent all
  three of its attempts within a few seconds of the outage starting and then
  dead-lettered permanently. A five-minute outage meant those books were never enriched
  again.

Retries alone would not have fixed the second one, which is the more damaging.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from recordings import recording, redirect_location
from sqlalchemy import Engine

from book_tracker.domains.book.providers import OpenLibraryProvider
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.providers import (
    PROVIDER_ATTEMPTS,
    ProviderPayloadError,
    create_provider_client,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def engine(tmp_path):  # type: ignore[no-untyped-def]
    from book_tracker.config import Settings
    from book_tracker.database import create_engine as create_sqlalchemy_engine
    from book_tracker.migrations import upgrade

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    value = create_sqlalchemy_engine(configured)
    yield value
    value.dispose()


def flaky(statuses: list[int], body: object) -> tuple[httpx.MockTransport, list[int]]:
    """A transport that answers with each status in turn, then serves the body."""
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        index = len(calls)
        calls.append(index)
        if index < len(statuses):
            return httpx.Response(statuses[index], json={"error": "unavailable"})
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler), calls


@pytest.mark.anyio
async def test_a_transient_503_is_retried_and_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def no_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("book_tracker.infrastructure.providers.asyncio.sleep", no_sleep)
    transport, calls = flaky([503, 503], recording("work_OL14860424W.json"))

    async with create_provider_client(transport=transport) as client:
        body = await OpenLibraryProvider(client, "t@e.invalid")._json(
            "https://openlibrary.org/works/OL14860424W.json"
        )

    assert body["title"]
    assert len(calls) == 3
    # Backing off rather than hammering a service that is already struggling.
    assert slept == sorted(slept)
    assert all(delay > 0 for delay in slept)


@pytest.mark.anyio
async def test_retries_are_bounded_and_the_typed_error_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("book_tracker.infrastructure.providers.asyncio.sleep", no_sleep)
    transport, calls = flaky([503] * 10, {})

    async with create_provider_client(transport=transport) as client:
        with pytest.raises(ProviderPayloadError) as caught:
            await OpenLibraryProvider(client, "t@e.invalid").fetch_by_isbn("9788437604572")

    assert len(calls) == PROVIDER_ATTEMPTS
    assert caught.value.code == "provider_http_error"


@pytest.mark.anyio
async def test_a_404_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not found is an answer. Retrying it wastes the provider's time and ours."""

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("book_tracker.infrastructure.providers.asyncio.sleep", no_sleep)
    transport, calls = flaky([404] * 5, {})

    async with create_provider_client(transport=transport) as client:
        with pytest.raises(ProviderPayloadError) as caught:
            await OpenLibraryProvider(client, "t@e.invalid").fetch_by_isbn("9788437604572")

    assert len(calls) == 1
    assert caught.value.code == "edition_not_found"


@pytest.mark.anyio
async def test_retry_after_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider that says how long to wait is telling us something useful."""
    slept: list[float] = []

    async def no_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("book_tracker.infrastructure.providers.asyncio.sleep", no_sleep)

    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(len(calls))
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "2"}, json={})
        return httpx.Response(200, json=recording("work_OL14860424W.json"))

    async with create_provider_client(transport=httpx.MockTransport(handler)) as client:
        await OpenLibraryProvider(client, "t@e.invalid")._json(
            "https://openlibrary.org/works/OL14860424W.json"
        )

    assert slept == [2.0]


def test_a_failed_job_backs_off_instead_of_retrying_immediately(engine: Engine) -> None:
    """The damaging half of the outage.

    `available_at = now` meant three attempts inside a few seconds, so a provider that
    was down for minutes dead-lettered every job it touched. The retry is now scheduled
    into the future and the gap grows with each attempt.
    """
    repository = JobRepository(engine)
    job_id = repository.enqueue(None, "enrich_item", {"item_id": 1, "isbn": "9788437604572"})
    now = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    repository.fail(job_id, "Open Library could not be reached", now, code="provider_unreachable")
    first = repository.get_job(job_id)
    assert first is not None
    assert first["state"] == "queued"
    assert first["available_at"] > now.isoformat()

    repository.fail(job_id, "again", now, code="provider_unreachable")
    second = repository.get_job(job_id)
    assert second is not None
    assert second["available_at"] > first["available_at"]


def test_a_job_still_dead_letters_eventually(engine: Engine) -> None:
    """Backing off must not turn a genuinely broken job into an immortal one."""
    repository = JobRepository(engine)
    job_id = repository.enqueue(None, "enrich_item", {"item_id": 1, "isbn": "9788437604572"})
    now = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    for _ in range(3):
        repository.fail(job_id, "nope", now, code="provider_unreachable")

    job = repository.get_job(job_id)
    assert job is not None
    assert job["state"] == "failed"


assert redirect_location  # kept for parity with the other provider suites
assert timedelta


@pytest.mark.anyio
async def test_search_is_never_retried_because_someone_is_waiting_on_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The UX split, pinned so it cannot drift back.

    A batch import can take as long as it needs; the moment-to-moment experience must
    not pay for a provider's bad day. Search already has a five-second budget and the
    other provider's results still render, so a second attempt returns nothing sooner
    and nothing better — it just spends the budget.
    """
    slept: list[float] = []

    async def no_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("book_tracker.infrastructure.providers.asyncio.sleep", no_sleep)
    transport, calls = flaky([503] * 5, {"docs": []})

    async with create_provider_client(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await OpenLibraryProvider(client, "t@e.invalid").search("rayuela")

    assert len(calls) == 1
    assert slept == []


@pytest.mark.anyio
async def test_background_enrichment_is_allowed_to_be_patient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of the same split: nobody is watching an enrichment job."""
    slept: list[float] = []

    async def no_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("book_tracker.infrastructure.providers.asyncio.sleep", no_sleep)
    transport, calls = flaky([503] * 10, {})

    async with create_provider_client(transport=transport) as client:
        with pytest.raises(ProviderPayloadError):
            await OpenLibraryProvider(client, "t@e.invalid").fetch_by_isbn("9788437604572")

    assert len(calls) == PROVIDER_ATTEMPTS
    assert len(slept) == PROVIDER_ATTEMPTS - 1
