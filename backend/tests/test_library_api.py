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
        created = repository.create_or_get_entry(title="Rayuela", authors=("Julio Cortázar",))
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
