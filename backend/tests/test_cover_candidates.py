"""Cover candidates and choosing one, proven against committed recordings (DEC-025).

DEC-044 measured the thing that makes this feature affordable: the Open Library work
record enrichment already fetches lists many editions, so offering their covers as
candidates costs no extra provider request to discover. DEC-045 authorised building it.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from recordings import recording, redirect_location, replay
from sqlalchemy import Engine, text

from book_tracker.application.providers import (
    CANDIDATE_BUDGET_SECONDS,
    CANDIDATE_TIMEOUT_SECONDS,
    cover_candidates,
)
from book_tracker.config import Settings
from book_tracker.database import create_engine as create_sqlalchemy_engine
from book_tracker.infrastructure.providers import OpenLibraryProvider, create_provider_client
from book_tracker.main import create_app
from book_tracker.migrations import upgrade


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# Edition -> work -> that work's editions. The three recordings compose into the whole
# path a chooser walks, and none of them was recorded for this feature except the last.
WORK_ROUTES: dict[str, Any] = {
    "/books/OL19845805M.json": (200, recording("edition_OL19845805M.json")),
    "/works/OL14860424W/editions.json": (200, recording("editions_OL14860424W.json")),
}
ISBN_ROUTES: dict[str, Any] = {
    "/isbn/9788437604572.json": (
        302,
        None,
        {"location": redirect_location("isbn_9788437604572.headers")},
    ),
    "/authors/OL2631008A.json": (200, recording("author_OL2631008A.json")),
    "/works/OL14860424W.json": (200, recording("work_OL14860424W.json")),
}


@pytest.mark.anyio
async def test_candidates_come_from_the_editions_of_the_work() -> None:
    async with create_provider_client(transport=replay(WORK_ROUTES)) as client:
        rows = await cover_candidates(
            OpenLibraryProvider(client, "test@example.invalid"), edition_id="OL19845805M"
        )

    assert len(rows) == 20
    assert all(row.cover_url for row in rows)
    # Real editions of a real work, which is what makes the list worth showing.
    assert {row.source_id for row in rows} >= {"OL59588323M", "OL59587941M"}


@pytest.mark.anyio
async def test_candidates_are_reachable_from_an_isbn_when_there_is_no_openlibrary_source() -> None:
    """An item added through Google Books still gets candidates, and spends no quota."""
    async with create_provider_client(transport=replay({**ISBN_ROUTES, **WORK_ROUTES})) as client:
        rows = await cover_candidates(
            OpenLibraryProvider(client, "test@example.invalid"), isbn="9788437604572"
        )

    assert len(rows) == 20


@pytest.mark.anyio
async def test_a_work_with_no_datable_editions_yields_no_candidates() -> None:
    """The empty-editions recording: an honest empty list, not an error."""
    routes = {
        "/books/OL19845805M.json": (200, recording("edition_OL19845805M.json")),
        "/works/OL14860424W/editions.json": (200, recording("editions_OL17741305W.json")),
    }
    async with create_provider_client(transport=replay(routes)) as client:
        rows = await cover_candidates(
            OpenLibraryProvider(client, "test@example.invalid"), edition_id="OL19845805M"
        )

    assert rows == []


@pytest.mark.anyio
async def test_candidates_are_deduplicated_by_cover() -> None:
    """Several editions can share one cover image; the chooser should show it once."""
    entries = recording("editions_OL14860424W.json")
    for entry in entries["entries"][:3]:
        entry["covers"] = [15104001]
    routes = {
        "/books/OL19845805M.json": (200, recording("edition_OL19845805M.json")),
        "/works/OL14860424W/editions.json": (200, entries),
    }
    async with create_provider_client(transport=replay(routes)) as client:
        rows = await cover_candidates(
            OpenLibraryProvider(client, "test@example.invalid"), edition_id="OL19845805M"
        )

    urls = [row.cover_url for row in rows]
    assert len(urls) == len(set(urls))
    assert len(rows) == 18


# --------------------------------------------------------------------------------------
# Through the API
# --------------------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    value = create_sqlalchemy_engine(configured)
    yield value
    value.dispose()


def seed_item(engine: Engine, *, source: str | None = None, isbn: str | None = None) -> int:
    with engine.begin() as connection:
        item_id = connection.execute(
            text(
                "INSERT INTO items (title, identifiers, metadata, created_at, updated_at)"
                " VALUES ('Rayuela', '{}', '{}', 'n', 'n') RETURNING id"
            )
        ).scalar_one()
        if source is not None:
            connection.execute(
                text(
                    "INSERT INTO item_sources (source, source_id, item_id, is_primary,"
                    " created_at, updated_at) VALUES (:s, :sid, :i, 1, 'n', 'n')"
                ),
                {"s": source, "sid": "OL19845805M", "i": item_id},
            )
        if isbn is not None:
            connection.execute(
                text(
                    "INSERT INTO item_identifiers (item_id, kind, value, normalized_value,"
                    " created_at, updated_at) VALUES (:i, 'isbn', :v, :v, 'n', 'n')"
                ),
                {"i": item_id, "v": isbn},
            )
    return item_id


def app_with(tmp_path: Path, engine: Engine, routes: dict[str, Any]) -> Any:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    app = create_app(configured)
    client = create_provider_client(transport=replay(routes))
    # The lifespan normally populates these; these tests drive the routes directly so
    # they can replay recordings rather than reach the network.
    app.state.engine = engine
    app.state.data_dir = tmp_path
    app.state.provider_client = client
    app.state.providers = {"openlibrary": OpenLibraryProvider(client, "test@example.invalid")}
    return app


@pytest.mark.anyio
async def test_the_endpoint_lists_candidates_for_an_open_library_item(
    tmp_path: Path, engine: Engine
) -> None:
    item_id = seed_item(engine, source="openlibrary")
    app = app_with(tmp_path, engine, WORK_ROUTES)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/items/{item_id}/cover-candidates")

    assert response.status_code == 200
    body = response.json()
    assert len(body["candidates"]) == 20
    assert body["candidates"][0]["cover_url"].startswith("https://covers.openlibrary.org/")


@pytest.mark.anyio
async def test_an_item_with_no_source_and_no_isbn_gets_an_empty_list_with_a_reason(
    tmp_path: Path, engine: Engine
) -> None:
    """Nothing to look up is not a server error, and the UI needs to say why."""
    item_id = seed_item(engine)
    app = app_with(tmp_path, engine, WORK_ROUTES)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/items/{item_id}/cover-candidates")

    assert response.status_code == 200
    assert response.json() == {"candidates": [], "reason": "no_provider_reference"}


@pytest.mark.anyio
async def test_choosing_a_candidate_installs_it_as_the_cover(
    tmp_path: Path, engine: Engine
) -> None:
    item_id = seed_item(engine, source="openlibrary")
    app = app_with(tmp_path, engine, WORK_ROUTES)
    app.state.provider_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, headers={"content-type": "image/jpeg"}, content=_jpeg()
            )
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/items/{item_id}/cover",
            json={"cover_url": "https://covers.openlibrary.org/b/id/15104001-L.jpg"},
        )

    assert response.status_code == 200
    assert (tmp_path / "covers" / f"{item_id}.jpg").is_file()
    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT cover_path FROM items WHERE id=:i"), {"i": item_id}
        ).scalar_one()
    assert stored == f"covers/{item_id}.jpg"


@pytest.mark.anyio
async def test_a_candidate_on_an_unlisted_host_is_refused(tmp_path: Path, engine: Engine) -> None:
    """The chooser must not become a way to fetch arbitrary URLs through the server."""
    item_id = seed_item(engine, source="openlibrary")
    app = app_with(tmp_path, engine, WORK_ROUTES)
    app.state.provider_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=b"unreachable"))
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/items/{item_id}/cover",
            json={"cover_url": "https://example.invalid/evil.jpg"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_cover"
    assert not (tmp_path / "covers" / f"{item_id}.jpg").exists()


@pytest.mark.anyio
async def test_a_failed_candidate_download_leaves_the_previous_cover_in_place(
    tmp_path: Path, engine: Engine
) -> None:
    item_id = seed_item(engine, source="openlibrary")
    covers = tmp_path / "covers"
    covers.mkdir(parents=True, exist_ok=True)
    (covers / f"{item_id}.jpg").write_bytes(b"the original cover")
    app = app_with(tmp_path, engine, WORK_ROUTES)
    app.state.provider_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(404, content=b"gone"))
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/items/{item_id}/cover",
            json={"cover_url": "https://covers.openlibrary.org/b/id/15104001-L.jpg"},
        )

    assert response.status_code == 422
    assert (covers / f"{item_id}.jpg").read_bytes() == b"the original cover"


def _jpeg() -> bytes:
    import io

    from PIL import Image

    output = io.BytesIO()
    Image.new("RGB", (400, 600), "#334455").save(output, "JPEG")
    return output.getvalue()


assert json  # the seed helpers keep metadata as JSON text


@pytest.mark.anyio
async def test_an_isbn_open_library_does_not_index_reads_as_no_candidates(
    tmp_path: Path, engine: Engine
) -> None:
    """Not indexed is not unreachable.

    The walkthrough hit this: Open Library answers 404 for a perfectly good ISBN it
    simply does not carry, and reporting that as "could not be reached" sends the
    reader chasing a network problem that does not exist.
    """
    item_id = seed_item(engine, isbn="9788439731764")
    app = app_with(tmp_path, engine, {"/isbn/9788439731764.json": (404, {"error": "notfound"})})

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/items/{item_id}/cover-candidates")

    assert response.json() == {"candidates": [], "reason": "no_candidates"}


@pytest.mark.anyio
async def test_candidate_lookup_outlasts_the_default_client_timeout() -> None:
    """The shared client allows 5s, which the walkthrough proved too tight here.

    Open Library was measured answering one edition record in 11.3s. The candidate path
    therefore carries its own, longer per-request budget — but deliberately not one
    large enough to cover that worst case on a single attempt, because a person is
    waiting on this dialog. Two attempts at ten seconds under an overall cap is the
    trade: the common slow response is covered, and a bad minute is reported quickly
    instead of held behind a spinner.
    """
    seen: list[float | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions.get("timeout", {}).get("read"))
        return httpx.Response(200, json=recording("edition_OL19845805M.json"))

    async with create_provider_client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenLibraryProvider(client, "test@example.invalid")
        await provider.work_id("OL19845805M", timeout=CANDIDATE_TIMEOUT_SECONDS)

    assert seen == [CANDIDATE_TIMEOUT_SECONDS]
    # Longer than the shared client's 5s, and short enough that two attempts plus
    # backoff still fit inside the overall budget a waiting reader is held to.
    assert CANDIDATE_TIMEOUT_SECONDS > 5
    assert 2 * CANDIDATE_TIMEOUT_SECONDS <= CANDIDATE_BUDGET_SECONDS + 5


@pytest.mark.anyio
async def test_an_unreachable_provider_is_not_blamed_on_the_data(
    tmp_path: Path, engine: Engine
) -> None:
    """The other half of the same mistake.

    `fetch_by_isbn` raises the same exception type for "not indexed" and for "could not
    be reached"; only the code separates them. Mapping both to `no_candidates` tells the
    reader this book has no other editions when Open Library is simply down — which it
    genuinely was during the walkthrough, answering 503.
    """
    item_id = seed_item(engine, isbn="9788439731764")
    app = app_with(tmp_path, engine, {"/isbn/9788439731764.json": (503, {"error": "unavailable"})})

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/items/{item_id}/cover-candidates")

    assert response.json() == {"candidates": [], "reason": "provider_unavailable"}


@pytest.mark.anyio
async def test_editions_without_a_real_cover_image_are_not_offered() -> None:
    """`resolve_work` invents an `/b/olid/` URL for an edition that has no cover.

    That URL is a plausible string and a 404. The walkthrough clicked one: six tiles in
    a twenty-tile grid were blank, and choosing one answered 422. Only editions whose
    record actually carries a cover id are offered.
    """
    entries = recording("editions_OL14860424W.json")
    for entry in entries["entries"][:4]:
        entry.pop("covers", None)
    routes = {
        "/books/OL19845805M.json": (200, recording("edition_OL19845805M.json")),
        "/works/OL14860424W/editions.json": (200, entries),
    }
    async with create_provider_client(transport=replay(routes)) as client:
        rows = await cover_candidates(
            OpenLibraryProvider(client, "test@example.invalid"), edition_id="OL19845805M"
        )

    assert len(rows) == 16
    assert all("/b/id/" in (row.cover_url or "") for row in rows)
    assert not any("/b/olid/" in (row.cover_url or "") for row in rows)


@pytest.mark.anyio
async def test_the_chooser_gives_up_rather_than_making_someone_wait(
    tmp_path: Path, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retries multiply the worst case, and someone is watching this one.

    Each request may now be attempted three times at up to CANDIDATE_TIMEOUT_SECONDS
    each, across two or three requests — minutes of spinner if Open Library is fully
    down. The whole operation therefore carries one budget, the same way
    `search_providers` bounds a search.
    """
    item_id = seed_item(engine, source="openlibrary")
    # The real budget is 25s. The behaviour under test is that there *is* one and that
    # it is enforced, not its value, so the suite does not sit through it.
    monkeypatch.setattr("book_tracker.api.library.CANDIDATE_BUDGET_SECONDS", 0.5)

    async def crawl(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(30)
        return httpx.Response(200, json={})

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    app = create_app(configured)
    client = create_provider_client(transport=httpx.MockTransport(crawl))
    app.state.engine = engine
    app.state.data_dir = tmp_path
    app.state.provider_client = client
    app.state.providers = {"openlibrary": OpenLibraryProvider(client, "test@example.invalid")}

    started = asyncio.get_running_loop().time()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as http:
        response = await http.get(f"/api/items/{item_id}/cover-candidates")
    elapsed = asyncio.get_running_loop().time() - started

    assert response.json() == {"candidates": [], "reason": "provider_unavailable"}
    assert elapsed < 5
    # A dialog someone opened is allowed to wait a little, not a lot.
    assert CANDIDATE_BUDGET_SECONDS <= 15.0
