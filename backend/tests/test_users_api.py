from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.api.auth import COOKIE_NAME
from book_tracker.application.passwords import hash_password
from book_tracker.application.sessions import SessionStore
from book_tracker.config import Settings
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app

ADMIN_PASSWORD = "admin's private password"
SECOND_PASSWORD = "second person's password"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        user_agent_contact="test@example.invalid",
        auth="on",
    )


def credential_admin(app: object) -> None:
    credential = hash_password(ADMIN_PASSWORD)
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE users SET username='admin', display_name='Admin', "
                "password_hash=:digest, password_salt=:salt WHERE id=1"
            ),
            {"digest": credential.digest, "salt": credential.salt},
        )


async def login(client: httpx.AsyncClient, username: str, password: str) -> str:
    response = await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.cookies[COOKIE_NAME]


async def create_second(client: httpx.AsyncClient, *, admin: bool = False) -> dict[str, object]:
    response = await client.post(
        "/api/users",
        json={
            "username": "Bruno",
            "display_name": "Bruno",
            "password": SECOND_PASSWORD,
            "is_admin": admin,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def seed_import_ledger(app: object, user_id: int, entry_id: int, item_id: int) -> str:
    now = datetime.now(UTC).isoformat()
    batch_id = f"batch-{user_id}"
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_batches "
                "(id,user_id,kind,fingerprint,state,source_descriptor,preview_summary,counters,"
                "created_at,updated_at) VALUES "
                "(:batch,:user,'goodreads',:fingerprint,'committed','{}','{}','{}',:now,:now)"
            ),
            {"batch": batch_id, "user": user_id, "fingerprint": f"fp-{user_id}", "now": now},
        )
        record_id = int(
            connection.execute(
                text(
                    "INSERT INTO import_records "
                    "(batch_id,user_id,row_number,normalized_payload,matched_item_id,matched_entry_id,"
                    "conflicts,validation_errors,created_at,updated_at) VALUES "
                    "(:batch,:user,1,'{}',:item,:entry,'{}','[]',:now,:now) RETURNING id"
                ),
                {
                    "batch": batch_id,
                    "user": user_id,
                    "item": item_id,
                    "entry": entry_id,
                    "now": now,
                },
            ).scalar_one()
        )
        connection.execute(
            text(
                "INSERT INTO import_effects "
                "(batch_id,user_id,record_id,effect_type,entity_type,entity_id,before_values,"
                "after_values) VALUES "
                "(:batch,:user,:record,'create','entry',:entry,'{}','{}')"
            ),
            {
                "batch": batch_id,
                "user": user_id,
                "record": record_id,
                "entry": str(entry_id),
            },
        )
    JobRepository(app.state.engine).enqueue(
        batch_id, "enrich_item", {"item_id": item_id}, user_id=user_id
    )
    return batch_id


@pytest.mark.anyio
async def test_admin_creates_lists_renames_and_resets_a_user(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        credential_admin(app)
        DomainRepository(app.state.engine, 1).create_or_get_entry(title="Rayuela")
        DomainRepository(app.state.engine, 1).create_shelf("Favourites")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await login(client, "admin", ADMIN_PASSWORD)
            second = await create_second(client)
            users = await client.get("/api/users")
            assert users.status_code == 200
            assert users.json() == [
                {
                    "id": 1,
                    "username": "admin",
                    "display_name": "Admin",
                    "is_admin": True,
                    "entry_count": 1,
                    "shelf_count": 1,
                },
                {
                    "id": second["id"],
                    "username": "bruno",
                    "display_name": "Bruno",
                    "is_admin": False,
                    "entry_count": 0,
                    "shelf_count": 0,
                },
            ]
            patched = await client.patch(
                f"/api/users/{second['id']}",
                json={"display_name": "B", "password": "reset private password"},
            )
            assert patched.status_code == 200
            assert patched.json()["display_name"] == "B"
            assert (
                await client.post(
                    "/api/auth/login",
                    json={"username": "bruno", "password": SECOND_PASSWORD},
                )
            ).status_code == 401
            assert (
                await client.post(
                    "/api/auth/login",
                    json={"username": "bruno", "password": "reset private password"},
                )
            ).status_code == 200


@pytest.mark.anyio
async def test_non_admin_is_refused_every_management_route(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        credential_admin(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await login(client, "admin", ADMIN_PASSWORD)
            second = await create_second(client)
            client.cookies.clear()
            await login(client, "bruno", SECOND_PASSWORD)
            calls = (
                client.get("/api/users"),
                client.post(
                    "/api/users",
                    json={"username": "third", "password": "third private password"},
                ),
                client.patch(f"/api/users/{second['id']}", json={"display_name": "X"}),
                client.request("DELETE", f"/api/users/{second['id']}", json={"action": "delete"}),
            )
            for call in calls:
                response = await call
                assert response.status_code == 403
                assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.anyio
async def test_password_change_keeps_current_session_and_revokes_only_its_siblings(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        credential_admin(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as admin:
            await login(admin, "admin", ADMIN_PASSWORD)
            second = await create_second(admin)
            admin_token = admin.cookies[COOKIE_NAME]
        sibling = SessionStore(app.state.engine).create(int(second["id"]))
        current = SessionStore(app.state.engine).create(int(second["id"]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            cookies={COOKIE_NAME: current.token},
        ) as client:
            changed = await client.patch(
                "/api/auth/password",
                json={"current_password": SECOND_PASSWORD, "new_password": "new private password"},
            )
            assert changed.status_code == 204
            assert (await client.get("/api/entries")).status_code == 200
        store = SessionStore(app.state.engine)
        assert store.lookup(sibling.token) is None
        assert store.lookup(admin_token) is not None


@pytest.mark.anyio
async def test_username_collision_self_delete_and_last_admin_demotion_are_stated(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        credential_admin(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await login(client, "admin", ADMIN_PASSWORD)
            assert (await create_second(client))["username"] == "bruno"
            collision = await client.post(
                "/api/users", json={"username": " BRUNO ", "password": SECOND_PASSWORD}
            )
            assert collision.status_code == 422
            assert collision.json()["error"]["details"]["field"] == "username"
            self_delete = await client.request("DELETE", "/api/users/1", json={"action": "delete"})
            assert self_delete.status_code == 409
            assert "yourself" in self_delete.json()["error"]["message"].lower()
            demote = await client.patch("/api/users/1", json={"is_admin": False})
            assert demote.status_code == 409
            assert "last admin" in demote.json()["error"]["message"].lower()


@pytest.mark.anyio
async def test_deleting_requires_a_decision_and_delete_leaves_shared_cache(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        credential_admin(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await login(client, "admin", ADMIN_PASSWORD)
            second = await create_second(client)
            owned = DomainRepository(app.state.engine, int(second["id"])).create_or_get_entry(
                title="Ficciones"
            )
            DomainRepository(app.state.engine, int(second["id"])).create_shelf("Private")
            seed_import_ledger(app, int(second["id"]), owned.entry_id, owned.item_id)
            now = datetime.now(UTC).isoformat()
            with app.state.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO attachments "
                        "(item_id,filename,byte_size,sha256,created_at,updated_at) "
                        "VALUES (:item,'notes.txt',4,:sha,:now,:now)"
                    ),
                    {"item": owned.item_id, "sha": "a" * 64, "now": now},
                )
            missing = await client.request("DELETE", f"/api/users/{second['id']}", json={})
            assert missing.status_code == 422
            deleted = await client.request(
                "DELETE", f"/api/users/{second['id']}", json={"action": "delete"}
            )
            assert deleted.status_code == 204
        with app.state.engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM entries WHERE user_id=:user"),
                    {"user": second["id"]},
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM shelves WHERE user_id=:user"),
                    {"user": second["id"]},
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM items WHERE id=:item"), {"item": owned.item_id}
                ).scalar_one()
                == 1
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM attachments WHERE item_id=:item"),
                    {"item": owned.item_id},
                ).scalar_one()
                == 1
            )
            for table in ("import_batches", "import_records", "import_effects", "jobs"):
                assert (
                    connection.execute(
                        text(f"SELECT count(*) FROM {table} WHERE user_id=:user"),
                        {"user": second["id"]},
                    ).scalar_one()
                    == 0
                )


@pytest.mark.anyio
async def test_transfer_moves_the_library_and_ledger_intact(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        credential_admin(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await login(client, "admin", ADMIN_PASSWORD)
            second = await create_second(client)
            owned = DomainRepository(app.state.engine, int(second["id"])).create_or_get_entry(
                title="The second library"
            )
            shelf_id = DomainRepository(app.state.engine, int(second["id"])).create_shelf("Moved")
            DomainRepository(app.state.engine, int(second["id"])).attach_shelf(
                owned.entry_id, shelf_id
            )
            batch_id = seed_import_ledger(app, int(second["id"]), owned.entry_id, owned.item_id)
            transferred = await client.request(
                "DELETE",
                f"/api/users/{second['id']}",
                json={"action": "transfer", "transfer_to_user_id": 1},
            )
            assert transferred.status_code == 204, transferred.text
        with app.state.engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM entries WHERE user_id=1")
                ).scalar_one()
                == 1
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM shelves WHERE user_id=1")
                ).scalar_one()
                == 1
            )
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM entry_shelves "
                        "WHERE entry_id=:entry AND shelf_id=:shelf"
                    ),
                    {"entry": owned.entry_id, "shelf": shelf_id},
                ).scalar_one()
                == 1
            )
            assert (
                connection.execute(
                    text("SELECT user_id FROM import_batches WHERE id=:batch"),
                    {"batch": batch_id},
                ).scalar_one()
                == 1
            )
            for table in ("import_records", "import_effects", "jobs"):
                assert (
                    connection.execute(
                        text(f"SELECT user_id FROM {table} WHERE batch_id=:batch"),
                        {"batch": batch_id},
                    ).scalar_one()
                    == 1
                )


@pytest.mark.anyio
async def test_admin_sets_and_clears_acting_as_on_only_the_current_session(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        credential_admin(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as admin:
            token = await login(admin, "admin", ADMIN_PASSWORD)
            second = await create_second(admin)
            sibling = SessionStore(app.state.engine).create(1)

            started = await admin.post(f"/api/auth/act-as/{second['id']}")
            assert started.status_code == 204
            me = await admin.get("/api/auth/me")
            assert me.json()["user"]["id"] == 1
            assert me.json()["acting_as"] == {
                "id": second["id"],
                "username": "bruno",
                "display_name": "Bruno",
                "is_admin": False,
            }
            assert SessionStore(app.state.engine).lookup(token).acting_as_user_id == second["id"]
            assert SessionStore(app.state.engine).lookup(sibling.token).acting_as_user_id is None

            stopped = await admin.delete("/api/auth/act-as")
            assert stopped.status_code == 204
            assert (await admin.get("/api/auth/me")).json()["acting_as"] is None


@pytest.mark.anyio
async def test_non_admin_is_refused_both_act_as_routes(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        credential_admin(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await login(client, "admin", ADMIN_PASSWORD)
            await create_second(client)
            client.cookies.clear()
            await login(client, "bruno", SECOND_PASSWORD)
            for response in (
                await client.post("/api/auth/act-as/1"),
                await client.delete("/api/auth/act-as"),
            ):
                assert response.status_code == 403
                assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.anyio
async def test_acting_as_ends_on_logout_target_deletion_and_either_password_change(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        credential_admin(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as admin:
            token = await login(admin, "admin", ADMIN_PASSWORD)
            second = await create_second(admin)
            assert (await admin.post(f"/api/auth/act-as/{second['id']}")).status_code == 204

            changed = await admin.patch(
                "/api/auth/password",
                json={"current_password": ADMIN_PASSWORD, "new_password": "admin changed"},
            )
            assert changed.status_code == 204
            assert SessionStore(app.state.engine).lookup(token).acting_as_user_id is None

            assert (await admin.post(f"/api/auth/act-as/{second['id']}")).status_code == 204
            reset = await admin.patch(
                f"/api/users/{second['id']}", json={"password": "second changed"}
            )
            assert reset.status_code == 200
            assert SessionStore(app.state.engine).lookup(token).acting_as_user_id is None

            assert (await admin.post(f"/api/auth/act-as/{second['id']}")).status_code == 204
            deleted = await admin.request(
                "DELETE", f"/api/users/{second['id']}", json={"action": "delete"}
            )
            assert deleted.status_code == 204
            assert SessionStore(app.state.engine).lookup(token).acting_as_user_id is None

            third = await create_second(admin)
            assert (await admin.post(f"/api/auth/act-as/{third['id']}")).status_code == 204
            assert (await admin.delete("/api/auth/session")).status_code == 204
            assert SessionStore(app.state.engine).lookup(token) is None
            assert (
                await admin.post(
                    "/api/auth/login", json={"username": "admin", "password": "admin changed"}
                )
            ).status_code == 200
            assert (await admin.get("/api/auth/me")).json()["acting_as"] is None
