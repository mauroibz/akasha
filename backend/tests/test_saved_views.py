"""Saved views (Sprint 100, DEC-139): a library filter kept under a name.

A view is the library's own query string, so it reopens exactly what was on screen,
and it belongs to the person who saved it.
"""

from pathlib import Path

import httpx
import pytest
from alembic import command

from book_tracker.application.library import LibraryError, LibraryService
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.main import create_app
from book_tracker.migrations import alembic_config, upgrade


@pytest.fixture
def engine(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert settings.database_url is not None
    upgrade(settings.database_url)
    value = create_engine(settings)
    yield value
    value.dispose()


def test_a_view_is_saved_listed_renamed_by_saving_again_and_deleted(engine) -> None:  # type: ignore[no-untyped-def]
    library = LibraryService(engine, 1)
    first = library.save_view("Unread Spanish novels", "type=book&status=to_read&q=novela")
    assert library.list_views() == [first]
    again = library.save_view("Unread Spanish novels", "type=book&status=to_read")
    assert again["id"] == first["id"] and again["query"] == "type=book&status=to_read"
    library.save_view("Vinyl", "type=album&format=vinyl")
    assert [view["name"] for view in library.list_views()] == ["Unread Spanish novels", "Vinyl"]
    library.delete_view(first["id"])
    assert [view["name"] for view in library.list_views()] == ["Vinyl"]


def test_a_view_needs_a_name_and_belongs_to_one_person(engine) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(LibraryError):
        LibraryService(engine, 1).save_view("  ", "type=book")
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,username,is_admin,created_at,updated_at) "
                "VALUES (2,'other',0,'n','n')"
            )
        )
    mine = LibraryService(engine, 1).save_view("Mine", "type=book")
    assert LibraryService(engine, 2).list_views() == []
    with pytest.raises(LibraryError) as refused:
        LibraryService(engine, 2).delete_view(mine["id"])
    assert refused.value.status_code == 404


def test_the_migration_reverses(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert settings.database_url is not None
    config = alembic_config(settings.database_url)
    command.upgrade(config, "head")
    command.downgrade(config, "0023_entry_search")
    command.upgrade(config, "head")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_views_routes(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        created = await client.post("/api/views", json={"name": "Vinyl", "query": "type=album"})
        assert created.status_code == 201
        listed = await client.get("/api/views")
        assert [view["name"] for view in listed.json()] == ["Vinyl"]
        deleted = await client.delete(f"/api/views/{created.json()['id']}")
        assert deleted.status_code == 204
        assert (await client.get("/api/views")).json() == []
