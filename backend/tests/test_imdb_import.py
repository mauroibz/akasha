"""The IMDb connector, against synthetic CSVs built here.

Nothing in this file comes from the owner's exports. The `tt` ids, titles, ratings and
dates below are invented; the *shapes* are the two measured on 2026-08-31 — a ratings
export beginning `Const,Your Rating,Date Rated,…` and a list export beginning
`Position,Const,Created,Modified,Description,…`, whose `Your Rating` and `Date Rated`
sit at the end and are routinely blank.

The owner's real files are three rows between them and exercise almost none of what is
below. That is DEC-093's lesson stated as a test file: **a reader tested only against
the file in front of you is tested against one file.**
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from book_tracker.domain.importers import ImportReadContext, ImportReadError, ImportSource
from book_tracker.domains.movie.imdb import IMPORTER, ImdbError, parse_imdb

RATINGS_HEADER = (
    "Const,Your Rating,Date Rated,Title,Original Title,URL,Title Type,IMDb Rating,"
    "Runtime (mins),Year,Genres,Num Votes,Release Date,Directors"
)
LIST_HEADER = (
    "Position,Const,Created,Modified,Description,Title,Original Title,URL,Title Type,"
    "IMDb Rating,Runtime (mins),Year,Genres,Num Votes,Release Date,Directors,"
    "Your Rating,Date Rated"
)


def ratings(*rows: str) -> bytes:
    return ("\n".join([RATINGS_HEADER, *rows]) + "\n").encode("utf-8")


def listing(*rows: str) -> bytes:
    return ("\n".join([LIST_HEADER, *rows]) + "\n").encode("utf-8")


#: A ratings row, with every column in the measured order.
def rating_row(
    *,
    const: str = "tt0111161",
    score: str = "9",
    date_rated: str = "2024-03-01",
    title: str = "The Shawshank Redemption",
    original: str = "",
    kind: str = "Movie",
    runtime: str = "142",
    year: str = "1994",
    genres: str = "Drama",
    directors: str = "Frank Darabont",
) -> str:
    return (
        f"{const},{score},{date_rated},{title},{original},"
        f"https://www.imdb.com/title/{const}/,{kind},9.3,{runtime},{year},"
        f'"{genres}",2900000,1994-10-14,"{directors}"'
    )


def list_row(
    *,
    const: str = "tt0903747",
    position: str = "1",
    created: str = "2024-05-06",
    description: str = "",
    title: str = "Breaking Bad",
    original: str = "",
    kind: str = "TV Series",
    runtime: str = "49",
    year: str = "2008",
    genres: str = "Crime",
    directors: str = "",
    score: str = "",
    date_rated: str = "",
) -> str:
    return (
        f"{position},{const},{created},2024-05-06,{description},{title},{original},"
        f"https://www.imdb.com/title/{const}/,{kind},9.5,{runtime},{year},"
        f'"{genres}",2100000,2008-01-20,"{directors}",{score},{date_rated}'
    )


def read(data: bytes) -> Any:
    return IMPORTER.read(
        ImportSource(data=data, filename="ratings.csv"), ImportReadContext(Path("."))
    )


def only(data: bytes) -> Any:
    records = read(data).records
    assert len(records) == 1, [row.item.title for row in records]
    return records[0]


class TestTwoShapes:
    """The header decides, never the column position (deliverable 1)."""

    def test_a_ratings_export_is_read(self) -> None:
        record = only(ratings(rating_row()))
        assert record.item.title == "The Shawshank Redemption"
        assert record.item.identifiers == {"imdb": "tt0111161"}
        assert record.entry.score == 9

    def test_a_list_export_is_read_with_the_same_mappings(self) -> None:
        """A Watchlist is a list export. Its rating columns are at the end and blank."""
        record = only(listing(list_row()))
        assert record.item.title == "Breaking Bad"
        assert record.item.identifiers == {"imdb": "tt0903747"}
        assert record.entry.score is None

    def test_the_same_row_maps_identically_through_either_shape(self) -> None:
        """The columns move; nothing they mean does."""
        from_ratings = only(ratings(rating_row(kind="TV Series", const="tt0903747")))
        from_list = only(
            listing(list_row(score="9", date_rated="2024-03-01", created="2024-03-01"))
        )
        assert from_ratings.item.identifiers == from_list.item.identifiers
        assert from_ratings.entry.score == from_list.entry.score == 9
        assert from_ratings.entry.date_added == from_list.entry.date_added == "2024-03-01"

    def test_a_header_that_is_neither_shape_is_a_file_level_refusal(self) -> None:
        """A Letterboxd CSV uploaded here is the wrong file, not a bad row."""
        with pytest.raises(ImdbError) as refused:
            read(b"Date,Name,Year,Letterboxd URI\n2024-01-01,Solaris,1972,x\n")
        assert refused.value.code == "unknown_export_shape"
        assert refused.value.code in IMPORTER.error_codes
        # A person can act on it, which is the whole point of `action` (DEC-080).
        assert refused.value.action

    def test_an_empty_file_is_refused_rather_than_read_as_zero_rows(self) -> None:
        with pytest.raises(ImdbError) as refused:
            read(b"")
        assert refused.value.code == "unknown_export_shape"

    def test_a_header_missing_a_required_column_is_refused(self) -> None:
        with pytest.raises(ImdbError) as refused:
            read(b"Const,Your Rating,Date Rated,Title\ntt0111161,9,2024-03-01,X\n")
        assert refused.value.code == "unknown_export_shape"

    def test_a_byte_order_mark_does_not_hide_the_first_column(self) -> None:
        """IMDb serves these UTF-8 with a BOM; `Const` must still be `Const`."""
        record = only(b"\xef\xbb\xbf" + ratings(rating_row()))
        assert record.item.identifiers == {"imdb": "tt0111161"}


class TestRouting:
    """The declared table, whose default is skip-and-count (deliverable 1)."""

    @pytest.mark.parametrize(
        ("title_type", "target"),
        [
            ("Movie", "movie"),
            ("TV Movie", "movie"),
            ("Video", "movie"),
            ("TV Series", "series"),
            ("TV Mini Series", "series"),
        ],
    )
    def test_a_declared_type_routes_to_its_library(self, title_type: str, target: str) -> None:
        record = only(ratings(rating_row(kind=title_type)))
        assert record.item_type == target

    @pytest.mark.parametrize(
        "title_type", ["TV Episode", "Short", "Podcast Series", "Video Game", "Music Video"]
    )
    def test_a_kind_no_library_holds_is_counted_and_not_a_row(self, title_type: str) -> None:
        snapshot = read(ratings(rating_row(kind=title_type)))
        assert snapshot.records == ()
        assert [(skip.reason, skip.count) for skip in snapshot.skipped] == [(title_type, 1)]

    def test_a_title_type_imdb_has_not_published_yet_is_a_number_not_an_outage(self) -> None:
        """The default is skip and count. It is never a guess and never an error."""
        snapshot = read(
            ratings(
                rating_row(const="tt0000001", kind="Interactive Holodeck Experience"),
                rating_row(const="tt0111161", kind="Movie"),
            )
        )
        assert [row.item.title for row in snapshot.records] == ["The Shawshank Redemption"]
        assert [(skip.reason, skip.count) for skip in snapshot.skipped] == [
            ("Interactive Holodeck Experience", 1)
        ]
        assert all(not row.errors for row in snapshot.records)

    def test_skips_are_tallied_by_reason_not_listed_per_row(self) -> None:
        """Bounded by the number of distinct kinds, not by the size of the export."""
        snapshot = read(
            ratings(
                *[rating_row(const=f"tt000000{n}", kind="TV Episode") for n in range(1, 5)],
                rating_row(const="tt1000000", kind="Podcast Episode"),
            )
        )
        assert [(skip.reason, skip.count) for skip in snapshot.skipped] == [
            ("TV Episode", 4),
            ("Podcast Episode", 1),
        ]

    def test_a_blank_title_type_is_skipped_under_a_readable_reason(self) -> None:
        """Never guessed — and never counted under an empty word, which would render
        as a gap on the preview screen."""
        snapshot = read(ratings(rating_row(kind="")))
        assert snapshot.records == ()
        assert [(skip.reason, skip.count) for skip in snapshot.skipped] == [("(no title type)", 1)]

    def test_one_file_produces_records_of_both_types(self) -> None:
        snapshot = read(
            ratings(
                rating_row(const="tt0111161", kind="Movie"),
                rating_row(const="tt0903747", kind="TV Series", title="Breaking Bad"),
            )
        )
        assert [row.item_type for row in snapshot.records] == ["movie", "series"]


class TestMappings:
    def test_the_const_is_the_identity_both_libraries_already_use(self) -> None:
        record = only(ratings(rating_row(const="tt1375666")))
        assert record.item.identifiers == {"imdb": "tt1375666"}

    def test_a_const_that_is_not_an_imdb_id_is_a_row_error_not_an_identity(self) -> None:
        record = only(ratings(rating_row(const="nm0000151")))
        assert record.item.identifiers == {}
        assert {"field": "Const", "code": "invalid_identifier", "value": "nm0000151"} in list(
            record.errors
        )

    def test_a_rating_maps_one_to_one_with_no_doubling(self) -> None:
        """Letterboxd's half-stars double; IMDb's 1-10 is already the scale."""
        record = only(ratings(rating_row(score="7")))
        assert record.entry.score == 7
        assert record.entry.score_provisional is False

    def test_a_blank_rating_is_unscored_rather_than_zero(self) -> None:
        assert only(ratings(rating_row(score=""))).entry.score is None

    @pytest.mark.parametrize("score", ["0", "11", "-1", "4.5", "nine"])
    def test_a_rating_outside_the_scale_is_a_row_error(self, score: str) -> None:
        """`ck_entries_score` allows 1-10 and nothing between here and commit
        re-checks: an out-of-range value would raise mid-batch (DEC-093)."""
        record = only(ratings(rating_row(score=score)))
        assert record.entry.score is None
        assert [row["field"] for row in record.errors] == ["Your Rating"]

    def test_a_scored_row_suggests_the_watched_word_of_its_own_library(self) -> None:
        assert only(ratings(rating_row(kind="Movie"))).entry.suggested_status == "watched"
        assert only(ratings(rating_row(kind="TV Series"))).entry.suggested_status == "completed"

    def test_an_unscored_row_suggests_the_planned_word_of_its_own_library(self) -> None:
        assert only(listing(list_row(kind="Movie"))).entry.suggested_status == "watchlist"
        assert only(listing(list_row(kind="TV Series"))).entry.suggested_status == "plan_to_watch"

    def test_the_arrival_date_is_the_export_s_own_and_is_never_a_viewing_date(self) -> None:
        """IMDb does not record when you watched anything. Relabelling `Date Rated`
        as a viewing date would invent one."""
        rated = only(ratings(rating_row(date_rated="2024-03-01")))
        assert rated.entry.date_added == "2024-03-01"
        assert rated.entry.values.get("date_finished") is None
        listed = only(listing(list_row(created="2024-05-06")))
        assert listed.entry.date_added == "2024-05-06"
        assert listed.entry.values.get("date_finished") is None

    def test_a_malformed_date_is_a_row_error_and_not_stored_verbatim(self) -> None:
        """A half-known date stored in a text column reads as a date thereafter."""
        record = only(ratings(rating_row(date_rated="2021-05-00")))
        assert record.entry.date_added is None
        assert [row["field"] for row in record.errors] == ["Date Rated"]

    def test_the_year_and_genres_come_across(self) -> None:
        record = only(ratings(rating_row(year="1994", genres="Drama, Crime")))
        assert record.item.year == 1994
        assert record.item.metadata["genres"] == ["Drama", "Crime"]

    def test_directors_become_creators_for_a_film(self) -> None:
        record = only(ratings(rating_row(directors="Denis Villeneuve, Roger Deakins")))
        assert record.item.metadata["creators"] == ["Denis Villeneuve", "Roger Deakins"]

    def test_a_series_with_no_directors_carries_no_creators_rather_than_a_blank_one(
        self,
    ) -> None:
        record = only(ratings(rating_row(kind="TV Series", directors="")))
        assert record.item.metadata.get("creators", []) == []

    def test_an_original_title_is_kept_only_when_it_differs(self) -> None:
        same = only(ratings(rating_row(title="Solaris", original="Solaris")))
        assert "original_title" not in same.item.metadata
        differs = only(ratings(rating_row(title="Solaris", original="Солярис")))
        assert differs.item.metadata["original_title"] == "Солярис"

    def test_the_runtime_column_means_two_different_things(self) -> None:
        """`Runtime (mins)` is the film's length and the *episode's* length. The
        routing table is where that divergence is written down."""
        film = only(ratings(rating_row(kind="Movie", runtime="142")))
        assert film.item.metadata["runtime"] == 142
        assert "episode_minutes" not in film.item.metadata
        show = only(ratings(rating_row(kind="TV Series", runtime="49")))
        assert show.item.metadata["episode_minutes"] == 49
        assert "runtime" not in show.item.metadata

    def test_the_row_keeps_the_export_s_own_word_for_what_it_is(self) -> None:
        """`source_fields` is opaque to the shared layer and is what the preview can
        show. It carries IMDb's word, not one of ours reverse-mapped back."""
        record = only(ratings(rating_row(kind="TV Mini Series")))
        assert record.source_fields == {"title_type": "TV Mini Series"}

    def test_the_crowds_opinion_and_the_url_are_not_imported(self) -> None:
        record = only(ratings(rating_row()))
        stored = {**record.item.metadata, **record.entry.values}
        assert "imdb_rating" not in stored
        assert "num_votes" not in stored
        assert not any("imdb.com" in str(value) for value in stored.values())

    def test_a_list_row_carries_no_shelves_and_no_description(self) -> None:
        """Explicit non-scope: no list name, no description, no ordering as a shelf."""
        record = only(listing(list_row(description="Films to watch with my brother")))
        assert record.shelves == ()
        assert record.entry.notes is None


class TestRowErrorsNotFileErrors:
    """One bad row costs a row. The traps DEC-093 recorded, on this source."""

    def test_a_blank_title_is_a_row_error_and_the_batch_survives(self) -> None:
        snapshot = read(
            ratings(
                rating_row(const="tt0000002", title=""),
                rating_row(const="tt0111161"),
            )
        )
        assert len(snapshot.records) == 2
        assert [row["field"] for row in snapshot.records[0].errors] == ["Title"]
        assert snapshot.records[1].errors == ()

    def test_a_zero_runtime_is_a_row_error_rather_than_a_refused_batch(self) -> None:
        """`runtime` and `episode_minutes` both declare a minimum of 1. A 0 reaching
        the shared validator aborts the whole import under a code no screen has copy
        for — the exact shape of DEC-093's `series_episodes` of 0."""
        for kind in ("Movie", "TV Series"):
            record = only(ratings(rating_row(kind=kind, runtime="0")))
            assert "runtime" not in record.item.metadata
            assert "episode_minutes" not in record.item.metadata
            assert [row["field"] for row in record.errors] == ["Runtime (mins)"]

    def test_a_repeated_const_keeps_both_rows_and_says_so(self) -> None:
        """Silently collapsing them discards the second row's score under a success."""
        snapshot = read(
            ratings(
                rating_row(const="tt0111161", score="9"),
                rating_row(const="tt0111161", score="4"),
            )
        )
        assert len(snapshot.records) == 2
        assert [row["code"] for row in snapshot.records[1].errors] == ["duplicate_identifier"]

    def test_an_absurd_year_is_a_row_error_rather_than_a_stored_number(self) -> None:
        record = only(ratings(rating_row(year="19x4")))
        assert record.item.year is None
        assert [row["field"] for row in record.errors] == ["Year"]

    def test_a_row_with_too_few_columns_is_a_visible_error_not_a_silent_skip(self) -> None:
        """A damaged row and a kind no library holds are different answers. Counting
        the first as the second hides file damage inside a number."""
        snapshot = read(ratings("tt0000003,9", rating_row(const="tt0111161")))
        assert len(snapshot.records) == 2
        assert [row["code"] for row in snapshot.records[0].errors] == ["malformed_row"]
        assert snapshot.records[1].errors == ()
        assert snapshot.skipped == ()

    def test_a_title_longer_than_the_column_is_truncated_not_refused(self) -> None:
        record = only(ratings(rating_row(title="A" * 800)))
        assert 0 < len(record.item.title) <= 500

    def test_row_numbers_are_the_readers_own_and_stay_stable(self) -> None:
        snapshot = read(
            ratings(
                rating_row(const="tt0000004", kind="TV Episode"),
                rating_row(const="tt0111161"),
                rating_row(const="tt0903747", kind="TV Series"),
            )
        )
        # The skipped row is not a record, and does not leave a hole in the numbering.
        assert [row.row_number for row in snapshot.records] == [1, 2]


class TestBounds:
    def test_a_file_beyond_the_readers_ceiling_is_refused_with_something_to_do(self) -> None:
        """`ImportInputSpec.max_bytes` is not enforced for `kind="upload"`, so the
        reader bounds its own stream (DEC-093)."""
        from book_tracker.domains.movie.imdb import MAX_BYTES

        with pytest.raises(ImdbError) as refused:
            read(ratings(rating_row()) + b"x" * MAX_BYTES)
        assert refused.value.code == "export_too_large"
        assert refused.value.action

    def test_a_file_with_more_rows_than_the_reader_will_hold_is_refused(self) -> None:
        from book_tracker.domains.movie.imdb import MAX_ROWS

        rows = [rating_row(const=f"tt{n:07d}") for n in range(MAX_ROWS + 1)]
        with pytest.raises(ImdbError) as refused:
            read(ratings(*rows))
        assert refused.value.code == "export_too_large"

    def test_undecodable_bytes_are_a_file_level_refusal(self) -> None:
        with pytest.raises(ImportReadError):
            read(RATINGS_HEADER.encode() + b"\n\xff\xfe\x00 not utf-8\n")


class TestFingerprint:
    def test_the_same_bytes_fingerprint_the_same_and_different_bytes_do_not(self) -> None:
        one = read(ratings(rating_row())).fingerprint
        again = read(ratings(rating_row())).fingerprint
        other = read(ratings(rating_row(score="8"))).fingerprint
        assert one == again != other


class TestDeclaration:
    def test_it_targets_both_libraries_and_trusts_one_identity(self) -> None:
        assert IMPORTER.item_types == ("movie", "series")
        assert IMPORTER.identity_kinds == frozenset({"imdb"})

    def test_its_guidance_names_where_each_export_actually_lives(self) -> None:
        guide = " ".join(IMPORTER.input.guide)
        assert "Ratings" in guide and "Watchlist" in guide
        assert IMPORTER.input.help_url.startswith("https://")
        assert IMPORTER.input.empty_state

    def test_it_says_that_a_re_import_adds_and_does_not_update(self) -> None:
        """The limit is read on the import screen rather than discovered after."""
        guide = " ".join(IMPORTER.input.guide).lower()
        assert "snapshot" in guide or "does not" in guide

    def test_the_suggested_statuses_are_ones_the_target_domains_declare(self) -> None:
        from book_tracker.domain.registry import DOMAINS

        for item_type, words in (
            ("movie", ("watched", "watchlist")),
            ("series", ("completed", "plan_to_watch")),
        ):
            declared = {status.value for status in DOMAINS[item_type].statuses}
            assert set(words) <= declared


def test_parse_returns_rows_in_file_order() -> None:
    rows = parse_imdb(
        ratings(
            rating_row(const="tt0000005", title="One"),
            rating_row(const="tt0000006", title="Two"),
            rating_row(const="tt0000007", title="Three"),
        )
    )
    assert [row.title for row in rows.rows] == ["One", "Two", "Three"]
