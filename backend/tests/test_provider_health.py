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
    # In the order each domain prefers its sources, domains in registry order, rather
    # than in an order this endpoint decides for itself (DEC-067 row 5).
    assert body["providers"] == [
        {"name": "openlibrary", "available": True, "reason": None},
        {
            "name": "googlebooks",
            "available": False,
            "reason": "GOOGLE_BOOKS_API_KEY is not set",
        },
        # The album provider needs no key, so it is available wherever it is wired.
        {"name": "musicbrainz", "available": True, "reason": None},
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
        "googlebooks",
        "musicbrainz",
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


@pytest.mark.anyio
async def test_the_rows_are_derived_from_the_registry_not_from_a_list_of_names(
    tmp_path: Path,
) -> None:
    """A domain's provider appears here without the endpoint learning its name.

    `provider_health` used to spell `openlibrary`, `musicbrainz` and `googlebooks` as
    literals, so a third domain's provider was invisible until somebody remembered to
    add a fourth row (DEC-067 row 5). Shared infrastructure does not name a provider:
    the order comes from each domain's source preference, and the rows from the catalog
    the lifespan built.
    """

    class Stub:
        name = "igdb"
        item_type = "game"
        enabled = False
        unavailable_reason = "IGDB_CLIENT_ID is not set"

    app = create_app(settings(tmp_path, key="test-key"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.provider_catalog = {**app.state.provider_catalog, "igdb": Stub()}
        response = await client.get("/api/health/providers")

    body = response.json()
    assert body["degraded"] is True
    assert {
        "name": "igdb",
        "available": False,
        "reason": "IGDB_CLIENT_ID is not set",
    } in body["providers"]


@pytest.mark.anyio
async def test_the_rows_follow_the_order_each_domain_prefers(tmp_path: Path) -> None:
    """Open Library before Google Books is books' own preference (product spec 4.3)."""
    app = create_app(settings(tmp_path, key="test-key"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/health/providers")

    assert [row["name"] for row in response.json()["providers"]] == [
        "openlibrary",
        "googlebooks",
        "musicbrainz",
    ]
