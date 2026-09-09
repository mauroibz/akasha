from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.routing import APIRoute
from PIL import Image
from sqlalchemy import text

from book_tracker.api.auth import COOKIE_NAME
from book_tracker.application.add import AddService
from book_tracker.application.passwords import hash_password
from book_tracker.config import Settings
from book_tracker.domain.identity import Identifier
from book_tracker.domain.providers import ItemPayload, SourceRef
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app

ADMIN_PASSWORD = "admin's private password"
SECOND_PASSWORD = "second person's password"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# Every application route has an explicit isolation policy. This inventory is
# deliberately hard-coded beside the runtime comparison: adding a route without
# deciding its policy makes the suite fail before that route can ship.
ROUTE_POLICY = {
    ("GET", "/api/health/live"): "shared",
    ("GET", "/api/health/ready"): "shared",
    ("GET", "/api/health/providers"): "shared",
    ("POST", "/api/auth/login"): "auth",
    ("DELETE", "/api/auth/session"): "auth",
    ("GET", "/api/auth/me"): "auth",
    ("POST", "/api/auth/setup"): "auth",
    ("PATCH", "/api/auth/password"): "self",
    ("GET", "/api/users"): "admin",
    ("POST", "/api/users"): "admin",
    ("PATCH", "/api/users/{user_id}"): "admin",
    ("DELETE", "/api/users/{user_id}"): "admin",
    ("GET", "/api/entries"): "private-collection",
    ("GET", "/api/insights"): "private-collection",
    ("GET", "/api/insights/scores"): "private-collection",
    ("POST", "/api/entries"): "private-write",
    ("PATCH", "/api/entries/bulk"): "private-id",
    ("POST", "/api/entries/accept-suggested"): "private-write",
    ("GET", "/api/entries/{entry_id}"): "private-id",
    ("PATCH", "/api/entries/{entry_id}"): "private-id",
    ("DELETE", "/api/entries/{entry_id}"): "private-id",
    ("GET", "/api/items/{item_id}"): "owned-shared-cache",
    ("PATCH", "/api/items/{item_id}"): "owned-shared-cache",
    ("GET", "/api/item-types"): "shared",
    ("GET", "/api/items/{item_id}/cover"): "owned-shared-cache",
    ("GET", "/api/items/{item_id}/cover-candidates"): "owned-shared-cache",
    ("POST", "/api/items/{item_id}/cover"): "owned-shared-cache",
    ("GET", "/api/items/{item_id}/attachments"): "owned-shared-cache",
    ("POST", "/api/items/{item_id}/attachments"): "owned-shared-cache",
    ("GET", "/api/items/{item_id}/attachments/{attachment_id}"): "owned-shared-cache",
    ("PATCH", "/api/items/{item_id}/attachments/{attachment_id}"): "owned-shared-cache",
    ("DELETE", "/api/items/{item_id}/attachments/{attachment_id}"): "owned-shared-cache",
    ("POST", "/api/items/{item_id}/refresh"): "owned-shared-cache",
    ("POST", "/api/items/{item_id}/cover/fetch"): "owned-shared-cache",
    ("GET", "/api/shelves"): "private-collection",
    ("POST", "/api/shelves"): "private-write",
    ("PATCH", "/api/shelves/{shelf_id}"): "private-id",
    ("DELETE", "/api/shelves/{shelf_id}"): "private-id",
    ("GET", "/api/search/resolve"): "shared-provider",
    ("GET", "/api/search/preview"): "shared-provider",
    ("GET", "/api/search"): "shared-provider",
    ("POST", "/api/import/{importer_name}/preview"): "private-write",
    ("POST", "/api/import/{importer_name}/plan"): "private-write",
    ("POST", "/api/import/{importer_name}/batches/{batch_id}/files"): "private-id",
    ("GET", "/api/import/{importer_name}/browse"): "shared-source",
    ("POST", "/api/import/{importer_name}/commit"): "private-id",
    ("GET", "/api/import/jobs/{job_id}"): "private-id",
    ("DELETE", "/api/import/batches/{batch_id}"): "private-id",
    ("GET", "/api/importers"): "shared",
    ("POST", "/api/enrichment/backfill"): "shared-cache-write",
    ("GET", "/api/export"): "private-collection",
    ("GET", "/api/exports"): "shared",
    ("GET", "/api/export/{view}"): "private-collection",
}


def test_every_application_route_has_an_isolation_policy(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", auth="on")
    )
    actual = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/api/")
        and route.name != "missing_api"
        for method in route.methods or set()
    }
    assert actual == set(ROUTE_POLICY)


def _seed_users(app: object) -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    admin_credential = hash_password(ADMIN_PASSWORD)
    second_credential = hash_password(SECOND_PASSWORD)
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE users SET username='admin',display_name='Admin',password_hash=:digest,"
                "password_salt=:salt WHERE id=1"
            ),
            {"digest": admin_credential.digest, "salt": admin_credential.salt},
        )
        connection.execute(
            text(
                "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
                "created_at,updated_at) VALUES (2,'bruno','Bruno',:digest,:salt,0,:now,:now)"
            ),
            {"digest": second_credential.digest, "salt": second_credential.salt, "now": now},
        )


def _seed_users_and_private_rows(app: object, tmp_path: Path) -> dict[str, object]:
    _seed_users(app)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    identifier = Identifier("test", "shared-item", "shared-item")
    owned = DomainRepository(app.state.engine, 1).create_or_get_entry(
        title="Only Admin Owns", identifiers=(identifier,)
    )
    shelf = DomainRepository(app.state.engine, 1).create_shelf("Admin shelf")
    DomainRepository(app.state.engine, 1).set_cover_path(
        owned.item_id, f"covers/{owned.item_id}.jpg"
    )
    cover = tmp_path / "data" / "covers" / f"{owned.item_id}.jpg"
    cover.write_bytes(b"a real enough jpeg for the route")
    digest = hashlib.sha256(b"private attachment").hexdigest()
    blob = tmp_path / "data" / "attachments" / digest[:2] / digest[2:4] / digest
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"private attachment")
    batch_id = "admin-private-batch"
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with app.state.engine.begin() as connection:
        attachment_id = int(
            connection.execute(
                text(
                    "INSERT INTO attachments "
                    "(item_id,filename,byte_size,sha256,created_at,updated_at) "
                    "VALUES (:item,'private.txt',18,:sha,:now,:now) RETURNING id"
                ),
                {"item": owned.item_id, "sha": digest, "now": now},
            ).scalar_one()
        )
        connection.execute(
            text(
                "INSERT INTO import_batches "
                "(id,user_id,kind,fingerprint,state,source_descriptor,preview_summary,counters,error,"
                "committed_at,undo_expires_at,created_at,updated_at) VALUES "
                "(:id,1,'calibre','private-fingerprint','committed','{}','{}','{}',NULL,:now,"
                ":expires,:now,:now)"
            ),
            {"id": batch_id, "now": now, "expires": expires},
        )
    job_id = JobRepository(app.state.engine).enqueue(
        batch_id, "enrich_item", {"item_id": owned.item_id}, user_id=1
    )
    return {
        "entry_id": owned.entry_id,
        "item_id": owned.item_id,
        "shelf_id": shelf,
        "attachment_id": attachment_id,
        "batch_id": batch_id,
        "job_id": job_id,
    }


PRIVATE_PROBES = (
    ("GET", "/api/entries/{entry_id}", None, None),
    ("PATCH", "/api/entries/{entry_id}", {"notes": "probe"}, None),
    ("DELETE", "/api/entries/{entry_id}", None, None),
    ("PATCH", "/api/entries/bulk", {"entry_ids": ["ENTRY"], "set": {"score": 5}}, None),
    ("GET", "/api/items/{item_id}", None, None),
    ("PATCH", "/api/items/{item_id}", {"title": "probe"}, None),
    ("GET", "/api/items/{item_id}/cover", None, None),
    ("GET", "/api/items/{item_id}/cover-candidates", None, None),
    (
        "POST",
        "/api/items/{item_id}/cover",
        {"cover_url": "https://covers.openlibrary.org/b/id/1-L.jpg"},
        None,
    ),
    ("GET", "/api/items/{item_id}/attachments", None, None),
    ("POST", "/api/items/{item_id}/attachments", None, {"file": ("probe.txt", b"probe")}),
    ("GET", "/api/items/{item_id}/attachments/{attachment_id}", None, None),
    ("PATCH", "/api/items/{item_id}/attachments/{attachment_id}", {"filename": "probe.txt"}, None),
    ("DELETE", "/api/items/{item_id}/attachments/{attachment_id}", None, None),
    ("POST", "/api/items/{item_id}/refresh", {"overwrite": True}, None),
    ("POST", "/api/items/{item_id}/cover/fetch", None, None),
    ("PATCH", "/api/shelves/{shelf_id}", {"name": "probe"}, None),
    ("DELETE", "/api/shelves/{shelf_id}", None, None),
    ("POST", "/api/import/calibre/commit", {"batch_id": "BATCH", "choices": []}, None),
    (
        "POST",
        "/api/import/calibre/batches/{batch_id}/files",
        None,
        {"path": (None, "Author/Book/book.epub"), "file": ("book.epub", b"probe")},
    ),
    ("GET", "/api/import/jobs/{job_id}", None, None),
    ("DELETE", "/api/import/batches/{batch_id}", None, None),
)


@pytest.mark.anyio
@pytest.mark.parametrize(("method", "path_template", "body", "files"), PRIVATE_PROBES)
async def test_another_users_ids_are_always_404(
    tmp_path: Path,
    method: str,
    path_template: str,
    body: dict[str, object] | None,
    files: dict[str, tuple[object, ...]] | None,
) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", auth="on")
    )
    async with app.router.lifespan_context(app):
        ids = _seed_users_and_private_rows(app, tmp_path)
        path = path_template.format(**ids)
        payload = (
            json.loads(
                json.dumps(body)
                .replace('"ENTRY"', str(ids["entry_id"]))
                .replace('"BATCH"', json.dumps(ids["batch_id"]))
            )
            if body
            else None
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            login = await client.post(
                "/api/auth/login", json={"username": "bruno", "password": SECOND_PASSWORD}
            )
            assert COOKIE_NAME in login.cookies
            response = await client.request(method, path, json=payload, files=files)
        assert response.status_code == 404, (method, path, response.status_code, response.text)


@pytest.mark.anyio
async def test_two_users_share_one_item_and_cover_but_not_an_entry(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", auth="on")
    )
    async with app.router.lifespan_context(app):
        _seed_users(app)
        provider = CountingCoverProvider()
        output = io.BytesIO()
        Image.new("RGB", (900, 1200), "navy").save(output, "PNG")

        async def cover(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, headers={"content-type": "image/png"}, content=output.getvalue()
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(cover)) as cover_client:
            first = await AddService(
                app.state.engine,
                {provider.name: provider},
                user_id=1,
                cover_client=cover_client,
                data_dir=tmp_path / "data",
            ).add(
                manual=None,
                source=provider.name,
                source_id="OL-shared",
                supplied_refs=(),
                status=None,
                score=None,
                shelf_ids=(),
                idempotency_key=None,
            )
            second = await AddService(
                app.state.engine,
                {provider.name: provider},
                user_id=2,
                cover_client=cover_client,
                data_dir=tmp_path / "data",
            ).add(
                manual=None,
                source=provider.name,
                source_id="OL-shared",
                supplied_refs=(),
                status=None,
                score=None,
                shelf_ids=(),
                idempotency_key=None,
            )
        item_id = first["entry"]["item"]["id"]
        first_entry_id = first["entry"]["id"]
        second_entry_id = second["entry"]["id"]
        assert second["entry"]["item"]["id"] == item_id
        assert provider.fetches == 1
        with app.state.engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM items")).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM entries")).scalar_one() == 2
        assert len(list((tmp_path / "data" / "covers").glob("*.jpg"))) == 1
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/auth/login", json={"username": "bruno", "password": SECOND_PASSWORD}
            )
            assert (await client.get(f"/api/entries/{second_entry_id}")).status_code == 200
            assert (await client.get(f"/api/entries/{first_entry_id}")).status_code == 404
            assert (await client.get(f"/api/items/{item_id}")).status_code == 200


class CountingCoverProvider:
    name = "openlibrary"
    item_type = "book"

    def __init__(self) -> None:
        self.fetches = 0

    async def fetch(self, source_id: str) -> ItemPayload:
        self.fetches += 1
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title="Shared provider book",
            subtitle=None,
            creators=("Shared Author",),
            year=2026,
            cover_url="https://covers.openlibrary.org/shared.png",
            identifiers={"isbn13": "9788437604572"},
            language="en",
            metadata={"creators": ["Shared Author"]},
        )


@pytest.mark.anyio
async def test_collections_and_the_same_import_are_scoped_to_each_user(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", auth="on")
    )
    async with app.router.lifespan_context(app):
        _seed_users_and_private_rows(app, tmp_path)
        csv = (FIXTURES / "goodreads_valid.csv").read_bytes()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as admin:
            await admin.post(
                "/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
            )
            admin_preview = await admin.post(
                "/api/import/goodreads/preview", files={"file": ("library.csv", csv, "text/csv")}
            )
            assert admin_preview.status_code == 201
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as second:
            await second.post(
                "/api/auth/login", json={"username": "bruno", "password": SECOND_PASSWORD}
            )
            entries = await second.get("/api/entries", params={"status": "unsorted"})
            assert entries.json()["items"] == []
            assert (await second.get("/api/shelves")).json() == []
            assert (
                await second.get("/api/insights", params={"type": "book", "key": "creators"})
            ).json()["total_entries"] == 0
            export = await second.get("/api/export")
            assert export.json()["entries"] == []
            second_preview = await second.post(
                "/api/import/goodreads/preview", files={"file": ("library.csv", csv, "text/csv")}
            )
            assert second_preview.status_code == 201, second_preview.text
            assert second_preview.json()["batch_id"] != admin_preview.json()["batch_id"]
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE import_batches SET state='committed',committed_at=:now,"
                    "undo_expires_at=:expires WHERE id IN (:admin,:second)"
                ),
                {
                    "now": now,
                    "expires": expires,
                    "admin": admin_preview.json()["batch_id"],
                    "second": second_preview.json()["batch_id"],
                },
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as admin:
            await admin.post(
                "/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
            )
            assert (
                await admin.delete(f"/api/import/batches/{second_preview.json()['batch_id']}")
            ).status_code == 404
            own_undo = await admin.delete(f"/api/import/batches/{admin_preview.json()['batch_id']}")
            assert own_undo.status_code == 200, own_undo.text
        with app.state.engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT user_id FROM import_batches "
                    "WHERE fingerprint=:fingerprint ORDER BY user_id"
                ),
                {"fingerprint": admin_preview.json()["fingerprint"]},
            ).scalars().all() == [1, 2]
            assert (
                connection.execute(
                    text("SELECT state FROM import_batches WHERE id=:batch"),
                    {"batch": second_preview.json()["batch_id"]},
                ).scalar_one()
                == "committed"
            )
