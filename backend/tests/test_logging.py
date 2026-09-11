from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from book_tracker.application.passwords import hash_password
from book_tracker.config import Settings
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_each_acting_request_writes_one_minimal_audit_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", auth="on")
    )
    async with app.router.lifespan_context(app):
        admin = hash_password("admin private password")
        target = hash_password("target private password")
        with app.state.engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE users SET username='admin',display_name='Private Admin Name',"
                "password_hash=?,password_salt=? WHERE id=1",
                (admin.digest, admin.salt),
            )
            connection.exec_driver_sql(
                "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
                "created_at,updated_at) VALUES "
                "(2,'target','Private Target Name',?,?,0,'2026-09-10T00:00:00Z',"
                "'2026-09-10T00:00:00Z')",
                (target.digest, target.salt),
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin private password"},
            )
            await client.post("/api/auth/act-as/2")
            capsys.readouterr()
            response = await client.get(
                "/api/entries",
                params={"query": "private query words", "status": "unsorted"},
                headers={"cookie-probe": "private cookie words"},
            )
            assert response.status_code == 200

    lines = [
        json.loads(line) for line in capsys.readouterr().err.splitlines() if line.startswith("{")
    ]
    audit = [line for line in lines if line.get("event") == "admin_acting_request"]
    assert len(audit) == 1
    assert audit[0]["admin_user_id"] == 1
    assert audit[0]["acting_as_user_id"] == 2
    assert audit[0]["method"] == "GET"
    assert audit[0]["route"] == "/api/entries"
    rendered = json.dumps(audit[0])
    for private in (
        "Private Admin Name",
        "Private Target Name",
        "private query words",
        "private cookie words",
        "admin private password",
        "target private password",
    ):
        assert private not in rendered
