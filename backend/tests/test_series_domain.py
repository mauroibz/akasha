"""The series domain's declaration, pinned before the package exists.

Field coverage is measured, not guessed: `docs/series-domain-viability.md` holds the
table. Two assertions here are measurements with a shelf life, not taste:

- `seasons` and `cast` are **not** enrichment completeness fields — absent on 2/13 and
  4/13 of measured entities (0 on every animated series). Naming a legitimately empty
  field re-queues its row on every backfill for ever.
- `synopsis` holds Wikidata's one-line identification sentence in this sprint, exactly
  what movies call `description`. It is named for its Sprint 050 purpose (a real
  synopsis from TVmaze) because renaming a published field later is worse.
"""

import pytest

from book_tracker.domain.providers import SearchCandidate
from book_tracker.domain.spec import PASSAGE_FIELDS, UrlMatch, validate_progress
from book_tracker.domains.series import DOMAIN, recognize_series_url


def _candidate(identifiers: dict[str, str]) -> SearchCandidate:
    return SearchCandidate(
        source="wikidata-series",
        source_id="Q1",
        source_refs=(),
        title="",
        subtitle=None,
        creators=(),
        year=None,
        cover_url=None,
        identifiers=identifiers,
        language=None,
        metadata={},
    )


def test_the_domain_names_itself() -> None:
    assert DOMAIN.item_type == "series"
    assert DOMAIN.label == "Series"
    assert DOMAIN.entry_panel_label == "Your watch data"


def test_statuses_are_animes_five_plus_the_inbox() -> None:
    values = [status.value for status in DOMAIN.statuses]
    assert values == [
        "unsorted",
        "watching",
        "completed",
        "on_hold",
        "dropped",
        "plan_to_watch",
    ]
    assert DOMAIN.default_status == "plan_to_watch"
    hotkeys = {s.value: s.hotkey for s in DOMAIN.statuses if s.choosable}
    assert hotkeys == {
        "watching": "w",
        "completed": "c",
        "on_hold": "h",
        "dropped": "d",
        "plan_to_watch": "p",
    }


def test_formats_are_the_movie_four() -> None:
    assert [row.value for row in DOMAIN.formats] == ["streaming", "digital", "bluray", "dvd"]


def test_fields_match_the_measured_coverage_table() -> None:
    fields = {field.name: field for field in DOMAIN.fields}
    assert list(fields) == [
        "creators",
        "original_title",
        "countries",
        "languages",
        "genres",
        "episodes",
        "seasons",
        "episode_minutes",
        "network",
        "airing_status",
        "cast",
        "synopsis",
    ]
    assert fields["creators"].multiplicity == "many"
    assert fields["episodes"].type == "number"
    assert fields["episodes"].minimum == 1
    assert fields["episodes"].maximum == 100_000
    assert fields["seasons"].type == "number"
    assert fields["seasons"].maximum == 1_000
    assert fields["episode_minutes"].type == "number"
    assert fields["episode_minutes"].maximum == 1_000
    assert fields["synopsis"].type == "long_text"


def test_entry_shape() -> None:
    assert DOMAIN.entry_fields == PASSAGE_FIELDS
    assert DOMAIN.entry_field_labels == {"reread_count": "Rewatches"}


def test_progress_counts_episodes_against_the_measured_total() -> None:
    assert DOMAIN.progress is not None
    assert DOMAIN.progress.label == "Episodes watched"
    assert DOMAIN.progress.unit_label == "episode"
    assert DOMAIN.progress.total_field == "episodes"


def test_identity_is_the_imdb_id() -> None:
    assert DOMAIN.identity.identity_key(_candidate({"imdb": "tt0944947"})) == "imdb:tt0944947"
    assert DOMAIN.identity.identity_key(_candidate({})) is None
    assert DOMAIN.identity.source_preference == ("wikidata-series", "tvmaze")


def test_enrichment_is_keyed_on_imdb_and_excludes_measured_gaps() -> None:
    spec = DOMAIN.enrichment
    assert spec is not None
    assert spec.identity_kind == "imdb"
    assert spec.provider_order == ("wikidata-series", "tvmaze")
    # Measured 2026-08-31: `seasons` absent on 2/13, `cast` on 4/13 (every animated
    # series). Naming either re-queues those rows on every backfill for ever.
    assert "seasons" not in spec.completeness_fields
    assert "cast" not in spec.completeness_fields
    assert spec.completeness_fields == ("creators", "genres", "synopsis")


def test_no_cover_chooser() -> None:
    assert DOMAIN.chooses_covers is False


@pytest.mark.parametrize(
    ("url", "value"),
    [
        ("https://www.wikidata.org/wiki/Q22976", "Q22976"),
        ("https://www.wikidata.org/entity/Q22976/", "Q22976"),
        ("https://www.imdb.com/title/tt0944947/", "imdb:tt0944947"),
        ("https://m.imdb.com/title/tt0944947/ratings/", "imdb:tt0944947"),
        ("https://www.themoviedb.org/tv/1399-game-of-thrones", "tmdb:1399"),
        ("https://www.themoviedb.org/tv/1399", "tmdb:1399"),
        ("https://thetvdb.com/series/game-of-thrones", "tvdb:game-of-thrones"),
    ],
)
def test_series_urls_route_to_the_wikidata_adapter(url: str, value: str) -> None:
    assert recognize_series_url(url) == UrlMatch("wikidata-series", "fetch", value)


def test_a_tvmaze_url_routes_to_the_tvmaze_adapter() -> None:
    """Sprint 050: a TVmaze id resolves through the TVmaze adapter, not Wikidata."""
    assert recognize_series_url("https://www.tvmaze.com/shows/82/game-of-thrones") == UrlMatch(
        "tvmaze", "fetch", "82"
    )


@pytest.mark.parametrize(
    "url",
    [
        # TMDB's /movie/ path is a film and stays the movie domain's. A series
        # recognizer that claimed it would break add-by-URL for films.
        "https://www.themoviedb.org/movie/11906-suspiria",
        "https://www.imdb.com/name/nm0000602/",
        "https://thetvdb.com/movies/some-film",
        "https://www.tvmaze.com/people/123/somebody",
        "not a url at all",
        "",
    ],
)
def test_anything_else_is_declined(url: str) -> None:
    assert recognize_series_url(url) is None


def test_a_malformed_authority_is_declined_not_raised() -> None:
    # `urlsplit` raises on `http://[`; `split_url` answers None. A recognizer that
    # raises denies every domain registered after it its turn.
    assert recognize_series_url("http://[") is None


class TestProgress:
    def test_a_count_is_stored(self) -> None:
        assert validate_progress(DOMAIN, 20) == 20

    def test_a_count_above_the_total_is_stored_not_refused(self) -> None:
        # DEC-092: the cached total is display only and never a bound — an airing
        # series' total moves, and a count correct when written stays correct.
        assert validate_progress(DOMAIN, 200) == 200

    def test_zero_and_none_are_different_facts(self) -> None:
        assert validate_progress(DOMAIN, 0) == 0
        assert validate_progress(DOMAIN, None) is None

    def test_a_negative_count_is_refused(self) -> None:
        from book_tracker.domain.spec import InvalidProgress

        with pytest.raises(InvalidProgress):
            validate_progress(DOMAIN, -1)
