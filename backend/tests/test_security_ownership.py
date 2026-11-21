"""Sprint 128 ownership fixes (DEC-180 §2-§3; findings F5, F8, F17, F21).

Two people share one install: the admin (user 1) and Bruno (user 2), a plain
user. Items are a shared cache, so the same ISBN added by both lands on one item
row. What that sharing must not do is hand Bruno the admin's files, let him
rewrite the item everyone sees, let him claim a title the admin typed by hand,
or list the admin's catalogue in his export. The server-side Calibre mount and
install-wide enrichment are the operator's.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from sqlalchemy import text

from book_tracker.api.identity import current_user
from book_tracker.application.passwords import hash_password
from book_tracker.config import Settings
from book_tracker.domain.identity import Identifier
from book_tracker.infrastructure.attachments import blob_path
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app
from book_tracker.migrations import alembic_config, upgrade

ADMIN_PASSWORD = "admin's private password"
SECOND_PASSWORD = "second person's password"
ISBN = Identifier("isbn13", "9788437604572", "9788437604572")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app(tmp_path: Path) -> Any:
    return create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", auth="on")
    )


def _seed_users(app: Any) -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    admin = hash_password(ADMIN_PASSWORD)
    second = hash_password(SECOND_PASSWORD)
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE users SET username='admin',display_name='Admin',password_hash=:digest,"
                "password_salt=:salt WHERE id=1"
            ),
            {"digest": admin.digest, "salt": admin.salt},
        )
        connection.execute(
            text(
                "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
                "created_at,updated_at) VALUES (2,'bruno','Bruno',:digest,:salt,0,:now,:now)"
            ),
            {"digest": second.digest, "salt": second.salt, "now": now},
        )


async def _client(app: Any, username: str, password: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    return client


@pytest.fixture
async def two_users(tmp_path: Path) -> AsyncIterator[dict[str, Any]]:
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        _seed_users(app)
        admin = await _client(app, "admin", ADMIN_PASSWORD)
        bruno = await _client(app, "bruno", SECOND_PASSWORD)
        try:
            yield {"app": app, "admin": admin, "bruno": bruno, "data": tmp_path / "data"}
        finally:
            await admin.aclose()
            await bruno.aclose()


def _shared_item(app: Any) -> int:
    """One item both people hold, the way two adds of one ISBN produce it."""
    first = DomainRepository(app.state.engine, 1).create_or_get_entry(
        title="Rayuela", identifiers=(ISBN,)
    )
    second = DomainRepository(app.state.engine, 2).create_or_get_entry(
        title="Rayuela", identifiers=(ISBN,)
    )
    assert first.item_id == second.item_id
    return first.item_id


# --- F5: attachments are owned per user -------------------------------------------


@pytest.mark.anyio
async def test_another_users_attachment_on_a_shared_item_is_invisible(
    two_users: dict[str, Any],
) -> None:
    app, admin, bruno = two_users["app"], two_users["admin"], two_users["bruno"]
    item_id = _shared_item(app)
    uploaded = await admin.post(
        f"/api/items/{item_id}/attachments",
        files={"file": ("diary.pdf", b"the admin's private notes", "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["id"]
    base = f"/api/items/{item_id}/attachments"

    assert (await bruno.get(base)).json()["attachments"] == []
    assert (await bruno.get(f"{base}/{attachment_id}")).status_code == 404
    assert (
        await bruno.patch(f"{base}/{attachment_id}", json={"filename": "mine.pdf"})
    ).status_code == 404
    assert (await bruno.delete(f"{base}/{attachment_id}")).status_code == 404

    listed = (await admin.get(base)).json()["attachments"]
    assert [row["filename"] for row in listed] == ["diary.pdf"]
    download = await admin.get(f"{base}/{attachment_id}")
    assert download.content == b"the admin's private notes"


@pytest.mark.anyio
async def test_the_same_bytes_attached_by_two_people_are_two_rows_and_one_blob(
    two_users: dict[str, Any],
) -> None:
    app, admin, bruno = two_users["app"], two_users["admin"], two_users["bruno"]
    item_id = _shared_item(app)
    base = f"/api/items/{item_id}/attachments"
    body = b"identical epub bytes"
    first = await admin.post(base, files={"file": ("admin.epub", body, "application/epub+zip")})
    second = await bruno.post(base, files={"file": ("bruno.epub", body, "application/epub+zip")})
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    # Bruno's upload of the same bytes did not rename the admin's row.
    assert [r["filename"] for r in (await admin.get(base)).json()["attachments"]] == ["admin.epub"]
    assert [r["filename"] for r in (await bruno.get(base)).json()["attachments"]] == ["bruno.epub"]

    digest = first.json()["sha256"]
    blob = blob_path(two_users["data"], digest)
    assert (await admin.delete(f"{base}/{first.json()['id']}")).status_code == 204
    assert blob.is_file(), "Bruno's row still references the blob"
    assert (await bruno.get(f"{base}/{second.json()['id']}")).content == body
    assert (await bruno.delete(f"{base}/{second.json()['id']}")).status_code == 204
    assert not blob.exists()


# --- F5: a shared item's details are not one user's to rewrite -----------------------


SHARED_ITEM_WRITES: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("PATCH", "/api/items/{item_id}", {"title": "Bruno's title"}),
    ("POST", "/api/items/{item_id}/cover", {"cover_url": "https://covers.openlibrary.org/x.jpg"}),
    ("POST", "/api/items/{item_id}/refresh", {"overwrite": True}),
    ("POST", "/api/items/{item_id}/fill", None),
    ("POST", "/api/items/{item_id}/outline", None),
    ("POST", "/api/items/{item_id}/cover/fetch", None),
)


@pytest.mark.anyio
@pytest.mark.parametrize(("method", "template", "body"), SHARED_ITEM_WRITES)
async def test_a_plain_user_cannot_rewrite_an_item_someone_else_holds(
    two_users: dict[str, Any], method: str, template: str, body: dict[str, Any] | None
) -> None:
    app, bruno = two_users["app"], two_users["bruno"]
    item_id = _shared_item(app)
    response = await bruno.request(method, template.format(item_id=item_id), json=body)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "item_shared"
    with app.state.engine.connect() as connection:
        row = connection.execute(
            text("SELECT title, cover_path FROM items WHERE id=:id"), {"id": item_id}
        ).one()
    assert row == ("Rayuela", None)


@pytest.mark.anyio
async def test_the_sole_holder_and_an_admin_may_still_edit(two_users: dict[str, Any]) -> None:
    app, admin, bruno = two_users["app"], two_users["admin"], two_users["bruno"]
    shared = _shared_item(app)
    edited = await admin.patch(f"/api/items/{shared}", json={"title": "Rayuela (ed. crítica)"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["title"] == "Rayuela (ed. crítica)"

    own = DomainRepository(app.state.engine, 2).create_or_get_entry(title="Only Bruno's")
    mine = await bruno.patch(f"/api/items/{own.item_id}", json={"title": "Only Bruno's, fixed"})
    assert mine.status_code == 200, mine.text
    assert mine.json()["title"] == "Only Bruno's, fixed"


# --- F5: hand-typed items are per user ------------------------------------------------


@pytest.mark.anyio
async def test_a_hand_typed_item_is_not_claimable_by_its_key(two_users: dict[str, Any]) -> None:
    admin, bruno = two_users["admin"], two_users["bruno"]
    manual = {"item_type": "book", "title": "Cartas a mi hermana"}
    first = await admin.post(
        "/api/entries", json={"manual": manual, "idempotency_key": "letters-key"}
    )
    assert first.status_code == 201, first.text
    admin_item = first.json()["entry"]["item_id"]
    again = await admin.post(
        "/api/entries", json={"manual": manual, "idempotency_key": "letters-key"}
    )
    assert again.json()["entry"]["item_id"] == admin_item, "a retry is still idempotent"

    claimed = await bruno.post(
        "/api/entries",
        json={"manual": {"item_type": "book", "title": "x"}, "idempotency_key": "letters-key"},
    )
    assert claimed.status_code == 201, claimed.text
    assert claimed.json()["entry"]["item_id"] != admin_item
    assert claimed.json()["entry"]["item"]["title"] == "x"

    by_source = await bruno.post(
        "/api/entries", json={"source": "manual", "source_id": "letters-key"}
    )
    assert by_source.status_code == 422, by_source.text
    assert (await bruno.get(f"/api/items/{admin_item}")).status_code == 404


# --- F8: the export is the user's own ---------------------------------------------------


@pytest.mark.anyio
async def test_the_json_export_carries_only_the_users_items_and_files(
    two_users: dict[str, Any],
) -> None:
    app, admin, bruno = two_users["app"], two_users["admin"], two_users["bruno"]
    shared = _shared_item(app)
    private = DomainRepository(app.state.engine, 1).create_or_get_entry(title="Admin's alone")
    await admin.post(
        f"/api/items/{shared}/attachments",
        files={"file": ("admin.pdf", b"admin bytes", "application/pdf")},
    )
    await bruno.post(
        f"/api/items/{shared}/attachments",
        files={"file": ("bruno.pdf", b"bruno bytes", "application/pdf")},
    )
    exported = (await bruno.get("/api/export")).json()
    assert [item["id"] for item in exported["items"]] == [shared]
    assert [a["filename"] for a in exported["items"][0]["attachments"]] == ["bruno.pdf"]
    assert private.item_id not in {item["id"] for item in exported["items"]}

    admin_export = (await admin.get("/api/export")).json()
    assert {item["id"] for item in admin_export["items"]} == {shared, private.item_id}
    files = {a["filename"] for item in admin_export["items"] for a in item["attachments"]}
    assert files == {"admin.pdf"}


# --- F17: the server-side Calibre mount and install-wide backfill are the operator's ---


@pytest.mark.anyio
async def test_the_calibre_mount_is_admin_only_and_uploads_stay_open(
    two_users: dict[str, Any],
) -> None:
    admin, bruno = two_users["admin"], two_users["bruno"]
    browse = await bruno.get("/api/import/calibre/browse")
    assert browse.status_code == 403, browse.text
    assert browse.json()["error"]["code"] == "forbidden"
    preview = await bruno.post("/api/import/calibre/preview", json={"path": "Library"})
    assert preview.status_code == 403, preview.text
    # The admin passes the gate; the missing mount is a different refusal.
    assert (await admin.get("/api/import/calibre/browse")).status_code != 403
    admin_preview = await admin.post("/api/import/calibre/preview", json={"path": "Library"})
    assert admin_preview.status_code != 403
    # The per-user upload variant of the same connector is not gated.
    upload = await bruno.post(
        "/api/import/calibre/preview",
        files={"metadata.db": ("metadata.db", b"not a database")},
    )
    assert upload.status_code != 403, upload.text


@pytest.mark.anyio
async def test_install_wide_enrichment_backfill_is_admin_only(two_users: dict[str, Any]) -> None:
    admin, bruno = two_users["admin"], two_users["bruno"]
    refused = await bruno.post("/api/enrichment/backfill")
    assert refused.status_code == 403
    assert (await admin.post("/api/enrichment/backfill")).status_code == 202


# --- F21: a job with no owner is not everybody's --------------------------------------


@pytest.mark.anyio
async def test_ownerless_jobs_follow_their_batch_or_the_admin(two_users: dict[str, Any]) -> None:
    app, admin, bruno = two_users["app"], two_users["admin"], two_users["bruno"]
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with app.state.engine.begin() as connection:
        for batch_id, user_id in (("admin-batch", 1), ("bruno-batch", 2)):
            connection.execute(
                text(
                    "INSERT INTO import_batches (id,user_id,kind,fingerprint,state,"
                    "source_descriptor,preview_summary,counters,created_at,updated_at) VALUES "
                    "(:id,:user,'goodreads',:id,'committed','{}','{}','{}',:now,:now)"
                ),
                {"id": batch_id, "user": user_id, "now": now},
            )
    jobs = JobRepository(app.state.engine)
    nobodys = jobs.enqueue(None, "enrich_item", {"item_id": 1})
    on_admin_batch = jobs.enqueue("admin-batch", "enrich_item", {"item_id": 1})
    on_bruno_batch = jobs.enqueue("bruno-batch", "enrich_item", {"item_id": 1})
    for job_id in (nobodys, on_admin_batch):
        assert (await bruno.get(f"/api/import/jobs/{job_id}")).status_code == 404
        assert (await bruno.post(f"/api/import/jobs/{job_id}/retry")).status_code == 404
        assert (await admin.get(f"/api/import/jobs/{job_id}")).status_code == 200
    assert (await bruno.get(f"/api/import/jobs/{on_bruno_batch}")).status_code == 200
    assert (await admin.get(f"/api/import/jobs/{on_bruno_batch}")).status_code == 404


# --- Defence in depth: every API route names its principal ---------------------------

#: Routes that must answer before anyone is signed in. Everything else under `/api`
#: depends on `current_user`, so a request that slipped past the middleware still
#: answers 401 rather than reaching a handler.
PUBLIC_ROUTES = frozenset(
    {
        "/api/auth/login",
        "/api/auth/setup",
        "/api/auth/me",
        "/api/auth/session",
    }
)


def _depends_on_current_user(dependant: Dependant) -> bool:
    return any(
        dependency.call is current_user or _depends_on_current_user(dependency)
        for dependency in dependant.dependencies
    )


def test_every_api_route_depends_on_the_principal(tmp_path: Path) -> None:
    app = _app(tmp_path)
    missing = sorted(
        f"{sorted(route.methods or [])} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/api/")
        and not route.path.startswith("/api/health/")
        and route.path not in PUBLIC_ROUTES
        and route.name != "missing_api"
        and not _depends_on_current_user(route.dependant)
    )
    assert missing == []


# --- The migration ----------------------------------------------------------------------

BEFORE = "0033_unknown_fields"
NOW = "2026-11-21T00:00:00Z"


def test_existing_attachments_are_given_the_owner_the_ledger_or_the_item_names(
    tmp_path: Path,
) -> None:
    from alembic import command

    data = tmp_path / "data"
    data.mkdir()
    settings = Settings(
        data_dir=data, backup_dir=tmp_path / "backups", user_agent_contact="t@example.invalid"
    )
    assert settings.database_url is not None
    upgrade(settings.database_url, revision=BEFORE)
    database = data / "books.db"
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO users (id,username,is_admin,created_at,updated_at) VALUES (2,'b',0,?,?)",
        (NOW, NOW),
    )
    for item_id in (1, 2, 3, 4):
        connection.execute(
            "INSERT INTO items (id,type,title,identifiers,metadata,created_at,updated_at)"
            " VALUES (?,'book',?,'{}','{}',?,?)",
            (item_id, f"Item {item_id}", NOW, NOW),
        )
    # Item 1: both hold it, and Bruno's import attached the file.
    # Item 2: only Bruno holds it. Item 3: both hold it, nothing says whose.
    # Item 4: nobody holds it any more.
    for user_id, item_id in ((1, 1), (2, 1), (2, 2), (1, 3), (2, 3)):
        connection.execute(
            "INSERT INTO entries (user_id,item_id,status,date_added,created_at,updated_at)"
            " VALUES (?,?,'read',?,?,?)",
            (user_id, item_id, NOW, NOW, NOW),
        )
    for attachment_id, item_id in ((10, 1), (20, 2), (30, 3), (40, 4)):
        connection.execute(
            "INSERT INTO attachments (id,item_id,filename,byte_size,sha256,created_at,updated_at)"
            " VALUES (?,?,'f',1,?,?,?)",
            (attachment_id, item_id, f"{attachment_id:064d}", NOW, NOW),
        )
    connection.execute(
        "INSERT INTO import_batches (id,user_id,kind,fingerprint,state,source_descriptor,"
        "preview_summary,counters,created_at,updated_at) VALUES "
        "('b',2,'calibre','f','committed','{}','{}','{}',?,?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO import_records (id,batch_id,user_id,row_number,created_at,updated_at)"
        " VALUES (1,'b',2,1,?,?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO import_effects (batch_id,user_id,record_id,effect_type,entity_type,"
        "entity_id,after_values) VALUES ('b',2,1,'create','attachment','10',?)",
        (json.dumps({"created": True}),),
    )
    connection.commit()
    connection.close()

    command.upgrade(alembic_config(settings.database_url), "head")
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    owners = dict(connection.execute("SELECT id, user_id FROM attachments ORDER BY id"))
    assert owners == {10: 2, 20: 2, 30: 1, 40: 1}
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(attachments)")}
    assert columns["user_id"][3] == 1, "user_id is NOT NULL"
    foreign_keys = {
        (row[2], row[3], row[6])
        for row in connection.execute("PRAGMA foreign_key_list(attachments)")
    }
    assert ("users", "user_id", "CASCADE") in foreign_keys
    assert ("items", "item_id", "CASCADE") in foreign_keys
    # The same file on the same item may now be held once per person.
    connection.execute(
        "INSERT INTO attachments (item_id,user_id,filename,byte_size,sha256,created_at,updated_at)"
        " VALUES (3,2,'f',1,?,?,?)",
        (f"{30:064d}", NOW, NOW),
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO attachments (item_id,user_id,filename,byte_size,sha256,created_at,"
            "updated_at) VALUES (3,2,'g',1,?,?,?)",
            (f"{30:064d}", NOW, NOW),
        )
    indexes = {row[1] for row in connection.execute("PRAGMA index_list(attachments)")}
    assert {"ix_attachments_item_id", "ix_attachments_sha256"} <= indexes
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.commit()
    connection.close()

    command.downgrade(alembic_config(settings.database_url), BEFORE)
    connection = sqlite3.connect(database)
    assert "user_id" not in {row[1] for row in connection.execute("PRAGMA table_info(attachments)")}
    # The per-person duplicate folds back into the one row the old key allowed.
    assert [row[0] for row in connection.execute("SELECT id FROM attachments ORDER BY id")] == [
        10,
        20,
        30,
        40,
    ]
    connection.close()


@pytest.mark.anyio
async def test_refiling_moves_your_files_and_leaves_anothers(two_users: dict[str, Any]) -> None:
    from tests.test_refile import Fake

    app, admin, bruno = two_users["app"], two_users["admin"], two_users["bruno"]
    app.state.providers = {"anilist": Fake("anilist", "anime", "Cowboy Bebop", {"mal": "1"})}
    shared = _shared_item(app)
    base = f"/api/items/{shared}/attachments"
    await admin.post(base, files={"file": ("admin.txt", b"admin", "text/plain")})
    await bruno.post(base, files={"file": ("bruno.txt", b"bruno", "text/plain")})
    with app.state.engine.connect() as connection:
        entry_id = connection.execute(
            text("SELECT id FROM entries WHERE user_id=2 AND item_id=:item"), {"item": shared}
        ).scalar_one()
    moved = await bruno.post(
        f"/api/entries/{entry_id}/refile", json={"source": "anilist", "source_id": "1"}
    )
    assert moved.status_code == 200, moved.text
    new_item = moved.json()["item_id"]
    assert [r["filename"] for r in (await admin.get(base)).json()["attachments"]] == ["admin.txt"]
    files = (await bruno.get(f"/api/items/{new_item}/attachments")).json()["attachments"]
    assert [r["filename"] for r in files] == ["bruno.txt"]


@pytest.mark.anyio
async def test_an_import_fills_a_shared_cover_but_does_not_replace_one(
    two_users: dict[str, Any],
) -> None:
    from book_tracker.application.imports import ImportService
    from book_tracker.domain.registry import IMPORTERS

    app = two_users["app"]
    shared = _shared_item(app)
    own = DomainRepository(app.state.engine, 2).create_or_get_entry(title="Only Bruno's")
    bruno_import = ImportService(
        app.state.engine,
        two_users["data"],
        two_users["data"],
        IMPORTERS["calibre"],
        user_id=2,
    )
    assert bruno_import._may_replace_cover(shared), "an empty shared cover may be filled"
    assert bruno_import._may_replace_cover(own.item_id)
    for item_id in (shared, own.item_id):
        DomainRepository(app.state.engine, 1).set_cover_path(item_id, f"covers/{item_id}.jpg")
    assert not bruno_import._may_replace_cover(shared)
    assert bruno_import._may_replace_cover(own.item_id), "his alone, so his to replace"
