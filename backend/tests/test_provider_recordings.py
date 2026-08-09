"""Provider-boundary tests that replay committed real responses (DEC-025).

No test in this module may substitute a mock for the provider method it is proving.
"""

from __future__ import annotations

import pytest
from recordings import recording, redirect_location, replay

from book_tracker.infrastructure.providers import (
    OpenLibraryProvider,
    ProviderPayloadError,
    create_provider_client,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


REDIRECT = {"location": redirect_location("isbn_9788437604572.headers")}
EDITION_ROUTES = {
    "/isbn/9788437604572.json": (302, None, REDIRECT),
    "/books/OL19845805M.json": (200, recording("edition_OL19845805M.json")),
    "/authors/OL2631008A.json": (200, recording("author_OL2631008A.json")),
    "/works/OL14860424W.json": (200, recording("work_OL14860424W.json")),
}


@pytest.mark.anyio
async def test_fetch_by_isbn_replays_the_real_isbn_redirect_into_a_populated_payload() -> None:
    """The recorded 302 is the whole point: /books/{isbn} answers 404 for an ISBN."""
    requested: list[str] = []
    transport = replay(
        EDITION_ROUTES, on_request=lambda request: requested.append(request.url.path)
    )

    async with create_provider_client(transport=transport) as client:
        payload = await OpenLibraryProvider(client, "test@example.invalid").fetch_by_isbn(
            "9788437604572"
        )

    assert requested[0] == "/isbn/9788437604572.json"
    assert "/books/9788437604572.json" not in requested
    assert payload.source_id == "OL19845805M"
    assert payload.title == "Rayuela"
    assert payload.authors == ("Julio Cortázar",)
    assert payload.year == 1984
    assert payload.identifiers == {"isbn13": "9788437604572"}
    assert payload.language == "es"
    assert payload.metadata["publisher"] == "Cátedra"
    assert payload.metadata["page_count"] == 746
    assert payload.cover_url == "https://covers.openlibrary.org/b/id/15103185-L.jpg?default=false"


@pytest.mark.anyio
async def test_fetch_by_isbn_normalizes_an_isbn10_edition_record_to_isbn13() -> None:
    """The recorded edition carries only `isbn_10`; enrichment matches on ISBN13."""
    async with create_provider_client(transport=replay(EDITION_ROUTES)) as client:
        payload = await OpenLibraryProvider(client, "test@example.invalid").fetch_by_isbn(
            "9788437604572"
        )
    assert recording("edition_OL19845805M.json")["isbn_10"] == ["8437604575"]
    assert payload.identifiers["isbn13"] == "9788437604572"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("route", "message"),
    [
        ((404, {"error": "notfound"}), "Open Library has no edition"),
        ((200, b"<html>not json</html>"), "malformed JSON"),
        ((200, {"key": "/books/OL1M"}), "no title"),
    ],
)
async def test_fetch_by_isbn_raises_a_typed_error_instead_of_leaking_httpx(
    route: tuple[int, object], message: str
) -> None:
    transport = replay({"/isbn/9788437604572.json": route})  # type: ignore[arg-type]
    async with create_provider_client(transport=transport) as client:
        with pytest.raises(ProviderPayloadError) as failure:
            await OpenLibraryProvider(client, "test@example.invalid").fetch_by_isbn("9788437604572")
    assert message in str(failure.value)


@pytest.mark.anyio
async def test_shared_provider_client_follows_redirects() -> None:
    """`/isbn/` answers 302; a client that does not follow it parses HTML as JSON."""
    async with create_provider_client() as client:
        assert client.follow_redirects is True
