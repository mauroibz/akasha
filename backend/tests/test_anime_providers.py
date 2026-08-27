"""Anime's two adapters, replayed against responses captured from the live providers.

DEC-025 forbids proving a provider boundary with a mock of the method under test, so
every assertion here runs against a committed recording. Provenance for each file is in
`tests/fixtures/providers/README.md`; all of them were captured on 2026-08-27 during the
measurement that became DEC-088.
"""

import httpx
import pytest
from recordings import recording, replay

from book_tracker.domains.anime.providers import AniListProvider, KitsuProvider
from book_tracker.infrastructure.providers import ProviderPayloadError, create_provider_client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def anilist(routes: dict[str, object], **kwargs: object) -> AniListProvider:
    """An AniList provider whose pacing is disabled: the clock is not under test."""

    async def no_sleep(_seconds: float) -> None:
        return None

    client = create_provider_client(replay(routes, **kwargs))  # type: ignore[arg-type]
    return AniListProvider(client, "test@example.invalid", sleep=no_sleep)


def kitsu(routes: dict[str, object], **kwargs: object) -> KitsuProvider:
    client = create_provider_client(replay(routes, **kwargs))  # type: ignore[arg-type]
    return KitsuProvider(client, "test@example.invalid")


SEARCH_ROUTE = {"/": (200, recording("anilist_search_frieren.json"))}
AKAME_ROUTE = {"/": (200, recording("anilist_media_20613_akame.json"))}
CHAINSAW_ROUTE = {"/": (200, recording("anilist_media_mal_44511_chainsaw.json"))}


class TestAniListSearch:
    async def test_it_reads_the_recorded_search(self) -> None:
        rows = await anilist(SEARCH_ROUTE).search("frieren", limit=10)
        assert [row.source for row in rows] == ["anilist"] * len(rows)
        first = rows[0]
        assert first.title == "Sousou no Frieren"
        assert first.source_id == "154587"
        assert first.identifiers == {"mal": "52991"}
        assert first.year == 2023
        assert first.creators == ("MADHOUSE",)
        assert first.cover_url is not None
        assert first.cover_url.startswith("https://s4.anilist.co/")

    async def test_a_studio_is_never_inverted(self) -> None:
        """DEC-051: a source that knows the sort name seeds it, and MADHOUSE is not
        `MADHOUSE,`. DEC-068 predicted exactly this for a company rather than a person."""
        rows = await anilist(SEARCH_ROUTE).search("frieren", limit=10)
        assert rows[0].creator_sort == "MADHOUSE"

    async def test_a_row_with_no_mal_mapping_carries_no_identifier(self) -> None:
        """AniList really returns `idMal: null`, so this is not a defensive branch."""
        routes = {"/": (200, recording("anilist_search_bocchi_null_idmal.json"))}
        rows = await anilist(routes).search("bocchi the rock", limit=10)
        unmapped = [row for row in rows if not row.identifiers]
        assert unmapped, "the recording is supposed to contain a row with idMal null"
        assert all(row.title for row in unmapped)

    async def test_it_sends_a_user_agent(self) -> None:
        """Without one, Cloudflare answers `error code: 1010` with HTTP 403 (DEC-088)."""
        seen: list[httpx.Request] = []
        await anilist(SEARCH_ROUTE, on_request=seen.append).search("frieren")
        assert seen and seen[0].headers.get("user-agent", "").startswith("Akasha/")

    async def test_it_asks_by_post(self) -> None:
        seen: list[httpx.Request] = []
        await anilist(SEARCH_ROUTE, on_request=seen.append).search("frieren")
        assert seen[0].method == "POST"
        assert b"SEARCH_MATCH" in seen[0].content

    async def test_it_honours_the_limit(self) -> None:
        rows = await anilist(SEARCH_ROUTE).search("frieren", limit=2)
        assert len(rows) == 2


class TestAniListFetch:
    async def test_it_fetches_by_anilist_id(self) -> None:
        payload = await anilist(AKAME_ROUTE).fetch("20613")
        assert payload.title == "Akame ga Kill!"
        assert payload.source_id == "20613"
        assert payload.identifiers == {"mal": "22199"}
        assert payload.year == 2014
        assert payload.creators == ("WHITE FOX",)

    async def test_it_fetches_by_a_myanimelist_id(self) -> None:
        """The `mal:` prefix is how the recognizer hands over a myanimelist.net link."""
        seen: list[httpx.Request] = []
        payload = await anilist(CHAINSAW_ROUTE, on_request=seen.append).fetch("mal:44511")
        assert payload.title == "Chainsaw Man"
        assert payload.identifiers == {"mal": "44511"}
        assert b"idMal" in seen[0].content

    async def test_the_metadata_is_the_domain_s_own_fields(self) -> None:
        payload = await anilist(AKAME_ROUTE).fetch("20613")
        assert payload.metadata["kind"] == "TV"
        assert payload.metadata["episodes"] == 24
        assert payload.metadata["episode_minutes"] == 24
        assert payload.metadata["season"] == "Summer 2014"
        assert payload.metadata["source"] == "Manga"
        assert payload.metadata["airing_status"] == "Finished"
        assert payload.metadata["japanese_title"] == "アカメが斬る！"
        assert "Action" in payload.metadata["genres"]

    async def test_the_synopsis_carries_no_markup(self) -> None:
        """AniList returns `<br>` in `description` even with `asHtml: false`, and the
        field is declared `long_text` rather than markup."""
        payload = await anilist(AKAME_ROUTE).fetch("20613")
        synopsis = payload.metadata["synopsis"]
        assert "<br>" not in synopsis and "<" not in synopsis
        assert synopsis.startswith("In a land where corruption rules")

    async def test_a_missing_record_is_an_answer_and_not_an_outage(self) -> None:
        """AniList answers HTTP 404 with a GraphQL error body rather than a null."""
        routes = {"/": (404, recording("anilist_media_mal_missing.json"))}
        with pytest.raises(ProviderPayloadError):
            await anilist(routes).fetch("mal:99999999")

    async def test_it_refuses_a_payload_with_no_media(self) -> None:
        with pytest.raises(ProviderPayloadError):
            await anilist({"/": (200, {"data": {"Media": None}})}).fetch("20613")


KITSU_SEARCH = {"/api/edge/anime": (200, recording("kitsu_search_akame_mappings.json"))}
KITSU_FETCH = {"/api/edge/anime/8270": (200, recording("kitsu_anime_8270_akame.json"))}


class TestKitsuSearch:
    async def test_it_reads_the_recorded_search(self) -> None:
        rows = await kitsu(KITSU_SEARCH).search("akame ga kill", limit=10)
        assert rows[0].title == "Akame ga Kill!"
        assert rows[0].source == "kitsu"
        assert rows[0].source_id == "8270"
        assert rows[0].year == 2014
        assert rows[0].cover_url == "https://media.kitsu.app/anime/poster_images/8270/large.jpg"

    async def test_a_search_row_already_carries_the_myanimelist_id(self) -> None:
        """`include=mappings` is what makes anime's identity strategy work on this
        source: without it a Kitsu row could never merge with an AniList one."""
        rows = await kitsu(KITSU_SEARCH).search("akame ga kill", limit=10)
        assert rows[0].identifiers == {"mal": "22199"}
        assert rows[1].identifiers == {"mal": "25241"}

    async def test_it_asks_for_the_mappings(self) -> None:
        seen: list[httpx.Request] = []
        await kitsu(KITSU_SEARCH, on_request=seen.append).search("akame ga kill")
        assert seen[0].url.params["include"] == "mappings"
        assert seen[0].url.params["filter[text]"] == "akame ga kill"


class TestKitsuFetch:
    async def test_it_fetches_by_id(self) -> None:
        payload = await kitsu(KITSU_FETCH).fetch("8270")
        assert payload.title == "Akame ga Kill!"
        assert payload.identifiers == {"mal": "22199"}
        assert payload.year == 2014

    async def test_it_picks_the_studio_out_of_the_producers(self) -> None:
        """Four producers come back and only one has `role == "studio"`. Taking the
        first would have filed this under Square Enix, its manga publisher."""
        payload = await kitsu(KITSU_FETCH).fetch("8270")
        assert payload.creators == ("White Fox",)
        assert payload.creator_sort == "White Fox"

    async def test_the_metadata_is_the_domain_s_own_fields(self) -> None:
        payload = await kitsu(KITSU_FETCH).fetch("8270")
        assert payload.metadata["kind"] == "TV"
        assert payload.metadata["episodes"] == 24
        assert payload.metadata["episode_minutes"] == 23
        assert payload.metadata["airing_status"] == "Finished"
        assert "Action" in payload.metadata["genres"]
        assert payload.metadata["synopsis"].startswith("Under the rule of a tyrannical empire")

    async def test_it_fetches_by_slug(self) -> None:
        """A reader pastes `kitsu.io/anime/akame-ga-kill`, which names no numeric id."""
        routes = {"/api/edge/anime": (200, recording("kitsu_anime_slug_akame.json"))}
        seen: list[httpx.Request] = []
        payload = await kitsu(routes, on_request=seen.append).fetch("akame-ga-kill")
        assert payload.title == "Akame ga Kill!"
        assert payload.source_id == "8270"
        assert seen[0].url.params["filter[slug]"] == "akame-ga-kill"

    async def test_a_missing_record_is_refused(self) -> None:
        with pytest.raises(ProviderPayloadError):
            await kitsu({"/api/edge/anime": (200, {"data": []})}).fetch("nope-not-real")


class TestBothAdaptersAgree:
    async def test_the_same_series_gets_the_same_identity_from_either_source(self) -> None:
        """The whole point of DEC-088's identity rule, proved across two recordings."""
        from book_tracker.domains.anime import mal_identity

        from_anilist = await anilist(AKAME_ROUTE).fetch("20613")
        from_kitsu = await kitsu(KITSU_FETCH).fetch("8270")
        assert mal_identity(from_anilist) == mal_identity(from_kitsu) == "mal:22199"

    async def test_neither_leaks_a_raw_provider_row(self) -> None:
        """Technical spec 6.2: a raw response never rises above infrastructure."""
        payloads = [
            await anilist(AKAME_ROUTE).fetch("20613"),
            await kitsu(KITSU_FETCH).fetch("8270"),
        ]
        for payload in payloads:
            assert set(payload.metadata) <= {
                "creators",
                "english_title",
                "japanese_title",
                "kind",
                "episodes",
                "episode_minutes",
                "season",
                "source",
                "genres",
                "airing_status",
                "synopsis",
            }


class TestFetchByIdentifier:
    """Sprint 039: the interface background enrichment asks through.

    It replaced `fetch_by_isbn` as the enrichment entry point, because a domain's
    enrichment key is the domain's to name (DEC-067 row 3). Both anime adapters answer
    `mal`, which is the key `domains/anime` declares.
    """

    async def test_anilist_answers_a_myanimelist_id(self) -> None:
        payload = await anilist(CHAINSAW_ROUTE).fetch_by_identifier("mal", "44511")
        assert payload.title == "Chainsaw Man"
        assert payload.identifiers == {"mal": "44511"}

    async def test_kitsu_answers_a_myanimelist_id(self) -> None:
        """Kitsu reaches it in two requests: the mapping, then the record.

        Nested includes are refused with a 400 (measured 2026-08-27), so the mapping
        alone carries no studios or genres — and those are two of the three fields
        anime judges completeness by, so a one-request answer would leave every
        record looking incomplete for ever. Kitsu is the fallback provider, so the
        second request is only ever paid when AniList has already failed.
        """
        routes = {
            "/api/edge/mappings": (200, recording("kitsu_mappings_mal_22199.json")),
            "/api/edge/anime/8270": (200, recording("kitsu_anime_8270_akame.json")),
        }
        seen: list[httpx.Request] = []
        payload = await kitsu(routes, on_request=seen.append).fetch_by_identifier("mal", "22199")
        assert payload.creators == ("White Fox",)
        assert "Action" in payload.metadata["genres"]
        assert payload.title == "Akame ga Kill!"
        assert payload.source_id == "8270"
        assert payload.identifiers == {"mal": "22199"}
        assert seen[0].url.params["filter[externalSite]"] == "myanimelist/anime"
        assert seen[0].url.params["filter[externalId]"] == "22199"

    async def test_a_kind_the_adapter_does_not_answer_is_refused(self) -> None:
        """A domain naming a key its providers cannot answer is a wiring mistake, and
        it must surface as a typed provider error rather than a wrong lookup."""
        for provider in (anilist(AKAME_ROUTE), kitsu(KITSU_FETCH)):
            with pytest.raises(ProviderPayloadError) as caught:
                await provider.fetch_by_identifier("isbn", "9788437604572")
            assert caught.value.code == "unsupported_identity_kind"

    async def test_a_mal_id_that_resolves_to_nothing_is_refused(self) -> None:
        routes: dict[str, object] = {"/api/edge/mappings": (200, {"data": []})}
        with pytest.raises(ProviderPayloadError):
            await kitsu(routes).fetch_by_identifier("mal", "99999999")
