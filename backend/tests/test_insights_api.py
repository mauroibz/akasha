"""Sprint 065: `GET /api/insights` over HTTP — validation and the zero-score case.

Same fixture shape as `test_library_api.py`: a real app via `create_app`'s lifespan,
`DomainRepository` to seed, `httpx.AsyncClient` against the ASGI app directly.
"""

from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_a_groupable_key_ranks_over_http(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        entry = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET status='read' WHERE id=:id"), {"id": entry.entry_id}
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/insights", params={"type": "book", "key": "creators", "metric": "count"}
            )
    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == [
        {
            "key": "julio cortazar",
            "label": "Julio Cortázar",
            "count": 1,
            "rated_count": 0,
            "mean_score": None,
            "score_spread": None,
        }
    ]


@pytest.mark.anyio
async def test_an_unknown_domain_type_is_a_422(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get(
            "/api/insights", params={"type": "boardgame", "key": "creators"}
        )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_a_key_the_domain_does_not_declare_groupable_is_a_422_naming_the_domain(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/insights", params={"type": "book", "key": "description"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_insight_key"
    assert "Book" in body["error"]["message"]


@pytest.mark.anyio
async def test_a_zero_score_domain_reports_no_rated_groups_over_http(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        entry = repository.create_or_get_entry(title="Unrated", creators=("Nobody Rated",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET status='read' WHERE id=:id"), {"id": entry.entry_id}
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            count_response = await client.get(
                "/api/insights", params={"type": "book", "key": "creators", "metric": "count"}
            )
            score_response = await client.get(
                "/api/insights", params={"type": "book", "key": "creators", "metric": "score"}
            )
    assert count_response.json()["rows"]
    assert score_response.json()["rows"] == []
    assert score_response.json()["no_rated_groups"] is True


@pytest.mark.anyio
async def test_item_types_publishes_which_fields_are_groupable(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/item-types")
    book = next(domain for domain in response.json() if domain["id"] == "book")
    fields = {field["name"]: field["groupable"] for field in book["fields"]}
    assert fields["creators"] is True
    assert fields["description"] is False
