"""Re-file: move an entry that landed in the wrong library into the right one (Sprint 100).

The old item's type is never edited (adding-a-domain guide §8). The target domain's
record is fetched and created properly, the entry's own values move across as far as
the target declares them, and the old item goes when nothing else holds it.
"""

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


class Fake:
    def __init__(self, name: str, item_type: str, title: str, identifiers: dict[str, str]):
        self.name = name
        self.item_type = item_type
        self.title = title
        self.identifiers = identifiers

    async def search(self, query: str, limit: int = 20):  # type: ignore[no-untyped-def]
        return []

    async def fetch(self, source_id: str) -> ItemPayload:
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title=self.title,
            subtitle=None,
            creators=(),
            year=1998,
            cover_url=None,
            identifiers=self.identifiers,
            language=None,
            metadata={},
        )


def _app(tmp_path: Path):  # type: ignore[no-untyped-def]
    return create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))


def _client(app):  # type: ignore[no-untyped-def]
    return httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test")


@pytest.mark.anyio
async def test_a_series_refiled_as_anime_keeps_what_is_yours(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.router.lifespan_context(app), _client(app) as client:
        app.state.providers = {"anilist": Fake("anilist", "anime", "Cowboy Bebop", {"mal": "1"})}
        shelf = (await client.post("/api/shelves", json={"name": "Space"})).json()["id"]
        old = (
            await client.post(
                "/api/entries",
                json={
                    "manual": {"item_type": "series", "title": "Cowboy Bebop"},
                    "idempotency_key": "bebop",
                    "status": "on_hold",
                    "score": 9,
                    "shelf_ids": [shelf],
                    "notes": "Rewatch the movie after",
                    "date_finished": "2024-03-02",
                    "formats": ["dvd", "streaming"],
                },
            )
        ).json()["entry"]

        moved = await client.post(
            f"/api/entries/{old['id']}/refile",
            json={"source": "anilist", "source_id": "1"},
        )
        assert moved.status_code == 200, moved.text
        entry = moved.json()
        assert entry["item"]["type"] == "anime"
        assert entry["status"] == "on_hold"
        assert entry["score"] == 9
        assert entry["notes"] == "Rewatch the movie after"
        assert entry["date_finished"] == "2024-03-02"
        assert [value["id"] for value in entry["shelves"]] == [shelf]
        # Anime declares streaming but has no DVD.
        assert entry["formats"] == ["streaming"]

        assert (await client.get(f"/api/entries/{old['id']}")).status_code == 404
        with app.state.engine.connect() as connection:
            remaining = connection.execute(
                text("SELECT COUNT(*) FROM items WHERE id = :id"), {"id": old["item_id"]}
            ).scalar_one()
        assert remaining == 0


@pytest.mark.anyio
async def test_a_status_the_target_lacks_becomes_its_default(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.router.lifespan_context(app), _client(app) as client:
        app.state.providers = {
            "wikidata": Fake("wikidata", "movie", "Paprika", {"imdb": "tt0851578"})
        }
        old = (
            await client.post(
                "/api/entries",
                json={
                    "manual": {"item_type": "book", "title": "Paprika"},
                    "idempotency_key": "paprika",
                    "status": "reading",
                },
            )
        ).json()["entry"]
        moved = await client.post(
            f"/api/entries/{old['id']}/refile",
            json={"source": "wikidata", "source_id": "Q1"},
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["status"] == "watchlist"


@pytest.mark.anyio
async def test_refiling_into_the_same_library_is_refused(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.router.lifespan_context(app), _client(app) as client:
        app.state.providers = {"anilist": Fake("anilist", "anime", "Bebop", {"mal": "1"})}
        old = (
            await client.post(
                "/api/entries",
                json={"manual": {"item_type": "anime", "title": "Bebop"}, "idempotency_key": "b"},
            )
        ).json()["entry"]
        refused = await client.post(
            f"/api/entries/{old['id']}/refile", json={"source": "anilist", "source_id": "1"}
        )
        assert refused.status_code == 422
        assert refused.json()["error"]["code"] == "refile_same_domain"
        assert (await client.get(f"/api/entries/{old['id']}")).status_code == 200
