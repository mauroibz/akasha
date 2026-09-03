import io
from pathlib import Path

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.domain.providers import ItemPayload, SourceRef
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def image_bytes(size: tuple[int, int] = (900, 1200), color: str = "navy") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, "PNG")
    return output.getvalue()


class RefreshProvider:
    name = "openlibrary"
    item_type = "book"

    def __init__(self) -> None:
        self.fail = False

    async def fetch(self, source_id: str) -> ItemPayload:
        if self.fail:
            raise httpx.TimeoutException("offline")
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title="Provider title",
            subtitle=None,
            creators=("Provider Author",),
            year=2020,
            cover_url=None,
            identifiers={},
            language="es",
            metadata={"publisher": "New Publisher"},
        )


@pytest.mark.anyio
async def test_typed_partial_metadata_patch_migrates_legacy_publisher_and_clears(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        created = await client.post(
            "/api/entries",
            json={
                "manual": {"item_type": "book", "title": "Legacy"},
                "idempotency_key": "legacy",
            },
        )
        item_id = created.json()["entry"]["item_id"]
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET metadata = :metadata WHERE id = :id"),
                {"metadata": '{"creators": ["A"], "publishers": ["Legacy House"]}', "id": item_id},
            )
        migrated = await client.patch(
            f"/api/items/{item_id}", json={"metadata": {"language": "es"}}
        )
        cleared = await client.patch(
            f"/api/items/{item_id}", json={"metadata": {"publisher": None}}
        )
        invalid = await client.patch(
            f"/api/items/{item_id}", json={"metadata": {"unknown": "fabricated"}}
        )
        openapi = (await client.get("/openapi.json")).json()
    assert migrated.json()["metadata"]["publisher"] == "Legacy House"
    assert migrated.json()["metadata"]["language"] == "es"
    assert "publisher" not in cleared.json()["metadata"]
    assert invalid.status_code == 422
    # The patch is no longer typed by a model that names book fields; the fields are
    # published as data instead and the patch is checked against them (DEC-052 seam 3).
    assert "/api/item-types" in openapi["paths"]
    assert "ItemTypeResponse" in openapi["components"]["schemas"]


@pytest.mark.anyio
async def test_cover_replacement_is_bounded_and_preserves_previous_on_failure(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        created = await client.post(
            "/api/entries",
            json={
                "manual": {"item_type": "book", "title": "Rayuela"},
                "idempotency_key": "cover-item",
            },
        )
        item_id = created.json()["entry"]["item_id"]
        good = await client.post(
            f"/api/items/{item_id}/cover",
            files={"cover": ("cover.png", image_bytes(), "image/png")},
        )
        previous = (tmp_path / "covers" / f"{item_id}.jpg").read_bytes()
        served = await client.get(good.json()["cover_url"])
        bad = await client.post(
            f"/api/items/{item_id}/cover",
            files={"cover": ("bad.txt", b"not an image", "text/plain")},
        )
    assert good.status_code == 200
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert "immutable" in served.headers["cache-control"]
    with Image.open(tmp_path / "covers" / f"{item_id}.jpg") as normalized:
        assert normalized.format == "JPEG"
        assert max(normalized.size) == 600
    assert bad.status_code == 422
    assert (tmp_path / "covers" / f"{item_id}.jpg").read_bytes() == previous


@pytest.mark.anyio
async def test_confirmed_refresh_merges_present_metadata_and_failure_is_atomic(
    tmp_path: Path,
) -> None:
    provider = RefreshProvider()
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {provider.name: provider}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/entries",
                json={"source": "openlibrary", "source_id": "OL1M", "status": "reading"},
            )
            item_id = created.json()["entry"]["item_id"]
            await client.patch(
                f"/api/items/{item_id}",
                json={"title": "Hand title", "metadata": {"publisher": "Old", "series": "Keep"}},
            )
            required = await client.post(f"/api/items/{item_id}/refresh", json={"overwrite": False})
            refreshed = await client.post(f"/api/items/{item_id}/refresh", json={"overwrite": True})
            provider.fail = True
            failed = await client.post(f"/api/items/{item_id}/refresh", json={"overwrite": True})
            after = await client.get(f"/api/items/{item_id}")
            entry = await client.get(f"/api/entries/{created.json()['entry']['id']}")
    assert required.status_code == 422
    assert refreshed.status_code == 200
    assert refreshed.json()["title"] == "Provider title"
    assert refreshed.json()["metadata"] == {
        "publisher": "New Publisher",
        "series": "Keep",
        "creators": ["Provider Author"],
        "language": "es",
    }
    assert failed.status_code == 502
    assert after.json() == refreshed.json()
    assert entry.json()["status"] == "reading"


@pytest.mark.anyio
async def test_a_corrected_creator_sort_name_is_owner_data_and_outlives_a_refresh(
    tmp_path: Path,
) -> None:
    """Acceptance criterion 2: the correction is not cache.

    A refresh is the one path that overwrites provider-managed fields on purpose,
    so it is the sharpest test of whether the override is treated as owner data.
    It rewrites `metadata.authors` out from under the row; the sort name must not
    follow it.
    """
    provider = RefreshProvider()
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {provider.name: provider}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/entries", json={"source": "openlibrary", "source_id": "OL2M"}
            )
            item_id = created.json()["entry"]["item_id"]
            seeded = await client.get(f"/api/items/{item_id}")
            corrected = await client.patch(
                f"/api/items/{item_id}", json={"creator_sort_override": "Tolkien, J. R. R."}
            )
            refreshed = await client.post(f"/api/items/{item_id}/refresh", json={"overwrite": True})
            cleared = await client.patch(
                f"/api/items/{item_id}", json={"creator_sort_override": ""}
            )
    # Seeded by the heuristic, with nothing for the owner to keep yet.
    assert seeded.json()["creator_sort"] == "Author, Provider"
    assert "creator_sort_override" not in seeded.json()
    assert corrected.json()["creator_sort"] == "Tolkien, J. R. R."
    assert corrected.json()["creator_sort_override"] == "Tolkien, J. R. R."
    # The refresh replaced the authors and left the correction alone.
    assert refreshed.json()["metadata"]["creators"] == ["Provider Author"]
    assert refreshed.json()["creator_sort"] == "Tolkien, J. R. R."
    # Clearing it is how the owner goes back to the automatic value.
    assert cleared.json()["creator_sort"] == "Author, Provider"
    assert "creator_sort_override" not in cleared.json()


class CoverOnlyProvider:
    """A provider whose `fetch` reports a cover but different metadata each call.

    The difference is the assertion: `fetch_cover` must install the cover and
    leave the title/metadata exactly as they were, unlike `refresh`.
    """

    name = "openlibrary"
    item_type = "book"

    def __init__(self, *, cover_url: str | None) -> None:
        self.cover_url = cover_url

    async def fetch(self, source_id: str) -> ItemPayload:
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title="A title fetch_cover must not write",
            subtitle=None,
            creators=("Someone fetch_cover must not write",),
            year=1999,
            cover_url=self.cover_url,
            identifiers={},
            language=None,
            metadata={"publisher": "Not written by fetch_cover"},
        )


@pytest.mark.anyio
async def test_a_missing_cover_can_be_fetched_without_touching_metadata(
    tmp_path: Path,
) -> None:
    # No cover at add time — the scenario this endpoint exists for: an install that
    # failed (or, here, was never offered) at add time, with nothing else wrong.
    provider = CoverOnlyProvider(cover_url=None)

    async def cover_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image_bytes())

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {provider.name: provider}
        app.state.provider_client = httpx.AsyncClient(transport=httpx.MockTransport(cover_handler))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/entries", json={"source": "openlibrary", "source_id": "OL1M"}
            )
            item_id = created.json()["entry"]["item_id"]
            before = await client.patch(
                f"/api/items/{item_id}",
                json={"title": "Kept title", "metadata": {"publisher": "Owner's correction"}},
            )
            assert before.json().get("cover_url") is None
            # The provider now has a cover to offer — a since-fixed outage, in effect.
            provider.cover_url = "https://covers.openlibrary.org/b/id/12345-L.jpg"
            fetched = await client.post(f"/api/items/{item_id}/cover/fetch")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Kept title"
    assert fetched.json()["metadata"]["publisher"] == "Owner's correction"
    assert fetched.json()["cover_url"] is not None


@pytest.mark.anyio
async def test_fetching_a_cover_the_provider_does_not_have_reports_why(
    tmp_path: Path,
) -> None:
    provider = CoverOnlyProvider(cover_url=None)
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {provider.name: provider}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/entries", json={"source": "openlibrary", "source_id": "OL1M"}
            )
            item_id = created.json()["entry"]["item_id"]
            fetched = await client.post(f"/api/items/{item_id}/cover/fetch")
    assert fetched.status_code == 422
    assert fetched.json()["error"]["code"] == "cover_unavailable"


@pytest.mark.anyio
async def test_fetching_a_cover_for_an_item_with_no_provider_source_is_refused(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        created = await client.post(
            "/api/entries",
            json={
                "manual": {"item_type": "book", "title": "Manual entry"},
                "idempotency_key": "manual-cover-fetch",
            },
        )
        item_id = created.json()["entry"]["item_id"]
        fetched = await client.post(f"/api/items/{item_id}/cover/fetch")
    assert fetched.status_code == 422
    assert fetched.json()["error"]["code"] == "provider_disabled"
