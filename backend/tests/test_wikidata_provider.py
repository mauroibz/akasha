"""Wikidata's movie adapter, against responses recorded from the live API.

DEC-025 forbids proving provider-boundary behaviour with a mock of the method under
test, so every one of these replays a verbatim capture from 2026-08-27. The four query
classes are the ones Sprint 045 measured: an Argentine Spanish-language film, a 1927
film, a 2024 film, and the two films called `Suspiria` forty-one years apart.

Three traps in these fixtures are the whole reason the parser is not three lines:

- `Q546900` carries **four** `P364` original-language statements and the *third* is the
  preferred one. First-value parsing reads Suspiria as German.
- `Q151599` carries a **deprecated** `P495` and a `P364` with no value at all. First-value
  parsing puts Metropolis in a country Wikidata has explicitly retired.
- `P577` arrives up to thirty times at mixed precision, including `+1927-03-00T00:00:00Z`,
  which no date parser will read.
"""

from collections.abc import Callable, Mapping
from urllib.parse import parse_qsl

import httpx
import pytest
from recordings import Route, recording, redirect_location, replay

from book_tracker.domains.movie.providers import (
    ENTITY_BATCH_SIZE,
    FILM_FILTER,
    WikidataMovieProvider,
    wikidata_route_key,
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
) -> WikidataMovieProvider:
    """A provider whose pacing is disabled: the clock is not under test."""

    async def no_sleep(_seconds: float) -> None:
        return None

    transport = replay(routes, key=wikidata_route_key, on_request=on_request)  # type: ignore[arg-type]
    return WikidataMovieProvider(
        create_provider_client(transport),
        "test@example.invalid",
        sleep=no_sleep,
        entity_batch_size=entity_batch_size,
    )


def search_key(query: str) -> str:
    return f"search:{query} {FILM_FILTER}"


def claim_key(prop: str, value: str) -> str:
    return f"search:haswbstatement:{prop}={value}"


def entities_key(*ids: str) -> str:
    return "entities:labels|descriptions|claims:" + "|".join(ids)


def labels_key(body: object) -> str:
    """The label batch the adapter will ask for, read out of the recording itself."""
    assert isinstance(body, dict)
    return "labels:" + "|".join(body["entities"])


SUSPIRIA_LABELS = recording("wikidata_labels_suspiria_pair.json")
SECRETO_LABELS = recording("wikidata_labels_Q748851_secreto.json")
METROPOLIS_LABELS = recording("wikidata_labels_Q151599_metropolis.json")
SUSTANCIA_LABELS = recording("wikidata_labels_Q113380226_sustancia.json")
# A single-film fetch asks for its own film's linked values, which is a shorter list
# than the pair's: the label batch follows the entities actually read.
SUSPIRIA_1977_LABELS = recording("wikidata_labels_Q546900_suspiria_1977.json")

SUSPIRIA_SEARCH: dict[str, Route] = {
    search_key("Suspiria"): (200, recording("wikidata_search_suspiria_films.json")),
    entities_key("Q546900", "Q28123467"): (
        200,
        recording("wikidata_entities_suspiria_pair.json"),
    ),
    labels_key(SUSPIRIA_LABELS): (200, SUSPIRIA_LABELS),
}
SECRETO_SEARCH: dict[str, Route] = {
    search_key("El secreto de sus ojos"): (
        200,
        recording("wikidata_search_el_secreto_de_sus_ojos.json"),
    ),
    entities_key("Q748851"): (200, recording("wikidata_entity_Q748851_secreto.json")),
    labels_key(SECRETO_LABELS): (200, SECRETO_LABELS),
}
METROPOLIS_SEARCH: dict[str, Route] = {
    search_key("Metropolis"): (200, recording("wikidata_search_metropolis_films.json")),
    entities_key("Q151599"): (200, recording("wikidata_entity_Q151599_metropolis.json")),
    labels_key(METROPOLIS_LABELS): (200, METROPOLIS_LABELS),
}
SUSTANCIA_SEARCH: dict[str, Route] = {
    search_key("La sustancia"): (200, recording("wikidata_search_la_sustancia.json")),
    entities_key("Q113380226"): (200, recording("wikidata_entity_Q113380226_sustancia.json")),
    labels_key(SUSTANCIA_LABELS): (200, SUSTANCIA_LABELS),
}
# The same two films, one entity per request: what a batch bound of one asks for.
SUSPIRIA_ONE_AT_A_TIME: dict[str, Route] = {
    search_key("Suspiria"): (200, recording("wikidata_search_suspiria_films.json")),
    entities_key("Q546900"): (200, recording("wikidata_entity_Q546900_suspiria_1977.json")),
    entities_key("Q28123467"): (200, recording("wikidata_entity_Q28123467_suspiria_2018.json")),
    labels_key(SUSPIRIA_LABELS): (200, SUSPIRIA_LABELS),
}
FETCH_1977: dict[str, Route] = {
    entities_key("Q546900"): (200, recording("wikidata_entity_Q546900_suspiria_1977.json")),
    labels_key(SUSPIRIA_1977_LABELS): (200, SUSPIRIA_1977_LABELS),
}


class TestSearch:
    async def test_it_reads_the_recorded_remake_search(self) -> None:
        rows = await wikidata(SUSPIRIA_SEARCH).search("Suspiria")
        assert [row.source_id for row in rows] == ["Q546900", "Q28123467"]
        assert [row.year for row in rows] == [1977, 2018]
        assert all(row.source == "wikidata" for row in rows)

    async def test_it_asks_only_for_films(self) -> None:
        """The unfiltered control put the 1927 film tenth behind a record label."""
        seen: list[str] = []
        provider = wikidata(
            SUSPIRIA_SEARCH, on_request=lambda request: seen.append(str(request.url))
        )
        await provider.search("Suspiria")
        assert "haswbstatement" in seen[0] and "P31%3DQ11424" in seen[0]

    async def test_it_keeps_the_order_the_provider_ranked(self) -> None:
        """Six results for one word, and the 1927 film is the one that was meant."""
        rows = await wikidata(METROPOLIS_SEARCH).search("Metropolis", limit=1)
        assert rows[0].source_id == "Q151599"
        assert rows[0].year == 1927

    async def test_it_honours_a_limit_below_its_own_bound(self) -> None:
        rows = await wikidata(SECRETO_SEARCH).search("El secreto de sus ojos", limit=1)
        assert len(rows) == 1

    async def test_it_never_asks_for_more_entities_than_the_batch_bound(self) -> None:
        """Ten entities measured 1.9 MB against a 2 MiB response bound, so the batch is
        small and the search is several bounded reads rather than one large one."""
        asked: list[str] = []
        provider = wikidata(
            SUSPIRIA_ONE_AT_A_TIME,
            on_request=lambda request: asked.append(wikidata_route_key(request)),
            entity_batch_size=1,
        )
        rows = await provider.search("Suspiria")
        assert [row.source_id for row in rows] == ["Q546900", "Q28123467"]
        assert asked.count(entities_key("Q546900")) == 1
        assert asked.count(entities_key("Q28123467")) == 1

    async def test_it_reads_linked_labels_in_one_request(self) -> None:
        asked: list[str] = []
        provider = wikidata(
            SUSPIRIA_SEARCH, on_request=lambda request: asked.append(wikidata_route_key(request))
        )
        await provider.search("Suspiria")
        assert len([name for name in asked if name.startswith("labels:")]) == 1

    async def test_a_search_that_matches_nothing_is_an_answer(self) -> None:
        routes: dict[str, Route] = {
            search_key("nothing at all"): (200, recording("wikidata_search_p6127_no_match.json"))
        }
        assert await wikidata(routes).search("nothing at all") == []


class TestLocalization:
    async def test_spanish_wins_over_english(self) -> None:
        rows = await wikidata(METROPOLIS_SEARCH).search("Metropolis", limit=1)
        assert rows[0].title == "Metrópolis"
        assert rows[0].metadata["description"] == "película de 1927 dirigida por Fritz Lang"

    async def test_linked_values_are_localized_too(self) -> None:
        rows = await wikidata(SECRETO_SEARCH).search("El secreto de sus ojos", limit=1)
        assert rows[0].metadata["countries"] == ["Argentina", "España"]
        assert rows[0].metadata["languages"] == ["español"]
        assert "drama" in rows[0].metadata["genres"]

    async def test_the_original_title_is_kept_apart_from_the_display_title(self) -> None:
        """`El secreto de sus ojos` in Spanish, `The Secret in Their Eyes` in English:
        the display title follows the reader and `P1476` records what it was called."""
        rows = await wikidata(SECRETO_SEARCH).search("El secreto de sus ojos", limit=1)
        assert rows[0].title == "El secreto de sus ojos"
        assert rows[0].metadata["original_title"] == "El secreto de sus ojos"


class TestClaimRanks:
    async def test_a_preferred_statement_beats_the_ones_listed_before_it(self) -> None:
        """`Q546900` lists German, then Latin, then the preferred Italian, then English.
        Taking the first value reads Dario Argento's film as German."""
        payload = await wikidata(FETCH_1977).fetch("Q546900")
        assert payload.metadata["languages"] == ["italiano"]

    async def test_a_deprecated_statement_is_not_a_fact(self) -> None:
        """Metropolis' first `P495` is deprecated: Wikidata has explicitly retired it."""
        rows = await wikidata(METROPOLIS_SEARCH).search("Metropolis", limit=1)
        assert rows[0].metadata["countries"] == ["República de Weimar"]

    async def test_a_statement_with_no_value_is_skipped_rather_than_rendered(self) -> None:
        """Metropolis' first `P364` is a `somevalue` snak — known to exist, unknown what."""
        rows = await wikidata(METROPOLIS_SEARCH).search("Metropolis", limit=1)
        assert rows[0].metadata["languages"] == ["alemán"]


class TestTimeAndQuantity:
    async def test_the_year_is_the_earliest_best_ranked_release(self) -> None:
        """Thirty release dates across thirty countries; the film is from 1927."""
        rows = await wikidata(METROPOLIS_SEARCH).search("Metropolis", limit=1)
        assert rows[0].year == 1927

    async def test_a_month_precision_date_still_yields_its_year(self) -> None:
        """`+1977-03-00T00:00:00Z` is day zero, which is not a date any parser reads."""
        payload = await wikidata(FETCH_1977).fetch("Q546900")
        assert payload.year == 1977

    async def test_a_runtime_is_read_with_its_unit(self) -> None:
        payload = await wikidata(FETCH_1977).fetch("Q546900")
        assert payload.metadata["runtime"] == 94

    async def test_a_runtime_in_seconds_is_converted_and_a_strange_unit_ignored(self) -> None:
        rows = await wikidata(METROPOLIS_SEARCH).search("Metropolis", limit=1)
        assert rows[0].metadata["runtime"] == 153


class TestBoundsAndAbsence:
    async def test_the_cast_is_bounded(self) -> None:
        """`Q748851` credits thirty-one people; a detail page is not a call sheet."""
        rows = await wikidata(SECRETO_SEARCH).search("El secreto de sus ojos", limit=1)
        assert len(rows[0].metadata["cast"]) == 12
        assert rows[0].metadata["cast"][0]

    async def test_an_absent_claim_is_absent_and_not_empty(self) -> None:
        payload = await wikidata(FETCH_1977).fetch("Q546900")
        assert all(value not in (None, [], "") for value in payload.metadata.values())

    async def test_the_directors_are_the_creators(self) -> None:
        payload = await wikidata(FETCH_1977).fetch("Q546900")
        assert payload.creators == ("Dario Argento",)
        assert payload.metadata["creators"] == ["Dario Argento"]

    async def test_a_director_is_a_person_and_may_invert(self) -> None:
        """Unlike an anime studio, so the sort name is left to the shared heuristic."""
        payload = await wikidata(FETCH_1977).fetch("Q546900")
        assert payload.creator_sort is None


class TestCoverNeverComesFromWikidata:
    """Sprint 048 gave movies posters; it did **not** give Wikidata a say in them.

    `P18` stays unread. It is a general image property, and the two values measured were
    a set photograph and a festival photo of the cast — promoting either to a poster is
    worse than a blank tile (DEC-098). What changed is where a poster comes from, not
    what counts as one.
    """

    async def test_the_poster_is_built_from_the_imdb_id_and_not_from_p18(self) -> None:
        payload = await wikidata(FETCH_1977).fetch("Q546900")
        assert payload.cover_url == "https://images.metahub.space/poster/medium/tt0076786/img"

    async def test_metropolis_gets_a_poster_rather_than_its_set_photograph(self) -> None:
        """`Q151599` really does carry a `P18`: `Horst von Harbou - Metropolis set
        photograph 05.jpg`. The cover must not be it."""
        rows = await wikidata(METROPOLIS_SEARCH).search("Metropolis", limit=1)
        assert rows[0].cover_url == "https://images.metahub.space/poster/medium/tt0017136/img"
        assert "harbou" not in (rows[0].cover_url or "").casefold()
        assert rows[0].cover_fallback_urls == ()

    async def test_a_film_with_no_imdb_claim_and_no_fallback_stays_coverless(self) -> None:
        routes: dict[str, Route] = {
            entities_key("Q546900"): (
                200,
                {
                    "entities": {
                        "Q546900": {
                            "id": "Q546900",
                            "labels": {"es": {"language": "es", "value": "Suspiria"}},
                            "claims": {
                                "P31": [
                                    {
                                        "rank": "normal",
                                        "mainsnak": {
                                            "snaktype": "value",
                                            "datavalue": {"value": {"id": "Q11424"}},
                                        },
                                    }
                                ]
                            },
                        }
                    }
                },
            )
        }
        payload = await wikidata(routes).fetch("Q546900")
        assert payload.cover_url is None


class TestIdentifiers:
    async def test_it_emits_every_exact_identity_the_film_carries(self) -> None:
        payload = await wikidata(FETCH_1977).fetch("Q546900")
        assert payload.identifiers == {
            "wikidata": "Q546900",
            "imdb": "tt0076786",
            "tmdb": "11906",
            "letterboxd": "suspiria",
        }

    async def test_two_films_sharing_a_title_carry_different_identities(self) -> None:
        rows = await wikidata(SUSPIRIA_SEARCH).search("Suspiria")
        assert rows[0].identifiers["letterboxd"] == "suspiria"
        assert rows[1].identifiers["letterboxd"] == "suspiria-2018"


class TestFetchByIdentity:
    async def test_it_fetches_a_q_id(self) -> None:
        payload = await wikidata(FETCH_1977).fetch("Q546900")
        assert payload.source_id == "Q546900"
        assert payload.title == "Suspiria"

    async def test_it_resolves_an_imdb_id_through_an_exact_claim(self) -> None:
        routes: dict[str, Route] = {
            claim_key("P345", "tt0076786"): (
                200,
                recording("wikidata_search_p345_tt0076786.json"),
            ),
            **FETCH_1977,
        }
        payload = await wikidata(routes).fetch("imdb:tt0076786")
        assert payload.source_id == "Q546900"

    async def test_it_resolves_a_tmdb_movie_id(self) -> None:
        routes: dict[str, Route] = {
            claim_key("P4947", "11906"): (200, recording("wikidata_search_p4947_11906.json")),
            **FETCH_1977,
        }
        assert (await wikidata(routes).fetch("tmdb:11906")).source_id == "Q546900"

    async def test_it_resolves_a_letterboxd_slug(self) -> None:
        routes: dict[str, Route] = {
            claim_key("P6127", "suspiria"): (200, recording("wikidata_search_p6127_suspiria.json")),
            **FETCH_1977,
        }
        assert (await wikidata(routes).fetch("letterboxd:suspiria")).source_id == "Q546900"

    async def test_the_fetched_film_must_really_carry_the_claim_it_was_found_by(self) -> None:
        """The search index is not the record. If the entity does not hold the exact
        value asked for, the answer is a miss rather than a plausible neighbour."""
        routes: dict[str, Route] = {
            claim_key("P6127", "suspiria-2018"): (
                200,
                recording("wikidata_search_p6127_suspiria.json"),
            ),
            **FETCH_1977,
        }
        with pytest.raises(ProviderPayloadError) as error:
            await wikidata(routes).fetch("letterboxd:suspiria-2018")
        assert error.value.code == "record_not_found"

    async def test_an_identity_nothing_carries_is_a_miss(self) -> None:
        routes: dict[str, Route] = {
            claim_key("P6127", "this-film-does-not-exist-xyz"): (
                200,
                recording("wikidata_search_p6127_no_match.json"),
            )
        }
        with pytest.raises(ProviderPayloadError) as error:
            await wikidata(routes).fetch("letterboxd:this-film-does-not-exist-xyz")
        assert error.value.code == "record_not_found"

    async def test_an_identity_two_films_claim_is_refused_rather_than_guessed(self) -> None:
        routes: dict[str, Route] = {
            claim_key("P345", "tt0076786"): (200, recording("wikidata_search_ambiguous.json"))
        }
        with pytest.raises(ProviderPayloadError) as error:
            await wikidata(routes).fetch("imdb:tt0076786")
        assert error.value.code == "identity_ambiguous"

    @pytest.mark.parametrize(
        "value",
        ["", "   ", "Q0", "Q", "12345", "imdb:", "imdb:nm0000602", "tmdb:abc", "letterboxd:"],
    )
    async def test_a_malformed_identity_never_reaches_the_network(self, value: str) -> None:
        def forbidden(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"unexpected call to {request.url}")

        client = create_provider_client(httpx.MockTransport(forbidden))
        provider = WikidataMovieProvider(client, "test@example.invalid")
        with pytest.raises(ProviderPayloadError):
            await provider.fetch(value)


class TestShortUriResolution:
    """Following a `boxd.it` link is identity resolution, not page scraping."""

    LOCATION = redirect_location("letterboxd_boxd_it_redirect.headers")

    async def test_it_follows_a_short_uri_with_a_head_request_only(self) -> None:
        methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            methods.append(request.method)
            if request.url.host == "boxd.it":
                return httpx.Response(302, headers={"location": self.LOCATION})
            raise AssertionError(f"unexpected call to {request.url}")

        client = create_provider_client(httpx.MockTransport(handler))
        provider = WikidataMovieProvider(client, "test@example.invalid")
        assert await provider.resolve_letterboxd_slug("https://boxd.it/2b0k") == "the-dark-knight"
        assert methods == ["HEAD"]

    async def test_a_redirect_off_letterboxd_is_refused(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://evil.test/film/stolen/"})

        client = create_provider_client(httpx.MockTransport(handler))
        provider = WikidataMovieProvider(client, "test@example.invalid")
        with pytest.raises(ProviderPayloadError) as error:
            await provider.resolve_letterboxd_slug("https://boxd.it/2b0k")
        assert error.value.code == "unsafe_redirect"

    async def test_a_downgrade_to_plaintext_is_refused(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "http://letterboxd.com/film/x/"})

        client = create_provider_client(httpx.MockTransport(handler))
        provider = WikidataMovieProvider(client, "test@example.invalid")
        with pytest.raises(ProviderPayloadError) as error:
            await provider.resolve_letterboxd_slug("https://boxd.it/2b0k")
        assert error.value.code == "unsafe_redirect"

    async def test_a_redirect_loop_ends(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://boxd.it/2b0k"})

        client = create_provider_client(httpx.MockTransport(handler))
        provider = WikidataMovieProvider(client, "test@example.invalid")
        with pytest.raises(ProviderPayloadError) as error:
            await provider.resolve_letterboxd_slug("https://boxd.it/2b0k")
        assert error.value.code == "unsafe_redirect"

    async def test_a_destination_that_is_not_a_film_page_is_refused(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://letterboxd.com/tomate/"})

        client = create_provider_client(httpx.MockTransport(handler))
        provider = WikidataMovieProvider(client, "test@example.invalid")
        with pytest.raises(ProviderPayloadError) as error:
            await provider.resolve_letterboxd_slug("https://boxd.it/2b0k")
        assert error.value.code == "unsafe_redirect"

    async def test_a_film_url_needs_no_network_at_all(self) -> None:
        def forbidden(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"unexpected call to {request.url}")

        client = create_provider_client(httpx.MockTransport(forbidden))
        provider = WikidataMovieProvider(client, "test@example.invalid")
        slug = await provider.resolve_letterboxd_slug("https://letterboxd.com/film/suspiria/")
        assert slug == "suspiria"


class TestEnrichmentEntryPoint:
    """What background enrichment asks through (DEC-067 row 3)."""

    SLUG_ROUTES: dict[str, Route] = {
        claim_key("P6127", "suspiria"): (200, recording("wikidata_search_p6127_suspiria.json")),
        **FETCH_1977,
    }

    async def test_it_answers_a_bare_slug(self) -> None:
        """What a film added through search stores, straight out of `P6127`."""
        payload = await wikidata(self.SLUG_ROUTES).fetch_by_identifier("letterboxd", "suspiria")
        assert payload.source_id == "Q546900"

    async def test_it_answers_the_short_uri_the_importer_will_store(self) -> None:
        """Sprint 047's export identifies a film by `boxd.it` URI, and the same stored
        kind therefore holds two shapes. Both have to resolve to one film."""
        location = redirect_location("letterboxd_boxd_it_redirect.headers")
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.method)
            if request.url.host == "boxd.it":
                return httpx.Response(
                    302, headers={"location": location.replace("the-dark-knight", "suspiria")}
                )
            route = self.SLUG_ROUTES[wikidata_route_key(request)]
            return httpx.Response(route[0], json=route[1])

        client = create_provider_client(httpx.MockTransport(handler))
        provider = WikidataMovieProvider(client, "test@example.invalid")
        payload = await provider.fetch_by_identifier("letterboxd", "https://boxd.it/2b0k")
        assert payload.source_id == "Q546900"
        assert seen[0] == "HEAD"

    async def test_a_kind_it_does_not_answer_is_refused_rather_than_guessed(self) -> None:
        def forbidden(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"unexpected call to {request.url}")

        client = create_provider_client(httpx.MockTransport(forbidden))
        provider = WikidataMovieProvider(client, "test@example.invalid")
        with pytest.raises(ProviderPayloadError) as error:
            await provider.fetch_by_identifier("isbn", "9788437604572")
        assert error.value.code == "unsupported_identity_kind"


class TestFailures:
    """Nothing raw reaches the layer above: not a row, and not an exception."""

    async def test_a_missing_entity_is_an_answer_and_not_an_outage(self) -> None:
        routes: dict[str, Route] = {
            entities_key("Q546900"): (200, {"entities": {"Q546900": {"missing": ""}}})
        }
        with pytest.raises(ProviderPayloadError) as error:
            await wikidata(routes).fetch("Q546900")
        assert error.value.code == "record_not_found"

    async def test_a_server_error_is_an_outage(self) -> None:
        routes: dict[str, Route] = {entities_key("Q546900"): (500, {"error": "boom"})}
        with pytest.raises(ProviderPayloadError) as error:
            await wikidata(routes).fetch("Q546900")
        assert error.value.code == "provider_http_error"

    async def test_replication_lag_is_reported_rather_than_parsed(self) -> None:
        """Wikimedia answers `maxlag` with **HTTP 200** and an error object, so nothing
        below this notices it and the payload has no entity in it at all."""
        routes: dict[str, Route] = {
            entities_key("Q546900"): (
                200,
                {"error": {"code": "maxlag", "info": "Waiting for a database server"}},
            )
        }
        with pytest.raises(ProviderPayloadError) as error:
            await wikidata(routes).fetch("Q546900")
        assert error.value.code == "provider_http_error"

    async def test_a_payload_with_no_entities_is_refused(self) -> None:
        routes: dict[str, Route] = {entities_key("Q546900"): (200, {"batchcomplete": True})}
        with pytest.raises(ProviderPayloadError):
            await wikidata(routes).fetch("Q546900")

    async def test_an_entity_that_is_not_a_film_is_refused(self) -> None:
        """A `Q` id pasted into the add box has been through no film filter at all, and
        a person or a television series is a perfectly legible thing to paste."""
        routes: dict[str, Route] = {
            entities_key("Q53011"): (
                200,
                {
                    "entities": {
                        "Q53011": {
                            "id": "Q53011",
                            "labels": {"es": {"language": "es", "value": "Dario Argento"}},
                            "claims": {
                                "P31": [
                                    {
                                        "rank": "normal",
                                        "mainsnak": {
                                            "snaktype": "value",
                                            "datavalue": {"value": {"id": "Q5"}},
                                        },
                                    }
                                ]
                            },
                        }
                    }
                },
            )
        }
        with pytest.raises(ProviderPayloadError) as error:
            await wikidata(routes).fetch("Q53011")
        assert error.value.code == "record_not_found"

    async def test_an_entity_with_no_usable_label_is_refused(self) -> None:
        routes: dict[str, Route] = {
            entities_key("Q546900"): (
                200,
                {"entities": {"Q546900": {"id": "Q546900", "labels": {}, "claims": {}}}},
            )
        }
        with pytest.raises(ProviderPayloadError):
            await wikidata(routes).fetch("Q546900")

    async def test_it_sends_a_descriptive_user_agent(self) -> None:
        """Wikimedia's data-access guidance asks clients to identify themselves."""
        seen: list[str] = []
        provider = wikidata(
            FETCH_1977,
            on_request=lambda request: seen.append(request.headers.get("user-agent", "")),
        )
        await provider.fetch("Q546900")
        assert "Akasha" in seen[0] and "test@example.invalid" in seen[0]

    async def test_no_request_declares_a_lag_tolerance(self) -> None:
        """`maxlag` is Wikimedia's brake on *writes* and bulk automated jobs. Every read
        this adapter makes is a `query` or a `wbgetentities`, and the lag the parameter
        answers to is the **query service** replica pool — measured at 15–17 s on two
        separate days, which shed every single `maxlag=5` request and blacked out the
        movie domain twice (DEC-108, then DEC-125). The courtesy obligations are met by
        `_Paced`, the byte bound and the User-Agent, none of which this removes."""
        seen: list[str] = []
        provider = wikidata(FETCH_1977, on_request=lambda request: seen.append(str(request.url)))
        await provider.fetch("Q546900")
        assert seen and all("maxlag" not in url for url in seen)


def test_the_route_key_separates_operations_that_share_one_path() -> None:
    """Every Wikidata read is a `GET /w/api.php`, so the test transport keys on what
    actually distinguishes them. This is the helper the fixtures are named by."""
    request = httpx.Request(
        "GET",
        "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q1|Q2&props=labels",
    )
    assert wikidata_route_key(request) == "labels:Q1|Q2"
    assert dict(parse_qsl(request.url.query.decode()))["action"] == "wbgetentities"
