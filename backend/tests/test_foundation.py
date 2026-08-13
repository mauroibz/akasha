from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.main import create_app


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_factory_has_no_filesystem_side_effects(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))

    assert app is not None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_live_health_never_opens_database(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        database = tmp_path / "books.db"
        database.unlink()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}
    assert not database.exists()


@pytest.mark.anyio
async def test_ready_health_reports_migrated_database(tmp_path: Path) -> None:
    configured = settings(tmp_path)
    app = create_app(configured)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.anyio
async def test_ready_health_reports_unavailable_database(tmp_path: Path) -> None:
    configured = settings(tmp_path)
    configured.database_url = "sqlite:////proc/unavailable/books.db"
    app = create_app(configured)
    app.state.skip_migrations = True
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


@pytest.mark.anyio
async def test_ready_health_reports_unmigrated_database(tmp_path: Path) -> None:
    configured = settings(tmp_path)
    engine = create_engine(configured)
    with engine.begin() as connection:
        connection.execute(text("SELECT 1"))
    engine.dispose()

    app = create_app(configured)
    app.state.skip_migrations = True
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "schema_not_current"


def test_database_connections_apply_sqlite_pragmas(tmp_path: Path) -> None:
    configured = settings(tmp_path)
    configured.sqlite_busy_timeout_ms = 4321
    engine = create_engine(configured)

    with engine.connect() as connection:
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
        busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()

    assert foreign_keys == 1
    assert journal_mode == "wal"
    assert busy_timeout == 4321


@pytest.mark.anyio
async def test_spa_fallback_does_not_capture_api_routes(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<main>Akasha SPA</main>", encoding="utf-8")
    configured = settings(tmp_path / "data")
    configured.static_dir = static_dir

    app = create_app(configured)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        frontend = await client.get("/books/123")
        missing_api = await client.get("/api/missing")

    assert frontend.status_code == 200
    assert "Akasha SPA" in frontend.text
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")


def test_backup_dir_defaults_beside_the_data_directory(tmp_path: Path) -> None:
    """The container mounts `/data` and `/backups` as siblings, so derive rather than hardcode.

    A backup written inside the volume it backs up dies with that volume (DEC-040).
    """
    configured = Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid")

    assert configured.backup_dir == tmp_path / "backups"
    assert Settings(data_dir=Path("/data"), user_agent_contact="x@y.invalid").backup_dir == Path(
        "/backups"
    )


def test_backup_dir_is_overridable(tmp_path: Path) -> None:
    configured = Settings(
        data_dir=tmp_path,
        backup_dir=tmp_path / "elsewhere",
        user_agent_contact="test@example.invalid",
    )

    assert configured.backup_dir == tmp_path / "elsewhere"
