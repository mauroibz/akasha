"""Provider configuration is visible instead of silently halving search."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def settings(tmp_path: Path, key: str = "") -> Settings:
    # The field is populated through its environment alias, not its Python name.
    return Settings(
        data_dir=tmp_path,
        USER_AGENT_CONTACT="test@example.invalid",
        GOOGLE_BOOKS_API_KEY=key,
    )


@pytest.mark.anyio
async def test_missing_google_key_warns_at_startup_and_reports_a_degraded_provider(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app(settings(tmp_path))
    with caplog.at_level(logging.WARNING):
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            response = await client.get("/api/health/providers")

    assert "GOOGLE_BOOKS_API_KEY" in caplog.text
    body = response.json()
    assert response.status_code == 200
    assert body["degraded"] is True
    assert body["providers"] == [
        {"name": "openlibrary", "available": True, "reason": None},
        # The album provider needs no key, so it is available wherever it is wired.
        {"name": "musicbrainz", "available": True, "reason": None},
        {
            "name": "googlebooks",
            "available": False,
            "reason": "GOOGLE_BOOKS_API_KEY is not set",
        },
    ]


@pytest.mark.anyio
async def test_a_configured_key_reports_every_provider_available(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path, key="test-key"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/health/providers")

    body = response.json()
    assert body["degraded"] is False
    assert [row["name"] for row in body["providers"]] == [
        "openlibrary",
        "musicbrainz",
        "googlebooks",
    ]
    assert all(row["available"] for row in body["providers"])


@pytest.mark.anyio
async def test_readiness_stays_about_the_database_not_the_providers(tmp_path: Path) -> None:
    """Technical spec 8: readiness must not depend on public provider availability."""
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        assert (await client.get("/api/health/ready")).status_code == 200


@pytest.mark.anyio
async def test_search_still_answers_from_one_provider_when_the_other_is_absent(
    tmp_path: Path,
) -> None:
    from recordings import recording, replay

    from book_tracker.infrastructure.providers import OpenLibraryProvider, create_provider_client

    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        transport = replay({"/search.json": (200, recording("search_rayuela.json"))})
        async with create_provider_client(transport=transport) as provider_client:
            app.state.providers = {
                "openlibrary": OpenLibraryProvider(provider_client, "test@example.invalid")
            }
            response = await client.get("/api/search", params={"q": "Rayuela Cortázar"})

    assert response.status_code == 200
    assert response.json()
