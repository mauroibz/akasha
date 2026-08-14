import io
from pathlib import Path

import anyio
import httpx
import pytest
from PIL import Image

from book_tracker.config import Settings
from book_tracker.domain.identity import normalize_identifier
from book_tracker.domain.matching import MatchKind
from book_tracker.domain.providers import ItemPayload, SourceRef
from book_tracker.infrastructure.repositories import DomainRepository, SourceIdentity
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Provider:
    name = "openlibrary"
    item_type = "book"
    fetches = 0

    async def search(self, query: str, limit: int = 20):  # type: ignore[no-untyped-def]
        return []

    async def fetch(self, source_id: str) -> ItemPayload:
        self.fetches += 1
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title="Rayuela",
            subtitle="Edición crítica",
            creators=("Julio Cortázar",),
            year=2001,
            cover_url=None,
            identifiers={"isbn13": "9788437604572"},
            language="es",
            metadata={"publisher": "Cátedra", "creators": ["Julio Cortázar"]},
        )


class SortNameProvider:
    """A provider that knows how its own creator sorts, the way MusicBrainz does."""

    name = "openlibrary"
    item_type = "book"

    def __init__(self, creator: str, creator_sort: str | None) -> None:
        self.creator = creator
        self.creator_sort = creator_sort

    async def search(self, query: str, limit: int = 20):  # type: ignore[no-untyped-def]
        return []

    async def fetch(self, source_id: str) -> ItemPayload:
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title="Discovery",
            subtitle=None,
            creators=(self.creator,),
            year=2001,
            cover_url=None,
            identifiers={},
            language="en",
            metadata={"creators": [self.creator]},
            creator_sort=self.creator_sort,
        )


@pytest.mark.anyio
async def test_a_source_that_knows_the_sort_name_seeds_it_and_the_heuristic_stays_out(
    tmp_path: Path,
) -> None:
    """The rule seam 1 generalizes from Calibre: a source that knows, seeds (DEC-051).

    The heuristic assumes a person's name and would file `Daft Punk` under P, which is
    the observation the whole architecture turns on (DEC-052). It must not run on a
    name a source already answered — and it must still run when nothing knew.
    """
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": SortNameProvider("Daft Punk", "Daft Punk")}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            known = await client.post(
                "/api/entries",
                json={"source": "openlibrary", "source_id": "known", "status": "read"},
            )
        app.state.providers = {"openlibrary": SortNameProvider("Miles Davis", None)}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            unknown = await client.post(
                "/api/entries",
                json={"source": "openlibrary", "source_id": "unknown", "status": "read"},
            )

    seeded = known.json()["entry"]["item"]
    assert seeded["creator_sort_override"] == "Daft Punk"
    assert seeded["creator_sort"] == "Daft Punk"
    # Nothing knew, so the heuristic answers and stays correctable.
    guessed = unknown.json()["entry"]["item"]
    assert guessed["creator_sort_override"] is None
    assert guessed["creator_sort"] == "Davis, Miles"


@pytest.mark.anyio
async def test_manual_add_is_cached_and_idempotent_and_near_editions_only_warn(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        body = {
            "manual": {
                "title": "Rayuela",
                "creators": ["Julio Cortázar"],
                "year": 1999,
                "isbn": "978-84-376-0457-2",
            },
            "status": "read",
            "score": 9,
            "idempotency_key": "manual-rayuela-1",
        }
        created = await client.post("/api/entries", json=body)
        duplicate = await client.post("/api/entries", json=body)
        near = await client.post(
            "/api/entries",
            json={
                "manual": {
                    "title": "Rayuela",
                    "creators": ["Julio Cortázar"],
                    "year": 2005,
                    "isbn": "9780307474728",
                },
                "status": "to_read",
                "idempotency_key": "manual-rayuela-2",
            },
        )
        confirmed = await client.post(
            "/api/entries",
            json={
                "manual": {
                    "title": "Rayuela",
                    "creators": ["Julio Cortázar"],
                    "year": 2005,
                    "isbn": "9780307474728",
                },
                "status": "to_read",
                "idempotency_key": "manual-rayuela-2",
                "confirm_near_match": True,
            },
        )
    assert created.status_code == 201
    assert created.json()["entry"]["item"]["year"] == 1999
    assert created.json()["entry"]["status"] == "read"
    assert created.json()["entry"]["score"] == 9
    assert duplicate.status_code == 200
    assert duplicate.json()["already_exists"] is True
    assert near.status_code == 409
    assert near.json()["error"]["code"] == "near_match_confirmation_required"
    assert near.json()["error"]["details"]["entry_ids"] == [created.json()["entry"]["id"]]
    assert confirmed.status_code == 201
    assert confirmed.json()["near_matches"] == [created.json()["entry"]["id"]]


@pytest.mark.anyio
async def test_provider_add_refetches_once_then_library_render_uses_only_cache(
    tmp_path: Path,
) -> None:
    provider = Provider()
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
            provider.fetches = 0
            library = await client.get("/api/entries", params={"status": "reading"})
    assert created.status_code == 201
    assert created.json()["entry"]["item"]["metadata"]["publisher"] == "Cátedra"
    assert library.json()["items"][0]["item"]["title"] == "Rayuela"
    assert provider.fetches == 0


@pytest.mark.anyio
async def test_concurrent_double_submit_is_idempotent(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    statuses: list[int] = []
    async with app.router.lifespan_context(app):

        async def submit() -> None:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/entries",
                    json={
                        "manual": {"title": "Concurrent", "creators": ["Ada"]},
                        "status": "read",
                        "idempotency_key": "same-request",
                    },
                )
                statuses.append(response.status_code)

        async with anyio.create_task_group() as tasks:
            tasks.start_soon(submit)
            tasks.start_soon(submit)
    assert sorted(statuses) == [200, 201]


@pytest.mark.anyio
async def test_provider_wait_does_not_hold_sqlite_write_lock(tmp_path: Path) -> None:
    started = anyio.Event()
    release = anyio.Event()

    class WaitingProvider(Provider):
        async def fetch(self, source_id: str) -> ItemPayload:
            started.set()
            await release.wait()
            return await super().fetch(source_id)

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": WaitingProvider()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            provider_response: list[httpx.Response] = []

            async def add_from_provider() -> None:
                provider_response.append(
                    await client.post(
                        "/api/entries",
                        json={"source": "openlibrary", "source_id": "OL1M", "status": "read"},
                    )
                )

            async with anyio.create_task_group() as tasks:
                tasks.start_soon(add_from_provider)
                await started.wait()
                manual = await client.post(
                    "/api/entries",
                    json={
                        "manual": {"title": "No lock", "creators": ["Ada"]},
                        "status": "read",
                        "idempotency_key": "no-lock",
                    },
                )
                release.set()
    assert manual.status_code == 201
    assert provider_response[0].status_code == 201


@pytest.mark.anyio
async def test_secondary_source_is_attached_only_when_canonical_isbn_agrees(tmp_path: Path) -> None:
    class Secondary(Provider):
        name = "googlebooks"

        def __init__(self, isbn: str) -> None:
            self.isbn = isbn

        async def fetch(self, source_id: str) -> ItemPayload:
            payload = await super().fetch(source_id)
            isbn = "9780307474728" if source_id == "disagree" else self.isbn
            return ItemPayload(
                **{**payload.__dict__, "source": self.name, "identifiers": {"isbn13": isbn}}
            )

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {
            "openlibrary": Provider(),
            "googlebooks": Secondary("9788437604572"),
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/entries",
                json={
                    "source": "openlibrary",
                    "source_id": "OL1M",
                    "source_refs": [
                        {"source": "googlebooks", "source_id": "agree"},
                        {"source": "googlebooks", "source_id": "disagree"},
                    ],
                },
            )
        repository = DomainRepository(app.state.engine)
        agreed = repository.match(sources=[SourceIdentity("googlebooks", "agree", False)])
        rejected = repository.match(sources=[SourceIdentity("googlebooks", "disagree", False)])
    assert response.status_code == 201
    assert agreed.kind is MatchKind.EXACT
    assert rejected.kind is MatchKind.NEW


@pytest.mark.anyio
async def test_cover_failure_is_nonfatal_and_success_sets_only_valid_local_path(
    tmp_path: Path,
) -> None:
    class CoverProvider(Provider):
        async def fetch(self, source_id: str) -> ItemPayload:
            payload = await super().fetch(source_id)
            return ItemPayload(
                **{
                    **payload.__dict__,
                    "source_id": source_id,
                    "source_refs": (SourceRef(self.name, source_id),),
                    "identifiers": {},
                    "cover_url": f"https://covers.openlibrary.org/{source_id}",
                }
            )

    output = io.BytesIO()
    Image.new("RGB", (900, 1200), "navy").save(output, "PNG")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("bad"):
            return httpx.Response(500)
        return httpx.Response(200, headers={"content-type": "image/png"}, content=output.getvalue())

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as cover_client,
    ):
        app.state.providers = {"openlibrary": CoverProvider()}
        app.state.provider_client = cover_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            failed = await client.post(
                "/api/entries", json={"source": "openlibrary", "source_id": "bad"}
            )
            succeeded = await client.post(
                "/api/entries",
                json={
                    "source": "openlibrary",
                    "source_id": "good",
                    "confirm_near_match": True,
                },
            )
    assert failed.status_code == 201
    assert failed.json()["entry"]["item"]["cover_url"] is None
    assert "cover_path" not in failed.json()["entry"]["item"]
    assert succeeded.status_code == 201
    item_id = succeeded.json()["entry"]["item"]["id"]
    assert succeeded.json()["entry"]["item"]["cover_url"].startswith(
        f"/api/items/{item_id}/cover?v="
    )
    assert (tmp_path / "covers" / f"{item_id}.jpg").is_file()
    assert list((tmp_path / "covers").glob("*.tmp")) == []


@pytest.mark.anyio
async def test_contradictory_exact_identities_do_not_attach(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        repository.create_or_get_entry(
            title="ISBN item", identifiers=[normalize_identifier("isbn", "9788437604572")]
        )
        repository.create_or_get_entry(
            title="Source item", sources=[SourceIdentity("openlibrary", "OL1M", True)]
        )
        app.state.providers = {"openlibrary": Provider()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/entries",
                json={"source": "openlibrary", "source_id": "OL1M", "status": "read"},
            )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "identity_conflict"
