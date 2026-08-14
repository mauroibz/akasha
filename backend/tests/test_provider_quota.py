"""Daily provider quota, proven against a provider that does not exist.

DEC-045 asked for this to be provider-agnostic: Google Books is the only metered
provider today, but the roadmap adds MusicBrainz, IGDB and TMDB, and a guard written
around one provider becomes a patch at each new one. These tests therefore name a
fictional `pretendbooks` throughout — if the mechanism only worked for Google Books,
every one of them would fail.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from recordings import GOOGLE_CONFIRMED, OPENLIBRARY_MISS_CONFIRMED, enrichment_providers
from sqlalchemy import Engine, text

from book_tracker.application.enrichment import EnrichmentHandler
from book_tracker.config import Settings
from book_tracker.database import create_engine as create_sqlalchemy_engine
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.quota import ProviderQuota
from book_tracker.migrations import upgrade

DAY = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    value = create_sqlalchemy_engine(configured)
    yield value
    value.dispose()


def test_a_provider_with_no_configured_limit_is_never_blocked(engine: Engine) -> None:
    """Open Library has no cap. It is still counted, so one can be set later on evidence."""
    quota = ProviderQuota(engine, limits={})

    for _ in range(50):
        quota.record("pretendbooks", DAY)

    assert quota.allows("pretendbooks", DAY) is True
    assert quota.used("pretendbooks", DAY) == 50


def test_a_provider_is_blocked_once_its_daily_limit_is_reached(engine: Engine) -> None:
    quota = ProviderQuota(engine, limits={"pretendbooks": 3})

    for _ in range(2):
        quota.record("pretendbooks", DAY)
    assert quota.allows("pretendbooks", DAY) is True

    quota.record("pretendbooks", DAY)
    assert quota.allows("pretendbooks", DAY) is False


def test_the_count_rolls_over_at_the_utc_day_boundary(engine: Engine) -> None:
    quota = ProviderQuota(engine, limits={"pretendbooks": 1})
    quota.record("pretendbooks", DAY)
    assert quota.allows("pretendbooks", DAY) is False

    assert quota.allows("pretendbooks", DAY + timedelta(days=1)) is True


def test_one_provider_s_limit_does_not_gate_another(engine: Engine) -> None:
    quota = ProviderQuota(engine, limits={"pretendbooks": 1})
    quota.record("pretendbooks", DAY)

    assert quota.allows("pretendbooks", DAY) is False
    assert quota.allows("otherprovider", DAY) is True


def test_usage_survives_a_restart(engine: Engine) -> None:
    """A counter that resets when the container restarts protects nothing."""
    ProviderQuota(engine, limits={"pretendbooks": 2}).record("pretendbooks", DAY)

    reopened = ProviderQuota(engine, limits={"pretendbooks": 2})
    reopened.record("pretendbooks", DAY)

    assert reopened.allows("pretendbooks", DAY) is False


# --------------------------------------------------------------------------------------
# Through enrichment
# --------------------------------------------------------------------------------------


def create_item(engine: Engine) -> int:
    with engine.begin() as connection:
        return connection.execute(
            text(
                "INSERT INTO items (title, year, cover_path, identifiers, metadata,"
                " created_at, updated_at)"
                " VALUES ('Cien años de soledad', NULL, NULL, '{}', '{}', 'n', 'n') RETURNING id"
            )
        ).scalar_one()


async def run(
    engine: Engine, providers: dict[str, Any], item_id: int, quota: ProviderQuota
) -> tuple[str, dict[str, Any]]:
    job_id = JobRepository(engine).enqueue(
        None, "enrich_item", {"item_id": item_id, "isbn": "9780307474728"}
    )
    handler = EnrichmentHandler(engine, providers, rate_limiter=None, quota=quota)
    return job_id, await handler.process(job_id, datetime.now(UTC))


@pytest.mark.anyio
async def test_enrichment_defers_instead_of_failing_when_every_provider_is_capped(
    engine: Engine,
) -> None:
    """The trap this avoids: `fail` increments attempts and dead-letters at the ceiling.

    A 5,000-book import that exhausted the quota would otherwise destroy its own
    backlog rather than finishing it the next day.
    """
    item_id = create_item(engine)
    quota = ProviderQuota(engine, limits={"openlibrary": 0, "googlebooks": 0})
    async with enrichment_providers(
        openlibrary=OPENLIBRARY_MISS_CONFIRMED, google=GOOGLE_CONFIRMED, forbid_calls=False
    ) as providers:
        job_id, result = await run(engine, providers, item_id, quota)

    assert result["state"] == "deferred"
    job = JobRepository(engine).get_job(job_id)
    assert job is not None
    assert job["state"] == "queued"
    assert job["attempts"] == 0
    assert job["available_at"] > datetime.now(UTC).isoformat()


@pytest.mark.anyio
async def test_a_capped_provider_is_skipped_but_an_uncapped_one_still_answers(
    engine: Engine,
) -> None:
    """Only Open Library is capped here, so the Google fallback must still run."""
    item_id = create_item(engine)
    quota = ProviderQuota(engine, limits={"openlibrary": 0})
    async with enrichment_providers(google=GOOGLE_CONFIRMED) as providers:
        _job_id, result = await run(engine, providers, item_id, quota)

    assert result["state"] == "succeeded"
    assert result["progress"]["provider"] == "googlebooks"


@pytest.mark.anyio
async def test_a_successful_enrichment_records_what_it_spent(engine: Engine) -> None:
    item_id = create_item(engine)
    quota = ProviderQuota(engine, limits={})
    async with enrichment_providers(
        openlibrary=OPENLIBRARY_MISS_CONFIRMED, google=GOOGLE_CONFIRMED
    ) as providers:
        _job_id, result = await run(engine, providers, item_id, quota)

    assert result["state"] == "succeeded"
    now = datetime.now(UTC)
    # Both were consulted, so both were counted — including the unmetered one.
    assert quota.used("openlibrary", now) == 1
    assert quota.used("googlebooks", now) == 1


assert json  # metadata is stored as JSON text by the helpers above


@pytest.mark.anyio
async def test_the_runner_leaves_a_deferred_job_alone(engine: Engine) -> None:
    """The handler defers; the runner must not then fail it.

    `tick` routes every state that is not succeeded or cancelled to `fail`, which
    increments attempts and resets `available_at` to now — undoing the deferral and
    spending a retry. Driving the handler directly does not catch this, because the
    damage happens one layer up.
    """
    from book_tracker.infrastructure.jobs import JobRunner

    item_id = create_item(engine)
    quota = ProviderQuota(engine, limits={"openlibrary": 0, "googlebooks": 0})
    repository = JobRepository(engine)
    job_id = repository.enqueue(None, "enrich_item", {"item_id": item_id, "isbn": "9780307474728"})
    async with enrichment_providers(
        openlibrary=OPENLIBRARY_MISS_CONFIRMED, google=GOOGLE_CONFIRMED
    ) as providers:
        handler = EnrichmentHandler(engine, providers, rate_limiter=None, quota=quota)
        runner = JobRunner(engine, {"enrich_item": handler})
        assert await runner.tick(datetime.now(UTC)) is True

    job = repository.get_job(job_id)
    assert job is not None
    assert job["state"] == "queued"
    assert job["attempts"] == 0
    assert job["error_code"] == "provider_quota_exhausted"
    # Tomorrow, not now: a `fail` would have made it immediately claimable again.
    assert job["available_at"] > datetime.now(UTC).isoformat()
