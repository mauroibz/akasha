"""The Letterboxd connector, against synthetic archives built here.

Nothing in this file comes from the owner's export. The titles, URIs, ratings and
reviews below are invented; the *shapes* are the ones measured on 2026-08-27 — the five
live tables, their exact spaced headers, ISO dates and half-star ratings.

The mapping matrix is the point. An export is five tables about the same films, and
almost every interesting behaviour is what happens when two of them disagree.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import pytest

from book_tracker.domain.importers import ImportReadContext, ImportReadError, ImportSource
from book_tracker.domains.movie.letterboxd import IMPORTER, LetterboxdError, parse_letterboxd

HEADERS = {
    "watched.csv": "Date,Name,Year,Letterboxd URI",
    "ratings.csv": "Date,Name,Year,Letterboxd URI,Rating",
    "diary.csv": "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date",
    "reviews.csv": "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Review,Tags,Watched Date",
    "watchlist.csv": "Date,Name,Year,Letterboxd URI",
}

SUSPIRIA = "https://boxd.it/aaaa"
SOLARIS = "https://boxd.it/bbbb"


def archive(tables: dict[str, list[str]], extra: dict[str, str] | None = None) -> bytes:
    """A Letterboxd-shaped ZIP. Every named table gets its real header."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        for name, rows in tables.items():
            zipped.writestr(name, "\n".join([HEADERS[name], *rows]) + "\n")
        for name, body in (extra or {}).items():
            zipped.writestr(name, body)
    return buffer.getvalue()


def read(data: bytes) -> Any:
    return IMPORTER.read(
        ImportSource(data=data, filename="letterboxd.zip"), ImportReadContext(Path("."))
    )


def only(data: bytes) -> Any:
    records = read(data).records
    assert len(records) == 1, [row.item.title for row in records]
    return records[0]


class TestOneFilmFromManyTables:
    def test_a_film_in_four_tables_is_one_record(self) -> None:
        """The whole reason this reader aggregates: `watched`, `ratings`, `diary` and
        `reviews` all name the same film, and four rows is not four films."""
        record = only(
            archive(
                {
                    "watched.csv": [f"2026-01-01,Suspiria,1977,{SUSPIRIA}"],
                    "ratings.csv": [f"2026-01-02,Suspiria,1977,{SUSPIRIA},4.5"],
                    "diary.csv": [f"2026-01-03,Suspiria,1977,{SUSPIRIA},4,No,,2026-01-03"],
                    "reviews.csv": [
                        f"2026-01-04,Suspiria,1977,{SUSPIRIA},4,No,Extraordinary.,,2026-01-04"
                    ],
                }
            )
        )
        assert record.item.title == "Suspiria"
        assert record.item.year == 1977
        assert record.item.identifiers == {"letterboxd": SUSPIRIA}

    def test_repeated_diary_rows_are_viewings_and_not_duplicates(self) -> None:
        record = only(
            archive(
                {
                    "diary.csv": [
                        f"2026-01-01,Solaris,1972,{SOLARIS},4,No,,2026-01-01",
                        f"2026-02-01,Solaris,1972,{SOLARIS},5,Yes,,2026-02-01",
                        f"2026-03-01,Solaris,1972,{SOLARIS},5,Yes,,2026-03-01",
                    ]
                }
            )
        )
        assert record.entry.values["reread_count"] == 2
        assert record.entry.values["date_finished"] == "2026-03-01"


class TestStatus:
    def test_any_watched_evidence_suggests_watched(self) -> None:
        for table, row in (
            ("watched.csv", f"2026-01-01,Suspiria,1977,{SUSPIRIA}"),
            ("ratings.csv", f"2026-01-01,Suspiria,1977,{SUSPIRIA},4"),
            ("diary.csv", f"2026-01-01,Suspiria,1977,{SUSPIRIA},4,No,,2026-01-01"),
        ):
            assert only(archive({table: [row]})).entry.suggested_status == "watched"

    def test_a_film_only_on_the_watchlist_suggests_watchlist(self) -> None:
        record = only(archive({"watchlist.csv": [f"2026-01-01,Solaris,1972,{SOLARIS}"]}))
        assert record.entry.suggested_status == "watchlist"

    def test_watched_wins_over_a_stale_watchlist_row(self) -> None:
        """A film can sit in both tables; having seen it is the newer fact."""
        record = only(
            archive(
                {
                    "watchlist.csv": [f"2026-01-01,Suspiria,1977,{SUSPIRIA}"],
                    "watched.csv": [f"2026-02-01,Suspiria,1977,{SUSPIRIA}"],
                }
            )
        )
        assert record.entry.suggested_status == "watched"


class TestScore:
    @pytest.mark.parametrize(
        ("stars", "score"),
        [("0.5", 1), ("1", 2), ("2.5", 5), ("3.5", 7), ("4.5", 9), ("5", 10)],
    )
    def test_half_stars_double_exactly(self, stars: str, score: int) -> None:
        record = only(archive({"ratings.csv": [f"2026-01-01,S,1977,{SUSPIRIA},{stars}"]}))
        assert record.entry.score == score

    def test_a_doubled_letterboxd_rating_is_not_provisional(self) -> None:
        """Unlike a Goodreads star, nothing is lost in the doubling: 3.5 *was* a 7."""
        record = only(archive({"ratings.csv": [f"2026-01-01,S,1977,{SUSPIRIA},3.5"]}))
        assert record.entry.score_provisional is False

    def test_the_current_rating_wins_over_a_diary_rating(self) -> None:
        """`ratings.csv` is how the owner feels now; a diary rating is that night."""
        record = only(
            archive(
                {
                    "ratings.csv": [f"2026-03-01,S,1977,{SUSPIRIA},5"],
                    "diary.csv": [f"2026-01-01,S,1977,{SUSPIRIA},3,No,,2026-01-01"],
                }
            )
        )
        assert record.entry.score == 10

    def test_the_latest_event_rating_is_used_when_there_is_no_current_one(self) -> None:
        record = only(
            archive(
                {
                    "diary.csv": [
                        f"2026-01-01,S,1977,{SUSPIRIA},3,No,,2026-01-01",
                        f"2026-06-01,S,1977,{SUSPIRIA},4.5,Yes,,2026-06-01",
                    ]
                }
            )
        )
        assert record.entry.score == 9

    def test_blank_is_unrated_and_not_an_error(self) -> None:
        record = only(archive({"ratings.csv": [f"2026-01-01,S,1977,{SUSPIRIA},"]}))
        assert record.entry.score is None
        assert record.errors == ()

    @pytest.mark.parametrize("value", ["0", "6", "-1", "five"])
    def test_a_rating_outside_the_scale_is_a_visible_row_error(self, value: str) -> None:
        """Letterboxd has no zero-star rating, so a `0` is a file something else wrote —
        and passing it through would violate `ck_entries_score` mid-commit."""
        record = only(archive({"ratings.csv": [f"2026-01-01,S,1977,{SUSPIRIA},{value}"]}))
        assert record.entry.score is None
        assert [row["field"] for row in record.errors] == ["Rating"]


class TestDates:
    def test_the_earliest_source_date_is_when_it_was_added(self) -> None:
        record = only(
            archive(
                {
                    "watched.csv": [f"2026-05-01,S,1977,{SUSPIRIA}"],
                    "ratings.csv": [f"2026-01-01,S,1977,{SUSPIRIA},4"],
                }
            )
        )
        assert record.entry.date_added == "2026-01-01"

    def test_only_a_watched_date_becomes_the_watched_date(self) -> None:
        """`watched.csv.Date` is when the row was created, not when the film was seen.
        Relabelling it would invent a viewing that never happened."""
        record = only(archive({"watched.csv": [f"2026-05-01,S,1977,{SUSPIRIA}"]}))
        assert record.entry.values["date_finished"] is None

    def test_the_latest_watched_date_wins(self) -> None:
        record = only(
            archive(
                {
                    "diary.csv": [
                        f"2026-01-01,S,1977,{SUSPIRIA},4,No,,2020-01-01",
                        f"2026-01-02,S,1977,{SUSPIRIA},4,Yes,,2024-07-07",
                    ]
                }
            )
        )
        assert record.entry.values["date_finished"] == "2024-07-07"

    def test_an_impossible_date_is_a_row_error_and_not_a_date(self) -> None:
        record = only(archive({"watched.csv": [f"2026-02-31,S,1977,{SUSPIRIA}"]}))
        assert record.entry.date_added is None
        assert [row["code"] for row in record.errors] == ["invalid_date"]


class TestReviewsAndTags:
    def test_the_latest_review_seeds_plain_text_notes(self) -> None:
        record = only(
            archive(
                {
                    "reviews.csv": [
                        f"2026-01-01,S,1977,{SUSPIRIA},4,No,Early thoughts.,,2026-01-01",
                        f"2026-06-01,S,1977,{SUSPIRIA},5,Yes,Later thoughts.,,2026-06-01",
                    ]
                }
            )
        )
        assert record.entry.notes == "Later thoughts."

    def test_review_markup_is_read_as_text_and_never_stored_as_markup(self) -> None:
        """Letterboxd's own import docs say review text may be HTML, and no renderer
        here interprets markup — a tag left in would be shown to the reader verbatim."""
        record = only(
            archive(
                {
                    "reviews.csv": [
                        f"2026-01-01,S,1977,{SUSPIRIA},4,No,"
                        '"<p>Bold <b>colour</b> &amp; sound</p>",,2026-01-01'
                    ]
                }
            )
        )
        assert record.entry.notes == "Bold colour & sound"

    def test_tags_become_shelves_and_empty_ones_are_skipped(self) -> None:
        record = only(
            archive(
                {
                    "diary.csv": [
                        f'2026-01-01,S,1977,{SUSPIRIA},4,No,"horror, rewatch, ,!!!",2026-01-01'
                    ]
                }
            )
        )
        assert record.shelves == ("horror", "rewatch")

    def test_tags_from_several_events_are_unioned(self) -> None:
        record = only(
            archive(
                {
                    "diary.csv": [f'2026-01-01,S,1977,{SUSPIRIA},4,No,"horror",2026-01-01'],
                    "reviews.csv": [
                        f'2026-02-01,S,1977,{SUSPIRIA},4,No,Good.,"horror, giallo",2026-02-01'
                    ],
                }
            )
        )
        assert record.shelves == ("horror", "giallo")


class TestRowErrors:
    def test_two_tables_disagreeing_about_a_film_is_visible(self) -> None:
        record = only(
            archive(
                {
                    "watched.csv": [f"2026-01-01,Suspiria,1977,{SUSPIRIA}"],
                    "ratings.csv": [f"2026-01-02,Suspiria,2018,{SUSPIRIA},4"],
                }
            )
        )
        assert [row["code"] for row in record.errors] == ["conflicting_year"]
        assert record.item.year == 1977

    def test_an_unusable_uri_does_not_take_the_valid_rows_with_it(self) -> None:
        records = read(
            archive(
                {
                    "watched.csv": [
                        "2026-01-01,Broken,1977,http://boxd.it/aaaa",
                        f"2026-01-01,Solaris,1972,{SOLARIS}",
                    ]
                }
            )
        ).records
        assert len(records) == 2
        broken = next(row for row in records if not row.item.identifiers)
        good = next(row for row in records if row.item.identifiers)
        assert [row["code"] for row in broken.errors] == ["unusable_uri"]
        assert good.item.title == "Solaris"
        assert good.errors == ()

    @pytest.mark.parametrize(
        "uri",
        [
            "http://boxd.it/aaaa",
            "https://evil.test/aaaa",
            "https://boxd.it.evil.test/aaaa",
            "ftp://boxd.it/aaaa",
            "",
        ],
    )
    def test_only_a_real_letterboxd_address_becomes_an_identity(self, uri: str) -> None:
        """This value becomes an exact identifier a later lookup will follow, so an
        identity nobody can check is worse than no identity at all."""
        record = only(archive({"watched.csv": [f"2026-01-01,S,1977,{uri}"]}))
        assert record.item.identifiers == {}

    def test_a_full_film_url_is_also_a_valid_identity(self) -> None:
        record = only(
            archive({"watched.csv": ["2026-01-01,S,1977,https://letterboxd.com/film/suspiria/"]})
        )
        assert record.item.identifiers == {"letterboxd": "https://letterboxd.com/film/suspiria/"}


class TestArchiveSafety:
    def test_a_file_that_is_not_a_zip_is_refused_with_a_way_out(self) -> None:
        with pytest.raises(LetterboxdError) as error:
            read(b"not a zip at all")
        assert error.value.code == "invalid_archive"
        assert error.value.action

    def test_an_encrypted_member_is_refused(self) -> None:
        data = bytearray(archive({"watched.csv": [f"2026-01-01,S,1977,{SUSPIRIA}"]}))
        # The encryption bit, set in both the local header and the central directory.
        # `ZipFile.infolist()` reads the central directory, so patching only the local
        # header would leave the flag invisible to the check under test.
        data[data.find(b"PK\x03\x04") + 6] |= 0x1
        data[data.find(b"PK\x01\x02") + 8] |= 0x1
        with pytest.raises(LetterboxdError) as error:
            read(bytes(data))
        assert error.value.code == "unsafe_archive"

    @pytest.mark.parametrize(
        "name", ["../escape.csv", "/absolute.csv", "nested/../../escape.csv", ".hidden/x.csv"]
    )
    def test_a_member_that_tries_to_escape_is_refused(self, name: str) -> None:
        with pytest.raises(LetterboxdError) as error:
            read(archive({"watched.csv": [f"2026-01-01,S,1977,{SUSPIRIA}"]}, {name: "x"}))
        assert error.value.code == "unsafe_archive"

    def test_an_archive_naming_one_member_twice_is_refused(self) -> None:
        """Whichever copy is read, the other was ignored, and nothing here can say which
        one the owner meant."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("watched.csv", HEADERS["watched.csv"] + "\n")
            zipped.writestr("watched.csv", HEADERS["watched.csv"] + "\n")
        with pytest.raises(LetterboxdError) as error:
            read(buffer.getvalue())
        assert error.value.code == "unsafe_archive"

    def test_an_archive_that_claims_to_expand_enormously_is_refused(self) -> None:
        """Compressed size is not a bound: deflate reaches about 1,000:1."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr("watched.csv", HEADERS["watched.csv"] + "\n")
            zipped.writestr("bomb.txt", b"\0" * (17 * 1024 * 1024))
        with pytest.raises(LetterboxdError) as error:
            read(buffer.getvalue())
        assert error.value.code == "export_too_large"

    def test_a_table_missing_its_columns_is_refused_with_a_way_out(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("watched.csv", "Date,Name\n2026-01-01,S\n")
        with pytest.raises(LetterboxdError) as error:
            read(buffer.getvalue())
        assert error.value.code == "missing_columns"
        assert error.value.action

    def test_an_archive_with_no_letterboxd_tables_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("holiday.jpg", b"\xff\xd8\xff")
        with pytest.raises(LetterboxdError) as error:
            read(buffer.getvalue())
        assert error.value.code == "invalid_archive"

    def test_a_member_that_is_not_utf8_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("watched.csv", HEADERS["watched.csv"].encode() + b"\n\xff\xfe\x00\n")
        with pytest.raises(LetterboxdError) as error:
            read(buffer.getvalue())
        assert error.value.code == "invalid_archive"

    def test_every_declared_error_code_is_one_this_reader_can_raise(self) -> None:
        assert set(LetterboxdError.ACTIONS) == set(IMPORTER.error_codes)


class TestWhatIsDeliberatelyIgnored:
    def test_deleted_orphaned_likes_comments_and_the_profile_are_not_read(self) -> None:
        """Silently restoring something the owner deleted is not import fidelity, and
        the profile names them — none of which is Akasha's to keep."""
        data = archive(
            {"watched.csv": [f"2026-01-01,Solaris,1972,{SOLARIS}"]},
            {
                "profile.csv": (
                    "Date Joined,Username,Given Name,Email Address\n2020-01-01,x,y,z@w\n"
                ),
                "deleted/diary.csv": HEADERS["diary.csv"]
                + f"\n2026-01-01,Gone,1999,{SUSPIRIA},5,No,,2026-01-01\n",
                "orphaned/reviews.csv": HEADERS["reviews.csv"]
                + f"\n2026-01-01,Gone,1999,{SUSPIRIA},5,No,Deleted.,,2026-01-01\n",
                "likes/films.csv": (
                    f"Date,Name,Year,Letterboxd URI\n2026-01-01,Liked,1999,{SUSPIRIA}\n"
                ),
                "comments.csv": "Date,Content,Comment\n",
            },
        )
        records = read(data).records
        assert [row.item.title for row in records] == ["Solaris"]
        assert records[0].shelves == ()

    def test_nothing_from_the_profile_reaches_the_snapshot(self) -> None:
        snapshot = read(archive({"watched.csv": [f"2026-01-01,S,1977,{SUSPIRIA}"]}))
        assert snapshot.source_descriptor == {"filename": "letterboxd.zip"}


class TestDeclaration:
    def test_it_targets_the_movie_domain_and_trusts_one_identity(self) -> None:
        assert IMPORTER.item_types == ("movie",)
        assert IMPORTER.identity_kinds == frozenset({"letterboxd"})

    def test_its_guidance_points_at_letterboxd_and_says_it_is_a_snapshot(self) -> None:
        assert IMPORTER.input.help_url == "https://letterboxd.com/settings/data/"
        assert any("snapshot" in step for step in IMPORTER.input.guide)

    def test_the_suggested_statuses_are_ones_this_domain_declares(self) -> None:
        """Stated against the domain rather than left to the accident that movies are
        the only domain with these words."""
        from book_tracker.domains.movie import DOMAIN

        for status in ("watched", "watchlist"):
            assert DOMAIN.status(status) is not None

    def test_a_read_error_is_always_one_a_reader_can_act_on(self) -> None:
        for code in IMPORTER.error_codes:
            error = LetterboxdError(code, "x")
            assert isinstance(error, ImportReadError)
            assert error.user_message and error.action


def test_the_owner_sample_shape_reads_as_two_watched_films() -> None:
    """The measured shape of the owner's real archive, rebuilt from invented values:
    two watched films that are the same two rated films, every other table empty."""
    records = read(
        archive(
            {
                "watched.csv": [
                    f"2026-08-01,First,2001,{SUSPIRIA}",
                    f"2026-08-02,Second,1999,{SOLARIS}",
                ],
                "ratings.csv": [
                    f"2026-08-01,First,2001,{SUSPIRIA},4",
                    f"2026-08-02,Second,1999,{SOLARIS},3.5",
                ],
                "diary.csv": [],
                "reviews.csv": [],
                "watchlist.csv": [],
            }
        )
    ).records
    assert len(records) == 2
    assert [row.entry.suggested_status for row in records] == ["watched", "watched"]
    assert [row.entry.score for row in records] == [8, 7]
    assert all(row.errors == () for row in records)


def test_parse_returns_films_in_a_stable_order() -> None:
    films = parse_letterboxd(
        archive(
            {
                "watched.csv": [
                    f"2026-01-01,A,2001,{SUSPIRIA}",
                    f"2026-01-02,B,1999,{SOLARIS}",
                ]
            }
        )
    )
    assert [film.row_number for film in films] == [1, 2]


# --------------------------------------------------------------------------------------
# The one shared behaviour change: title + exact year, scoped, as an offer only
# --------------------------------------------------------------------------------------


def library(tmp_path: Path) -> Any:
    from sqlalchemy import text

    from book_tracker.config import Settings
    from book_tracker.database import create_engine
    from book_tracker.infrastructure.repositories import DomainRepository
    from book_tracker.migrations import upgrade

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    engine = create_engine(configured)

    def add(title: str, item_type: str, year: int | None, **columns: Any) -> int:
        import json

        # `creator_primary` is a generated column over `metadata.creators[0]`, so a
        # creator is written the way the application writes one.
        metadata = json.dumps({"creators": [columns["creator"]]} if columns.get("creator") else {})
        with engine.begin() as connection:
            item_id = connection.execute(
                text(
                    "INSERT INTO items(type,title,year,identifiers,metadata,"
                    "created_at,updated_at) VALUES(:type,:title,:year,'{}',:metadata,'n','n') "
                    "RETURNING id"
                ),
                {"type": item_type, "title": title, "year": year, "metadata": metadata},
            ).scalar_one()
            if "letterboxd" in columns:
                connection.execute(
                    text(
                        "INSERT INTO item_identifiers(item_id,kind,normalized_value,value,"
                        "created_at,updated_at) VALUES(:item,'letterboxd',:value,:value,'n','n')"
                    ),
                    {"item": item_id, "value": columns["letterboxd"]},
                )
        return item_id

    return DomainRepository(engine), add


def decide(matcher: Any, record: Any) -> Any:
    return IMPORTER.match(record, matcher)


def test_the_exact_letterboxd_identity_matches_without_a_near_guess(tmp_path: Path) -> None:
    matcher, add = library(tmp_path)
    existing = add("Suspiria", "movie", 1977, letterboxd=SUSPIRIA)
    record = only(archive({"watched.csv": [f"2026-01-01,Suspiria,1977,{SUSPIRIA}"]}))
    decision = decide(matcher, record)
    assert decision.kind.value == "exact"
    assert decision.item_id == existing


def test_title_and_year_are_offered_as_an_ambiguity_and_never_merged(tmp_path: Path) -> None:
    """The case this seam exists for: the film is already in the library from a Wikidata
    search, carrying the *slug*, while the export carries the short URI."""
    matcher, add = library(tmp_path)
    existing = add("Suspiria", "movie", 1977, letterboxd="suspiria")
    record = only(archive({"watched.csv": [f"2026-01-01,Suspiria,1977,{SUSPIRIA}"]}))
    decision = decide(matcher, record)
    assert decision.kind.value == "ambiguous"
    assert decision.candidates == (existing,)
    assert decision.item_id is None


def test_a_remake_is_not_offered_for_the_original(tmp_path: Path) -> None:
    """Two films called Suspiria, forty-one years apart. The year is exact, not near."""
    matcher, add = library(tmp_path)
    add("Suspiria", "movie", 2018, letterboxd="suspiria-2018")
    record = only(archive({"watched.csv": [f"2026-01-01,Suspiria,1977,{SUSPIRIA}"]}))
    assert decide(matcher, record).kind.value == "new"


def test_a_novel_is_never_offered_as_a_candidate_for_the_film_of_it(tmp_path: Path) -> None:
    """Title plus year is a far weaker signal than title plus author, and a book and its
    adaptation routinely share both. The offer is scoped to the importer's own domain."""
    matcher, add = library(tmp_path)
    add("Dune", "book", 2021, creator="Frank Herbert")
    record = only(archive({"watched.csv": [f"2026-01-01,Dune,2021,{SOLARIS}"]}))
    assert decide(matcher, record).kind.value == "new"


def test_a_film_with_no_year_offers_nothing_rather_than_every_same_titled_film(
    tmp_path: Path,
) -> None:
    matcher, add = library(tmp_path)
    add("Suspiria", "movie", 1977, letterboxd="suspiria")
    record = only(archive({"watched.csv": [f"2026-01-01,Suspiria,,{SUSPIRIA}"]}))
    assert decide(matcher, record).kind.value == "new"


def test_every_other_connector_matches_exactly_as_it_did(tmp_path: Path) -> None:
    """The matcher gained two optional arguments; a caller that passes neither must get
    the old query, or this sprint has changed three connectors it never touched."""
    matcher, add = library(tmp_path)
    book = add("Ficciones", "book", 1944, creator="Jorge Luis Borges")
    assert matcher.match(title="Ficciones", first_author="Jorge Luis Borges").candidates == (book,)
    assert matcher.match(title="Ficciones", first_author="Someone Else").kind.value == "new"
    # No author and no year is still not a near match, in either direction.
    assert matcher.match(title="Ficciones", first_author="").kind.value == "new"
