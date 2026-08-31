import asyncio

import httpx
import pytest

from book_tracker.application.providers import (
    InvalidResolution,
    ProvidersUnavailable,
    resolve_input,
    search_providers,
)
from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef, merge_and_rank
from book_tracker.domains.book import BOOK_IDENTITY
from book_tracker.domains.book.providers import GoogleBooksProvider, OpenLibraryProvider
from book_tracker.infrastructure.providers import MAX_PROVIDER_BYTES, ProviderPayloadError


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def candidate(
    source: str,
    source_id: str,
    *,
    isbn: str | None = None,
    title: str = "Rayuela",
    cover: str | None = None,
) -> SearchCandidate:
    return SearchCandidate(
        source=source,
        source_id=source_id,
        source_refs=(SourceRef(source, source_id),),
        title=title,
        subtitle=None,
        creators=("Julio Cortázar",),
        year=None,
        cover_url=cover,
        identifiers={"isbn13": isbn} if isbn else {},
        language="es",
        metadata={},
    )


class StubProvider:
    item_type = "book"

    def __init__(
        self,
        name: str,
        results: list[SearchCandidate] | None = None,
        error: Exception | None = None,
        delay: float = 0,
    ) -> None:
        self.name = name
        self.results = results or []
        self.error = error
        self.delay = delay

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.results[:limit]

    async def fetch(self, source_id: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError


def test_merge_retains_sources_and_prefers_google_cover_without_losing_ol_primary() -> None:
    merged = merge_and_rank(
        "Rayuela",
        [
            candidate("googlebooks", "g1", isbn="9788437604572", cover="https://cover"),
            candidate("openlibrary", "OL1M", isbn="9788437604572"),
        ],
        identity=BOOK_IDENTITY,
    )
    assert len(merged) == 1
    assert merged[0].source == "openlibrary"
    assert merged[0].cover_url == "https://cover"
    assert set(merged[0].source_refs) == {
        SourceRef("openlibrary", "OL1M"),
        SourceRef("googlebooks", "g1"),
    }


@pytest.mark.anyio
async def test_search_returns_partial_results_with_independent_timeout() -> None:
    result = await search_providers(
        "Rayuela",
        [
            StubProvider("openlibrary", [candidate("openlibrary", "OL1M")]),
            StubProvider("googlebooks", delay=0.05),
        ],
        timeout_seconds=0.01,
    )
    assert [row.source_id for row in result] == ["OL1M"]


@pytest.mark.anyio
async def test_search_reports_typed_error_only_when_every_enabled_provider_fails() -> None:
    with pytest.raises(ProvidersUnavailable):
        await search_providers(
            "Rayuela",
            [
                StubProvider("openlibrary", error=RuntimeError("bad payload")),
                StubProvider("googlebooks", error=TimeoutError()),
            ],
            timeout_seconds=0.01,
        )


@pytest.mark.anyio
async def test_openlibrary_search_keeps_work_year_out_of_edition_year() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "Akasha/0.1 (test@example.invalid)"
        return httpx.Response(
            200,
            json={
                "docs": [
                    {
                        "key": "/works/OL1W",
                        "title": "Rayuela",
                        "author_name": ["Julio Cortázar"],
                        "first_publish_year": 1963,
                        "edition_key": ["OL1M"],
                        "isbn": ["9788437604572"],
                        "language": ["spa"],
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await OpenLibraryProvider(client, "test@example.invalid").search("Rayuela")
    assert rows[0].source_id == "OL1M"
    assert rows[0].year is None
    assert rows[0].metadata["original_year"] == 1963


@pytest.mark.anyio
async def test_openlibrary_selects_nested_edition_and_resolves_full_metadata() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/search.json":
            return httpx.Response(
                200,
                json={
                    "docs": [
                        {
                            "title": "Rayuela",
                            "first_publish_year": 1963,
                            "edition_key": ["WRONG"],
                            "editions": {
                                "docs": [
                                    {
                                        "key": "/books/OL1M",
                                        "author_name": ["Julio Cortázar"],
                                        "publish_date": "2019",
                                        "isbn": ["9788437604572"],
                                        "language": ["spa"],
                                    }
                                ]
                            },
                        }
                    ]
                },
            )
        if path == "/books/OL1M.json":
            return httpx.Response(
                200,
                json={
                    "title": "Rayuela",
                    "authors": [{"key": "/authors/OL1A"}],
                    "works": [{"key": "/works/OL1W"}],
                    "publish_date": "2019",
                    "publishers": ["Cátedra"],
                    "number_of_pages": 736,
                    "languages": [{"key": "/languages/spa"}],
                    "isbn_13": ["9788437604572"],
                    "covers": [42],
                    "subjects": ["Fiction"],
                },
            )
        if path == "/authors/OL1A.json":
            return httpx.Response(200, json={"name": "Julio Cortázar"})
        if path == "/works/OL1W.json":
            return httpx.Response(
                200, json={"description": {"value": "A novel"}, "first_publish_date": "1963"}
            )
        raise AssertionError(path)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenLibraryProvider(client, "test@example.invalid")
        search = await provider.search("Rayuela")
        payload = await provider.fetch(search[0].source_id)
    assert (search[0].source_id, search[0].year, search[0].original_year) == ("OL1M", 2019, 1963)
    assert payload.creators == ("Julio Cortázar",)
    assert payload.metadata == {
        "creators": ["Julio Cortázar"],
        "publisher": "Cátedra",
        "language": "es",
        "page_count": 736,
        "description": "A novel",
        "subjects": ["Fiction"],
        "original_year": 1963,
    }
    assert payload.cover_url == "https://covers.openlibrary.org/b/id/42-L.jpg?default=false"


@pytest.mark.anyio
async def test_googlebooks_normalizes_cover_and_can_be_disabled_without_a_key() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "g1",
                        "volumeInfo": {
                            "title": "Rayuela",
                            "authors": ["Julio Cortázar"],
                            "publishedDate": "1963-06",
                            "industryIdentifiers": [
                                {"type": "ISBN_13", "identifier": "9788437604572"}
                            ],
                            "imageLinks": {
                                "thumbnail": "http://books.google.com/cover?zoom=1&edge=curl"
                            },
                        },
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await GoogleBooksProvider(client, "secret").search("Rayuela")
        disabled = GoogleBooksProvider(client, "")
    assert rows[0].year == 1963
    assert rows[0].cover_url == "https://books.google.com/cover?zoom=3"
    assert disabled.enabled is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (httpx.Response(429), httpx.HTTPStatusError),
        (httpx.Response(200, content=b"not-json"), ProviderPayloadError),
        (
            httpx.Response(
                200,
                headers={"content-length": str(MAX_PROVIDER_BYTES + 1)},
                content=b"{}",
            ),
            ProviderPayloadError,
        ),
    ],
)
async def test_provider_rejects_429_malformed_and_oversized_responses(
    response: httpx.Response, error_type: type[Exception]
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        response.request = request
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(error_type):
            await OpenLibraryProvider(client, "test@example.invalid").search("Rayuela")


@pytest.mark.anyio
async def test_resolve_work_url_requires_edition_choices_and_rejects_unsupported_urls() -> None:
    editions = [candidate("openlibrary", "OL1M"), candidate("openlibrary", "OL2M")]

    class Resolver(StubProvider):
        async def resolve_work(self, work_id: str, limit: int = 20) -> list[SearchCandidate]:
            assert work_id == "OL9W"
            return editions

    provider = Resolver("openlibrary")
    result = await resolve_input("https://openlibrary.org/works/OL9W", {"openlibrary": provider})
    assert [row.source_id for row in result] == ["OL1M", "OL2M"]
    with pytest.raises(InvalidResolution):
        await resolve_input("https://goodreads.com/book/show/1", {"openlibrary": provider})


@pytest.mark.anyio
async def test_resolve_accepts_isbn_and_supported_edition_urls() -> None:
    fetched: list[str] = []

    class Resolver(StubProvider):
        async def fetch(self, source_id: str) -> SearchCandidate:
            fetched.append(source_id)
            return candidate(self.name, source_id)

    openlibrary = Resolver("openlibrary", [candidate("openlibrary", "OL1M")])
    google = Resolver("googlebooks")
    isbn = await resolve_input("978-84-376-0457-2", {"openlibrary": openlibrary})
    ol = await resolve_input("https://openlibrary.org/books/OL7M", {"openlibrary": openlibrary})
    gb = await resolve_input("https://books.google.com/books?id=g7", {"googlebooks": google})
    assert isbn[0].source_id == "OL1M"
    assert [row.source_id for row in (*ol, *gb)] == ["OL7M", "g7"]
    assert fetched == ["OL7M", "g7"]


@pytest.mark.anyio
async def test_a_pasted_film_link_reaches_the_movie_adapter(tmp_path_factory: object) -> None:
    """The whole add-by-URL path for the fourth domain, against real recordings.

    IMDb, TMDB and Letterboxd have no adapter here. Their links still work, because the
    movie domain recognizes them and spends them on the exact Wikidata claim that names
    the same film — identity resolution against a source we have, rather than a scrape
    of one we do not (DEC-098).
    """
    from recordings import recording, replay
    from test_wikidata_provider import FETCH_1977, claim_key

    from book_tracker.domains.movie.providers import WikidataMovieProvider, wikidata_route_key
    from book_tracker.infrastructure.providers import create_provider_client

    routes = {
        claim_key("P345", "tt0076786"): (200, recording("wikidata_search_p345_tt0076786.json")),
        **FETCH_1977,
    }
    client = create_provider_client(replay(routes, key=wikidata_route_key))
    provider = WikidataMovieProvider(client, "test@example.invalid")
    try:
        resolved = await resolve_input(
            "https://www.imdb.com/title/tt0076786/", {"wikidata": provider}
        )
    finally:
        await client.aclose()

    assert [row.source_id for row in resolved] == ["Q546900"]
    assert resolved[0].title == "Suspiria"
    assert resolved[0].year == 1977


@pytest.mark.anyio
async def test_a_url_the_first_domain_refuses_falls_through_to_the_next() -> None:
    """A series IMDb URL must reach the series adapter, not die on the movie guard.

    The movie recognizer claims every `imdb.com/title/tt…` URL because it is
    registered first; its provider then refuses a series entity with
    `record_not_found`. That refusal is an answer about *its* catalogue, not about
    the URL, so the loop must offer the next domain its turn rather than returning
    the first domain's miss as the resolve's failure.
    """
    calls: list[str] = []

    class MovieStub(StubProvider):
        item_type = "movie"

        async def fetch(self, source_id: str) -> ItemPayload:
            calls.append(f"movie:{source_id}")
            raise ProviderPayloadError(
                f"Wikidata has no usable film at {source_id}", code="record_not_found"
            )

    class SeriesStub(StubProvider):
        item_type = "series"

        async def fetch(self, source_id: str) -> ItemPayload:
            calls.append(f"series:{source_id}")
            return ItemPayload(**vars(candidate(self.name, "Q1079", title="Breaking Bad")))

    resolved = await resolve_input(
        "https://www.imdb.com/title/tt0903747/",
        {"wikidata": MovieStub("wikidata"), "wikidata-series": SeriesStub("wikidata-series")},
    )
    assert [row.source_id for row in resolved] == ["Q1079"]
    # The movie adapter was asked first and refused; the series adapter then got its turn.
    assert calls == ["movie:imdb:tt0903747", "series:imdb:tt0903747"]


@pytest.mark.anyio
async def test_a_url_every_domain_refuses_is_a_miss_not_an_outage() -> None:
    """When no domain holds the record, the last refusal is the answer.

    Continuing on `record_not_found` must not turn a genuine miss into a success,
    and must not swallow a real provider outage: only the typed miss falls through.
    """

    class RefusingMovie(StubProvider):
        item_type = "movie"

        async def fetch(self, source_id: str) -> ItemPayload:
            raise ProviderPayloadError("no film here", code="record_not_found")

    class RefusingSeries(StubProvider):
        item_type = "series"

        async def fetch(self, source_id: str) -> ItemPayload:
            raise ProviderPayloadError("no series here", code="record_not_found")

    with pytest.raises(ProviderPayloadError, match="no series here"):
        await resolve_input(
            "https://www.imdb.com/title/tt9999999/",
            {
                "wikidata": RefusingMovie("wikidata"),
                "wikidata-series": RefusingSeries("wikidata-series"),
            },
        )


@pytest.mark.anyio
async def test_a_provider_outage_does_not_fall_through() -> None:
    """An outage is not a miss: the first domain being unwell is the answer.

    `record_not_found` is the only code that falls through. Anything else — the
    provider unreachable, throttled, or returning garbage — must surface as the
    failure it is rather than quietly asking the next domain to guess.
    """
    calls: list[str] = []

    class UnwellMovie(StubProvider):
        item_type = "movie"

        async def fetch(self, source_id: str) -> ItemPayload:
            calls.append("movie")
            raise ProviderPayloadError("Wikidata could not be reached", code="provider_unreachable")

    class SeriesStub(StubProvider):
        item_type = "series"

        async def fetch(self, source_id: str) -> ItemPayload:
            calls.append("series")
            return ItemPayload(**vars(candidate(self.name, "Q1079")))

    with pytest.raises(ProviderPayloadError, match="could not be reached"):
        await resolve_input(
            "https://www.imdb.com/title/tt0903747/",
            {"wikidata": UnwellMovie("wikidata"), "wikidata-series": SeriesStub("wikidata-series")},
        )
    # The series adapter was never asked: an outage is not an invitation to guess.
    assert calls == ["movie"]
