"""The metadata field spec: what a domain says its fields are, served as data.

`ItemResponse.metadata` used to be `BookMetadataResponse`, so the twelve book fields
were a contract in three places — the response model, the patch model, and a form
that listed them by hand. A second domain cannot join that arrangement without the
shared layer learning both vocabularies (DEC-052 seam 3).

Storage stays opaque. What moves is the *description* of the fields, which the API
publishes and the dialog renders.
"""

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
async def test_every_domain_publishes_its_fields(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/item-types")

    assert response.status_code == 200
    published = {row["id"]: row for row in response.json()}
    assert set(published) == {"book", "album"}

    book_fields = {field["name"]: field for field in published["book"]["fields"]}
    assert book_fields["creators"]["multiplicity"] == "many"
    assert book_fields["page_count"]["type"] == "number"
    assert book_fields["description"]["type"] == "long_text"
    # A book has no label and an album has no page count. Neither domain carries the
    # other's fields as optional nulls, which is the thing a shared model cannot avoid.
    assert "label" not in book_fields
    album_fields = {field["name"]: field for field in published["album"]["fields"]}
    assert "page_count" not in album_fields
    assert album_fields["label"]["label"] == "Label"
    assert album_fields["creators"]["label"] == "Artists"


@pytest.mark.anyio
async def test_a_patch_is_validated_against_the_fields_of_its_own_type(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        repository = DomainRepository(app.state.engine)
        book = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        album = repository.create_or_get_entry(title="Discovery", creators=("Daft Punk",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET type='album' WHERE id=:id"), {"id": album.item_id}
            )

        on_its_own_type = await client.patch(
            f"/api/items/{album.item_id}", json={"metadata": {"label": "Virgin"}}
        )
        borrowed = await client.patch(
            f"/api/items/{book.item_id}", json={"metadata": {"label": "Virgin"}}
        )
        invented = await client.patch(
            f"/api/items/{book.item_id}", json={"metadata": {"nonsense": "x"}}
        )
        out_of_range = await client.patch(
            f"/api/items/{book.item_id}", json={"metadata": {"page_count": 0}}
        )
        wrong_shape = await client.patch(
            f"/api/items/{book.item_id}", json={"metadata": {"creators": "Cortázar"}}
        )

    assert on_its_own_type.status_code == 200
    assert on_its_own_type.json()["metadata"]["label"] == "Virgin"
    # A field the domain does not declare is refused exactly as an invented one is:
    # `extra="forbid"` used to do this for the one vocabulary that existed.
    assert borrowed.status_code == 422
    assert invented.status_code == 422
    assert out_of_range.status_code == 422
    assert wrong_shape.status_code == 422


@pytest.mark.anyio
async def test_metadata_stays_opaque_in_the_response(tmp_path: Path) -> None:
    """The spec describes the fields; it does not become the storage schema."""
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        repository = DomainRepository(app.state.engine)
        album = repository.create_or_get_entry(title="Discovery", creators=("Daft Punk",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE items SET type='album',"
                    " metadata=json_set(metadata, '$.catalog_number', '7243 8 49606 1 4')"
                    " WHERE id=:id"
                ),
                {"id": album.item_id},
            )
        response = await client.get(f"/api/items/{album.item_id}")

    body = response.json()
    assert body["metadata"]["catalog_number"] == "7243 8 49606 1 4"
    assert body["metadata"]["creators"] == ["Daft Punk"]


@pytest.mark.anyio
async def test_each_domain_publishes_the_statuses_it_actually_has(tmp_path: Path) -> None:
    """Seam 5b: not the shared vocabulary renamed, a different one (DEC-057).

    Seam 5a let an album call `read` "Listened". That was honest and temporary: an
    album is played hundreds of times or twice, so possession is the fact worth
    storing, and `read` is not a state it can be in at all.
    """
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        published = {row["id"]: row for row in (await client.get("/api/item-types")).json()}

    album = published["album"]
    assert [row["value"] for row in album["statuses"]] == [
        "unsorted",
        "wishlist",
        "pending",
        "owned",
    ]
    assert album["default_status"] == "owned"
    assert album["entry_panel_label"] == "Your copy"
    # The passage fields go with the consumption vocabulary that no longer exists here.
    assert album["entry_fields"] == []

    book = published["book"]
    assert [row["value"] for row in book["statuses"]] == [
        "unsorted",
        "read",
        "reading",
        "to_read",
        "wishlist",
        "dropped",
    ]
    assert book["default_status"] == "read"
    assert sorted(book["entry_fields"]) == ["date_finished", "date_started", "reread_count"]
    # Every domain has the inbox, and nothing offers it as a choice.
    for domain in published.values():
        inbox = next(row for row in domain["statuses"] if row["value"] == "unsorted")
        assert inbox["choosable"] is False
        assert inbox["hotkey"] == "u"


@pytest.mark.anyio
async def test_each_domain_publishes_its_own_format_vocabulary(tmp_path: Path) -> None:
    """DEC-059: a closed vocabulary the domain declares, not free text and not a shelf."""
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        published = {row["id"]: row for row in (await client.get("/api/item-types")).json()}

    assert [row["value"] for row in published["album"]["formats"]] == ["vinyl", "cd", "digital"]
    assert [row["label"] for row in published["book"]["formats"]] == [
        "Physical",
        "Borrowed",
        "Digital",
    ]


@pytest.mark.anyio
async def test_a_tracklist_is_described_as_rows_and_validated_as_rows(tmp_path: Path) -> None:
    """The first field the spec could not describe (Sprint 026 deliverable 7).

    Text, a number and a list of strings could all be validated by shape alone. An
    ordered list of structured rows needs the row described too, or the dialog and
    the export are back to knowing that `tracklist` is a music thing.
    """
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        published = {row["id"]: row for row in (await client.get("/api/item-types")).json()}
        repository = DomainRepository(app.state.engine)
        album = repository.create_or_get_entry(title="Discovery", creators=("Daft Punk",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET type='album' WHERE id=:id"), {"id": album.item_id}
            )
        accepted = await client.patch(
            f"/api/items/{album.item_id}",
            json={
                "metadata": {
                    "tracklist": [{"number": "A1", "title": "One More Time", "length_ms": 320306}]
                }
            },
        )
        invented_column = await client.patch(
            f"/api/items/{album.item_id}",
            json={"metadata": {"tracklist": [{"bpm": 123}]}},
        )
        wrong_cell_type = await client.patch(
            f"/api/items/{album.item_id}",
            json={"metadata": {"tracklist": [{"length_ms": "5:20"}]}},
        )
        not_rows = await client.patch(
            f"/api/items/{album.item_id}", json={"metadata": {"tracklist": ["A1 So What"]}}
        )

    spec = next(field for field in published["album"]["fields"] if field["name"] == "tracklist")
    assert spec["type"] == "rows"
    assert [column["name"] for column in spec["columns"]] == ["number", "title", "length_ms"]
    assert spec["columns"][2]["type"] == "duration"
    # A book has no tracklist at all, so its detail page cannot render an empty one.
    assert all(field["type"] != "rows" for field in published["book"]["fields"])

    assert accepted.status_code == 200
    assert accepted.json()["metadata"]["tracklist"][0]["title"] == "One More Time"
    assert invented_column.status_code == 422
    assert wrong_cell_type.status_code == 422
    assert not_rows.status_code == 422
