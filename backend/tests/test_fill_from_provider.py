"""Sprint 109: *Fill from provider* fills only what is empty (DEC-176)."""

from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.domain.providers import ItemPayload, SourceRef
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FillProvider:
    """Answers thinly at add time and fully afterwards, as a provider that has since
    learnt more about a record does."""

    name = "openlibrary"
    item_type = "book"

    def __init__(self) -> None:
        self.full = False
        self.fail = False

    async def fetch(self, source_id: str) -> ItemPayload:
        if self.fail:
            raise httpx.TimeoutException("offline")
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title="Provider title",
            subtitle="Provider subtitle" if self.full else None,
            creators=("Provider Author",),
            year=2020 if self.full else None,
            cover_url=None,
            identifiers={},
            language=None,
            metadata=({"publisher": "Provider House", "page_count": 320} if self.full else {}),
        )


def _app(tmp_path: Path):  # type: ignore[no-untyped-def]
    return create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))


@pytest.mark.anyio
async def test_fill_fills_only_what_is_empty(tmp_path: Path) -> None:
    provider = FillProvider()
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        app.state.providers = {provider.name: provider}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/entries", json={"source": "openlibrary", "source_id": "OL1M"}
            )
            item_id = created.json()["entry"]["item_id"]
            await client.patch(
                f"/api/items/{item_id}",
                json={"title": "Hand title", "metadata": {"publisher": "Owner's house"}},
            )
            provider.full = True
            filled = await client.post(f"/api/items/{item_id}/fill")
            again = await client.post(f"/api/items/{item_id}/fill")
    assert filled.status_code == 200
    body = filled.json()
    assert body["item"]["title"] == "Hand title"
    assert body["item"]["metadata"]["publisher"] == "Owner's house"
    assert body["item"]["metadata"]["page_count"] == 320
    assert body["item"]["year"] == 2020
    assert body["item"]["subtitle"] == "Provider subtitle"
    assert sorted(body["filled"]) == ["page_count", "subtitle", "year"]
    assert body["provider"] == "Open Library"
    assert body["queued"] == 0
    assert again.json()["filled"] == []


@pytest.mark.anyio
async def test_a_failed_fill_changes_nothing(tmp_path: Path) -> None:
    provider = FillProvider()
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        app.state.providers = {provider.name: provider}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/entries", json={"source": "openlibrary", "source_id": "OL1M"}
            )
            item_id = created.json()["entry"]["item_id"]
            before = await client.get(f"/api/items/{item_id}")
            provider.full = True
            provider.fail = True
            failed = await client.post(f"/api/items/{item_id}/fill")
            after = await client.get(f"/api/items/{item_id}")
    assert failed.status_code == 502
    assert after.json() == before.json()


@pytest.mark.anyio
async def test_an_item_with_no_source_queues_its_own_enrichment(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        created = await client.post(
            "/api/entries",
            json={
                "manual": {
                    "item_type": "book",
                    "title": "Imported",
                    "identifiers": {"isbn": "9780141182803"},
                },
                "idempotency_key": "no-source",
            },
        )
        other = await client.post(
            "/api/entries",
            json={
                "manual": {
                    "item_type": "book",
                    "title": "Other",
                    "identifiers": {"isbn": "9780307474728"},
                },
                "idempotency_key": "other",
            },
        )
        assert other.status_code == 201
        item_id = created.json()["entry"]["item_id"]
        with app.state.engine.begin() as connection:
            connection.execute(text("DELETE FROM jobs"))
        filled = await client.post(f"/api/items/{item_id}/fill")
        with app.state.engine.connect() as connection:
            jobs = connection.execute(
                text("SELECT kind, json_extract(payload, '$.item_id') FROM jobs")
            ).all()
    assert filled.status_code == 200, filled.text
    assert filled.json()["queued"] == 1
    assert filled.json()["filled"] == []
    assert jobs == [("enrich_item", item_id)]


@pytest.mark.anyio
async def test_asking_again_queues_a_lookup_even_for_an_item_the_backfill_calls_complete(
    tmp_path: Path,
) -> None:
    """A field added since (a book's `chapters`) is empty on screen; the owner's own
    request queues the lookup that the backfill's completeness rule would skip."""
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        created = await client.post(
            "/api/entries",
            json={
                "manual": {
                    "item_type": "book",
                    "title": "Complete",
                    "year": 2006,
                    "identifiers": {"isbn": "9781590171998"},
                    "metadata": {
                        "publisher": "NYRB",
                        "page_count": 278,
                        "description": "A novel",
                    },
                },
                "idempotency_key": "complete",
            },
        )
        item_id = created.json()["entry"]["item_id"]
        with app.state.engine.begin() as connection:
            connection.execute(text("DELETE FROM jobs"))
            connection.execute(
                text("UPDATE items SET cover_path = 'covers/x.jpg' WHERE id = :id"),
                {"id": item_id},
            )
        filled = await client.post(f"/api/items/{item_id}/fill")
        repeated = await client.post(f"/api/items/{item_id}/fill")
        with app.state.engine.connect() as connection:
            jobs = connection.execute(text("SELECT COUNT(*) FROM jobs")).scalar_one()
    assert filled.json()["queued"] == 1
    # One already waiting answers the second request: reported, not queued twice.
    assert repeated.json()["queued"] == 1
    assert jobs == 1
