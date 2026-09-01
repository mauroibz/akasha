"""The Trakt connector, against synthetic archives built here.

Nothing in this file comes from the owner's archive. The shows, ids, ratings and
timestamps below are invented; the *shapes* are the ones measured on 2026-08-31
(`docs/series-domain-viability.md`): a ZIP of verbatim API responses, `ids.imdb`
on every movie, show and episode object, and `watched-history.json` as the only
member with episode detail.

Two members are never opened — `user-settings.json` and `user-profile.json`
carry the owner's email address — and the malformed-member test below is how
that is proved: if the import succeeds, nothing read them. DEC-093's lesson as a
test file: **a reader tested only against the archive in front of you is tested
against one archive.**
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from book_tracker.domain.importers import ImportReadContext, ImportReadError, ImportSource
from book_tracker.domains.movie.trakt import IMPORTER, TraktError

# ----------------------------------------------------------------------------------
# Synthetic archive builders. Every id, title and timestamp is invented.
# ----------------------------------------------------------------------------------


def ids(
    trakt: int = 1,
    slug: str = "invented",
    imdb: str = "tt0000001",
    tmdb: int = 1,
    tvdb: int | None = None,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "trakt": trakt,
        "slug": slug,
        "imdb": imdb,
        "tmdb": tmdb,
        # `plex` is deliberately absent: the reader must never read it. A missing
        # key is the stronger test — a reader that touched it would KeyError.
    }
    if tvdb is not None:
        block["tvdb"] = tvdb
    return block


def movie_obj(
    imdb: str = "tt0000001", title: str = "Invented Film", year: int = 2020
) -> dict[str, Any]:
    return {
        "title": title,
        "year": year,
        "ids": ids(trakt=10, slug="invented-film", imdb=imdb, tmdb=11),
    }


def show_obj(
    imdb: str = "tt0000010",
    title: str = "Invented Show",
    year: int = 2015,
    aired: int = 12,
) -> dict[str, Any]:
    return {
        "title": title,
        "year": year,
        "aired_episodes": aired,
        "ids": ids(trakt=20, slug="invented-show", imdb=imdb, tmdb=21, tvdb=22),
    }


def episode_obj(season: int, number: int, imdb: str = "tt0000099") -> dict[str, Any]:
    return {
        "season": season,
        "number": number,
        "title": f"S{season}E{number}",
        "ids": ids(trakt=30 + number, slug=f"invented-{season}-{number}", imdb=imdb, tmdb=31),
    }


def watched_movie(
    imdb: str = "tt0000001",
    last_watched_at: str = "2026-01-10T20:00:00.000Z",
    plays: int = 1,
) -> dict[str, Any]:
    return {
        "plays": plays,
        "last_watched_at": last_watched_at,
        "last_updated_at": "2026-01-10T20:00:01.000Z",
        "movie": movie_obj(imdb=imdb),
        "total_count": plays,
    }


def watched_show(
    imdb: str = "tt0000010",
    last_watched_at: str = "2026-02-01T21:00:00.000Z",
    plays: int = 12,
    aired: int = 12,
    reset_at: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "plays": plays,
        "last_watched_at": last_watched_at,
        "last_updated_at": "2026-02-01T21:00:01.000Z",
        "reset_at": reset_at,
        "show": show_obj(imdb=imdb, aired=aired),
    }
    return row


def rated_movie(
    rating: int = 8,
    rated_at: str = "2026-01-11T10:00:00.000Z",
    imdb: str = "tt0000001",
) -> dict[str, Any]:
    return {"rating": rating, "rated_at": rated_at, "type": "movie", "movie": movie_obj(imdb=imdb)}


def rated_show(
    rating: int = 9,
    rated_at: str = "2026-02-02T10:00:00.000Z",
    imdb: str = "tt0000010",
    aired: int = 12,
) -> dict[str, Any]:
    return {
        "rating": rating,
        "rated_at": rated_at,
        "type": "show",
        "show": show_obj(imdb=imdb, aired=aired),
    }


def episode_event(
    show_imdb: str,
    season: int,
    number: int,
    watched_at: str = "2026-01-15T20:00:00.000Z",
    action: str = "watch",
    aired: int = 12,
) -> dict[str, Any]:
    return {
        "id": 1000 + season * 100 + number,
        "watched_at": watched_at,
        "action": action,
        "type": "episode",
        "episode": episode_obj(season=season, number=number),
        "show": show_obj(imdb=show_imdb, aired=aired),
    }


def movie_event(
    imdb: str = "tt0000001", watched_at: str = "2026-01-10T20:00:00.000Z"
) -> dict[str, Any]:
    return {
        "id": 999,
        "watched_at": watched_at,
        "action": "watch",
        "type": "movie",
        "movie": movie_obj(imdb=imdb),
    }


def watchlist_row(kind: str, imdb: str, title: str, year: int, listed_at: str) -> dict[str, Any]:
    """The populated watchlist shape, declared from Trakt's published API and not
    measured — the owner's archive holds only `[]` (the sprint's own risk note)."""
    obj = (
        movie_obj(imdb=imdb, title=title, year=year)
        if kind == "movie"
        else show_obj(imdb=imdb, title=title, year=year)
    )
    return {"listed_at": listed_at, "type": kind, kind: obj}


def archive(
    members: dict[str, Any] | None = None,
    *,
    include_empties: bool = False,
) -> bytes:
    """A synthetic Trakt archive: the work members given, plus the private two and,
    optionally, the 26 empty members the owner's real shape carries (AC8)."""
    body: dict[str, Any] = dict(members or {})
    body.setdefault("user-settings.json", {"user": {"email": "nobody@example.invalid"}})
    body.setdefault("user-profile.json", {"username": "nobody"})
    if include_empties:
        for name in (
            "hidden-calendar.json",
            "hidden-progress-watched.json",
            "hidden-progress-watched-reset.json",
            "hidden-progress-collected.json",
            "hidden-recommendations.json",
            "network-followers-requests.json",
            "network-followers.json",
            "network-following.json",
            "network-friends.json",
            "likes-comments.json",
            "likes-lists.json",
            "comments-movies.json",
            "comments-shows.json",
            "comments-seasons.json",
            "comments-episodes.json",
            "comments-lists.json",
            "notes-movies.json",
            "notes-shows.json",
            "notes-seasons.json",
            "notes-episodes.json",
            "notes-people.json",
            "notes-activities.json",
            "notes-collection_items.json",
            "notes-ratings.json",
            "watched-playback.json",
        ):
            body.setdefault(name, [])
        body.setdefault("lists-watchlist.json", [])
        body.setdefault("lists-favorites.json", [])
        body.setdefault("lists-collaborations.json", [])
        body.setdefault("lists-lists.json", [])
        body.setdefault("collection-movies.json", [])
        body.setdefault("collection-shows.json", [])
        body.setdefault("collection-episodes.json", [])
        body.setdefault("ratings-seasons.json", [])
        body.setdefault("ratings-episodes.json", [])
        body.setdefault("user-last-activities.json", {})
        body.setdefault("user-stats.json", {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        for name, payload in body.items():
            text = payload if isinstance(payload, str) else json.dumps(payload)
            if isinstance(payload, bytes):
                zipped.writestr(name, payload)
            else:
                zipped.writestr(name, text)
    return buffer.getvalue()


def read(data: bytes) -> Any:
    return IMPORTER.read(
        ImportSource(data=data, filename="trakt.zip"), ImportReadContext(Path("."))
    )


def only(data: bytes) -> Any:
    records = read(data).records
    assert len(records) == 1, [(row.item.title, row.item_type) for row in records]
    return records[0]


# ----------------------------------------------------------------------------------
# Deliverable 1: which members are read, and what each produces
# ----------------------------------------------------------------------------------


class TestMembers:
    def test_watched_movies_produces_a_watched_movie(self) -> None:
        record = only(archive({"watched-movies.json": [watched_movie()]}))
        assert record.item_type == "movie"
        assert record.item.title == "Invented Film"
        assert record.item.year == 2020
        assert record.item.identifiers == {"imdb": "tt0000001"}
        assert record.entry.suggested_status == "watched"

    def test_watched_shows_produces_a_series(self) -> None:
        record = only(archive({"watched-shows.json": [watched_show()]}))
        assert record.item_type == "series"
        assert record.item.title == "Invented Show"
        assert record.item.metadata["episodes"] == 12

    def test_ratings_supply_the_score(self) -> None:
        record = only(
            archive(
                {
                    "watched-movies.json": [watched_movie()],
                    "ratings-movies.json": [rated_movie(rating=8)],
                }
            )
        )
        assert record.entry.score == 8
        assert record.entry.score_provisional is False

    def test_show_ratings_supply_the_score(self) -> None:
        record = only(
            archive(
                {
                    "watched-shows.json": [watched_show()],
                    "ratings-shows.json": [rated_show(rating=9)],
                }
            )
        )
        assert record.item_type == "series"
        assert record.entry.score == 9

    def test_a_rated_movie_absent_from_the_watched_member_is_still_imported(self) -> None:
        """A rating is evidence of watching; the two members are not in lockstep."""
        record = only(archive({"ratings-movies.json": [rated_movie()]}))
        assert record.entry.score == 8
        assert record.entry.suggested_status == "watched"

    def test_the_watchlist_produces_rows_when_present(self) -> None:
        record = only(
            archive(
                {
                    "lists-watchlist.json": [
                        watchlist_row(
                            "movie", "tt0000042", "Later Film", 2024, "2026-03-01T09:00:00.000Z"
                        )
                    ]
                }
            )
        )
        assert record.entry.suggested_status == "watchlist"
        assert record.entry.date_added == "2026-03-01"

    def test_a_show_on_the_watchlist_suggests_plan_to_watch(self) -> None:
        record = only(
            archive(
                {
                    "lists-watchlist.json": [
                        watchlist_row(
                            "show", "tt0000043", "Later Show", 2021, "2026-03-02T09:00:00.000Z"
                        )
                    ]
                }
            )
        )
        assert record.item_type == "series"
        assert record.entry.suggested_status == "plan_to_watch"

    def test_history_supplies_a_movie_the_other_members_missed(self) -> None:
        record = only(archive({"watched-history.json": [movie_event()]}))
        assert record.item.title == "Invented Film"
        assert record.entry.suggested_status == "watched"
        assert record.entry.date_added == "2026-01-10"

    def test_watched_wins_over_a_stale_watchlist_row(self) -> None:
        record = only(
            archive(
                {
                    "watched-movies.json": [watched_movie()],
                    "lists-watchlist.json": [
                        watchlist_row(
                            "movie", "tt0000001", "Invented Film", 2020, "2026-03-01T09:00:00.000Z"
                        )
                    ],
                }
            )
        )
        assert record.entry.suggested_status == "watched"

    def test_one_film_across_three_members_is_one_record(self) -> None:
        record = only(
            archive(
                {
                    "watched-movies.json": [watched_movie()],
                    "ratings-movies.json": [rated_movie()],
                    "watched-history.json": [movie_event()],
                }
            )
        )
        assert record.item.title == "Invented Film"
        assert record.entry.score == 8

    def test_films_and_shows_in_one_archive_produce_both_types(self) -> None:
        records = read(
            archive(
                {
                    "watched-movies.json": [watched_movie(imdb="tt0000001")],
                    "watched-shows.json": [watched_show(imdb="tt0000010")],
                    "watched-history.json": [
                        episode_event("tt0000010", 1, number) for number in range(1, 13)
                    ],
                }
            )
        ).records
        assert sorted(row.item_type for row in records) == ["movie", "series"]


# ----------------------------------------------------------------------------------
# Deliverable 2: the episode roll-up
# ----------------------------------------------------------------------------------


def history_archive(events: list[dict[str, Any]], **members: Any) -> bytes:
    """History events plus optional other members, keyed by their real member
    names — `history_archive(events, watched_show=…)` becomes
    `watched-shows.json`. A single member row is a dict, so it is wrapped in a
    list: every Trakt member holds a list of entries."""
    body: dict[str, Any] = {"watched-history.json": events}
    for name, rows in members.items():
        member = (
            "watched-shows.json"
            if name == "watched_show"
            else "watched-movies.json"
            if name == "watched_movie"
            else name
        )
        body[member] = [rows] if isinstance(rows, dict) else rows
    return archive(body)


class TestRollUp:
    """Progress is distinct episodes, not plays (AC2, AC3)."""

    def test_progress_counts_distinct_episodes(self) -> None:
        record = only(
            history_archive(
                [
                    episode_event("tt0000010", 1, 1),
                    episode_event("tt0000010", 1, 2),
                    episode_event("tt0000010", 2, 1),
                ],
                watched_show=watched_show(imdb="tt0000010", aired=24),
            )
        )
        assert record.item_type == "series"
        assert record.entry.values["progress"] == 3
        assert record.item.metadata["episodes"] == 24

    def test_a_rewatched_episode_does_not_inflate_progress(self) -> None:
        record = only(
            history_archive(
                [
                    episode_event("tt0000010", 1, 1, watched_at="2026-01-01T20:00:00.000Z"),
                    episode_event("tt0000010", 1, 1, watched_at="2026-02-01T20:00:00.000Z"),
                    episode_event("tt0000010", 1, 2),
                ],
                watched_show=watched_show(imdb="tt0000010", plays=3, aired=12),
            )
        )
        assert record.entry.values["progress"] == 2
        assert not record.errors

    def test_season_zero_is_excluded_from_progress(self) -> None:
        record = only(
            history_archive(
                [
                    episode_event("tt0000010", 0, 1),
                    episode_event("tt0000010", 1, 1),
                ],
                watched_show=watched_show(imdb="tt0000010", aired=12),
            )
        )
        assert record.entry.values["progress"] == 1

    def test_a_checkin_or_scrobble_action_is_not_a_watch(self) -> None:
        """Neither a checkin nor a scrobble is a completed watch, so neither
        counts toward progress. The show is still in `watched-shows.json` with
        `plays`, and a fallback that fires *is* the designed rule (deliverable
        2) — so the assertion is on what the fallback left, not on silence."""
        record = only(
            history_archive(
                [
                    episode_event("tt0000010", 1, 1, action="scrobble"),
                    episode_event("tt0000010", 1, 2, action="checkin"),
                ],
                watched_show=watched_show(imdb="tt0000010", plays=0, aired=12),
            )
        )
        assert record.entry.values.get("progress", 0) == 0
        # The fallback did not fire on a zero, and no history events counted.
        assert record.entry.notes is None

    def test_a_checkin_or_scrobble_action_falls_back_to_plays(self) -> None:
        """With no counted episodes and a non-zero `plays`, the designed
        fallback supplies the row — the events are not silently dropped, they
        are answered by the other member."""
        record = only(
            history_archive(
                [
                    episode_event("tt0000010", 1, 1, action="scrobble"),
                ],
                watched_show=watched_show(imdb="tt0000010", plays=5, aired=12),
            )
        )
        assert record.entry.values["progress"] == 5
        assert record.entry.notes is not None

    def test_a_show_in_history_but_not_in_watched_shows_is_imported(self) -> None:
        record = only(history_archive([episode_event("tt0000050", 1, 1)]))
        assert record.item_type == "series"
        assert record.item.title == "Invented Show"
        assert record.entry.values["progress"] == 1

    def test_history_carries_the_episode_total_at_export_time(self) -> None:
        record = only(history_archive([episode_event("tt0000010", 1, 1, aired=44)]))
        assert record.item.metadata["episodes"] == 44

    def test_the_plays_fallback_is_used_when_history_is_absent(self) -> None:
        record = only(archive({"watched-shows.json": [watched_show(plays=40, aired=44)]}))
        assert record.entry.values["progress"] == 40
        assert record.source_fields["plays_used"] is True

    def test_the_plays_fallback_is_used_when_history_holds_no_episodes_for_a_show(self) -> None:
        """Two shows in one archive: history names only one, so the other falls
        back to `plays`. Distinct titles and ids, or the two records are one."""
        snapshot = read(
            history_archive(
                [
                    episode_event(
                        "tt0000090",
                        1,
                        1,
                        watched_at="2026-01-20T20:00:00.000Z",
                    )
                ],
                watched_show=watched_show(imdb="tt0000010", plays=7, aired=12),
            )
        )
        by_title = {row.item.identifiers["imdb"]: row for row in snapshot.records}
        assert len(snapshot.records) == 2
        fallback = by_title["tt0000010"]
        counted = by_title["tt0000090"]
        assert fallback.item.title == "Invented Show"
        assert counted.item.title == "Invented Show"  # same builder, different ids
        assert fallback.entry.values["progress"] == 7
        assert fallback.source_fields["plays_used"] is True
        assert counted.entry.values["progress"] == 1
        assert counted.source_fields["plays_used"] is False

    def test_a_row_that_used_plays_carries_a_visible_warning(self) -> None:
        record = only(archive({"watched-shows.json": [watched_show(plays=40, aired=44)]}))
        # The warning rides the row's notes, because a row *error* blocks commit
        # and this row has nothing wrong with it — the sprint forbids the
        # alternative of counting it as an error, and AC11 forbids a UI change.
        assert record.entry.notes is not None
        assert "play count" in record.entry.notes
        assert not record.errors

    def test_a_history_derived_row_never_carries_the_plays_warning(self) -> None:
        record = only(
            history_archive(
                [episode_event("tt0000010", 1, number) for number in range(1, 13)],
                watched_show=watched_show(imdb="tt0000010", plays=12, aired=12),
            )
        )
        assert record.source_fields["plays_used"] is False
        assert record.entry.notes is None

    def test_progress_above_the_stored_total_is_kept_rather_than_refused(self) -> None:
        """DEC-092: the total is display only, never a bound (AC5)."""
        record = only(
            history_archive(
                [episode_event("tt0000010", 1, number) for number in range(1, 13)]
                + [episode_event("tt0000010", 2, number) for number in range(1, 13)],
                watched_show=watched_show(imdb="tt0000010", aired=12),
            )
        )
        assert record.entry.values["progress"] == 24
        assert record.item.metadata["episodes"] == 12
        assert not record.errors


# ----------------------------------------------------------------------------------
# Deliverable 3: status, score and dates
# ----------------------------------------------------------------------------------


class TestStatusSuggestion:
    def test_a_partially_watched_show_suggests_watching(self) -> None:
        record = only(
            history_archive(
                [episode_event("tt0000010", 1, 1)],
                watched_show=watched_show(imdb="tt0000010", plays=1, aired=12),
            )
        )
        assert record.entry.suggested_status == "watching"

    def test_a_fully_watched_show_suggests_completed(self) -> None:
        record = only(
            history_archive(
                [episode_event("tt0000010", 1, number) for number in range(1, 13)],
                watched_show=watched_show(imdb="tt0000010", plays=12, aired=12),
            )
        )
        assert record.entry.suggested_status == "completed"

    def test_a_show_watched_beyond_its_total_suggests_completed(self) -> None:
        record = only(archive({"watched-shows.json": [watched_show(plays=40, aired=12)]}))
        assert record.entry.suggested_status == "completed"

    def test_a_movie_suggests_watched(self) -> None:
        record = only(archive({"watched-movies.json": [watched_movie()]}))
        assert record.entry.suggested_status == "watched"


class TestScores:
    """Trakt's 1-10 is Akasha's scale: 1:1, nothing provisional (DEC-077's line
    for seasons and episodes is under TestWhatIsDeliberatelyNotImported)."""

    @pytest.mark.parametrize("rating", [1, 5, 10])
    def test_scores_map_one_to_one(self, rating: int) -> None:
        record = only(archive({"ratings-movies.json": [rated_movie(rating=rating)]}))
        assert record.entry.score == rating
        assert record.entry.score_provisional is False

    @pytest.mark.parametrize("rating", [0, 11, -1])
    def test_a_score_outside_the_scale_is_a_visible_row_error(self, rating: int) -> None:
        record = only(archive({"ratings-movies.json": [rated_movie(rating=rating)]}))
        assert record.entry.score is None
        assert any(row["code"] == "rating_out_of_range" for row in record.errors)

    def test_a_blank_rating_is_unscored_and_not_an_error(self) -> None:
        record = only(
            archive({"watched-movies.json": [watched_movie()], "ratings-movies.json": []})
        )
        assert record.entry.score is None
        assert not record.errors

    def test_season_and_episode_ratings_never_touch_a_score(self) -> None:
        record = only(
            archive(
                {
                    "watched-shows.json": [watched_show(imdb="tt0000010")],
                    "ratings-seasons.json": [
                        {
                            "rating": 7,
                            "rated_at": "2026-02-03T10:00:00.000Z",
                            "type": "season",
                            "season": {"number": 1, "ids": ids()},
                            "show": show_obj(imdb="tt0000010"),
                        }
                    ],
                    "ratings-episodes.json": [
                        {
                            "rating": 6,
                            "rated_at": "2026-02-04T10:00:00.000Z",
                            "type": "episode",
                            "episode": episode_obj(1, 1),
                            "show": show_obj(imdb="tt0000010"),
                        }
                    ],
                }
            )
        )
        assert record.entry.score is None
        assert not record.errors


class TestDates:
    def test_the_earliest_known_date_becomes_date_added(self) -> None:
        record = only(
            archive(
                {
                    "watched-movies.json": [
                        watched_movie(last_watched_at="2026-01-10T20:00:00.000Z")
                    ],
                    "ratings-movies.json": [rated_movie(rated_at="2026-01-11T10:00:00.000Z")],
                    "lists-watchlist.json": [
                        watchlist_row(
                            "movie", "tt0000001", "Invented Film", 2020, "2026-01-05T09:00:00.000Z"
                        )
                    ],
                }
            )
        )
        assert record.entry.date_added == "2026-01-05"

    def test_last_watched_at_becomes_the_finished_date_for_a_movie(self) -> None:
        record = only(archive({"watched-movies.json": [watched_movie()]}))
        assert record.entry.values["date_finished"] == "2026-01-10"
        assert record.entry.date_added == "2026-01-10"

    def test_a_fully_watched_show_gets_the_last_episode_date_as_finished(self) -> None:
        record = only(
            history_archive(
                [
                    episode_event("tt0000010", 1, 1, watched_at="2026-01-01T20:00:00.000Z"),
                    episode_event("tt0000010", 1, 2, watched_at="2026-01-08T20:00:00.000Z"),
                ],
                watched_show=watched_show(imdb="tt0000010", plays=2, aired=2),
            )
        )
        assert record.entry.values["date_finished"] == "2026-01-08"

    def test_a_partially_watched_show_gets_no_finish_date(self) -> None:
        """Progress, not a finish date: the show is still going."""
        record = only(
            history_archive(
                [episode_event("tt0000010", 1, 1)],
                watched_show=watched_show(imdb="tt0000010", plays=1, aired=12),
            )
        )
        assert record.entry.values.get("date_finished") is None

    def test_a_malformed_timestamp_does_not_become_a_date(self) -> None:
        record = only(
            archive({"watched-movies.json": [watched_movie(last_watched_at="not a date")]})
        )
        assert record.entry.values.get("date_finished") is None


# ----------------------------------------------------------------------------------
# Deliverable 1's never-read members, and AC6's counted skips
# ----------------------------------------------------------------------------------


class TestWhatIsDeliberatelyNotImported:
    def test_user_settings_and_user_profile_are_never_opened(self) -> None:
        """If the import succeeds, nothing read them: both members are deliberately
        malformed — a JSON *comment* — so any read would fail the whole import."""
        data = archive(
            {"watched-movies.json": [watched_movie()]},
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            for name in ("user-settings.json", "user-profile.json"):
                zipped.writestr(name, "// a JSON comment is not JSON")
            with zipfile.ZipFile(io.BytesIO(data)) as original:
                for info in original.infolist():
                    if info.filename in ("user-settings.json", "user-profile.json"):
                        continue
                    zipped.writestr(info.filename, original.read(info.filename))
        record = only(buffer.getvalue())
        assert record.item.title == "Invented Film"
        assert "email" not in json.dumps(record.source_fields)

    def test_season_and_episode_ratings_are_counted_not_imported(self) -> None:
        snapshot = read(
            archive(
                {
                    "watched-shows.json": [watched_show(imdb="tt0000010")],
                    "ratings-seasons.json": [
                        {
                            "rating": 7,
                            "rated_at": "2026-02-03T10:00:00.000Z",
                            "type": "season",
                            "season": {"number": 1, "ids": ids()},
                            "show": show_obj(imdb="tt0000010"),
                        }
                    ],
                    "ratings-episodes.json": [
                        {
                            "rating": 6,
                            "rated_at": "2026-02-04T10:00:00.000Z",
                            "type": "episode",
                            "episode": episode_obj(1, 1),
                            "show": show_obj(imdb="tt0000010"),
                        }
                    ],
                }
            )
        )
        reasons = {skip.reason: skip.count for skip in snapshot.skipped}
        assert reasons.get("season rating") == 1
        assert reasons.get("episode rating") == 1

    def test_collection_comments_notes_and_likes_are_counted_not_imported(self) -> None:
        snapshot = read(
            archive(
                {
                    "watched-movies.json": [watched_movie()],
                    "collection-movies.json": [watched_movie(imdb="tt0000055")],
                    "comments-movies.json": [{"comment": "x", "movie": movie_obj()}],
                    "notes-movies.json": [{"note": "x", "movie": movie_obj()}],
                    "likes-comments.json": [{"liked_at": "2026-01-01T00:00:00.000Z"}],
                }
            )
        )
        assert len(snapshot.records) == 1
        reasons = {skip.reason: skip.count for skip in snapshot.skipped}
        assert reasons.get("collection entry") == 1
        assert reasons.get("comment") == 1
        assert reasons.get("note") == 1
        assert reasons.get("like") == 1

    def test_the_plex_sub_object_is_never_read(self) -> None:
        row = watched_movie()
        row["movie"]["ids"]["plex"] = {"an_unexpected": "subobject"}
        record = only(archive({"watched-movies.json": [row]}))
        assert record.item.identifiers == {"imdb": "tt0000001"}

    def test_the_trakt_and_tmdb_ids_do_not_become_authoritative_identities(self) -> None:
        record = only(archive({"watched-movies.json": [watched_movie()]}))
        assert set(record.item.identifiers) == {"imdb"}


# ----------------------------------------------------------------------------------
# Deliverable 1's refusals: every one the Letterboxd reader makes (AC9)
# ----------------------------------------------------------------------------------


class TestRefusals:
    def test_a_file_that_is_not_a_zip_is_refused_with_a_way_out(self) -> None:
        with pytest.raises(TraktError) as refused:
            read(b"not a zip at all")
        assert refused.value.code == "invalid_archive"
        assert refused.value.action

    def test_an_encrypted_member_is_refused(self) -> None:
        data = bytearray(archive({"watched-movies.json": [watched_movie()]}))
        data[data.find(b"PK\x03\x04") + 6] |= 0x1
        data[data.find(b"PK\x01\x02") + 8] |= 0x1
        with pytest.raises(TraktError) as refused:
            read(bytes(data))
        assert refused.value.code == "unsafe_archive"

    @pytest.mark.parametrize(
        "name", ["../escape.json", "/absolute.json", "nested/../../escape.json", ".hidden/x.json"]
    )
    def test_a_member_that_tries_to_escape_is_refused(self, name: str) -> None:
        with pytest.raises(TraktError) as refused:
            read(_member_with(name))
        assert refused.value.code == "unsafe_archive"

    def test_an_archive_naming_one_member_twice_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("watched-movies.json", json.dumps([watched_movie()]))
            zipped.writestr("watched-movies.json", json.dumps([watched_movie()]))
        with pytest.raises(TraktError) as refused:
            read(buffer.getvalue())
        assert refused.value.code == "unsafe_archive"

    def test_an_archive_that_claims_to_expand_enormously_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr("watched-movies.json", json.dumps([watched_movie()]))
            zipped.writestr("bomb.txt", b"\0" * (17 * 1024 * 1024))
        with pytest.raises(TraktError) as refused:
            read(buffer.getvalue())
        assert refused.value.code == "export_too_large"

    def test_a_member_that_lies_about_its_size_is_refused_while_read(self) -> None:
        """The declared sizes are checked on the way in; a member whose real
        expansion exceeds its declaration is refused mid-read."""
        from book_tracker.domains.movie import trakt as module

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
            zipped.writestr("watched-movies.json", json.dumps([watched_movie()]))
            payload = b"0" * (module.MAX_MEMBER_BYTES + 1)
            info = zipfile.ZipInfo("watched-history.json")
            zipped.writestr(info, payload)
        with pytest.raises(TraktError) as refused:
            read(buffer.getvalue())
        assert refused.value.code == "export_too_large"

    def test_a_member_that_is_not_valid_json_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("watched-movies.json", "{not json")
        with pytest.raises(TraktError) as refused:
            read(buffer.getvalue())
        assert refused.value.code == "invalid_archive"

    def test_a_member_that_is_not_utf8_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("watched-movies.json", b"\xff\xfe\x00")
        with pytest.raises(TraktError) as refused:
            read(buffer.getvalue())
        assert refused.value.code == "invalid_archive"

    def test_a_member_whose_rows_are_not_objects_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("watched-movies.json", json.dumps(["a string"]))
        with pytest.raises(TraktError) as refused:
            read(buffer.getvalue())
        assert refused.value.code == "invalid_archive"

    def test_an_archive_with_no_trakt_members_is_refused(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("holiday.jpg", b"\xff\xd8\xff")
        with pytest.raises(TraktError) as refused:
            read(buffer.getvalue())
        assert refused.value.code == "invalid_archive"

    def test_every_declared_error_code_is_one_this_reader_can_raise(self) -> None:
        assert set(TraktError.ACTIONS) == set(IMPORTER.error_codes)

    def test_a_read_error_is_always_one_a_reader_can_act_on(self) -> None:
        for code in IMPORTER.error_codes:
            error = TraktError(code, "x")
            assert isinstance(error, ImportReadError)
            assert error.user_message and error.action


def _member_with(name: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        zipped.writestr("watched-movies.json", json.dumps([watched_movie()]))
        zipped.writestr(name, "x")
    return buffer.getvalue()


# ----------------------------------------------------------------------------------
# The owner's real shape, invented: 26 empty members, no watchlist (AC8)
# ----------------------------------------------------------------------------------


def test_an_archive_with_the_owners_member_shape_imports_cleanly() -> None:
    snapshot = read(
        archive(
            {
                "watched-movies.json": [watched_movie(imdb="tt0000060")],
                "watched-shows.json": [watched_show(imdb="tt0000070", plays=5, aired=10)],
                "ratings-movies.json": [rated_movie(imdb="tt0000060", rating=7)],
                "watched-history.json": [
                    episode_event("tt0000070", 1, 1),
                    episode_event("tt0000070", 1, 2),
                    movie_event(imdb="tt0000060"),
                ],
            },
            include_empties=True,
        )
    )
    assert len(snapshot.records) == 2
    assert not any(row.errors for row in snapshot.records)
    assert snapshot.skipped == ()


# ----------------------------------------------------------------------------------
# The declaration, and identity matching (AC1, AC10)
# ----------------------------------------------------------------------------------


class TestDeclaration:
    def test_it_targets_both_libraries(self) -> None:
        assert IMPORTER.item_types == ("movie", "series")

    def test_it_trusts_the_imdb_identity_only(self) -> None:
        assert IMPORTER.identity_kinds == frozenset({"imdb"})

    def test_its_guide_says_exporting_is_a_vip_feature(self) -> None:
        assert any("vip" in step.lower() for step in IMPORTER.input.guide)

    def test_its_help_link_is_https(self) -> None:
        assert (IMPORTER.input.help_url or "").startswith("https://")

    def test_the_suggested_statuses_are_ones_the_domains_declare(self) -> None:
        from book_tracker.domains.movie import DOMAIN as MOVIE
        from book_tracker.domains.series import DOMAIN as SERIES

        for domain, statuses in (
            (MOVIE, ("watched", "watchlist")),
            (SERIES, ("watching", "completed", "plan_to_watch")),
        ):
            for status in statuses:
                assert domain.status(status) is not None


def library(tmp_path: Path) -> tuple[Any, Any]:
    """`(DomainRepository, add)`, the same shape the IMDb tests use."""
    from sqlalchemy import text

    from book_tracker.config import Settings
    from book_tracker.database import create_engine
    from book_tracker.infrastructure.repositories import DomainRepository
    from book_tracker.migrations import upgrade

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    engine = create_engine(configured)

    def add(title: str, item_type: str, year: int | None, **identifiers: str) -> int:
        with engine.begin() as connection:
            item_id = connection.execute(
                text(
                    "INSERT INTO items(type,title,year,identifiers,metadata,"
                    "created_at,updated_at) VALUES(:type,:title,:year,'{}','{}','n','n') "
                    "RETURNING id"
                ),
                {"type": item_type, "title": title, "year": year},
            ).scalar_one()
            for kind, value in identifiers.items():
                connection.execute(
                    text(
                        "INSERT INTO item_identifiers(item_id,kind,normalized_value,value,"
                        "created_at,updated_at) VALUES(:item,:kind,:value,:value,'n','n')"
                    ),
                    {"item": item_id, "kind": kind, "value": value},
                )
        return item_id

    return DomainRepository(engine), add


class TestMatching:
    def test_a_film_already_in_the_library_matches_exactly_on_imdb(self, tmp_path: Path) -> None:
        matcher, add = library(tmp_path)
        existing = add("Invented Film", "movie", 2020, imdb="tt0000001")
        record = only(archive({"watched-movies.json": [watched_movie()]}))
        decision = IMPORTER.match(record, matcher)
        assert decision.kind.value == "exact"
        assert decision.item_id == existing

    def test_a_film_imported_from_letterboxd_matches_after_enrichment_added_imdb(
        self, tmp_path: Path
    ) -> None:
        """AC10: the same film described by a different source is one film."""
        matcher, add = library(tmp_path)
        existing = add(
            "Invented Film", "movie", 2020, letterboxd="https://boxd.it/2b3c", imdb="tt0000001"
        )
        record = only(archive({"watched-movies.json": [watched_movie()]}))
        decision = IMPORTER.match(record, matcher)
        assert decision.kind.value == "exact"
        assert decision.item_id == existing

    def test_a_show_matches_scoped_to_the_series_library(self, tmp_path: Path) -> None:
        matcher, add = library(tmp_path)
        existing = add("Invented Show", "series", 2015, imdb="tt0000010")
        record = only(
            history_archive(
                [episode_event("tt0000010", 1, 1)],
                watched_show=watched_show(imdb="tt0000010", plays=1, aired=12),
            )
        )
        decision = IMPORTER.match(record, matcher)
        assert decision.kind.value == "exact"
        assert decision.item_id == existing

    def test_title_and_year_alone_are_offered_never_merged(self, tmp_path: Path) -> None:
        matcher, add = library(tmp_path)
        existing = add("Invented Film", "movie", 2020)
        record = only(archive({"watched-movies.json": [watched_movie(imdb="tt0000099")]}))
        decision = IMPORTER.match(record, matcher)
        assert decision.kind.value == "ambiguous"
        assert decision.candidates == (existing,)
        assert decision.item_id is None

    def test_a_film_and_a_series_sharing_a_title_are_not_confused(self, tmp_path: Path) -> None:
        """A near match is scoped to the row's own type (DEC-106)."""
        matcher, add = library(tmp_path)
        add("Invented Show", "movie", 2015)
        record = only(
            history_archive(
                [episode_event("tt0000010", 1, 1)],
                watched_show=watched_show(imdb="tt0000010", aired=12),
            )
        )
        decision = IMPORTER.match(record, matcher)
        assert decision.candidates == ()


# ----------------------------------------------------------------------------------
# Through the real pipeline: preview, targets, commit, undo, enrichment (AC1, AC4,
# AC10, AC11's negative half — the shared route hosts this connector unmodified).
# ----------------------------------------------------------------------------------


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app(tmp_path: Path) -> Any:
    from book_tracker.config import Settings
    from book_tracker.main import create_app

    return create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid")
    )


async def _preview(client: Any, data: bytes, targets: str | None = None) -> Any:
    form = {"targets": targets} if targets else None
    return await client.post(
        "/api/import/trakt/preview",
        files={"file": ("trakt.zip", data, "application/zip")},
        data=form,
    )


def _types(engine: Any) -> dict[str, int]:
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        return {
            str(row[0]): int(row[1])
            for row in session.execute(text("SELECT type, count(*) FROM items GROUP BY type"))
        }


def _entries(engine: Any) -> list[tuple[str, Any, Any]]:
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        return [
            (str(row[0]), row[1], row[2])
            for row in session.execute(
                text(
                    "SELECT i.type, e.progress, e.suggested_status FROM entries e "
                    "JOIN items i ON i.id = e.item_id ORDER BY i.type"
                )
            )
        ]


MIXED_ARCHIVE = archive(
    {
        "watched-movies.json": [watched_movie(imdb="tt0000001")],
        "ratings-movies.json": [rated_movie(imdb="tt0000001", rating=8)],
        "watched-shows.json": [watched_show(imdb="tt0000010", plays=12, aired=12)],
        "watched-history.json": [episode_event("tt0000010", 1, number) for number in range(1, 13)]
        + [movie_event(imdb="tt0000001")],
        "ratings-seasons.json": [
            {
                "rating": 7,
                "rated_at": "2026-02-03T10:00:00.000Z",
                "type": "season",
                "season": {"number": 1, "ids": ids()},
                "show": show_obj(imdb="tt0000010"),
            }
        ],
    }
)


@pytest.mark.anyio
async def test_one_archive_lands_in_both_libraries(tmp_path: Path) -> None:
    """AC1. Two libraries, one archive, one batch — with the season rating counted
    (AC6) and nothing else lost."""
    import httpx

    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await _preview(client, MIXED_ARCHIVE)
        assert preview.status_code == 201, preview.text
        body = preview.json()
        assert body["summary"]["total"] == 2
        assert body["summary"]["errors"] == 0
        assert {row["item_type"] for row in body["records"]} == {"movie", "series"}
        reasons = {row["reason"]: row["count"] for row in body["summary"]["skipped_reasons"]}
        assert reasons == {"season rating": 1}

        committed = await client.post(
            "/api/import/trakt/commit", json={"batch_id": body["batch_id"]}
        )
        assert committed.status_code == 200, committed.text
        assert committed.json()["created_items"] == 2

    assert _types(app.state.engine) == {"movie": 1, "series": 1}
    # The roll-up survived the commit: the show carries progress 12.
    progress = {item_type: value for item_type, value, _ in _entries(app.state.engine)}
    assert progress == {"movie": None, "series": 12}


@pytest.mark.anyio
async def test_the_progress_control_total_is_the_episodes_metadata(tmp_path: Path) -> None:
    """AC2 through the API: the stored total the progress control renders against."""
    import httpx

    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await _preview(client, MIXED_ARCHIVE)
        await client.post("/api/import/trakt/commit", json={"batch_id": preview.json()["batch_id"]})
        show = next(row for row in preview.json()["records"] if row["item_type"] == "series")
    assert show["item"]["metadata"]["episodes"] == 12


@pytest.mark.anyio
async def test_re_importing_matches_on_imdb_with_nothing_created(tmp_path: Path) -> None:
    """AC10, against a different archive so the fingerprint cannot replay it."""
    import httpx

    again = archive(
        {
            "watched-movies.json": [watched_movie(imdb="tt0000001")],
            "watched-shows.json": [watched_show(imdb="tt0000010", plays=12, aired=12)],
            "watched-history.json": [
                episode_event("tt0000010", 1, number) for number in range(1, 13)
            ],
        }
    )
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        first = await _preview(client, MIXED_ARCHIVE)
        await client.post("/api/import/trakt/commit", json={"batch_id": first.json()["batch_id"]})
        second = await _preview(client, again)
        assert [row["planned_action"] for row in second.json()["records"]] == [
            "reuse_item",
            "reuse_item",
        ]
        committed = await client.post(
            "/api/import/trakt/commit", json={"batch_id": second.json()["batch_id"]}
        )

    assert committed.json()["created_items"] == 0
    assert committed.json()["unchanged_entries"] == 2
    assert _types(app.state.engine) == {"movie": 1, "series": 1}


@pytest.mark.anyio
async def test_an_imdb_imported_film_is_not_duplicated_by_trakt(tmp_path: Path) -> None:
    """AC10's interesting case: the two sources describe the same library."""
    import httpx

    from tests.test_imdb_import import LIST_HEADER  # noqa: F401  (shape documented there)

    imdb_csv = (
        b"Const,Your Rating,Date Rated,Title,Original Title,URL,Title Type,IMDb Rating,"
        b"Runtime (mins),Year,Genres,Num Votes,Release Date,Directors\n"
        b"tt0000001,9,2024-03-01,Invented Film,,https://www.imdb.com/title/tt0000001/,"
        b"Movie,7.5,100,2020,Drama,10,2020-01-01,A Director\n"
    )
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        first = await client.post(
            "/api/import/imdb/preview",
            files={"file": ("ratings.csv", imdb_csv, "text/csv")},
        )
        assert first.status_code == 201, first.text
        await client.post("/api/import/imdb/commit", json={"batch_id": first.json()["batch_id"]})
        second = await _preview(client, archive({"watched-movies.json": [watched_movie()]}))
        assert [row["planned_action"] for row in second.json()["records"]] == ["reuse_item"]
        committed = await client.post(
            "/api/import/trakt/commit", json={"batch_id": second.json()["batch_id"]}
        )

    assert committed.json()["created_items"] == 0
    assert _types(app.state.engine) == {"movie": 1}


@pytest.mark.anyio
async def test_unticking_movies_leaves_only_series(tmp_path: Path) -> None:
    """The service applies the choice; this connector never sees it (DEC-112)."""
    import httpx

    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await _preview(client, MIXED_ARCHIVE, targets="series")
        body = preview.json()
        assert [row["item_type"] for row in body["records"]] == ["series"]
        assert body["summary"]["skipped_not_requested"] == 1
        assert body["summary"]["skipped_reasons"] == [{"reason": "season rating", "count": 1}]


@pytest.mark.anyio
async def test_the_plays_fallback_row_commits_and_carries_its_warning(tmp_path: Path) -> None:
    """AC4 end to end: a row that used `plays` commits (it is not an error) and the
    warning is visible on the stored entry."""
    import httpx
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    fallback = archive({"watched-shows.json": [watched_show(imdb="tt0000010", plays=40, aired=44)]})
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await _preview(client, fallback)
        assert preview.status_code == 201, preview.text
        assert preview.json()["summary"]["errors"] == 0
        committed = await client.post(
            "/api/import/trakt/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        assert committed.status_code == 200, committed.text

    with Session(app.state.engine) as session:
        notes, progress = session.execute(text("SELECT notes, progress FROM entries")).one()
    assert progress == 40
    assert notes is not None and "play count" in notes


@pytest.mark.anyio
async def test_undo_takes_back_both_libraries(tmp_path: Path) -> None:
    import httpx
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await _preview(client, MIXED_ARCHIVE)
        batch_id = preview.json()["batch_id"]
        await client.post("/api/import/trakt/commit", json={"batch_id": batch_id})
        undone = await client.delete(f"/api/import/batches/{batch_id}")

    assert undone.status_code == 200, undone.text
    with Session(app.state.engine) as session:
        assert session.execute(text("SELECT count(*) FROM items")).scalar_one() == 0
        assert session.execute(text("SELECT count(*) FROM entries")).scalar_one() == 0


@pytest.mark.anyio
async def test_committing_queues_enrichment_for_both_libraries(tmp_path: Path) -> None:
    """Both target domains enrich on `imdb` (DEC-113), and a Trakt archive carries
    IMDb ids — checked rather than assumed."""
    import json

    import httpx
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await _preview(client, MIXED_ARCHIVE)
        await client.post("/api/import/trakt/commit", json={"batch_id": preview.json()["batch_id"]})
        with Session(app.state.engine) as session:
            payloads = [
                json.loads(str(row[0]))
                for row in session.execute(
                    text("SELECT payload FROM jobs WHERE kind = 'enrich_item' ORDER BY id")
                )
            ]

    assert sorted((row["kind"], row["value"]) for row in payloads) == [
        ("imdb", "tt0000001"),
        ("imdb", "tt0000010"),
    ]


@pytest.mark.anyio
async def test_the_connector_is_published_with_both_of_its_libraries(tmp_path: Path) -> None:
    import httpx

    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        published = {row["id"]: row for row in (await client.get("/api/importers")).json()}

    assert published["trakt"]["item_types"] == ["movie", "series"]
    assert published["trakt"]["input"]["accept"] == ".zip,application/zip"
    assert published["trakt"]["input"]["help_url"].startswith("https://")
