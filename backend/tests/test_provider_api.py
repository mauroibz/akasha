from pathlib import Path

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.domain.providers import SearchCandidate, SourceRef
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Provider:
    name = "openlibrary"
    item_type = "book"

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                source=self.name,
                source_id="OL1M",
                source_refs=(SourceRef(self.name, "OL1M"),),
                title=query,
                subtitle=None,
                authors=("Author",),
                year=2001,
                cover_url=None,
                identifiers={},
                language="es",
                metadata={},
            )
        ]

    async def fetch(self, source_id: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError


@pytest.mark.anyio
async def test_search_api_returns_typed_candidates(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": Provider()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/search", params={"q": "Rayuela"})
    assert response.status_code == 200
    assert response.json()[0]["source_refs"] == [{"source": "openlibrary", "source_id": "OL1M"}]


@pytest.mark.anyio
async def test_search_api_maps_all_provider_failure_and_invalid_resolution(tmp_path: Path) -> None:
    class Failed(Provider):
        async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
            raise httpx.TimeoutException("timeout")

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": Failed()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            failed = await client.get("/api/search", params={"q": "Rayuela"})
            invalid = await client.get(
                "/api/search/resolve", params={"url": "https://goodreads.com/book/1"}
            )
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "providers_unavailable"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_resolution"


@pytest.mark.anyio
async def test_search_api_announces_partial_provider_results(tmp_path: Path) -> None:
    class Failed(Provider):
        name = "googlebooks"

        async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
            raise httpx.TimeoutException("timeout")

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": Provider(), "googlebooks": Failed()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/search", params={"q": "Rayuela"})
    assert response.status_code == 200
    assert response.headers["X-Provider-Warning"] == "Some metadata providers are unavailable"
