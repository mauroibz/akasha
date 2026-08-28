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
    rows = {row["name"]: row for row in body["providers"]}
    # The one provider that needs configuration says so, by name and with the reason.
    assert rows["googlebooks"] == {
        "name": "googlebooks",
        "available": False,
        "reason": "GOOGLE_BOOKS_API_KEY is not set",
    }
    # Every other wired provider needs no key, so it is available. Asserted over the
    # catalog rather than over a literal list: this test used to enumerate the three
    # providers of the day, so registering a third domain's two adapters failed it for
    # no behavioural reason. That is the same defect `test_item_types.py` was repaired
    # for when the guide was proved by following it (DEC-070), one layer down.
    assert rows.keys() == set(app.state.provider_catalog)
    assert all(row["available"] for name, row in rows.items() if name != "googlebooks")


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
    # Every provider this build wires, and nothing this endpoint decided for itself.
    assert {row["name"] for row in body["providers"]} == set(app.state.provider_catalog)
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

    from book_tracker.domains.book.providers import OpenLibraryProvider
    from book_tracker.infrastructure.providers import create_provider_client

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
    """Open Library before Google Books is books' own preference (product spec 4.3).

    Checked as *relative* order per domain, derived from each domain's declared
    `source_preference`, rather than as one literal list. A list is a snapshot of which
    domains happened to be registered on the day it was written, which is exactly what
    made this test fail when a third domain arrived without changing any behaviour.
    """
    from book_tracker.domain.registry import DOMAINS

    app = create_app(settings(tmp_path, key="test-key"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/health/providers")

    order = [row["name"] for row in response.json()["providers"]]
    assert order, "the endpoint published no providers at all"
    for domain in DOMAINS.values():
        wired = [name for name in domain.identity.source_preference if name in order]
        positions = [order.index(name) for name in wired]
        assert positions == sorted(positions), (
            f"{domain.item_type}'s providers are not in the order it prefers them"
        )
