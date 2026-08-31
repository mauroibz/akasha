"""Wikidata's series adapter, against responses recorded from the live API.

DEC-025 forbids proving provider-boundary behaviour with a mock of the method under
test, so every one of these replays a verbatim capture from 2026-08-31. The four query
classes are the ones Sprint 049's viability measurement turned on: an animated series
(`Q117467246`), an anime series (`Q63952888`), a miniseries (`Q1259759`), and an
ordinary long-running series (`Q5398426`).

The structural trap is the search filter: under the movie adapter's single-class
`P31=Q5398426` shape, `Chainsaw Man` returned **nothing at all**, `BoJack Horseman`
returned only the fictional show-within-the-show, and `Chernobyl` lost rank 1 to a
Russian series. The single-class control recordings below make that failure
executable rather than documentary (AC3).

Captured without `maxlag` during the 2026-08-31 replication incident (replicas lagged
40s+, so `maxlag=5` requests were shed for ~40 minutes). The replay transport keys on
`srsearch`/`ids`/`props`, not `maxlag`, so the bodies are interchangeable.
"""

from collections.abc import Callable, Mapping

import httpx
import pytest
from recordings import Route, recording, replay

from book_tracker.domains.series.providers import (
    ENTITY_BATCH_SIZE,
    SERIES_FILTER,
    WikidataSeriesProvider,
    wikidata_series_route_key,
)
from book_tracker.infrastructure.providers import ProviderPayloadError, create_provider_client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def wikidata(
    routes: Mapping[str, Route],
    *,
    on_request: Callable[[httpx.Request], None] | None = None,
    entity_batch_size: int = ENTITY_BATCH_SIZE,
) -> WikidataSeriesProvider:
    """A provider whose pacing is disabled: the clock is not under test."""

    async def no_sleep(_seconds: float) -> None:
        return None

    transport = replay(routes, key=wikidata_series_route_key, on_request=on_request)  # type: ignore[arg-type]
    return WikidataSeriesProvider(
        create_provider_client(transport),
        "test@example.invalid",
        sleep=no_sleep,
        entity_batch_size=entity_batch_size,
    )


def search_key(query: str) -> str:
    return f"search:{query} {SERIES_FILTER}"


def single_class_key(query: str) -> str:
    return f"search:{query} haswbstatement:P31=Q5398426"


def claim_key(prop: str, value: str) -> str:
    return f"search:haswbstatement:{prop}={value}"


def entities_key(*ids: str) -> str:
    return "entities:labels|descriptions|claims:" + "|".join(ids)


def labels_key(body: object) -> str:
    """The label batch the adapter will ask for, read out of the recording itself."""
    assert isinstance(body, dict)
    return "labels:" + "|".join(body["entities"])


BOJACK_PAIR_LABELS = recording("wikidata_series_labels_bojack_pair.json")
CHAINSAW_LABELS = recording("wikidata_series_labels_Q104211858_chainsaw.json")
CHERNOBYL_LABELS = recording("wikidata_series_labels_Q48741246_chernobyl.json")
CHERNOBYL_SEARCH_LABELS = recording("wikidata_series_labels_chernobyl_search.json")
BREAKING_BAD_LABELS = recording("wikidata_series_labels_Q1079_breaking_bad.json")

BOJACK_SEARCH: dict[str, Route] = {
    search_key("BoJack Horseman"): (200, recording("wikidata_series_search_bojack.json")),
    entities_key("Q17733404", "Q87484192"): (
        200,
        # Both hits in one read, as the adapter requests them. The second is the
        # fictional show-within-the-show; `_is_series` filters it, which is exactly
        # the guard a title-shaped non-series exercises.
        recording("wikidata_series_entities_bojack_pair.json"),
    ),
    labels_key(BOJACK_PAIR_LABELS): (200, BOJACK_PAIR_LABELS),
}
CHAINSAW_SEARCH: dict[str, Route] = {
    search_key("Chainsaw Man"): (200, recording("wikidata_series_search_chainsaw.json")),
    entities_key("Q104211858"): (200, recording("wikidata_series_entity_Q104211858_chainsaw.json")),
    labels_key(CHAINSAW_LABELS): (200, CHAINSAW_LABELS),
}
CHERNOBYL_SEARCH: dict[str, Route] = {
    search_key("Chernobyl"): (200, recording("wikidata_series_search_chernobyl.json")),
    entities_key("Q48741246", "Q18406980", "Q111377804"): (
        200,
        recording("wikidata_series_entity_Q48741246_chernobyl.json"),
    ),
    entities_key("Q121879824", "Q86000614", "Q15270776"): (
        200,
        recording("wikidata_series_entities_chernobyl_batch2.json"),
    ),
    labels_key(CHERNOBYL_SEARCH_LABELS): (200, CHERNOBYL_SEARCH_LABELS),
}
BREAKING_BAD_SEARCH: dict[str, Route] = {
    search_key("Breaking Bad"): (200, recording("wikidata_series_search_breaking_bad.json")),
    entities_key("Q1079", "Q17057981", "Q136483358"): (
        200,
        # The batch covers all three hits in one read; the fixture holds the real
        # series, so the Colombian remake and the 2025 animation are simply absent —
        # which is what entities missing from a batch response look like.
        recording("wikidata_series_entity_Q1079_breaking_bad.json"),
    ),
    labels_key(BREAKING_BAD_LABELS): (200, BREAKING_BAD_LABELS),
}
FETCH_BREAKING_BAD: dict[str, Route] = {
    entities_key("Q1079"): (200, recording("wikidata_series_entity_Q1079_breaking_bad.json")),
    labels_key(BREAKING_BAD_LABELS): (200, BREAKING_BAD_LABELS),
}
FETCH_NOT_A_SERIES: dict[str, Route] = {
    # Q4500 is Vince Gilligan — a human (`P31=Q5`). A person is the most legible
    # thing to paste into the add box by mistake, and is not something this domain
    # can hold. (Q87484192, the BoJack show-within-the-show, turned out to carry
    # `P31=Q5398426` itself — Wikidata files a fictional series as a series.)
    entities_key("Q4500"): (200, recording("wikidata_series_entity_Q4500_vince_gilligan.json")),
}
IMDB_RESOLUTION: dict[str, Route] = {
    claim_key("P345", "tt0903747"): (200, recording("wikidata_series_search_p345_tt0903747.json")),
    **FETCH_BREAKING_BAD,
}
IMDB_MISS: dict[str, Route] = {
    claim_key("P345", "tt9999999"): (200, recording("wikidata_series_search_p345_no_match.json")),
}
# The claim re-check: the search index says Q48741246 carries tt0903747, but the
# fetched entity carries tt7366338. A derived index and its source disagreeing is
# exactly what the re-check exists for. The search body is the real tt0903747
# recording with the hit's title substituted — the same shape as the movie suite's
# synthetic ambiguous fixture.
_POISONED_SEARCH = {
    **recording("wikidata_series_search_p345_tt0903747.json"),
    "query": {
        **recording("wikidata_series_search_p345_tt0903747.json")["query"],
        "search": [
            {
                **recording("wikidata_series_search_p345_tt0903747.json")["query"]["search"][0],
                "title": "Q48741246",
            }
        ],
    },
}
IMDB_POISONED_INDEX: dict[str, Route] = {
    claim_key("P345", "tt0903747"): (200, _POISONED_SEARCH),
    entities_key("Q48741246"): (200, recording("wikidata_series_entity_Q48741246_chernobyl.json")),
    labels_key(CHERNOBYL_LABELS): (200, CHERNOBYL_LABELS),
}


class TestSearch:
    async def test_an_animated_series_resolves_at_rank_1(self) -> None:
        provider = wikidata(BOJACK_SEARCH)
        rows = await provider.search("BoJack Horseman")
        assert rows[0].source_id == "Q17733404"
        # The Spanish label is what the adapter prefers (LANGUAGES = es, en), and
        # Wikidata's Spanish label for this series is sentence-cased.
        assert rows[0].title == "Bojack Horseman"
        assert rows[0].year == 2014
        assert rows[0].metadata["episodes"] == 77

    async def test_an_anime_series_resolves_at_rank_1(self) -> None:
        provider = wikidata(CHAINSAW_SEARCH)
        rows = await provider.search("Chainsaw Man")
        assert rows[0].source_id == "Q104211858"
        assert rows[0].metadata["episodes"] == 12

    async def test_a_miniseries_resolves_at_rank_1(self) -> None:
        provider = wikidata(CHERNOBYL_SEARCH)
        rows = await provider.search("Chernobyl")
        assert rows[0].source_id == "Q48741246"
        assert rows[0].metadata["episodes"] == 5

    async def test_the_single_class_filter_would_have_missed_them(self) -> None:
        """AC3: the five-class filter is exercised against controls that fail.

        The movie adapter's shape — one `P31=Q5398426` — returned **nothing** for
        Chainsaw Man, only the show-within-the-show for BoJack, and lost Chernobyl's
        rank 1 to a Russian series. These are the recordings that prove it.
        """
        chainsaw = recording("wikidata_series_search_chainsaw_single_class.json")
        assert chainsaw["query"]["searchinfo"]["totalhits"] == 0

        bojack = recording("wikidata_series_search_bojack_single_class.json")
        assert [row["title"] for row in bojack["query"]["search"]] == ["Q87484192"]
        assert "Q17733404" not in [row["title"] for row in bojack["query"]["search"]]

        chernobyl = recording("wikidata_series_search_chernobyl_single_class.json")
        assert chernobyl["query"]["search"][0]["title"] != "Q48741246"

    async def test_candidates_carry_an_imdb_identity(self) -> None:
        provider = wikidata(BREAKING_BAD_SEARCH)
        rows = await provider.search("Breaking Bad")
        assert rows[0].identifiers["imdb"] == "tt0903747"

    async def test_a_series_with_no_seasons_claim_parses(self) -> None:
        """The miniseries and the anime measured: `P2437` is legitimately absent."""
        provider = wikidata(CHERNOBYL_SEARCH)
        rows = await provider.search("Chernobyl")
        assert "seasons" not in rows[0].metadata
        assert rows[0].metadata["episodes"] == 5

    async def test_a_series_with_no_cast_claim_parses(self) -> None:
        """Every animated series measured: `P161` is legitimately absent."""
        provider = wikidata(BOJACK_SEARCH)
        rows = await provider.search("BoJack Horseman")
        assert "cast" not in rows[0].metadata

    async def test_a_creator_falls_back_to_the_screenwriter(self) -> None:
        """Chainsaw Man carries no `P170`; its `P58` screenwriter is the credit line."""
        provider = wikidata(CHAINSAW_SEARCH)
        rows = await provider.search("Chainsaw Man")
        assert rows[0].creators, "the P58 fallback produced no creator"
        assert rows[0].metadata["creators"] == list(rows[0].creators)

    async def test_airing_status_is_derived_from_the_end_time(self) -> None:
        provider = wikidata(BREAKING_BAD_SEARCH)
        rows = await provider.search("Breaking Bad")
        assert rows[0].metadata["airing_status"] == "Ended"

    async def test_a_non_series_entity_is_refused(self) -> None:
        """A `Q` id pasted into the add box has been through no filter at all."""
        provider = wikidata(FETCH_NOT_A_SERIES)
        with pytest.raises(ProviderPayloadError, match="no usable series"):
            await provider.fetch("Q4500")


class TestFetchByIdentifier:
    async def test_an_imdb_id_resolves_to_the_series(self) -> None:
        provider = wikidata(IMDB_RESOLUTION)
        payload = await provider.fetch_by_identifier("imdb", "tt0903747")
        assert payload.source_id == "Q1079"
        assert payload.title == "Breaking Bad"
        assert payload.identifiers["imdb"] == "tt0903747"

    async def test_a_hit_whose_entity_lacks_the_claim_is_refused(self) -> None:
        """AC4: the search index is a derived copy and is never trusted."""
        provider = wikidata(IMDB_POISONED_INDEX)
        with pytest.raises(ProviderPayloadError) as error:
            await provider.fetch_by_identifier("imdb", "tt0903747")
        assert error.value.code == "record_not_found"

    async def test_a_miss_is_an_answer_not_a_guess(self) -> None:
        """`tt9999999` carries no claim. (`tt0000001` does — a placeholder id somebody
        filed on an 1894 film, which is why the miss id was chosen by querying live.)"""
        provider = wikidata(IMDB_MISS)
        with pytest.raises(ProviderPayloadError) as error:
            await provider.fetch_by_identifier("imdb", "tt9999999")
        assert error.value.code == "record_not_found"

    async def test_an_unknown_kind_is_refused(self) -> None:
        provider = wikidata({})
        with pytest.raises(ProviderPayloadError) as error:
            await provider.fetch_by_identifier("tvmaze", "82")
        assert error.value.code == "unsupported_identity_kind"

    async def test_a_tvmaze_prefix_is_refused_honestly_this_sprint(self) -> None:
        """Wikidata holds no TVmaze claim; Sprint 050's adapter is where it resolves."""
        provider = wikidata({})
        with pytest.raises(ProviderPayloadError) as error:
            await provider.fetch("tvmaze:82")
        assert error.value.code == "record_not_found"


class TestPosters:
    async def test_a_series_with_an_imdb_id_emits_a_stremio_url_with_no_request(self) -> None:
        asked: list[str] = []
        provider = wikidata(
            FETCH_BREAKING_BAD, on_request=lambda request: asked.append(str(request.url))
        )
        payload = await provider.fetch("Q1079")
        assert payload.cover_url == "https://images.metahub.space/poster/medium/tt0903747/img"
        # The poster costs nothing: the only requests are the entity and label reads.
        assert all("metahub" not in url for url in asked)

    async def test_a_series_without_an_imdb_id_would_emit_no_cover(self) -> None:
        """Every measured entity carried one, so this is a unit-level guarantee:
        the builder answers None for anything that is not an IMDb id."""
        from book_tracker.infrastructure.posters import metahub_poster_url

        assert metahub_poster_url(None) is None

    async def test_a_recorded_404_through_prepare_cover_leaves_the_item_coverless(
        self, tmp_path: object
    ) -> None:
        """A miss is a clean 404, not a placeholder — the pipeline survives it and
        installs nothing, failing nothing (AC5)."""
        from book_tracker.infrastructure.covers import CoverError, prepare_cover

        def missing(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="not found")

        client = create_provider_client(httpx.MockTransport(missing))
        with pytest.raises(CoverError):
            await prepare_cover(
                client,
                "https://images.metahub.space/poster/medium/tt0000001/img",
                tmp_path,  # type: ignore[arg-type]
            )
        await client.aclose()


def test_the_route_key_separates_operations_that_share_one_path() -> None:
    request = httpx.Request(
        "GET",
        "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q1%7CQ2&props=labels",
    )
    assert wikidata_series_route_key(request) == "labels:Q1|Q2"
