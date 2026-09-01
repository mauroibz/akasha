"""Sprint 060, deliverable 4: a write that cannot complete is refused before it
starts.

Filling a real disk to test this would be its own small disaster; every test here
injects the free-space reading at the one seam that produces it
(`shutil.disk_usage`, wrapped by `infrastructure.diskspace.free_bytes`) rather than
writing gigabytes to force a real ENOSPC.
"""

from pathlib import Path
from typing import Any

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.infrastructure.diskspace import InsufficientDiskSpace, ensure_free_space
from book_tracker.main import create_app


def test_ensure_free_space_passes_above_the_minimum(tmp_path: Path) -> None:
    ensure_free_space(tmp_path, 1)  # 1 byte free is not a real constraint


def test_ensure_free_space_refuses_below_the_minimum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("book_tracker.infrastructure.diskspace.free_bytes", lambda _path: 100)

    with pytest.raises(InsufficientDiskSpace) as caught:
        ensure_free_space(tmp_path, 1000)

    assert caught.value.free_bytes == 100
    assert caught.value.minimum_bytes == 1000


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app(tmp_path: Path) -> Any:
    return create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid")
    )


@pytest.mark.anyio
async def test_an_attachment_upload_is_refused_below_the_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        created = await client.post(
            "/api/entries",
            json={
                "manual": {"item_type": "book", "title": "Disk Guard", "metadata": {}},
                "status": "read",
                "idempotency_key": "disk-guard-drill",
            },
        )
        item_id = created.json()["entry"]["item_id"]

        monkeypatch.setattr("book_tracker.infrastructure.diskspace.free_bytes", lambda _path: 0)
        response = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("note.txt", b"hello", "text/plain")},
        )

    assert response.status_code == 507, response.text
    body = response.json()["error"]
    assert body["code"] == "insufficient_disk_space"
    assert "free_bytes" in body["details"]


@pytest.mark.anyio
async def test_an_import_preview_is_refused_below_the_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        monkeypatch.setattr("book_tracker.infrastructure.diskspace.free_bytes", lambda _path: 0)
        response = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("library.csv", b"Book Id,Title\n", "text/csv")},
        )

    assert response.status_code == 507, response.text
    assert response.json()["error"]["code"] == "insufficient_disk_space"


@pytest.mark.anyio
async def test_readiness_reports_low_disk_without_going_unready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC8: a full disk can still read, so /api/health/ready must stay 200 — the
    same shape /api/health/providers already uses for a degraded-but-serving
    condition."""
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        monkeypatch.setattr("book_tracker.main.free_bytes", lambda _path: 0)
        response = await client.get("/api/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["disk"] == {"free_bytes": 0, "low": True}


def test_a_backup_is_refused_before_writing_anything_below_the_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from book_tracker.backup import create_backup
    from book_tracker.database import create_engine
    from book_tracker.migrations import upgrade

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    settings = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert settings.database_url is not None
    upgrade(settings.database_url)
    create_engine(settings).dispose()

    dest = tmp_path / "backups"
    monkeypatch.setattr("book_tracker.infrastructure.diskspace.free_bytes", lambda _path: 0)

    with pytest.raises(InsufficientDiskSpace):
        create_backup(
            database_path=data_dir / "books.db",
            data_dir=data_dir,
            dest=dest,
            min_free_bytes=1000,
        )

    # Nothing partial left behind: the check runs before the backup directory
    # (beyond dest itself) is ever created.
    assert list(dest.iterdir()) == []
