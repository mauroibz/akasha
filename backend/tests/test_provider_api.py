from pathlib import Path

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef
from book_tracker.infrastructure.providers import ProviderPayloadError
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Provider:
    name = "openlibrary"
    item_type = "book"

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                source=self.name,
                source_id="OL1M",
                source_refs=(SourceRef(self.name, "OL1M"),),
                title=query,
                subtitle=None,
                creators=("Author",),
                year=2001,
                cover_url=None,
                identifiers={},
                language="es",
                metadata={},
            )
        ]

    async def fetch(self, source_id: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError


@pytest.mark.anyio
async def test_search_api_returns_typed_candidates(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": Provider()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/search", params={"q": "Rayuela"})
    assert response.status_code == 200
    assert response.json()[0]["source_refs"] == [{"source": "openlibrary", "source_id": "OL1M"}]


@pytest.mark.anyio
async def test_search_api_maps_all_provider_failure_and_invalid_resolution(tmp_path: Path) -> None:
    class Failed(Provider):
        async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
            raise httpx.TimeoutException("timeout")

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": Failed()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            failed = await client.get("/api/search", params={"q": "Rayuela"})
            invalid = await client.get(
                "/api/search/resolve", params={"url": "https://goodreads.com/book/1"}
            )
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "providers_unavailable"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_resolution"


@pytest.mark.anyio
async def test_search_api_announces_partial_provider_results(tmp_path: Path) -> None:
    class Failed(Provider):
        name = "googlebooks"

        async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
            raise httpx.TimeoutException("timeout")

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": Provider(), "googlebooks": Failed()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/search", params={"q": "Rayuela"})
    assert response.status_code == 200
    assert response.headers["X-Provider-Warning"] == "Some metadata providers are unavailable"


class RecordingProvider:
    """A provider that only says whether it was asked."""

    def __init__(self, name: str, item_type: str) -> None:
        self.name = name
        self.item_type = item_type
        self.searches: list[str] = []

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        self.searches.append(query)
        return [
            SearchCandidate(
                source=self.name,
                source_id=f"{self.name}-1",
                source_refs=(SourceRef(self.name, f"{self.name}-1"),),
                title=query,
                subtitle=None,
                creators=("Someone",),
                year=2001,
                cover_url=None,
                identifiers={},
                language="en",
                metadata={},
            )
        ]

    async def fetch(self, source_id: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError


@pytest.mark.anyio
async def test_a_search_reaches_only_the_providers_of_the_domain_it_names(
    tmp_path: Path,
) -> None:
    """AC5, and it is structural rather than careful.

    A provider serves one domain, and the search endpoint selects by `item_type`, so
    adding an album cannot spend a book-provider request even by accident — which
    matters because Google Books is metered (DEC-045).
    """
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    books = RecordingProvider("openlibrary", "book")
    albums = RecordingProvider("musicbrainz", "album")
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.providers = {"openlibrary": books, "musicbrainz": albums}
        book_search = await client.get("/api/search", params={"q": "Rayuela"})
        album_search = await client.get(
            "/api/search", params={"q": "Kind of Blue", "type": "album"}
        )
        unknown = await client.get("/api/search", params={"q": "x", "type": "sculpture"})

    assert books.searches == ["Rayuela"]
    assert albums.searches == ["Kind of Blue"]
    # The default is books, so every client that predates the second domain is unchanged.
    assert book_search.json()[0]["source"] == "openlibrary"
    assert album_search.json()[0]["source"] == "musicbrainz"
    assert unknown.status_code == 422


@pytest.mark.anyio
async def test_a_url_is_resolved_by_the_domain_that_recognizes_it(tmp_path: Path) -> None:
    """Seam 6: `resolve_input` stopped knowing three book URL shapes by heart.

    Each domain recognizes its own, and only the recognizing domain's provider is
    asked — so pasting a MusicBrainz link spends nothing at Open Library.
    """
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    books = RecordingProvider("openlibrary", "book")
    albums = RecordingProvider("musicbrainz", "album")
    fetched: list[tuple[str, str]] = []

    async def remember(provider: RecordingProvider, source_id: str) -> SearchCandidate:
        fetched.append((provider.name, source_id))
        return (await provider.search(source_id))[0]

    books.fetch = lambda source_id: remember(books, source_id)  # type: ignore[method-assign]
    albums.fetch = lambda source_id: remember(albums, source_id)  # type: ignore[method-assign]

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.providers = {"openlibrary": books, "musicbrainz": albums}
        album = await client.get(
            "/api/search/resolve",
            params={
                "url": "https://musicbrainz.org/release-group/8e8a594f-2175-38c7-a871-abb68ec363e7"
            },
        )
        book = await client.get(
            "/api/search/resolve",
            params={"url": "https://openlibrary.org/books/OL19845805M"},
        )
        nonsense = await client.get("/api/search/resolve", params={"url": "https://example.com/x"})

    assert album.status_code == 200
    assert book.status_code == 200
    assert fetched == [
        ("musicbrainz", "8e8a594f-2175-38c7-a871-abb68ec363e7"),
        ("openlibrary", "OL19845805M"),
    ]
    assert nonsense.status_code == 422


class PreviewProvider:
    """A provider whose fetch returns more than its search did, which is the point."""

    name = "openlibrary"
    item_type = "book"

    def __init__(self) -> None:
        self.fetched: list[str] = []

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        return []

    async def fetch(self, source_id: str) -> ItemPayload:
        self.fetched.append(source_id)
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title="Rayuela",
            subtitle=None,
            creators=("Julio Cortázar",),
            year=1963,
            cover_url=None,
            identifiers={"isbn13": "9788437604572"},
            language="es",
            metadata={"publisher": "Sudamericana", "page_count": 736, "description": "A novel"},
        )


@pytest.mark.anyio
async def test_a_candidate_can_be_previewed_in_full_without_adding_it(tmp_path: Path) -> None:
    """The search response carries an identity; the description and page count do not
    come with it. This is the fetch that has them, on demand and writing nothing."""
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    provider = PreviewProvider()
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": provider}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            preview = await client.get(
                "/api/search/preview", params={"source": "openlibrary", "source_id": "OL1M"}
            )
            unknown = await client.get(
                "/api/search/preview", params={"source": "discogs", "source_id": "1"}
            )
            entries = await client.get("/api/entries", params={"status": "unsorted"})

    assert preview.status_code == 200
    body = preview.json()
    assert body["metadata"]["page_count"] == 736
    assert body["metadata"]["description"] == "A novel"
    assert provider.fetched == ["OL1M"]
    assert unknown.status_code == 422
    # Nothing was written: a preview is a look, not an add.
    assert entries.json()["total"] == 0


@pytest.mark.anyio
async def test_a_preview_records_its_spend_but_is_never_blocked(tmp_path: Path) -> None:
    """`search`'s rule, not enrichment's (DEC-045): somebody is waiting for this one,
    so the last request of a day belongs to them."""
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": PreviewProvider()}

        recorded: list[str] = []

        class Quota:
            def record(self, name: str, moment: object) -> None:
                recorded.append(name)

            def allows(self, name: str, moment: object) -> bool:
                return False

        app.state.provider_quota = Quota()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/preview", params={"source": "openlibrary", "source_id": "OL1M"}
            )

    assert response.status_code == 200
    assert recorded == ["openlibrary"]


@pytest.mark.anyio
async def test_a_failed_preview_is_a_502_and_not_a_crash(tmp_path: Path) -> None:
    class Broken(PreviewProvider):
        async def fetch(self, source_id: str) -> ItemPayload:
            raise RuntimeError("upstream is down")

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {"openlibrary": Broken()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/preview", params={"source": "openlibrary", "source_id": "OL1M"}
            )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_failure"


# ----------------------------------------------------------------------------------
# Sprint 055, deliverable 2: the two defects DEC-100 recorded and left.
# ----------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_record_that_does_not_exist_is_a_miss_not_an_outage(
    tmp_path: Path,
) -> None:
    """A typed `record_not_found` is an answer: "no such record". Mapping it to
    502 tells the owner the provider is down when the provider said, precisely
    and in a typed way, that the record does not exist (DEC-100)."""

    class Missing(Provider):
        name = "openlibrary"
        item_type = "book"

        async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
            return []

        async def fetch(self, source_id: str) -> ItemPayload:
            raise ProviderPayloadError("No edition at this id", code="record_not_found")

        async def fetch_by_identifier(self, kind: str, value: str) -> ItemPayload:
            raise ProviderPayloadError("No edition at this id", code="record_not_found")

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.providers = {"openlibrary": Missing()}
        miss = await client.get(
            "/api/search/resolve",
            params={"url": "https://openlibrary.org/books/OL00000000M"},
        )
        outage = await client.get(
            "/api/search/resolve",
            params={"url": "https://openlibrary.org/books/OL00000000M"},
        )

    assert miss.status_code == 404, miss.text
    assert miss.json()["error"]["code"] == "record_not_found"
    assert outage.status_code == 404
    # The message is the provider's own sentence, carried through.
    assert miss.json()["error"]["message"] == "No edition at this id"


@pytest.mark.anyio
async def test_a_transport_failure_still_reads_as_a_provider_failure(
    tmp_path: Path,
) -> None:
    """The other half of the split: a real outage stays a 502, so the typed
    miss is not hiding a provider that is genuinely down."""

    class Unreachable(Provider):
        name = "openlibrary"
        item_type = "book"

        async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
            return []

        async def fetch(self, source_id: str) -> ItemPayload:
            raise httpx.ConnectError("connection refused")

        async def fetch_by_identifier(self, kind: str, value: str) -> ItemPayload:
            raise httpx.ConnectError("connection refused")

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.providers = {"openlibrary": Unreachable()}
        failure = await client.get(
            "/api/search/resolve",
            params={"url": "https://openlibrary.org/books/OL19845805M"},
        )

    assert failure.status_code == 502, failure.text
    assert failure.json()["error"]["code"] == "provider_failure"
