"""Export: the library leaves the application in a format its owner can read.

The acceptance criterion that shapes every test here is that nothing the owner
*typed* may be missing, and nothing the application *derived* may be present.
A derived column in the dump would read as authority to whoever imports it
later, when in truth it rebuilds itself on write (DEC-036, DEC-051).
"""

from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app

DERIVED_COLUMNS = (
    "sort_author",
    "creator_sort",
    "title_normalized",
    "sort_author_normalized",
    "creator_sort_normalized",
)


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_export_carries_owner_data_and_omits_derived_columns(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(title="Rayuela", authors=("Julio Cortázar",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET creator_sort_override=:sort WHERE id=:id"),
                {"sort": "Cortázar, Julio", "id": created.item_id},
            )
            connection.execute(
                text(
                    "UPDATE entries SET score=8, notes='Read it twice', reread_count=2,"
                    " date_finished='2026-01-05' WHERE id=:id"
                ),
                {"id": created.entry_id},
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "akasha-export"
    assert payload["version"] == 1

    item = payload["items"][0]
    # The override is the one creator field no algorithm can reconstruct (DEC-051).
    assert item["creator_sort_override"] == "Cortázar, Julio"
    assert item["type"] == "book"
    assert item["metadata"]["authors"] == ["Julio Cortázar"]
    for column in DERIVED_COLUMNS:
        assert column not in item, f"{column} is derived and must not be exported"

    entry = payload["entries"][0]
    assert entry["score"] == 8
    assert entry["notes"] == "Read it twice"
    assert entry["reread_count"] == 2
    assert entry["date_finished"] == "2026-01-05"


@pytest.mark.anyio
async def test_export_of_an_empty_library_is_valid_and_empty(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.get("/api/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["entries"] == []
    assert payload["kind"] == "akasha-export"


@pytest.mark.anyio
async def test_export_does_not_special_case_the_item_type(tmp_path: Path) -> None:
    """A type the application has never seen exports through the same path.

    This is the criterion that keeps the format honest ahead of DEC-052's domain
    work: nothing here may assume the type is `book`.
    """
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(title="Kind of Blue", authors=("Miles Davis",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET type='album', metadata=:meta WHERE id=:id"),
                {
                    "meta": '{"creators": ["Miles Davis"], "label": "Columbia"}',
                    "id": created.item_id,
                },
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export")

    item = response.json()["items"][0]
    assert item["type"] == "album"
    # Opaque: the album's own vocabulary survives untranslated.
    assert item["metadata"] == {"creators": ["Miles Davis"], "label": "Columbia"}


@pytest.mark.anyio
async def test_export_carries_attachment_references_with_their_digest(tmp_path: Path) -> None:
    """References, not bytes (DEC-054).

    The filename is owner data (DEC-050), so a dump that rebuilt names from digests
    would lose a correction. The digest is what makes the reference resolvable
    against a backup, because the blob's path *is* its digest.
    """
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(title="Rayuela", authors=("Julio Cortázar",))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            upload = await client.post(
                f"/api/items/{created.item_id}/attachments",
                files={"file": ("Rayuela.epub", b"epub bytes here", "application/epub+zip")},
            )
            assert upload.status_code == 201
            attachment_id = upload.json()["id"]
            renamed = await client.patch(
                f"/api/items/{created.item_id}/attachments/{attachment_id}",
                json={"filename": "Rayuela (1963, Sudamericana).epub"},
            )
            assert renamed.status_code == 200
            response = await client.get("/api/export")

    attachments = response.json()["items"][0]["attachments"]
    assert len(attachments) == 1
    reference = attachments[0]
    # The name the owner typed, not the one the file arrived under.
    assert reference["filename"] == "Rayuela (1963, Sudamericana).epub"
    assert reference["byte_size"] == len(b"epub bytes here")
    assert len(reference["sha256"]) == 64
    assert reference["path"].endswith(f"/attachments/{attachment_id}")
    # References, not bytes.
    assert "content" not in reference and "data" not in reference
