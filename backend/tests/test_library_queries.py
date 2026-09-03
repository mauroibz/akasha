"""Sprint 065 deliverable 7: `/api/entries` gains a precise `key`/`value` filter.

A new file, not an extension of `test_library_api.py` — the sprint doc names
`test_library_queries.py` as though it already existed, but it didn't; this is the
first thing in it. Covers the shared mechanism with `test_insights.py`'s `rank()`
(AC8: a ranking row must show *exactly* the entries behind its number).
"""

from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.application.library import LibraryError, LibraryService
from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_key_value_returns_exactly_the_ranked_members(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        cortazar_1 = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        cortazar_2 = repository.create_or_get_entry(
            title="Bestiario", creators=("julio cortazar", "Someone Else")
        )
        other = repository.create_or_get_entry(title="Other", creators=("Someone Else",))
        with app.state.engine.begin() as connection:
            for entry in (cortazar_1, cortazar_2, other):
                connection.execute(
                    text("UPDATE entries SET status='read' WHERE id=:id"), {"id": entry.entry_id}
                )

        service = LibraryService(app.state.engine)
        ranked = service.rank(item_type="book", key="creators", metric="count")
        cortazar_row = next(row for row in ranked["rows"] if row["key"] == "julio cortazar")

        filtered = service.list_entries(types=["book"], key="creators", value="julio cortazar")

        titles = {item["item"]["title"] for item in filtered["items"]}
        assert titles == {"Rayuela", "Bestiario"}
        assert len(filtered["items"]) == cortazar_row["count"]


@pytest.mark.anyio
async def test_key_value_filters_over_http(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        match = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        other = repository.create_or_get_entry(title="Other", creators=("Someone Else",))
        with app.state.engine.begin() as connection:
            for entry in (match, other):
                connection.execute(
                    text("UPDATE entries SET status='read' WHERE id=:id"), {"id": entry.entry_id}
                )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/entries",
                params={"type": "book", "key": "creators", "value": "julio cortazar"},
            )
    assert response.status_code == 200
    titles = [item["item"]["title"] for item in response.json()["items"]]
    assert titles == ["Rayuela"]


@pytest.mark.anyio
async def test_key_requires_exactly_one_type(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        service = LibraryService(app.state.engine)
        with pytest.raises(LibraryError) as refused:
            service.list_entries(types=[], key="creators", value="x")
    assert refused.value.status_code == 422


@pytest.mark.anyio
async def test_an_undeclared_key_is_refused(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        service = LibraryService(app.state.engine)
        with pytest.raises(LibraryError) as refused:
            service.list_entries(types=["book"], key="description", value="x")
    assert refused.value.code == "invalid_insight_key"
