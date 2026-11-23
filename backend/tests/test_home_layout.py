"""Home's stored layout (Sprint 131, DEC-183): order, size and hidden, per person.

`GET /api/home/layout` and `PUT /api/home/layout`; migration 0036 stores it. A key the
server does not know is ignored on read and refused on write, and a module the stored
layout does not name is appended with its default, so a layout saved before a module
was added or removed still loads.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text

from book_tracker.api.auth import COOKIE_NAME
from book_tracker.application.home_layout import DEFAULT_LAYOUT, MODULES, defaults
from book_tracker.application.passwords import hash_password
from book_tracker.application.sessions import SessionStore
from book_tracker.config import Settings
from book_tracker.main import create_app
from book_tracker.migrations import alembic_config, upgrade


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@asynccontextmanager
async def _client(tmp_path: Path, **extra: Any) -> AsyncIterator[tuple[Any, httpx.AsyncClient]]:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", **extra)
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        yield app, client


def _defaults() -> list[dict[str, Any]]:
    """The default for a person with no shelves: the fixed modules and each library's year."""
    return [dict(row) for row in defaults()]


def _keys() -> list[str]:
    return [row["module"] for row in defaults()]


def test_the_default_names_every_module_once() -> None:
    assert [row["module"] for row in DEFAULT_LAYOUT] == list(MODULES)
    assert set(MODULES) >= {"now", "next", "year", "libraries", "lately", "tidy"}
    assert all(row["size"] in {"S", "M", "L"} and row["hidden"] is False for row in DEFAULT_LAYOUT)


@pytest.mark.anyio
async def test_a_person_with_no_stored_layout_reads_the_default(tmp_path: Path) -> None:
    async with _client(tmp_path) as (_app, client):
        response = await client.get("/api/home/layout")
    assert response.status_code == 200
    assert response.json() == {"modules": _defaults(), "defaults": _defaults()}


@pytest.mark.anyio
async def test_a_saved_layout_reads_back_as_saved(tmp_path: Path) -> None:
    saved = _defaults()
    saved.reverse()
    saved[0] = {**saved[0], "size": "S", "hidden": True}
    async with _client(tmp_path) as (_app, client):
        put = await client.put("/api/home/layout", json={"modules": saved})
        got = await client.get("/api/home/layout")
    assert put.status_code == 200, put.text
    assert put.json()["modules"] == saved
    assert got.json()["modules"] == saved


@pytest.mark.anyio
async def test_a_layout_naming_only_some_modules_gets_the_rest_appended(tmp_path: Path) -> None:
    async with _client(tmp_path) as (_app, client):
        await client.put(
            "/api/home/layout",
            json={"modules": [{"module": "year", "size": "S", "hidden": False}]},
        )
        modules = (await client.get("/api/home/layout")).json()["modules"]
    assert modules[0] == {"module": "year", "size": "S", "hidden": False, "label": None}
    assert [row["module"] for row in modules[1:]] == [m for m in _keys() if m != "year"]


@pytest.mark.anyio
async def test_a_stored_layout_naming_a_module_that_no_longer_exists_still_loads(
    tmp_path: Path,
) -> None:
    stored = [
        {"module": "retired", "size": "L", "hidden": False},
        {"module": "lately", "size": "S", "hidden": True},
        "not even an object",
        {"module": "now", "size": "XL", "hidden": False},
    ]
    async with _client(tmp_path) as (app, client):
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO home_layouts (user_id, layout_json, updated_at)"
                    " VALUES (1, :layout, 'n')"
                ),
                {"layout": json.dumps(stored)},
            )
        layout = (await client.get("/api/home/layout")).json()["modules"]
        home = await client.get("/api/home")
    assert home.status_code == 200, home.text
    assert layout[0] == {"module": "lately", "size": "S", "hidden": True, "label": None}
    # An unknown size falls back to the module's default rather than failing the read.
    now_default = next(row for row in DEFAULT_LAYOUT if row["module"] == "now")
    assert layout[1] == {**now_default, "label": None}
    assert [row["module"] for row in layout] == [
        "lately",
        "now",
        *[m for m in _keys() if m not in {"lately", "now"}],
    ]


@pytest.mark.anyio
async def test_a_stored_layout_that_is_not_json_reads_as_the_default(tmp_path: Path) -> None:
    async with _client(tmp_path) as (app, client):
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO home_layouts (user_id, layout_json, updated_at)"
                    " VALUES (1, '{broken', 'n')"
                )
            )
        layout = (await client.get("/api/home/layout")).json()["modules"]
    assert layout == _defaults()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "modules",
    [
        [{"module": "retired", "size": "M", "hidden": False}],
        [{"module": "now", "size": "XL", "hidden": False}],
        [
            {"module": "now", "size": "M", "hidden": False},
            {"module": "now", "size": "S", "hidden": True},
        ],
    ],
    ids=["unknown module", "unknown size", "twice"],
)
async def test_a_write_naming_what_is_not_a_module_is_refused(
    tmp_path: Path, modules: list[dict[str, Any]]
) -> None:
    async with _client(tmp_path) as (_app, client):
        response = await client.put("/api/home/layout", json={"modules": modules})
        after = (await client.get("/api/home/layout")).json()["modules"]
    assert response.status_code == 422
    assert after == _defaults()


@pytest.mark.anyio
async def test_home_skips_a_hidden_module(tmp_path: Path) -> None:
    hidden = [
        {
            **row,
            "hidden": row["module"] in {"year", "lately", "tidy", "next", "libraries", "suggested"},
        }
        for row in _defaults()
    ]
    async with _client(tmp_path) as (_app, client):
        await client.put("/api/home/layout", json={"modules": hidden})
        body = (await client.get("/api/home")).json()
    assert body["year"] is None
    assert body["lately"] is None
    assert body["tidy"] is None
    assert body["next"] == []
    assert body["domains"] == []
    assert body["suggested"] is None


def _shelf(app: Any, name: str, user: int = 1) -> int:
    with app.state.engine.begin() as connection:
        return int(
            connection.execute(
                text(
                    "INSERT INTO shelves (user_id, name, slug, created_at, updated_at)"
                    " VALUES (:user, :name, :slug, 'n', 'n') RETURNING id"
                ),
                {"user": user, "name": name, "slug": name.lower().replace(" ", "-")},
            ).scalar_one()
        )


@pytest.mark.anyio
async def test_each_library_has_a_year_and_each_shelf_a_hidden_module(tmp_path: Path) -> None:
    """DEC-192: the families' members come from the registry and the person's shelves."""
    async with _client(tmp_path) as (app, client):
        shelf = _shelf(app, "Favorites")
        layout = (await client.get("/api/home/layout")).json()
    rows = {row["module"]: row for row in layout["modules"]}
    assert rows["year:book"] == {
        "module": "year:book",
        "size": "M",
        "hidden": False,
        "label": "Books this year",
    }
    # A library whose entries carry no finished date has no year (albums).
    assert "year:album" not in rows
    assert rows[f"shelf:{shelf}"] == {
        "module": f"shelf:{shelf}",
        "size": "M",
        "hidden": True,
        "label": "Shelf: Favorites",
    }
    assert layout["defaults"] == layout["modules"]
    # The libraries' years follow Lately, so the year and Lately keep their row.
    keys = [row["module"] for row in layout["modules"]]
    assert keys.index("year:book") == keys.index("lately") + 1


@pytest.mark.anyio
async def test_a_family_layout_round_trips_and_a_deleted_shelf_drops_out(tmp_path: Path) -> None:
    async with _client(tmp_path) as (app, client):
        kept = _shelf(app, "Favorites")
        gone = _shelf(app, "To lend")
        saved = [
            {"module": f"shelf:{gone}", "size": "S", "hidden": False},
            {"module": "year:movie", "size": "L", "hidden": False},
            {"module": f"shelf:{kept}", "size": "L", "hidden": False},
            {"module": "year:book", "size": "S", "hidden": True},
        ]
        put = await client.put("/api/home/layout", json={"modules": saved})
        with app.state.engine.begin() as connection:
            connection.execute(text("DELETE FROM shelves WHERE id = :id"), {"id": gone})
        after = (await client.get("/api/home/layout")).json()["modules"]
    assert put.status_code == 200, put.text
    assert [row["module"] for row in put.json()["modules"][:4]] == [s["module"] for s in saved]
    assert after[:3] == [
        {"module": "year:movie", "size": "L", "hidden": False, "label": "Movies this year"},
        {"module": f"shelf:{kept}", "size": "L", "hidden": False, "label": "Shelf: Favorites"},
        {"module": "year:book", "size": "S", "hidden": True, "label": "Books this year"},
    ]
    assert f"shelf:{gone}" not in {row["module"] for row in after}


@pytest.mark.anyio
@pytest.mark.parametrize("module", ["shelf:999", "year:album", "year:comic", "shelf:abc"])
async def test_a_family_member_that_does_not_exist_is_refused(tmp_path: Path, module: str) -> None:
    async with _client(tmp_path) as (_app, client):
        response = await client.put(
            "/api/home/layout", json={"modules": [{"module": module, "size": "M"}]}
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_module"


@pytest.mark.anyio
async def test_another_persons_shelf_is_not_a_module(tmp_path: Path) -> None:
    async with _client(tmp_path, auth="on") as (app, client):
        _seed_bruno(app)
        theirs = _shelf(app, "Bruno's", user=2)
        client.cookies.set(COOKIE_NAME, SessionStore(app.state.engine).create(1).token)
        layout = (await client.get("/api/home/layout")).json()["modules"]
        refused = await client.put(
            "/api/home/layout",
            json={"modules": [{"module": f"shelf:{theirs}", "size": "M", "hidden": False}]},
        )
    assert f"shelf:{theirs}" not in {row["module"] for row in layout}
    assert refused.status_code == 422


def _seed_bruno(app: Any) -> str:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    credential = hash_password("second person's password")
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
                "created_at,updated_at) VALUES (2,'bruno','Bruno',:digest,:salt,0,:now,:now)"
            ),
            {"digest": credential.digest, "salt": credential.salt, "now": now},
        )
    return SessionStore(app.state.engine).create(2).token


@pytest.mark.anyio
async def test_one_persons_layout_does_not_change_anothers(tmp_path: Path) -> None:
    mine = _defaults()
    mine.reverse()
    async with _client(tmp_path, auth="on") as (app, client):
        bruno = _seed_bruno(app)
        admin = SessionStore(app.state.engine).create(1).token
        client.cookies.set(COOKIE_NAME, admin)
        saved = await client.put("/api/home/layout", json={"modules": mine})
        client.cookies.set(COOKIE_NAME, bruno)
        theirs = (await client.get("/api/home/layout")).json()["modules"]
        client.cookies.set(COOKIE_NAME, admin)
        again = (await client.get("/api/home/layout")).json()["modules"]
        client.cookies.clear()
        anonymous = await client.get("/api/home/layout")
    assert saved.status_code == 200, saved.text
    assert theirs == _defaults()
    assert again == mine
    assert anonymous.status_code == 401


# -- migration 0036 ---------------------------------------------------------------------

BEFORE = "0035_join_indexes"


def _realistic(database: Path) -> None:
    """Two people, an item each, entries, a goal: the shape a real library has at 0035."""
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
        "created_at,updated_at) VALUES (2,'bruno','Bruno','x','y',0,'n','n')"
    )
    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
        " VALUES (1, 'book', 'Rayuela', '{}', '{}', 'n', 'n')"
    )
    for user in (1, 2):
        connection.execute(
            "INSERT INTO entries (user_id, item_id, status, date_added, reread_count,"
            " score_provisional, created_at, updated_at)"
            " VALUES (?, 1, 'read', 'n', 0, 0, 'n', 'n')",
            (user,),
        )
    connection.execute(
        "INSERT INTO goals (user_id, item_type, count, period, suggest, created_at, updated_at)"
        " VALUES (1, 'book', 2, 'month', 1, 'n', 'n')"
    )
    connection.commit()
    connection.close()


def _tables(database: Path) -> set[str]:
    connection = sqlite3.connect(database)
    try:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    finally:
        connection.close()


def test_0036_upgrades_and_downgrades_on_a_real_shaped_library(tmp_path: Path) -> None:
    from alembic import command

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    database = data_dir / "books.db"
    upgrade(configured.database_url, revision=BEFORE)
    _realistic(database)
    assert "home_layouts" not in _tables(database)

    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(home_layouts)")}
    assert set(columns) == {"user_id", "layout_json", "updated_at"}
    assert columns["user_id"][5] == 1  # the primary key: one layout per person
    keys = connection.execute("PRAGMA foreign_key_list(home_layouts)").fetchall()
    assert [(row[2], row[3], row[4], row[6]) for row in keys] == [
        ("users", "user_id", "id", "CASCADE")
    ]
    connection.execute(
        "INSERT INTO home_layouts (user_id, layout_json, updated_at) VALUES (2, '[]', 'n')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO home_layouts (user_id, layout_json, updated_at) VALUES (9, '[]', 'n')"
        )
    connection.commit()
    assert connection.execute("SELECT count(*) FROM entries").fetchone()[0] == 2
    # Deleting a person deletes their layout with them.
    connection.execute("DELETE FROM entries WHERE user_id = 2")
    connection.execute("DELETE FROM users WHERE id = 2")
    connection.commit()
    assert connection.execute("SELECT count(*) FROM home_layouts").fetchone()[0] == 0
    entries = connection.execute("SELECT count(*) FROM entries").fetchone()[0]
    connection.close()

    command.downgrade(alembic_config(configured.database_url), BEFORE)
    assert "home_layouts" not in _tables(database)
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT count(*) FROM entries").fetchone()[0] == entries
    assert connection.execute("SELECT count(*) FROM goals").fetchone()[0] == 1
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()
