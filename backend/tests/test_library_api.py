from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_entry_item_and_shelf_lifecycle(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET score=6, score_provisional=1 WHERE id=:id"),
                {"id": created.entry_id},
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            shelf = await client.post("/api/shelves", json={"name": "Favorites"})
            assert shelf.status_code == 201
            shelf_id = shelf.json()["id"]

            edited = await client.patch(
                f"/api/entries/{created.entry_id}",
                json={"status": "read", "score": 9, "shelf_ids": [shelf_id]},
            )
            assert edited.status_code == 200
            assert edited.json()["score"] == 9
            assert edited.json()["score_provisional"] is False
            assert edited.json()["shelves"][0]["name"] == "Favorites"

            item = await client.get(f"/api/items/{created.item_id}")
            assert item.status_code == 200
            assert item.json()["title"] == "Rayuela"
            corrected = await client.patch(
                f"/api/items/{created.item_id}", json={"subtitle": "A novel"}
            )
            assert corrected.json()["subtitle"] == "A novel"

            renamed = await client.patch(f"/api/shelves/{shelf_id}", json={"name": "Best"})
            assert renamed.json()["slug"] == "best"
            assert (await client.delete(f"/api/shelves/{shelf_id}")).status_code == 204
            assert (await client.get(f"/api/entries/{created.entry_id}")).status_code == 200
            assert (await client.delete(f"/api/entries/{created.entry_id}")).status_code == 204
            assert (await client.get(f"/api/items/{created.item_id}")).status_code == 200


@pytest.mark.anyio
async def test_domain_errors_are_stable_and_validation_is_422(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        missing = await client.get("/api/entries/999")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "entry_not_found"
        invalid = await client.patch("/api/entries/999", json={"score": 11})
        assert invalid.status_code == 422


def test_openapi_describes_static_routes_and_response_contracts(tmp_path: Path) -> None:
    schema = create_app(settings(tmp_path)).openapi()
    assert "/api/entries/bulk" in schema["paths"]
    assert "/api/entries/accept-suggested" in schema["paths"]
    list_response = schema["paths"]["/api/entries"]["get"]["responses"]["200"]
    assert list_response["content"]["application/json"]["schema"]["$ref"].endswith(
        "/EntryListResponse"
    )
    assert "ErrorResponse" in schema["components"]["schemas"]


@pytest.mark.anyio
async def test_shelf_entry_counts_and_deletion_retains_entries(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            shelf = await client.post("/api/shelves", json={"name": "Favorites"})
            shelf_id = shelf.json()["id"]
            await client.patch(
                f"/api/entries/{created.entry_id}",
                json={"status": "read", "shelf_ids": [shelf_id]},
            )
            shelves = await client.get("/api/shelves")
            assert shelves.status_code == 200
            assert shelves.json()[0]["entry_count"] == 1

            # Delete shelf detaches entries but does not delete them
            assert (await client.delete(f"/api/shelves/{shelf_id}")).status_code == 204
            entry = await client.get(f"/api/entries/{created.entry_id}")
            assert entry.status_code == 200
            assert entry.json()["shelves"] == []

            # Cached item, sources, and cover remain
            item = await client.get(f"/api/items/{created.item_id}")
            assert item.status_code == 200
            assert item.json()["title"] == "Rayuela"


# --------------------------------------------------------------------------------------
# Per-domain statuses and formats (seam 5b, DEC-057 and DEC-059)
# --------------------------------------------------------------------------------------


async def _one_of_each(app: object) -> tuple[int, int]:
    """A book entry and an album entry, returned as (book_entry_id, album_entry_id)."""
    repository = DomainRepository(app.state.engine)  # type: ignore[attr-defined]
    book = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
    album = repository.create_or_get_entry(title="Discovery", creators=("Daft Punk",))
    with app.state.engine.begin() as connection:  # type: ignore[attr-defined]
        connection.execute(
            text("UPDATE items SET type='album' WHERE id=:id"), {"id": album.item_id}
        )
    return book.entry_id, album.entry_id


@pytest.mark.anyio
async def test_a_status_is_refused_unless_the_items_own_domain_has_it(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        book_entry, album_entry = await _one_of_each(app)

        on_its_own = await client.patch(f"/api/entries/{album_entry}", json={"status": "owned"})
        borrowed = await client.patch(f"/api/entries/{album_entry}", json={"status": "read"})
        other_way = await client.patch(f"/api/entries/{book_entry}", json={"status": "owned"})
        in_bulk = await client.patch(
            "/api/entries/bulk",
            json={"entry_ids": [album_entry], "set": {"status": "read"}},
        )
        stored = await client.get(f"/api/entries/{album_entry}")

    assert on_its_own.status_code == 200
    assert on_its_own.json()["status"] == "owned"
    for refused in (borrowed, other_way, in_bulk):
        assert refused.status_code == 422
    # The message names the domain, because `read` is perfectly valid one row down.
    assert "Album" in borrowed.json()["error"]["message"]
    assert "Book" in other_way.json()["error"]["message"]
    # Refused, not stored: the bulk path writes in one transaction or not at all.
    assert stored.json()["status"] == "owned"


@pytest.mark.anyio
async def test_a_bulk_selection_spanning_domains_is_refused_whole(tmp_path: Path) -> None:
    """Half-applying a mixed bulk write is worse than refusing it: the reader cannot
    see which half landed, and the undo ledger does not cover a manual edit."""
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        book_entry, album_entry = await _one_of_each(app)
        response = await client.patch(
            "/api/entries/bulk",
            json={"entry_ids": [book_entry, album_entry], "set": {"status": "read"}},
        )
        book_after = (await client.get(f"/api/entries/{book_entry}")).json()

    assert response.status_code == 422
    assert "Album" in response.json()["error"]["message"]
    assert book_after["status"] == "unsorted"


@pytest.mark.anyio
async def test_an_album_refuses_the_fields_it_has_no_meaning_for(tmp_path: Path) -> None:
    """DEC-057. Hiding them in the UI would leave the API able to store one."""
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        book_entry, album_entry = await _one_of_each(app)
        rereads = await client.patch(f"/api/entries/{album_entry}", json={"reread_count": 2})
        started = await client.patch(
            f"/api/entries/{album_entry}", json={"date_started": "2026-01-01"}
        )
        opinion = await client.patch(f"/api/entries/{album_entry}", json={"score": 9})
        on_a_book = await client.patch(f"/api/entries/{book_entry}", json={"reread_count": 2})

    assert rereads.status_code == 422
    assert "Album" in rereads.json()["error"]["message"]
    assert started.status_code == 422
    # The score and the note carry the opinion for an album, and always could.
    assert opinion.status_code == 200
    assert opinion.json()["score"] == 9
    assert on_a_book.status_code == 200
    assert on_a_book.json()["reread_count"] == 2


@pytest.mark.anyio
async def test_a_format_hangs_on_the_entry_and_is_independent_of_status(tmp_path: Path) -> None:
    """DEC-059's whole point: "wishlist → vinyl" is the record you mean to buy."""
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        book_entry, album_entry = await _one_of_each(app)

        intended = await client.patch(
            f"/api/entries/{album_entry}", json={"status": "wishlist", "formats": ["vinyl"]}
        )
        both = await client.patch(
            f"/api/entries/{album_entry}", json={"formats": ["digital", "vinyl"]}
        )
        borrowed = await client.patch(f"/api/entries/{album_entry}", json={"formats": ["borrowed"]})
        on_a_book = await client.patch(f"/api/entries/{book_entry}", json={"formats": ["borrowed"]})
        cleared = await client.patch(f"/api/entries/{album_entry}", json={"formats": []})

    # A wishlist entry carrying a format: neither value implies the other.
    assert intended.status_code == 200
    assert intended.json()["status"] == "wishlist"
    assert intended.json()["formats"] == ["vinyl"]
    # Vinyl frequently ships with a download code, so two formats is ordinary.
    assert both.json()["formats"] == ["vinyl", "digital"]
    assert borrowed.status_code == 422
    assert "Album" in borrowed.json()["error"]["message"]
    assert on_a_book.json()["formats"] == ["borrowed"]
    assert cleared.json()["formats"] == []


@pytest.mark.anyio
async def test_formats_filter_and_count_across_a_mixed_library(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        book_entry, album_entry = await _one_of_each(app)
        await client.patch(
            f"/api/entries/{album_entry}", json={"status": "owned", "formats": ["vinyl"]}
        )
        await client.patch(
            f"/api/entries/{book_entry}", json={"status": "read", "formats": ["digital"]}
        )
        owned = await client.get("/api/entries", params={"status": "owned"})
        vinyl = await client.get("/api/entries", params={"format": "vinyl"})
        digital = await client.get("/api/entries", params={"format": "digital"})
        unknown = await client.get("/api/entries", params={"format": "cassette"})

    # "Sort by owned and see how" — the status filter plus the format on the row.
    assert [row["item"]["title"] for row in owned.json()["items"]] == ["Discovery"]
    assert owned.json()["items"][0]["formats"] == ["vinyl"]
    assert [row["id"] for row in vinyl.json()["items"]] == [album_entry]
    assert [row["id"] for row in digital.json()["items"]] == [book_entry]
    # `digital` is declared by both domains and counted once across the library.
    counts = vinyl.json()["facets"]["format_counts"]
    assert counts["vinyl"] == 1
    assert counts["digital"] == 1
    assert unknown.status_code == 422


@pytest.mark.anyio
async def test_status_counts_cover_statuses_only_one_domain_has(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        book_entry, album_entry = await _one_of_each(app)
        await client.patch(f"/api/entries/{album_entry}", json={"status": "owned"})
        await client.patch(f"/api/entries/{book_entry}", json={"status": "read"})
        page = await client.get("/api/entries")

    assert page.json()["facets"]["status_counts"] == {"owned": 1, "read": 1}
