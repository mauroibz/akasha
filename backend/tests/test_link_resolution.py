"""More links resolve (Sprint 095, proposal §4.3, DEC-165 point 4).

A link without its scheme, a Spotify album link (looked up by MusicBrainz's stored
Spotify relation, or, failing that, by the title Spotify's keyless oEmbed gives), and a
Goodreads book link (by the title its slug spells; Goodreads' pages are not scraped).
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from book_tracker.application.providers import resolve_input
from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef
from book_tracker.domains.album import recognize_album_url
from book_tracker.domains.book import recognize_book_input
from book_tracker.domains.movie import recognize_movie_url
from book_tracker.infrastructure.providers import ProviderPayloadError

OEMBED = Path(__file__).parent / "fixtures" / "providers" / "spotify_oembed_kind_of_blue.json"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_a_link_without_its_scheme_is_still_a_link() -> None:
    match = recognize_movie_url("imdb.com/title/tt0111161")
    assert match is not None and match.value == "imdb:tt0111161"
    assert recognize_movie_url("www.imdb.com/title/tt0111161/") is not None


def test_a_plain_title_is_not_mistaken_for_a_link() -> None:
    assert recognize_movie_url("Kind of Blue") is None
    assert recognize_album_url("Dr. Strangelove") is None


def test_a_spotify_album_link_asks_musicbrainz_by_spotify_identity() -> None:
    for link in (
        "https://open.spotify.com/album/1weenld61qoidwYuZ1GESA",
        "open.spotify.com/intl-es/album/1weenld61qoidwYuZ1GESA?si=abc",
    ):
        match = recognize_album_url(link)
        assert match is not None, link
        assert (match.provider, match.action, match.value) == (
            "musicbrainz",
            "identifier",
            "spotify:1weenld61qoidwYuZ1GESA",
        )
        assert match.title_from == (
            "https://open.spotify.com/oembed?url=https://open.spotify.com/album/1weenld61qoidwYuZ1GESA"
        )


def test_a_goodreads_link_searches_by_the_title_its_slug_spells() -> None:
    match = recognize_book_input("https://www.goodreads.com/book/show/53413.Rayuela")
    assert match is not None and (match.action, match.value) == ("search", "Rayuela")
    slugged = recognize_book_input("goodreads.com/book/show/18144590-the-alchemist")
    assert slugged is not None and slugged.value == "the alchemist"


class Musicbrainz:
    name = "musicbrainz"
    item_type = "album"

    def __init__(self, *, relation: bool) -> None:
        self.relation = relation
        self.searched: list[str] = []

    async def fetch_by_identifier(self, kind: str, value: str, **_: Any) -> ItemPayload:
        assert kind == "spotify"
        if not self.relation:
            raise ProviderPayloadError("no relation", code="record_not_found")
        return ItemPayload(
            source="musicbrainz",
            source_id="rg-kind-of-blue",
            source_refs=(SourceRef("musicbrainz", "rg-kind-of-blue"),),
            title="Kind of Blue",
            subtitle=None,
            creators=("Miles Davis",),
            year=1959,
            cover_url=None,
            identifiers={},
            language=None,
            metadata={},
        )

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        self.searched.append(query)
        return []


@pytest.mark.anyio
async def test_a_spotify_link_resolves_through_the_stored_relation() -> None:
    provider = Musicbrainz(relation=True)
    rows = await resolve_input(
        "https://open.spotify.com/album/1weenld61qoidwYuZ1GESA", {"musicbrainz": provider}
    )
    assert [row.title for row in rows] == ["Kind of Blue"]


@pytest.mark.anyio
async def test_without_a_relation_the_oembed_title_is_searched(tmp_path: Path) -> None:
    requested: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, json=json.loads(OEMBED.read_text()))

    provider = Musicbrainz(relation=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        await resolve_input(
            "https://open.spotify.com/album/1weenld61qoidwYuZ1GESA",
            {"musicbrainz": provider},
            client=client,
        )
    assert requested and requested[0].startswith("https://open.spotify.com/oembed?url=")
    assert provider.searched == ["Kind Of Blue"]
