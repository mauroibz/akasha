"""The album adapter, against recorded MusicBrainz and Cover Art Archive responses.

DEC-025 forbids proving provider-boundary behaviour with a mock of the method under
test, and DEC-052's whole argument rests on what these responses actually contain —
so every assertion here replays a capture rather than a hand-written shape.
"""

from __future__ import annotations

import httpx
import pytest
from recordings import recording, replay

from book_tracker.domains.album.providers import (
    COVER_ART_THUMBNAIL,
    MUSICBRAINZ_MIN_INTERVAL_SECONDS,
    MusicBrainzProvider,
)
from book_tracker.infrastructure.providers import ProviderPayloadError, create_provider_client

#: The Sprint 064 classes below use bare `async def test_...` methods with no
#: per-method decorator; this applies anyio to the whole module rather than
#: repeating it, which the pre-existing functions above already do individually.
pytestmark = pytest.mark.anyio

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
        # The tracklist rides along in the same request; its own tests are below.
        "tracklist": payload.metadata["tracklist"],
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


@pytest.mark.anyio
async def test_two_throttled_answers_in_a_row_are_still_survived() -> None:
    """A two-attempt budget spent its whole allowance on one 503, so a second one failed
    the add outright — HTTP 502, "That could not be added", observed live on 2026-09-02
    with 5 of 47 requests throttled. An album add makes two sequential reads, so the odds
    compound. A source that throttles by design gets the full budget (DEC-125)."""
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) <= 2:
            return httpx.Response(503, text="rate limited")
        return httpx.Response(200, json=recording("musicbrainz_search_kind_of_blue.json"))

    async def no_sleep(_seconds: float) -> None:
        return None

    async with create_provider_client(transport=httpx.MockTransport(handler)) as client:
        rows = await MusicBrainzProvider(client, CONTACT, sleep=no_sleep).search("Kind of Blue")

    assert len(attempts) == 3
    assert rows[0].title == "Kind of Blue"


@pytest.mark.anyio
async def test_a_release_carries_its_tracklist_as_ordered_metadata() -> None:
    """One `inc` parameter and no extra request, measured 2026-08-14 and re-measured
    on re-recording: 6.5 KB for *Kind of Blue*.

    Tracks are metadata on the album, not child entities. Nothing hangs off a track,
    nothing opens one, and entry hierarchy stays Sprint 028's much larger question.
    """
    async with create_provider_client(transport=replay(FETCH_ROUTES)) as client:
        payload = await MusicBrainzProvider(client, CONTACT, min_interval_seconds=0).fetch(
            KIND_OF_BLUE
        )

    tracks = payload.metadata["tracklist"]
    assert [row["title"] for row in tracks] == [
        "So What",
        "Freddie Freeloader",
        "Blue in Green",
        "All Blues",
        "Flamenco Sketches",
    ]
    # The number as printed on the sleeve, not the sequential index: this is a record,
    # so side A track 1 is `A1`. They are different strings in the same response.
    assert [row["number"] for row in tracks] == ["A1", "A2", "A3", "B1", "B2"]
    assert tracks[0]["length_ms"] == 545426
    assert payload.metadata["track_count"] == 5


@pytest.mark.anyio
async def test_the_tracklist_is_stable_across_repeated_fetches() -> None:
    """A refresh overwrites metadata wholesale, so an order derived from anything but
    the response itself would reshuffle a tracklist behind the owner's back."""
    async with create_provider_client(transport=replay(FETCH_ROUTES)) as client:
        provider = MusicBrainzProvider(client, CONTACT, min_interval_seconds=0)
        first = await provider.fetch(KIND_OF_BLUE)
        second = await provider.fetch(KIND_OF_BLUE)

    assert first.metadata["tracklist"] == second.metadata["tracklist"]


@pytest.mark.anyio
async def test_a_release_with_no_recordings_carries_no_tracklist_key() -> None:
    """Absent, not empty: a domain that has no tracks renders no empty list, and
    DEC-056 says the API serves the metadata that exists and nothing else."""
    release = dict(recording("musicbrainz_release_kind_of_blue_mono.json"))
    release["media"] = [
        {key: value for key, value in medium.items() if key != "tracks"}
        for medium in release["media"]
    ]
    routes = {
        f"/ws/2/release-group/{KIND_OF_BLUE}": (
            200,
            recording("musicbrainz_release_group_kind_of_blue.json"),
        ),
        f"/ws/2/release/{ORIGINAL_RELEASE}": (200, release),
    }
    async with create_provider_client(transport=replay(routes)) as client:
        payload = await MusicBrainzProvider(client, CONTACT, min_interval_seconds=0).fetch(
            KIND_OF_BLUE
        )

    assert "tracklist" not in payload.metadata


# ----------------------------------------------------------------------------------
# Sprint 064: fetch_by_identifier("spotify", ...), the two-pass resolver.
# ----------------------------------------------------------------------------------

PLASTIC_BEACH_SPOTIFY = "2dIGnmEIy1WZIcZCFSj6i8"
PLASTIC_BEACH_RELEASE = "574166b1-78c0-4061-8781-b699f1e5b575"
PLASTIC_BEACH_GROUP = "5a676824-18cd-4f7f-89f0-df21623e2042"

PURPOSE_SPOTIFY = "7fZH0aUAjY3ay25obOUf2a"
PURPOSE_GROUP = "2660de3c-56db-4bd1-bf99-e162c68e5712"
PURPOSE_PREFERRED_RELEASE = "006391a6-3f99-4d38-9185-50633c43fe38"

RELATION_HIT_ROUTES = {
    "/ws/2/url": (200, recording("musicbrainz_url_spotify_plastic_beach.json")),
    # The relation names this release, and `_preferred_release` (tied on
    # `first-release-date` among 18 releases) picks this same one back out of the
    # group — measured, not assumed: `replay` keys purely on path, so one recording
    # answers both the pass-1 follow-up (`inc=release-groups`) and `fetch()`'s own
    # full read (`inc=artist-credits+labels+media+release-groups+recordings`), and
    # the full capture is a strict superset of the narrower one.
    f"/ws/2/release/{PLASTIC_BEACH_RELEASE}": (
        200,
        recording("musicbrainz_release_plastic_beach.json"),
    ),
    f"/ws/2/release-group/{PLASTIC_BEACH_GROUP}": (
        200,
        recording("musicbrainz_release_group_plastic_beach.json"),
    ),
}

TEXT_FALLBACK_ROUTES = {
    "/ws/2/url": (404, recording("musicbrainz_url_no_relation.json")),
    "/ws/2/release-group": (200, recording("musicbrainz_search_purpose_justin_bieber.json")),
    f"/ws/2/release-group/{PURPOSE_GROUP}": (
        200,
        recording("musicbrainz_release_group_purpose.json"),
    ),
    f"/ws/2/release/{PURPOSE_PREFERRED_RELEASE}": (
        200,
        recording("musicbrainz_release_purpose.json"),
    ),
}


def musicbrainz(routes: dict[str, object]) -> MusicBrainzProvider:
    client = create_provider_client(replay(routes))  # type: ignore[arg-type]
    return MusicBrainzProvider(client, CONTACT, min_interval_seconds=0)


class TestSpotifyUrlRelation:
    """Pass 1: a Spotify album id resolves through MusicBrainz's own relationship."""

    async def test_a_url_relation_resolves_to_the_release_group(self) -> None:
        payload = await musicbrainz(RELATION_HIT_ROUTES).fetch_by_identifier(
            "spotify", PLASTIC_BEACH_SPOTIFY
        )
        assert payload.source_id == PLASTIC_BEACH_GROUP
        assert payload.title == "Plastic Beach"
        assert payload.creators == ("Gorillaz",)

    async def test_an_unsupported_kind_is_refused(self) -> None:
        with pytest.raises(ProviderPayloadError) as error:
            await musicbrainz({}).fetch_by_identifier("isbn", "9780307474728")
        assert error.value.code == "unsupported_identity_kind"


class TestSpotifyTextFallback:
    """Pass 2: an exact title-and-artist match, only when pass 1 misses."""

    async def test_a_url_miss_falls_through_to_an_exact_text_match(self) -> None:
        payload = await musicbrainz(TEXT_FALLBACK_ROUTES).fetch_by_identifier(
            "spotify", PURPOSE_SPOTIFY, title="Purpose", creators=("Justin Bieber",)
        )
        assert payload.source_id == PURPOSE_GROUP
        assert payload.title == "Purpose"

    async def test_a_near_miss_at_a_lower_score_is_not_accepted(self) -> None:
        """`In Rainbows` shares its query with three plausible neighbours at
        92/87/83; only the exact top-scoring, exact-title match is usable."""
        routes = {
            "/ws/2/url": (404, recording("musicbrainz_url_no_relation.json")),
            "/ws/2/release-group": (
                200,
                recording("musicbrainz_search_in_rainbows_radiohead.json"),
            ),
        }
        payload = await musicbrainz(
            {
                **routes,
                # The correct top-scoring group's own fetch chain: proves the
                # resolver picked it and not one of the lower-scoring neighbours.
                "/ws/2/release-group/6e335887-60ba-38f0-95af-fae7774336bf": (
                    200,
                    {
                        "id": "6e335887-60ba-38f0-95af-fae7774336bf",
                        "title": "In Rainbows",
                        "first-release-date": "2007-10-10",
                        "artist-credit": [
                            {"name": "Radiohead", "artist": {"sort-name": "Radiohead"}}
                        ],
                        "releases": [
                            {
                                "id": "aaaaaaaa-0000-0000-0000-000000000000",
                                "status": "Official",
                                "date": "2007-10-10",
                            }
                        ],
                    },
                ),
                "/ws/2/release/aaaaaaaa-0000-0000-0000-000000000000": (
                    200,
                    {
                        "id": "aaaaaaaa-0000-0000-0000-000000000000",
                        "title": "In Rainbows",
                        "release-group": {"id": "6e335887-60ba-38f0-95af-fae7774336bf"},
                        "media": [],
                    },
                ),
            }
        ).fetch_by_identifier(
            "spotify", "0000000000000000000000", title="In Rainbows", creators=("Radiohead",)
        )
        assert payload.source_id == "6e335887-60ba-38f0-95af-fae7774336bf"

    async def test_no_usable_result_raises_record_not_found(self) -> None:
        routes = {
            "/ws/2/url": (404, recording("musicbrainz_url_no_relation.json")),
            "/ws/2/release-group": (200, recording("musicbrainz_search_no_match.json")),
        }
        with pytest.raises(ProviderPayloadError) as error:
            await musicbrainz(routes).fetch_by_identifier(
                "spotify",
                "zzzzzzzzzzzzzzzzzzzzzz",
                title="Zzzznonexistentalbumtitle123",
                creators=("Zzzznonexistentartist456",),
            )
        assert error.value.code == "record_not_found"

    async def test_a_url_miss_with_no_context_raises_record_not_found(self) -> None:
        """A caller that supplies no title/creators (an EnrichmentSpec that does not
        declare `needs_item_context`) gets pass 1 alone."""
        routes = {"/ws/2/url": (404, recording("musicbrainz_url_no_relation.json"))}
        with pytest.raises(ProviderPayloadError) as error:
            await musicbrainz(routes).fetch_by_identifier("spotify", PURPOSE_SPOTIFY)
        assert error.value.code == "record_not_found"
