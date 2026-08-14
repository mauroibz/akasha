"""The album adapter, against recorded MusicBrainz and Cover Art Archive responses.

DEC-025 forbids proving provider-boundary behaviour with a mock of the method under
test, and DEC-052's whole argument rests on what these responses actually contain —
so every assertion here replays a capture rather than a hand-written shape.
"""

from __future__ import annotations

import httpx
import pytest
from recordings import recording, replay

from book_tracker.infrastructure.musicbrainz import (
    COVER_ART_THUMBNAIL,
    MUSICBRAINZ_MIN_INTERVAL_SECONDS,
    MusicBrainzProvider,
)
from book_tracker.infrastructure.providers import ProviderPayloadError, create_provider_client

KIND_OF_BLUE = "8e8a594f-2175-38c7-a871-abb68ec363e7"
# The mono pressing: same day as the group's `first-release-date`, and the one the
# selection rule settles on among the two originals.
ORIGINAL_RELEASE = "79ed3ff2-1b33-3245-8755-947554bc8b3d"
CONTACT = "test@example.invalid"

SEARCH_ROUTES = {"/ws/2/release-group": (200, recording("musicbrainz_search_kind_of_blue.json"))}
FETCH_ROUTES = {
    f"/ws/2/release-group/{KIND_OF_BLUE}": (
        200,
        recording("musicbrainz_release_group_kind_of_blue.json"),
    ),
    f"/ws/2/release/{ORIGINAL_RELEASE}": (
        200,
        recording("musicbrainz_release_kind_of_blue_mono.json"),
    ),
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_search_maps_a_release_group_without_borrowing_book_vocabulary() -> None:
    async with create_provider_client(transport=replay(SEARCH_ROUTES)) as client:
        rows = await MusicBrainzProvider(client, CONTACT).search("Kind of Blue")

    top = rows[0]
    assert (top.source, top.source_id) == ("musicbrainz", KIND_OF_BLUE)
    assert top.title == "Kind of Blue"
    assert top.creators == ("Miles Davis",)
    assert top.year == 1959
    # A release group has no globally unique identifier, and inventing one would be
    # worse than having none: seam 2 merges nothing rather than merging on a weak key.
    assert top.identifiers == {}
    assert top.cover_url == COVER_ART_THUMBNAIL.format(release_group=KIND_OF_BLUE)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("fixture", "expected_creator", "expected_sort"),
    [
        ("musicbrainz_search_kind_of_blue.json", "Miles Davis", "Davis, Miles"),
        ("musicbrainz_search_discovery.json", "Daft Punk", "Daft Punk"),
        (
            "musicbrainz_search_now_thats_what_i_call_music.json",
            "Various Artists",
            "Various Artists",
        ),
    ],
)
async def test_the_source_supplies_the_sort_name_and_only_inverts_a_person(
    fixture: str, expected_creator: str, expected_sort: str
) -> None:
    """AC2, and the observation the whole architecture turns on.

    MusicBrainz knows `Person` from `Group` and only inverts a person. The DEC-051
    heuristic assumes a person's name and would file `Daft Punk` under P, so the
    adapter carries the curated value through instead of computing one.
    """
    async with create_provider_client(
        transport=replay({"/ws/2/release-group": (200, recording(fixture))})
    ) as client:
        rows = await MusicBrainzProvider(client, CONTACT).search("anything")

    assert rows[0].creators[0] == expected_creator
    assert rows[0].creator_sort == expected_sort


@pytest.mark.anyio
async def test_a_credit_is_the_rendered_string_not_the_join_of_the_list() -> None:
    """Obs. 4: `", ".join(names)` is not what the source says the record is credited to."""
    async with create_provider_client(
        transport=replay(
            {"/ws/2/release-group": (200, recording("musicbrainz_search_dean_blunt.json"))}
        )
    ) as client:
        rows = await MusicBrainzProvider(client, CONTACT).search("Dean Blunt")

    collaboration = next(row for row in rows if len(row.creators) > 1)
    assert collaboration.credit == " & ".join(collaboration.creators)
    assert collaboration.credit != ", ".join(collaboration.creators)


@pytest.mark.anyio
async def test_fetch_reaches_the_release_for_what_only_an_edition_knows() -> None:
    """Release group is the work, release is the edition (obs. 1).

    The label, catalogue number, country, language and track count live on the
    release; the title, year and credit belong to the group.
    """
    async with create_provider_client(transport=replay(FETCH_ROUTES)) as client:
        payload = await MusicBrainzProvider(client, CONTACT).fetch(KIND_OF_BLUE)

    assert payload.title == "Kind of Blue"
    assert payload.year == 1959
    assert payload.creators == ("Miles Davis",)
    assert payload.creator_sort == "Davis, Miles"
    assert payload.language == "eng"
    assert payload.metadata == {
        "creators": ["Miles Davis"],
        "credit": "Miles Davis",
        "label": "Columbia",
        "catalog_number": "CL 1355",
        "country": "US",
        "language": "eng",
        "format": '12" Vinyl',
        "track_count": 5,
    }
    # The 1959 release carries no barcode at all, which is the second half of why
    # albums have no cross-provider identity.
    assert payload.identifiers == {}


@pytest.mark.anyio
async def test_a_release_that_belongs_to_another_group_is_refused() -> None:
    """DEC-044: a candidate that cannot be tied to the requested record is not merged."""
    # A real release payload — the stereo pressing — reporting a different parent.
    stranger = dict(recording("musicbrainz_release_kind_of_blue.json"))
    stranger["release-group"] = {"id": "00000000-0000-0000-0000-000000000000"}
    routes = {
        f"/ws/2/release-group/{KIND_OF_BLUE}": (
            200,
            recording("musicbrainz_release_group_kind_of_blue.json"),
        ),
        f"/ws/2/release/{ORIGINAL_RELEASE}": (200, stranger),
    }
    async with create_provider_client(transport=replay(routes)) as client:
        with pytest.raises(ProviderPayloadError):
            await MusicBrainzProvider(client, CONTACT).fetch(KIND_OF_BLUE)


@pytest.mark.anyio
async def test_every_request_is_paced_and_carries_a_descriptive_user_agent() -> None:
    """AC6. The shared 0.5 s `RateLimiter` gates the job runner, not this provider.

    Albums declare no enrichment, so MusicBrainz is reached only from interactive
    paths that never touch that limiter. The pacing has to live in the adapter.
    """
    seen: list[httpx.Request] = []
    waits: list[float] = []

    async def record_sleep(seconds: float) -> None:
        waits.append(seconds)

    async with create_provider_client(
        transport=replay(SEARCH_ROUTES, on_request=seen.append)
    ) as client:
        provider = MusicBrainzProvider(client, CONTACT, sleep=record_sleep)
        await provider.search("Kind of Blue")
        await provider.search("Kind of Blue")

    assert len(seen) == 2
    assert all(CONTACT in request.headers["user-agent"] for request in seen)
    assert all("Akasha" in request.headers["user-agent"] for request in seen)
    # The first request pays nothing; the second waits out the documented ceiling.
    assert waits and waits[-1] >= MUSICBRAINZ_MIN_INTERVAL_SECONDS * 0.9


@pytest.mark.anyio
async def test_throttling_arrives_as_503_and_is_retried() -> None:
    """Obs. 7: MusicBrainz answers 503, not 429. A policy keyed on 429 sees nothing."""
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(503, text="rate limited")
        return httpx.Response(200, json=recording("musicbrainz_search_kind_of_blue.json"))

    async def no_sleep(_seconds: float) -> None:
        return None

    async with create_provider_client(transport=httpx.MockTransport(handler)) as client:
        rows = await MusicBrainzProvider(client, CONTACT, sleep=no_sleep).search("Kind of Blue")

    assert len(attempts) == 2
    assert rows[0].title == "Kind of Blue"
