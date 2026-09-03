"""Cinemeta's movie and series adapters, replayed against responses captured from the
live API on 2026-09-03.

DEC-025 forbids proving a provider boundary with a mock of the method under test, so
every assertion here runs against a committed recording. Provenance is in
`tests/fixtures/providers/README.md`; the coverage measurement behind AC1 is in
`docs/movie-domain-viability.md` and `docs/series-domain-viability.md`.

Two shapes are pinned here because an implementation would otherwise guess them wrong:

- The catalog search's own `poster` field is `m.media-amazon.com`, never allowlisted,
  and is never read. Both adapters build the metahub poster from the IMDb id instead.
- Search carries no `year` beyond a display string and no other usable field, so both
  adapters are search-then-fetch, like every other adapter in this codebase.
"""

from __future__ import annotations

import pytest
from recordings import recording, replay

from book_tracker.application.providers import search_providers
from book_tracker.domain.providers import ItemPayload, SearchCandidate, merge_and_rank
from book_tracker.domains.movie import MOVIE_IDENTITY, imdb_identity
from book_tracker.domains.movie.cinemeta import CinemetaMovieProvider
from book_tracker.domains.movie.providers import WikidataMovieProvider
from book_tracker.domains.series import SERIES_IDENTITY
from book_tracker.domains.series.cinemeta import CinemetaSeriesProvider
from book_tracker.domains.series.providers import WikidataSeriesProvider
from book_tracker.domains.series.tvmaze import TvmazeSeriesProvider
from book_tracker.infrastructure.cinemeta import parse_runtime_minutes
from book_tracker.infrastructure.providers import ProviderPayloadError, create_provider_client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _no_sleep(_seconds: float):  # type: ignore[no-untyped-def]
    async def sleep(_s: float) -> None:
        return None

    return sleep


def movie_provider(routes: dict[str, object]) -> CinemetaMovieProvider:
    client = create_provider_client(replay(routes))  # type: ignore[arg-type]
    return CinemetaMovieProvider(client, "test@example.invalid", sleep=_no_sleep(0))


def series_provider(routes: dict[str, object]) -> CinemetaSeriesProvider:
    client = create_provider_client(replay(routes))  # type: ignore[arg-type]
    return CinemetaSeriesProvider(client, "test@example.invalid", sleep=_no_sleep(0))


SEARCH_SEVEN_SAMURAI = {
    "/catalog/movie/top/search=Seven Samurai.json": (
        200,
        recording("cinemeta_search_seven_samurai.json"),
    )
}
META_SEVEN_SAMURAI = {
    "/meta/movie/tt0047478.json": (
        200,
        recording("cinemeta_meta_movie_tt0047478_seven_samurai.json"),
    )
}
SEARCH_LA_CIENAGA = {
    "/catalog/movie/top/search=La Cienaga.json": (200, recording("cinemeta_search_la_cienaga.json"))
}
META_LA_CIENAGA = {
    "/meta/movie/tt0240419.json": (200, recording("cinemeta_meta_movie_tt0240419_la_cienaga.json"))
}
SEARCH_SUSPIRIA = {
    "/catalog/movie/top/search=Suspiria.json": (200, recording("cinemeta_search_suspiria.json"))
}
META_SUSPIRIA_1977 = {
    "/meta/movie/tt0076786.json": (
        200,
        recording("cinemeta_meta_movie_tt0076786_suspiria_1977.json"),
    )
}
META_SUSPIRIA_2018 = {
    "/meta/movie/tt1034415.json": (
        200,
        recording("cinemeta_meta_movie_tt1034415_suspiria_2018.json"),
    )
}
SEARCH_BREAKING_BAD_SERIES = {
    "/catalog/series/top/search=Breaking Bad.json": (
        200,
        recording("cinemeta_search_breaking_bad_series.json"),
    )
}
META_BREAKING_BAD_SERIES = {
    "/meta/series/tt0903747.json": (
        200,
        recording("cinemeta_meta_series_tt0903747_breaking_bad.json"),
    )
}


class TestMovieSearchThenFetch:
    """Search carries no year; every other field needs the `/meta/` fetch."""

    async def test_it_reads_the_recorded_search_and_fetch(self) -> None:
        provider = movie_provider({**SEARCH_SEVEN_SAMURAI, **META_SEVEN_SAMURAI})
        rows = await provider.search("Seven Samurai", limit=1)
        assert rows[0].title == "Seven Samurai"
        assert rows[0].year == 1954
        assert rows[0].identifiers == {"imdb": "tt0047478"}
        assert rows[0].metadata["creators"] == ["Akira Kurosawa"]
        assert rows[0].metadata["countries"] == ["Japan"]
        assert "Drama" in rows[0].metadata["genres"]
        assert rows[0].metadata["description"].startswith("Farmers from a village")

    async def test_it_fetches_by_imdb_id(self) -> None:
        provider = movie_provider(META_SEVEN_SAMURAI)
        payload = await provider.fetch("tt0047478")
        assert payload.title == "Seven Samurai"
        assert payload.source == "cinemeta"

    async def test_a_non_english_title_carries_full_metadata(self) -> None:
        """The Argentine, Spanish-language case from the coverage sample."""
        provider = movie_provider({**SEARCH_LA_CIENAGA, **META_LA_CIENAGA})
        rows = await provider.search("La Cienaga", limit=1)
        row = next(r for r in rows if r.identifiers.get("imdb") == "tt0240419")
        assert row.title
        assert row.metadata["description"]
        assert row.metadata["runtime"]

    async def test_it_reports_no_raw_provider_row(self) -> None:
        """Technical spec 6.2: a raw response never rises above infrastructure."""
        provider = movie_provider(META_SEVEN_SAMURAI)
        payload = await provider.fetch("tt0047478")
        assert set(payload.metadata) <= {
            "creators",
            "original_title",
            "countries",
            "languages",
            "genres",
            "runtime",
            "cast",
            "description",
        }
        assert payload.identifiers.keys() <= {"imdb"}


class TestRuntimeParsing:
    def test_a_string_runtime_becomes_a_whole_number_of_minutes(self) -> None:
        assert parse_runtime_minutes("207 min") == 207

    def test_a_missing_runtime_becomes_none(self) -> None:
        assert parse_runtime_minutes(None) is None

    def test_a_malformed_runtime_becomes_none(self) -> None:
        assert parse_runtime_minutes("N/A") is None

    async def test_a_record_missing_the_field_entirely_parses_with_no_runtime(self) -> None:
        provider = movie_provider(
            {
                "/meta/movie/tt0047478.json": (
                    200,
                    recording("cinemeta_meta_movie_missing_runtime.json"),
                )
            }
        )
        payload = await provider.fetch("tt0047478")
        assert "runtime" not in payload.metadata


class TestCovers:
    """AC7: the search poster is ignored; the metahub URL is built from the IMDb id."""

    async def test_the_cover_is_the_metahub_url_not_the_search_poster(self) -> None:
        provider = movie_provider(META_SEVEN_SAMURAI)
        payload = await provider.fetch("tt0047478")
        assert payload.cover_url == "https://images.metahub.space/poster/medium/tt0047478/img"
        raw = recording("cinemeta_meta_movie_tt0047478_seven_samurai.json")["meta"]
        assert payload.cover_url != raw["poster"]
        assert "m.media-amazon.com" not in payload.cover_url

    async def test_no_request_ever_names_the_amazon_host(self) -> None:
        """AC7, structurally: the adapter only ever calls `CINEMETA_BASE`."""
        provider = movie_provider(META_SEVEN_SAMURAI)
        await provider.fetch("tt0047478")
        # `replay` raises on any path it was not given a recording for; the routes
        # above name only Cinemeta paths, so a request elsewhere would already have
        # failed the test above rather than needing a second assertion here.


class TestNoImdbId:
    """A record with no IMDb id yields no identity and no cover: it never becomes a
    candidate at all, since Cinemeta's catalog is IMDb-keyed by construction and there
    is nothing else to key it on."""

    async def test_a_record_with_no_imdb_id_is_refused(self) -> None:
        provider = movie_provider(
            {"/meta/movie/tt0047478.json": (200, recording("cinemeta_meta_movie_no_imdb_id.json"))}
        )
        with pytest.raises(ProviderPayloadError):
            await provider.fetch("tt0047478")


class TestMovieIdentityMerge:
    """AC4: two films sharing a title and differing IMDb id remain two rows."""

    async def test_the_suspiria_pair_stays_two_rows(self) -> None:
        provider = movie_provider({**META_SUSPIRIA_1977, **META_SUSPIRIA_2018})
        argento = await provider.fetch("tt0076786")
        guadagnino = await provider.fetch("tt1034415")
        assert imdb_identity(argento) != imdb_identity(guadagnino)
        merged = merge_and_rank("Suspiria", [argento, guadagnino], identity=MOVIE_IDENTITY)
        assert len(merged) == 2


def _wikidata_movie_provider(routes: dict[str, object]) -> WikidataMovieProvider:
    from book_tracker.domains.movie.providers import wikidata_route_key

    client = create_provider_client(replay(routes, key=wikidata_route_key))  # type: ignore[arg-type]
    return WikidataMovieProvider(client, "test@example.invalid", sleep=_no_sleep(0))


async def _wikidata_suspiria_1977() -> ItemPayload:
    """Wikidata's Suspiria (1977), replayed from Sprint 046's own recording."""
    labels = recording("wikidata_labels_Q546900_suspiria_1977.json")
    routes = {
        "entities:labels|descriptions|claims:Q546900": (
            200,
            recording("wikidata_entity_Q546900_suspiria_1977.json"),
        ),
        "labels:" + "|".join(labels["entities"]): (200, labels),
    }
    return await _wikidata_movie_provider(routes).fetch("Q546900")


def _wikidata_series_provider(routes: dict[str, object]) -> WikidataSeriesProvider:
    from book_tracker.domains.series.providers import wikidata_series_route_key

    client = create_provider_client(replay(routes, key=wikidata_series_route_key))  # type: ignore[arg-type]
    return WikidataSeriesProvider(client, "test@example.invalid", sleep=_no_sleep(0))


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
    return await _wikidata_series_provider(routes).fetch("Q1079")


class TestWikidataCinemetaMerge:
    """AC3: Wikidata primary, filled from Cinemeta, nothing overwritten."""

    async def test_cinemeta_fills_what_wikidata_left_empty_and_overwrites_nothing(self) -> None:
        wikidata_payload = await _wikidata_suspiria_1977()
        cinemeta_payload = await movie_provider(META_SUSPIRIA_1977).fetch("tt0076786")

        merged = merge_and_rank(
            "Suspiria", [wikidata_payload, cinemeta_payload], identity=MOVIE_IDENTITY
        )
        assert len(merged) == 1
        row = merged[0]
        assert row.source == "wikidata"
        assert {ref.source for ref in row.source_refs} == {"wikidata", "cinemeta"}
        # Every field Wikidata supplied survives verbatim.
        for key, value in wikidata_payload.metadata.items():
            assert row.metadata[key] == value
        # `description` is Cinemeta's only if Wikidata's own was empty; Sprint 045
        # measured Wikidata's own description present on this very entity, so this
        # proves fill-empty rather than overwrite.
        assert row.metadata["description"] == wikidata_payload.metadata["description"]


class TestThreeWaySeriesMerge:
    """AC5: a series search merges all three providers, still preferring Wikidata's,
    with TVmaze's fuller synopsis unaffected by Cinemeta's presence in the group."""

    async def test_wikidata_tvmaze_and_cinemeta_merge_to_one_row(self) -> None:
        tvmaze_client = create_provider_client(
            replay({"/shows/169": (200, recording("tvmaze_show_169_breaking_bad.json"))})  # type: ignore[arg-type]
        )
        tvmaze_provider = TvmazeSeriesProvider(
            tvmaze_client, "test@example.invalid", sleep=_no_sleep(0)
        )

        wikidata_payload = await _wikidata_breaking_bad()
        tvmaze_payload = await tvmaze_provider.fetch("169")
        cinemeta_payload = await series_provider(META_BREAKING_BAD_SERIES).fetch("tt0903747")

        merged = merge_and_rank(
            "Breaking Bad",
            [wikidata_payload, tvmaze_payload, cinemeta_payload],
            identity=SERIES_IDENTITY,
        )
        assert len(merged) == 1
        row = merged[0]
        assert row.source == "wikidata-series"
        assert {ref.source for ref in row.source_refs} == {
            "wikidata-series",
            "tvmaze",
            "cinemeta-series",
        }
        # Wikidata's own synopsis (the one-line identification sentence) is what
        # `merge_and_rank`'s fill-empty keeps: it is not empty, so neither TVmaze's
        # nor Cinemeta's longer answer displaces it here. The fuller-answer rule
        # (DEC-115) is the add path's job, proven in test_cached_add.py, not this
        # search-time merge's.
        assert row.metadata["synopsis"] == wikidata_payload.metadata["synopsis"]
        # `episode_minutes` lands as TVmaze's (60), not Cinemeta's (49): both
        # candidates carry the field for Breaking Bad, and fill-empty keeps whichever
        # was encountered first among the non-primary group members — proof that
        # Cinemeta being third in the group never overwrites what TVmaze already
        # filled, the same "fill-empty, never overwrite" rule AC3 states for movies.
        assert cinemeta_payload.metadata.get("episode_minutes") == 49
        assert row.metadata.get("episode_minutes") == tvmaze_payload.metadata.get("episode_minutes")


class TestMovieSearchSurvivesWikidataFailing:
    """The other half of AC2: proven at the application layer, with a real Cinemeta
    adapter standing behind a Wikidata that raises."""

    async def test_a_movie_search_survives_wikidata_raising(self) -> None:
        class RaisingWikidata:
            name = "wikidata"
            item_type = "movie"

            async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
                raise ProviderPayloadError(
                    "Wikidata declined the request (lagged)", code="provider_http_error"
                )

            async def fetch(self, source_id: str) -> ItemPayload:
                raise NotImplementedError

        cinemeta = movie_provider({**SEARCH_SEVEN_SAMURAI, **META_SEVEN_SAMURAI})
        results = await search_providers("Seven Samurai", [RaisingWikidata(), cinemeta], limit=1)
        merged = merge_and_rank("Seven Samurai", results, identity=MOVIE_IDENTITY)
        assert len(merged) == 1
        assert merged[0].source == "cinemeta"
        assert merged[0].cover_url is not None
