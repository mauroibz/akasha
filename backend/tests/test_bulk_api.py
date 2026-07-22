from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_bulk_explicit_ids_and_filter_exclusions_are_atomic(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        entries = [repository.create_or_get_entry(title=f"Book {index}") for index in range(3)]
        with app.state.engine.begin() as connection:
            connection.execute(text("UPDATE entries SET suggested_status='read'"))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            explicit = await client.patch(
                "/api/entries/bulk",
                json={"entry_ids": [entries[0].entry_id], "set": {"status": "reading"}},
            )
            assert explicit.status_code == 200
            assert explicit.json() == {"affected": 1}

            filtered = await client.patch(
                "/api/entries/bulk",
                json={
                    "filter": {"status": ["unsorted"]},
                    "excluded_entry_ids": [entries[2].entry_id],
                    "set": {"status": "to_read", "score": 7},
                },
            )
            assert filtered.status_code == 200
            assert filtered.json() == {"affected": 1}
            assert (await client.get(f"/api/entries/{entries[1].entry_id}")).json()["score"] == 7
            assert (await client.get(f"/api/entries/{entries[2].entry_id}")).json()[
                "status"
            ] == "unsorted"

            invalid = await client.patch(
                "/api/entries/bulk",
                json={
                    "entry_ids": [entries[0].entry_id],
                    "filter": {"status": ["reading"]},
                    "set": {"status": "read"},
                },
            )
            assert invalid.status_code == 422

            rollback = await client.patch(
                "/api/entries/bulk",
                json={
                    "entry_ids": [entries[0].entry_id],
                    "set": {"status": "dropped", "add_shelves": [999]},
                },
            )
            assert rollback.status_code == 404
            assert (await client.get(f"/api/entries/{entries[0].entry_id}")).json()[
                "status"
            ] == "reading"


@pytest.mark.anyio
async def test_accept_suggested_uses_filter_and_static_routes_are_not_shadowed(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        one = repository.create_or_get_entry(title="One")
        two = repository.create_or_get_entry(title="Two")
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET suggested_status='read' WHERE id=:id"),
                {"id": one.entry_id},
            )
            connection.execute(
                text("UPDATE entries SET suggested_status='reading' WHERE id=:id"),
                {"id": two.entry_id},
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            accepted = await client.post(
                "/api/entries/accept-suggested", json={"filter": {"q": "one"}}
            )
            assert accepted.status_code == 200
            assert accepted.json() == {"affected": 1}
            assert (await client.get(f"/api/entries/{one.entry_id}")).json()["status"] == "read"
            assert (await client.get(f"/api/entries/{two.entry_id}")).json()["status"] == "unsorted"
