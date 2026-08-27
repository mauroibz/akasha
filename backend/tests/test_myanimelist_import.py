"""The MyAnimeList connector's reader, against a fixture drawn from a real export.

The fixture is held as plain XML rather than gzipped so it is readable in a diff; these
tests gzip it in memory, which exercises the sniffing path and proves both branches from
one file. Its rows are the owner's own, anonymised: `myinfo` carries no `user_id` or
`user_name` and the real export is gitignored.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from book_tracker.domain.importers import ImportReadContext, ImportReadError, ImportSource
from book_tracker.domains.album import DOMAIN as ALBUM
from book_tracker.domains.anime import DOMAIN as ANIME
from book_tracker.domains.anime.myanimelist import (
    IMPORTER,
    MAX_DECOMPRESSED_BYTES,
    SUGGESTED_STATUS,
    parse_myanimelist,
)

FIXTURES = Path(__file__).parent / "fixtures" / "imports"


def sample() -> bytes:
    return (FIXTURES / "myanimelist_sample.xml").read_bytes()


def rows() -> dict[str, dict]:
    return {row["title"]: row for row in parse_myanimelist(sample())}


def read(data: bytes, filename: str = "animelist.xml") -> object:
    return IMPORTER.read(
        ImportSource(data=data, filename=filename), ImportReadContext(path_root=Path("/nowhere"))
    )


class TestDecoding:
    def test_it_reads_plain_xml_and_gzip_alike(self) -> None:
        """MyAnimeList serves the export gzipped and a reader may or may not have
        unpacked it, so the format is sniffed by magic bytes rather than by filename."""
        plain = parse_myanimelist(sample())
        # The filename deliberately lies: it says `.xml` while the bytes are gzip.
        zipped = parse_myanimelist(gzip.compress(sample()))
        assert len(plain) == len(zipped) == 8
        assert [row["mal_id"] for row in plain] == [row["mal_id"] for row in zipped]

    def test_a_decompression_bomb_is_refused_rather_than_expanded(self) -> None:
        """The route admits 5 MiB of *compressed* bytes and the owner's own file expands
        25x, so a crafted one reaches gigabytes. Bounded incrementally, never through
        `gzip.decompress`."""
        bomb = gzip.compress(b"<myanimelist>" + b" " * (MAX_DECOMPRESSED_BYTES + 1))
        assert len(bomb) < 200_000, "the point is that a tiny upload expands past the cap"
        with pytest.raises(ImportReadError) as refused:
            parse_myanimelist(bomb)
        assert refused.value.code == "export_too_large"

    def test_a_truncated_gzip_is_an_answer_not_a_crash(self) -> None:
        with pytest.raises(ImportReadError) as refused:
            parse_myanimelist(gzip.compress(sample())[:64])
        assert refused.value.code == "invalid_xml"

    def test_something_that_is_neither_gzip_nor_xml_is_refused(self) -> None:
        with pytest.raises(ImportReadError) as refused:
            parse_myanimelist(b"Title,Author\nRayuela,Cortazar\n")
        assert refused.value.code == "invalid_xml"

    def test_a_doctype_is_refused_before_the_parser_sees_it(self) -> None:
        """Measured on this build's Python 3.12: ElementTree **expands internal
        entities**, so billion laughs is live — and it expands in-parser, where the size
        cap above cannot reach it. A real export carries no DOCTYPE at all.
        """
        bomb = (
            b'<?xml version="1.0"?>\n'
            b'<!DOCTYPE lolz [ <!ENTITY lol "lol">'
            b' <!ENTITY lol2 "&lol;&lol;&lol;&lol;"> ]>\n'
            b"<myanimelist><anime><series_title>&lol2;</series_title></anime></myanimelist>"
        )
        with pytest.raises(ImportReadError) as refused:
            parse_myanimelist(bomb)
        assert refused.value.code == "invalid_xml"

    def test_a_file_whose_root_is_not_myanimelist_is_refused(self) -> None:
        with pytest.raises(ImportReadError) as refused:
            parse_myanimelist(b"<library><anime/></library>")
        assert refused.value.code == "invalid_xml"

    def test_a_manga_export_is_refused_with_something_to_do_about_it(self) -> None:
        """DEC-080: `action` is the only part of a failure a person can act on."""
        with pytest.raises(ImportReadError) as refused:
            parse_myanimelist((FIXTURES / "myanimelist_manga.xml").read_bytes())
        assert refused.value.code == "not_an_anime_export"
        assert refused.value.user_message
        assert refused.value.action


class TestTheMapping:
    def test_the_identity_is_the_myanimelist_id(self) -> None:
        """The same `mal` key the domain merges on and enrichment looks up by."""
        assert rows()["Black Clover"]["mal_id"] == "34572"
        assert IMPORTER.identity_kinds == frozenset({"mal"})

    def test_a_partial_watch_lands_as_progress(self) -> None:
        """What Sprint 040 exists for. Without it this row says only 'dropped'."""
        black_clover = rows()["Black Clover"]
        assert black_clover["progress"] == 20
        assert black_clover["episodes"] == 170

    def test_zero_watched_is_recorded_rather_than_absent(self) -> None:
        """A real row: 0 of 1 episodes, `Plan to Watch`. `0` is not `None`."""
        assert rows()["Gake no Ue no Ponyo"]["progress"] == 0

    def test_an_unrated_row_has_no_score_rather_than_a_score_of_zero(self) -> None:
        assert rows()["Psycho-Pass"]["score"] is None

    def test_a_score_transfers_unchanged_and_is_not_provisional(self) -> None:
        """MyAnimeList's scale is already 1-10, unlike Goodreads' five stars, so there
        is nothing to double and nothing to mark."""
        assert rows()["Akame ga Kill!"]["score"] == 8
        assert rows()["Akame ga Kill!"]["score_provisional"] is False

    def test_an_all_zero_date_is_absence_and_not_a_date(self) -> None:
        chainsaw = rows()["Chainsaw Man"]
        assert chainsaw["date_started"] is None
        assert chainsaw["date_finished"] == "2025-08-19"

    def test_tags_become_shelves_and_rewatches_become_a_count(self) -> None:
        chainsaw = rows()["Chainsaw Man"]
        assert chainsaw["shelves"] == ["favourites", "rewatch-me"]
        assert chainsaw["reread_count"] == 2

    def test_a_comment_becomes_the_note(self) -> None:
        assert rows()["Darwin's Game"]["notes"] == "Ended too soon."

    def test_an_apostrophe_in_a_title_survives_cdata(self) -> None:
        assert "Darwin's Game" in rows()

    def test_the_release_shape_and_episode_count_come_across(self) -> None:
        assert rows()["Black Clover"]["kind"] == "TV"
        assert rows()["Gake no Ue no Ponyo"]["kind"] == "Movie"


class TestTheStatusMap:
    def test_it_maps_every_myanimelist_state(self) -> None:
        assert SUGGESTED_STATUS == {
            "Watching": "watching",
            "Completed": "completed",
            "On-Hold": "on_hold",
            "Dropped": "dropped",
            "Plan to Watch": "plan_to_watch",
        }

    def test_every_suggestion_is_a_status_this_domain_declares(self) -> None:
        """Asserted over `DOMAIN.status(...)` the way Goodreads' map is, so a status
        renamed out from under it fails a test rather than silently suggesting nothing.
        """
        for value in SUGGESTED_STATUS.values():
            assert ANIME.status(value) is not None
            # And nothing leaks across domains.
            assert ALBUM.status(value) is None

    def test_the_fixture_exercises_all_five(self) -> None:
        suggested = {row["suggested_status"] for row in parse_myanimelist(sample())}
        assert suggested == set(SUGGESTED_STATUS.values())


class TestBadRows:
    def test_a_row_with_no_id_is_an_error_on_that_row_and_not_a_dead_file(self) -> None:
        """One malformed row must not cost the other eighty."""
        broken = sample().replace(b"<series_animedb_id>34572</series_animedb_id>", b"")
        parsed = parse_myanimelist(broken)
        assert len(parsed) == 8
        bad = next(row for row in parsed if row["title"] == "Black Clover")
        assert bad["mal_id"] is None
        assert [error["field"] for error in bad["errors"]] == ["series_animedb_id"]
        # Its neighbours are untouched.
        assert all(not row["errors"] for row in parsed if row["title"] != "Black Clover")

    def test_a_row_with_an_unreadable_number_reports_it_and_keeps_going(self) -> None:
        broken = sample().replace(
            b"<my_watched_episodes>20</my_watched_episodes>",
            b"<my_watched_episodes>twenty</my_watched_episodes>",
        )
        bad = next(row for row in parse_myanimelist(broken) if row["title"] == "Black Clover")
        assert bad["progress"] is None
        assert bad["errors"][0]["code"] == "invalid_integer"

    def test_a_row_with_a_status_myanimelist_does_not_have_suggests_nothing(self) -> None:
        broken = sample().replace(
            b"<my_status>Dropped</my_status>", b"<my_status>Bored</my_status>"
        )
        bad = next(row for row in parse_myanimelist(broken) if row["title"] == "Black Clover")
        assert bad["suggested_status"] is None


class TestTheSnapshot:
    def test_read_produces_a_record_per_row_in_the_neutral_shape(self) -> None:
        snapshot = read(sample())
        assert len(snapshot.records) == 8  # type: ignore[attr-defined]
        record = next(
            row
            for row in snapshot.records  # type: ignore[attr-defined]
            if row.item.title == "Black Clover"
        )
        assert record.item.identifiers == {"mal": "34572"}
        assert record.item.metadata["kind"] == "TV"
        assert record.item.metadata["episodes"] == 170
        assert record.entry.values["progress"] == 20
        assert record.entry.suggested_status == "dropped"
        assert record.source_fields == {"series_animedb_id": "34572"}

    def test_the_metadata_it_emits_is_only_what_the_domain_declares(self) -> None:
        """The shared service validates this before `match`, so a stray key is a 422."""
        declared = {field.name for field in ANIME.fields}
        for record in read(sample()).records:  # type: ignore[attr-defined]
            assert set(record.item.metadata) <= declared

    def test_the_same_bytes_fingerprint_the_same_whichever_way_they_arrive(self) -> None:
        """Replay is keyed on this, so a re-upload of one file must not import twice."""
        assert read(sample()).fingerprint == read(sample()).fingerprint  # type: ignore[attr-defined]
        assert (
            read(gzip.compress(sample())).fingerprint  # type: ignore[attr-defined]
            != read(sample()).fingerprint  # type: ignore[attr-defined]
        )

    def test_it_carries_no_source_with_a_reader_name_in_it(self) -> None:
        """The export names its owner; the descriptor must not keep that."""
        snapshot = read(sample(), filename="animelist_123_-_456.xml")
        assert snapshot.source_descriptor == {  # type: ignore[attr-defined]
            "filename": "animelist_123_-_456.xml"
        }
