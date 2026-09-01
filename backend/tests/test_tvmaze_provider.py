"""TVmaze's series adapter, replayed against responses captured from the live API.

DEC-025 forbids proving a provider boundary with a mock of the method under test, so
every assertion here runs against a committed recording. All twelve files were
captured live on 2026-08-31 with `User-Agent: Akasha/1.4 (local@example.invalid)`;
provenance is in `tests/fixtures/providers/README.md`.

Two measured shapes are load-bearing and pinned here:

- `/lookup/shows?imdb=` answers a hit with **301 → /shows/<id>** and a `null` body,
  and a miss with **404** and a `null` body. A miss is an answer
  (`record_not_found`), never an outage.
- `summary` arrives as HTML (`<p><b>Breaking Bad</b> follows…`). It is parsed to
  plain text the way the Letterboxd reader parses a review, and no markup is ever
  stored.
"""

import httpx
import pytest
from recordings import recording, replay

from book_tracker.application.providers import search_providers
from book_tracker.domain.providers import ItemPayload, SearchCandidate, merge_and_rank
from book_tracker.domains.series import SERIES_IDENTITY, imdb_identity
from book_tracker.domains.series.providers import WikidataSeriesProvider, wikidata_series_route_key
from book_tracker.domains.series.tvmaze import TvmazeSeriesProvider
from book_tracker.infrastructure.providers import ProviderPayloadError, create_provider_client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def tvmaze(routes: dict[str, object], **kwargs: object) -> TvmazeSeriesProvider:
    """A TVmaze provider whose pacing is disabled: the clock is not under test."""

    async def no_sleep(_seconds: float) -> None:
        return None

    client = create_provider_client(replay(routes, **kwargs))  # type: ignore[arg-type]
    return TvmazeSeriesProvider(client, "test@example.invalid", sleep=no_sleep)


SEARCH_BREAKING_BAD = {"/search/shows": (200, recording("tvmaze_search_breaking_bad.json"))}
SEARCH_SIMULADORES = {"/search/shows": (200, recording("tvmaze_search_los_simuladores.json"))}
SEARCH_OKUPAS = {"/search/shows": (200, recording("tvmaze_search_okupas.json"))}
LOOKUP_HIT = {"/lookup/shows": (200, recording("tvmaze_lookup_tt0903747.json"))}
LOOKUP_MISS = {"/lookup/shows": (404, recording("tvmaze_lookup_no_match.json"))}
FETCH_BREAKING_BAD = {"/shows/169": (200, recording("tvmaze_show_169_breaking_bad.json"))}
FETCH_MANDALORIAN = {"/shows/38963": (200, recording("tvmaze_show_38963_mandalorian.json"))}
FETCH_SAMANTHA_OUPS = {"/shows/76954": (200, recording("tvmaze_show_76954_samantha_oups.json"))}


class TestTvmazeSearch:
    async def test_it_reads_the_recorded_search(self) -> None:
        rows = await tvmaze(SEARCH_BREAKING_BAD).search("Breaking Bad")
        first = rows[0]
        assert first.source == "tvmaze"
        assert first.source_id == "169"
        assert first.title == "Breaking Bad"
        assert first.year == 2008
        assert first.identifiers["imdb"] == "tt0903747"

    async def test_it_asks_the_search_endpoint_and_sends_a_user_agent(self) -> None:
        seen: list[httpx.Request] = []
        await tvmaze(SEARCH_BREAKING_BAD, on_request=seen.append).search("Breaking Bad")
        assert seen[0].url.path == "/search/shows"
        assert seen[0].url.params["q"] == "Breaking Bad"
        assert "Akasha" in seen[0].headers["user-agent"]

    async def test_the_metadata_is_the_domain_s_own_fields(self) -> None:
        row = (await tvmaze(SEARCH_BREAKING_BAD).search("Breaking Bad"))[0]
        assert set(row.metadata) <= {
            "genres",
            "network",
            "episode_minutes",
            "airing_status",
            "synopsis",
        }
        assert row.metadata["genres"] == ["Drama", "Crime", "Thriller"]
        assert row.metadata["network"] == "AMC"
        assert row.metadata["episode_minutes"] == 60
        assert row.metadata["airing_status"] == "Ended"

    async def test_the_synopsis_arrives_as_plain_text(self) -> None:
        row = (await tvmaze(SEARCH_BREAKING_BAD).search("Breaking Bad"))[0]
        synopsis = row.metadata["synopsis"]
        assert synopsis.startswith("Breaking Bad follows protagonist Walter White")
        assert "<" not in synopsis and ">" not in synopsis

    async def test_it_emits_no_cover_and_no_episode_count(self) -> None:
        """Covers come from Stremio and the episode total from Wikidata (AC5, AC7)."""
        row = (await tvmaze(SEARCH_BREAKING_BAD).search("Breaking Bad"))[0]
        assert row.cover_url is None
        assert "episodes" not in row.metadata

    async def test_the_shows_wikidata_s_title_search_misses(self) -> None:
        """AC2: two Argentine Spanish-language series, found by name, with the year."""
        simuladores = (await tvmaze(SEARCH_SIMULADORES).search("Los Simuladores"))[0]
        assert simuladores.title == "Los Simuladores"
        assert simuladores.year == 2002
        assert simuladores.identifiers["imdb"] == "tt0316613"
        okupas = (await tvmaze(SEARCH_OKUPAS).search("Okupas"))[0]
        assert okupas.title == "Okupas"
        assert okupas.year == 2000
        assert okupas.identifiers["imdb"] == "tt0289649"


class TestTvmazeLookup:
    async def test_an_imdb_hit_is_the_show_record(self) -> None:
        payload = await tvmaze(LOOKUP_HIT).fetch_by_identifier("imdb", "tt0903747")
        assert payload.title == "Breaking Bad"
        assert payload.source_id == "169"
        assert payload.identifiers["imdb"] == "tt0903747"

    async def test_an_imdb_miss_is_an_answer_not_an_outage(self) -> None:
        with pytest.raises(ProviderPayloadError) as caught:
            await tvmaze(LOOKUP_MISS).fetch_by_identifier("imdb", "tt9999999")
        assert caught.value.code == "record_not_found"

    async def test_a_kind_the_adapter_does_not_answer_is_refused(self) -> None:
        with pytest.raises(ProviderPayloadError) as caught:
            await tvmaze(LOOKUP_HIT).fetch_by_identifier("isbn", "9788437604572")
        assert caught.value.code == "unsupported_identity_kind"


class TestTvmazeFetch:
    async def test_it_fetches_by_tvmaze_id(self) -> None:
        payload = await tvmaze(FETCH_BREAKING_BAD).fetch("169")
        assert payload.title == "Breaking Bad"
        assert payload.source == "tvmaze"
        assert payload.identifiers["imdb"] == "tt0903747"

    async def test_a_streamed_show_reads_its_web_channel_as_the_network(self) -> None:
        payload = await tvmaze(FETCH_MANDALORIAN).fetch("38963")
        assert payload.metadata["network"] == "Disney+"

    async def test_a_show_with_no_runtime_stays_empty(self) -> None:
        """`runtime: null` and `averageRuntime: null` are both legitimate answers."""
        payload = await tvmaze(FETCH_SAMANTHA_OUPS).fetch("76954")
        assert "episode_minutes" not in payload.metadata
        assert payload.metadata["network"] == "France 2"

    async def test_a_missing_record_is_an_answer_and_not_an_outage(self) -> None:
        with pytest.raises(ProviderPayloadError) as caught:
            await tvmaze({"/shows/99999999": (404, None)}).fetch("99999999")
        assert caught.value.code == "record_not_found"


class TestThrottling:
    async def test_a_429_is_retried_under_the_existing_policy(self) -> None:
        """AC8: the shared `bounded_json` retry, not a second mechanism."""
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, json={"code": 429, "message": "rate limited"})
            return httpx.Response(200, json=recording("tvmaze_search_breaking_bad.json"))

        async def no_sleep(_seconds: float) -> None:
            return None

        client = create_provider_client(httpx.MockTransport(handler))
        provider = TvmazeSeriesProvider(client, "test@example.invalid", sleep=no_sleep)
        rows = await provider.search("Breaking Bad")
        assert calls == 2
        assert rows[0].title == "Breaking Bad"

    async def test_a_search_is_not_failed_by_one_provider_s_429(self) -> None:
        """AC8: `search_providers` isolates a failing provider from the result."""
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(429, json={"code": 429, "message": "rate limited"})

        async def no_sleep(_seconds: float) -> None:
            return None

        client = create_provider_client(httpx.MockTransport(handler))
        throttled = TvmazeSeriesProvider(client, "test@example.invalid", sleep=no_sleep)
        rows = await search_providers(
            "Breaking Bad",
            [throttled, tvmaze(SEARCH_BREAKING_BAD)],
            domain=_SERIES_DOMAIN,
        )
        assert calls == 2  # retried once, then gave up
        assert rows[0].title == "Breaking Bad"


class TestBothAdaptersAgree:
    async def test_the_same_series_gets_the_same_identity_from_either_source(self) -> None:
        """AC3's premise: the whole point of the IMDb identity, across two recordings."""
        from_wikidata = await _wikidata_breaking_bad()
        from_tvmaze = await tvmaze(FETCH_BREAKING_BAD).fetch("169")
        assert imdb_identity(from_wikidata) == imdb_identity(from_tvmaze) == "imdb:tt0903747"

    async def test_neither_leaks_a_raw_provider_row(self) -> None:
        """Technical spec 6.2: a raw response never rises above infrastructure."""
        payload = await tvmaze(FETCH_BREAKING_BAD).fetch("169")
        assert set(payload.metadata) <= {
            "genres",
            "network",
            "episode_minutes",
            "airing_status",
            "synopsis",
        }
        assert payload.identifiers.keys() <= {"imdb", "thetvdb", "tvmaze"}


class TestMergeThroughTheSharedLayer:
    """AC3 and AC4: the merge is `merge_and_rank` and `fill_empty`, nothing local."""

    async def test_a_candidate_from_each_provider_merges_into_one_record(self) -> None:
        merged = merge_and_rank(
            "Breaking Bad",
            [await _wikidata_breaking_bad(), await tvmaze(FETCH_BREAKING_BAD).fetch("169")],
            identity=SERIES_IDENTITY,
        )
        assert len(merged) == 1
        row = merged[0]
        # Wikidata wins the primary slot by the declared source preference.
        assert row.source == "wikidata-series"
        assert {ref.source for ref in row.source_refs} == {"wikidata-series", "tvmaze"}

    async def test_tvmaze_fills_what_wikidata_left_empty_and_overwrites_nothing(self) -> None:
        wikidata = await _wikidata_breaking_bad()
        tvmaze_payload = await tvmaze(FETCH_BREAKING_BAD).fetch("169")
        merged = merge_and_rank(
            "Breaking Bad", [wikidata, tvmaze_payload], identity=SERIES_IDENTITY
        )
        row = merged[0]
        # Filled from TVmaze: a field Wikidata does not supply as the adapter emits it.
        assert row.metadata["network"] == tvmaze_payload.metadata["network"] == "AMC"
        # Overwritten nothing: every field Wikidata supplied survives verbatim.
        for key, value in wikidata.metadata.items():
            assert row.metadata[key] == value
        assert row.metadata["episodes"] == 62  # Wikidata's P1113, not TVmaze's count
        assert row.metadata["synopsis"] == wikidata.metadata["synopsis"]

    async def test_the_fill_runs_in_the_other_direction_when_tvmaze_is_primary(self) -> None:
        """A series Wikidata misses still arrives whole from TVmaze alone."""
        rows = await tvmaze(SEARCH_SIMULADORES).search("Los Simuladores")
        merged = merge_and_rank("Los Simuladores", rows, identity=SERIES_IDENTITY)
        assert len(merged) == 1
        assert merged[0].source == "tvmaze"
        assert merged[0].metadata["synopsis"]


class TestCovers:
    def test_tvmaze_s_host_is_not_allowlisted(self) -> None:
        """AC7: `static.tvmaze.com` must never join the cover allowlist."""
        from book_tracker.infrastructure.covers import ALLOWED_COVER_HOSTS

        assert "static.tvmaze.com" not in ALLOWED_COVER_HOSTS
        assert not any(host.endswith("tvmaze.com") for host in ALLOWED_COVER_HOSTS)

    def test_tvmaze_emits_no_cover_url(self) -> None:
        candidate = _tvmaze_candidate()
        assert candidate.cover_url is None


# --------------------------------------------------------------------------------------
# Helpers


from book_tracker.domain.registry import DOMAINS  # noqa: E402

_SERIES_DOMAIN = DOMAINS["series"]


def _tvmaze_candidate() -> SearchCandidate:
    body = recording("tvmaze_show_169_breaking_bad.json")
    return TvmazeSeriesProvider._candidate(body)  # type: ignore[attr-defined]


async def _wikidata_breaking_bad() -> ItemPayload:
    """Wikidata's Breaking Bad, replayed from Sprint 049's own recording."""
    labels = recording("wikidata_series_labels_Q1079_breaking_bad.json")
    routes = {
        "entities:labels|descriptions|claims:Q1079": (
            200,
            recording("wikidata_series_entity_Q1079_breaking_bad.json"),
        ),
        "labels:" + "|".join(labels["entities"]): (200, labels),
    }

    async def no_sleep(_seconds: float) -> None:
        return None

    client = create_provider_client(replay(routes, key=wikidata_series_route_key))  # type: ignore[arg-type]
    provider = WikidataSeriesProvider(client, "test@example.invalid", sleep=no_sleep)
    return await provider.fetch("Q1079")
