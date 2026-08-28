"""Movies: what this domain declares, and what its recognizer answers.

The conformance suite already holds every domain to the shared contract by
parametrization, so nothing here repeats it. What this file covers is the part only
this domain can be wrong about: the vocabulary Sprint 045 measured against live
Wikidata (DEC-098), the identity rule a single-provider domain needs, and the five URL
shapes a reader will paste.
"""

from book_tracker.domain.providers import SearchCandidate
from book_tracker.domain.spec import UrlMatch
from book_tracker.domains.movie import DOMAIN, recognize_movie_url, wikidata_identity


def candidate(**overrides: object) -> SearchCandidate:
    fields: dict[str, object] = {
        "source": "wikidata",
        "source_id": "Q546900",
        "source_refs": (),
        "title": "Suspiria",
        "subtitle": None,
        "creators": ("Dario Argento",),
        "year": 1977,
        "cover_url": None,
        "identifiers": {},
        "language": None,
        "metadata": {},
    }
    fields.update(overrides)
    return SearchCandidate(**fields)  # type: ignore[arg-type]


class TestVocabulary:
    def test_a_film_is_on_the_list_or_it_has_been_seen(self) -> None:
        """Three states, not the book vocabulary renamed.

        A film is not `reading` and there is no `dropped` half-watch worth a state of
        its own: the owner's Letterboxd export says watched or not watched.
        """
        assert [status.value for status in DOMAIN.statuses] == [
            "unsorted",
            "watchlist",
            "watched",
        ]
        assert DOMAIN.default_status == "watchlist"
        assert DOMAIN.status("unsorted") is not None
        assert not DOMAIN.status("unsorted").choosable  # type: ignore[union-attr]

    def test_the_common_triage_decision_gets_the_obvious_key(self) -> None:
        """An import arrives mostly watched, so `w` is spent on Watched, not Watchlist."""
        hotkeys = {status.value: status.hotkey for status in DOMAIN.statuses}
        assert hotkeys["watched"] == "w"
        assert hotkeys["watchlist"] == "l"

    def test_a_film_is_finished_or_rewatched_but_never_started(self) -> None:
        """You do not record the day you began a 94-minute film (DEC-057)."""
        assert DOMAIN.entry_fields == frozenset({"date_finished", "reread_count"})

    def test_it_declares_how_a_copy_is_held(self) -> None:
        assert [row.value for row in DOMAIN.formats] == [
            "streaming",
            "digital",
            "bluray",
            "dvd",
        ]

    def test_metadata_names_do_not_collide_with_entry_concepts(self) -> None:
        """`runtime` is not a format and `description` is not a status.

        The neutral `year` column holds the release year, so no field shadows it.
        """
        names = {field.name for field in DOMAIN.fields}
        assert names == {
            "creators",
            "original_title",
            "countries",
            "languages",
            "genres",
            "runtime",
            "cast",
            "description",
        }
        assert not names & {"title", "subtitle", "year", "creator_sort_override"}
        assert not names & {"status", "format"}

    def test_the_runtime_is_a_bounded_whole_number_of_minutes(self) -> None:
        runtime = next(field for field in DOMAIN.fields if field.name == "runtime")
        assert runtime.type == "number"
        assert runtime.minimum == 1

    def test_it_offers_no_cover_chooser(self) -> None:
        """The shared chooser is Open Library's work-editions path (DEC-067 row 7)."""
        assert DOMAIN.chooses_covers is False


class TestIdentity:
    """One provider, so a merge is not the question a key answers here.

    What it does answer is the one Sprint 045 measured as the real hazard: two films
    called `Suspiria`, forty-one years apart, must never collapse into one row.
    """

    def test_a_q_id_is_the_key(self) -> None:
        assert wikidata_identity(candidate()) == "wikidata:Q546900"

    def test_two_films_sharing_a_title_keep_separate_keys(self) -> None:
        remake = candidate(source_id="Q28123467", year=2018)
        assert wikidata_identity(candidate()) != wikidata_identity(remake)

    def test_a_row_with_no_q_id_merges_with_nothing(self) -> None:
        """`None` means never merge, which is the safe answer for an unusable row."""
        assert wikidata_identity(candidate(source_id="")) is None
        assert wikidata_identity(candidate(source_id="not-a-q-id")) is None

    def test_the_only_source_it_prefers_is_the_one_it_has(self) -> None:
        assert DOMAIN.identity.source_preference == ("wikidata",)


class TestRecognizer:
    """The five shapes a reader can paste, all spent on the one adapter."""

    def test_it_reads_a_wikidata_entity_url(self) -> None:
        assert recognize_movie_url("https://www.wikidata.org/wiki/Q546900") == UrlMatch(
            "wikidata", "fetch", "Q546900"
        )

    def test_it_reads_the_entity_data_url_too(self) -> None:
        assert recognize_movie_url("https://www.wikidata.org/entity/Q546900") == UrlMatch(
            "wikidata", "fetch", "Q546900"
        )

    def test_an_imdb_title_url_is_spent_on_wikidata(self) -> None:
        """No IMDb adapter is registered; the id is an exact `P345` claim instead."""
        assert recognize_movie_url("https://www.imdb.com/title/tt0076786/") == UrlMatch(
            "wikidata", "fetch", "imdb:tt0076786"
        )

    def test_a_tmdb_movie_url_is_spent_on_wikidata(self) -> None:
        assert recognize_movie_url("https://www.themoviedb.org/movie/11906-suspiria") == UrlMatch(
            "wikidata", "fetch", "tmdb:11906"
        )

    def test_a_letterboxd_film_url_is_spent_on_wikidata(self) -> None:
        assert recognize_movie_url("https://letterboxd.com/film/suspiria/") == UrlMatch(
            "wikidata", "fetch", "letterboxd:suspiria"
        )

    def test_a_short_uri_keeps_its_whole_address(self) -> None:
        """The adapter resolves it with a HEAD request; the recognizer never follows."""
        assert recognize_movie_url("https://boxd.it/2b0k") == UrlMatch(
            "wikidata", "fetch", "letterboxd:https://boxd.it/2b0k"
        )

    def test_it_declines_a_wikidata_property_page(self) -> None:
        """`P31` is a property, not a film."""
        assert recognize_movie_url("https://www.wikidata.org/wiki/Property:P31") is None

    def test_it_declines_a_tv_series_and_a_person(self) -> None:
        assert recognize_movie_url("https://www.themoviedb.org/tv/1396") is None
        assert recognize_movie_url("https://www.imdb.com/name/nm0000602/") is None

    def test_it_declines_a_letterboxd_list_or_review(self) -> None:
        assert recognize_movie_url("https://letterboxd.com/tomate/list/favourites/") is None

    def test_a_lookalike_host_is_not_letterboxd(self) -> None:
        """`letterboxd.com.evil.test` ends with the name and is a different site."""
        assert recognize_movie_url("https://letterboxd.com.evil.test/film/suspiria/") is None
        assert recognize_movie_url("https://evil.test/boxd.it/2b0k") is None

    def test_plain_http_is_not_followed(self) -> None:
        assert recognize_movie_url("http://boxd.it/2b0k") is None

    def test_it_declines_everything_else_without_raising(self) -> None:
        """A recognizer that raises denies every domain after it its turn."""
        for probe in ("", "   ", "http://[", "http://[::1", "https://", "//", "9780000000000"):
            assert recognize_movie_url(probe) is None


class TestEntryFieldLabels:
    def test_a_film_is_watched_and_rewatched(self) -> None:
        """`Finished` is right for a book and a series; for a film it is `Watched`."""
        assert DOMAIN.entry_field_labels["date_finished"] == "Watched"
        assert DOMAIN.entry_field_labels["reread_count"] == "Rewatches"

    def test_it_labels_only_fields_it_declares(self) -> None:
        assert set(DOMAIN.entry_field_labels) <= DOMAIN.entry_fields


class TestEnrichment:
    """The key is a Letterboxd film, because Sprint 047's export identifies films by one.

    A film added by hand arrives complete from one fetch, exactly as an album does. This
    declaration exists for the imported row that is a URI, a title and a year.
    """

    def test_it_enriches_on_the_letterboxd_film(self) -> None:
        assert DOMAIN.enrichment is not None
        assert DOMAIN.enrichment.identity_kind == "letterboxd"

    def test_wikidata_answers_that_key(self) -> None:
        assert DOMAIN.enrichment is not None
        assert DOMAIN.enrichment.provider_order == ("wikidata",)

    def test_incompleteness_names_only_claims_every_measured_film_carried(self) -> None:
        """`cast` and `description` are legitimately absent on real films, and a rule
        that named them would re-queue those rows for ever."""
        assert DOMAIN.enrichment is not None
        declared = {field.name for field in DOMAIN.fields}
        assert set(DOMAIN.enrichment.completeness_fields) <= declared
        assert set(DOMAIN.enrichment.completeness_fields) == {"creators", "genres", "runtime"}

    def test_enriches_reads_as_a_yes(self) -> None:
        assert DOMAIN.enriches is True


class TestProgress:
    def test_a_film_has_no_progress_count(self) -> None:
        """You are not 40 episodes into a film; DEC-077's `None` is a complete answer."""
        assert DOMAIN.progress is None
