"""Provider-boundary tests that replay committed real responses (DEC-025).

No test in this module may substitute a mock for the provider method it is proving.
"""

from __future__ import annotations

import pytest
from recordings import recording, redirect_location, replay

from book_tracker.infrastructure.providers import (
    EDITION_CONFIRMED,
    EDITION_CONTRADICTED,
    EDITION_UNVERIFIABLE,
    GoogleBooksProvider,
    OpenLibraryProvider,
    ProviderPayloadError,
    classify_edition,
    create_provider_client,
)

GOOGLE_RECORDING = "googlebooks_isbn_9788437604572.json"


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


# --------------------------------------------------------------------------------------
# Edition verification (Sprint 020)
#
# `GoogleBooksProvider.fetch_by_isbn` runs an `isbn:` *search* and takes the first hit,
# which is not guaranteed to carry the ISBN that was asked for. The committed Google
# recording is itself an instance: the only hit for `isbn:9788437604572` is volume
# `B-JeAAAAMAAJ`, whose `industryIdentifiers` hold a University of Michigan barcode and
# no ISBN at all. Nothing had to be re-recorded to prove this.
# --------------------------------------------------------------------------------------


def test_classify_edition_separates_confirmation_from_absence_of_evidence() -> None:
    """Three outcomes, not two: a volume with no ISBN denies nothing."""
    assert classify_edition(["9788437604572"], "9788437604572") == EDITION_CONFIRMED
    # The same edition expressed as ISBN10 is the same edition.
    assert classify_edition(["8437604575"], "9788437604572") == EDITION_CONFIRMED
    assert classify_edition(["9780307474728"], "9788437604572") == EDITION_CONTRADICTED
    assert classify_edition([], "9788437604572") == EDITION_UNVERIFIABLE
    assert classify_edition(["UOM:39015008575477"], "9788437604572") == EDITION_UNVERIFIABLE
    # A volume listing several formats is confirmed if any of them is the one asked for.
    assert classify_edition(["9780307474728", "8437604575"], "9788437604572") == EDITION_CONFIRMED


def test_the_committed_google_recording_is_itself_the_defect() -> None:
    """Read straight from the fixture, so what is at stake stays visible in the suite.

    The only hit for `isbn:9788437604572` is a scanned volume whose identifiers are a
    University of Michigan barcode. Before the repair its publisher and page count were
    merged into whatever item asked for that ISBN, with nothing tying the two together —
    and its page count disagrees with the Open Library edition's 746.
    """
    volume = recording(GOOGLE_RECORDING)["items"][0]
    info = volume["volumeInfo"]
    carried = [value.get("identifier") for value in info["industryIdentifiers"]]

    assert volume["id"] == "B-JeAAAAMAAJ"
    assert carried == ["UOM:39015008575477"]
    assert classify_edition(carried, "9788437604572") == EDITION_UNVERIFIABLE
    assert info["publisher"] == "Ediciones Catedra S.A."
    assert info["pageCount"] == 762


@pytest.mark.anyio
async def test_open_library_confirms_the_edition_its_isbn_redirect_resolves_to() -> None:
    """Open Library reaches the edition through `/isbn/`, so it can always be checked."""
    async with create_provider_client(transport=replay(EDITION_ROUTES)) as client:
        payload = await OpenLibraryProvider(client, "test@example.invalid").fetch_by_isbn(
            "9788437604572"
        )

    assert payload.edition_match == EDITION_CONFIRMED


@pytest.mark.anyio
async def test_a_payload_reached_without_a_requested_isbn_has_no_verdict() -> None:
    """`fetch` has no edition to verify against, and must not claim one."""
    async with create_provider_client(transport=replay(EDITION_ROUTES)) as client:
        payload = await OpenLibraryProvider(client, "test@example.invalid").fetch("OL19845805M")

    assert payload.edition_match is None


@pytest.mark.anyio
async def test_google_books_refuses_a_volume_it_cannot_tie_to_the_requested_isbn() -> None:
    """The repair: an unverifiable volume is not returned for merging at all.

    Measured in DEC-044: 19.6% of Google Books answers carry no ISBN, and the observed
    failure was not a wrong printing but a wholly different book — Open Library returned
    *Crónica de una muerte anunciada* for an ISBN where Google Books returned *Las venas
    abiertas de América Latina*.
    """
    transport = replay({"/books/v1/volumes": (200, recording(GOOGLE_RECORDING))})

    async with create_provider_client(transport=transport) as client:
        with pytest.raises(ProviderPayloadError) as caught:
            await GoogleBooksProvider(client, "test-key").fetch_by_isbn("9788437604572")

    assert caught.value.code == "edition_unverified"


@pytest.mark.anyio
async def test_google_books_still_returns_a_volume_that_carries_the_requested_isbn() -> None:
    """The repair must not degenerate into switching the fallback off."""
    transport = replay(
        {"/books/v1/volumes": (200, recording("googlebooks_isbn_9780307474728.json"))}
    )

    async with create_provider_client(transport=transport) as client:
        payload = await GoogleBooksProvider(client, "test-key").fetch_by_isbn("9780307474728")

    assert payload.edition_match == EDITION_CONFIRMED
    assert payload.identifiers == {"isbn13": "9780307474728"}
    assert payload.metadata["publisher"] == "Vintage Espanol"
    assert payload.metadata["page_count"] == 498
