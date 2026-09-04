"""Sprint 065: ranking a domain's entries by a declared groupable key.

Exercises `LibraryService.rank()` directly, the way `test_library_api.py` exercises
`list_entries` — these are the same repository, so the same fixture shape (a real
engine via `create_app`'s lifespan, `DomainRepository` to seed, raw SQL for the columns
the seeding helper does not expose) applies.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import text

from book_tracker.application.library import LibraryError, LibraryService
from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _Fixture:
    """A running app plus the two objects every test in this file needs."""

    def __init__(self, app: object) -> None:
        self.app = app
        self.repository = DomainRepository(app.state.engine)  # type: ignore[attr-defined]
        self.service = LibraryService(app.state.engine)  # type: ignore[attr-defined]

    def set_score(self, entry_id: int, score: int | None) -> None:
        with self.app.state.engine.begin() as connection:  # type: ignore[attr-defined]
            connection.execute(
                text("UPDATE entries SET score=:score WHERE id=:id"),
                {"score": score, "id": entry_id},
            )

    def set_status(self, entry_id: int, status: str) -> None:
        with self.app.state.engine.begin() as connection:  # type: ignore[attr-defined]
            connection.execute(
                text("UPDATE entries SET status=:status WHERE id=:id"),
                {"status": status, "id": entry_id},
            )

    def set_year(self, item_id: int, year: int | None) -> None:
        with self.app.state.engine.begin() as connection:  # type: ignore[attr-defined]
            connection.execute(
                text("UPDATE items SET year=:year WHERE id=:id"), {"year": year, "id": item_id}
            )

    def set_metadata_field(self, item_id: int, name: str, value: object) -> None:
        with self.app.state.engine.begin() as connection:  # type: ignore[attr-defined]
            current = connection.execute(
                text("SELECT metadata FROM items WHERE id=:id"), {"id": item_id}
            ).scalar_one()
            payload = json.loads(current)
            payload[name] = value
            connection.execute(
                text("UPDATE items SET metadata=:metadata WHERE id=:id"),
                {"metadata": json.dumps(payload), "id": item_id},
            )


@asynccontextmanager
async def _fixture(tmp_path: Path) -> AsyncIterator[_Fixture]:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        yield _Fixture(app)


@pytest.mark.anyio
async def test_count_ranking_over_a_many_field_counts_every_position(tmp_path: Path) -> None:
    """AC1, AC4: a book credited under a second author's first position still counts."""
    async with _fixture(tmp_path) as fx:
        a = fx.repository.create_or_get_entry(title="A", creators=["Alice"])
        b = fx.repository.create_or_get_entry(title="B", creators=["Bob", "Alice"])
        c = fx.repository.create_or_get_entry(title="C", creators=["Carol"])
        for entry in (a, b, c):
            fx.set_status(entry.entry_id, "read")

        result = fx.service.rank(item_type="book", key="creators", metric="count")

        by_key = {row["key"]: row for row in result["rows"]}
        assert by_key["alice"]["count"] == 2
        assert by_key["bob"]["count"] == 1
        assert by_key["carol"]["count"] == 1


@pytest.mark.anyio
async def test_score_ranking_honours_min_rated_and_the_mean_is_right(tmp_path: Path) -> None:
    """AC1: excludes anyone below `min_rated`, and shows the rated count beside the mean."""
    async with _fixture(tmp_path) as fx:
        a1 = fx.repository.create_or_get_entry(title="A1", creators=["Prolific"])
        a2 = fx.repository.create_or_get_entry(title="A2", creators=["Prolific"])
        single = fx.repository.create_or_get_entry(title="S", creators=["OneHit"])
        for entry in (a1, a2, single):
            fx.set_status(entry.entry_id, "read")
        fx.set_score(a1.entry_id, 10)
        fx.set_score(a2.entry_id, 8)
        fx.set_score(single.entry_id, 10)

        result = fx.service.rank(item_type="book", key="creators", metric="score", min_rated=2)

        keys = {row["key"] for row in result["rows"]}
        assert "prolific" in keys
        assert "onehit" not in keys
        prolific = next(row for row in result["rows"] if row["key"] == "prolific")
        assert prolific["mean_score"] == 9.0
        assert prolific["rated_count"] == 2


@pytest.mark.anyio
async def test_scalar_metadata_keys_rank(tmp_path: Path) -> None:
    """A `multiplicity="one"` field (`publisher`) ranks through `json_extract`, not `json_each`."""
    async with _fixture(tmp_path) as fx:
        a = fx.repository.create_or_get_entry(title="A", creators=["X"])
        b = fx.repository.create_or_get_entry(title="B", creators=["Y"])
        for entry in (a, b):
            fx.set_status(entry.entry_id, "read")
        fx.set_metadata_field(a.item_id, "publisher", "Sudamericana")
        fx.set_metadata_field(b.item_id, "publisher", "Sudamericana")

        result = fx.service.rank(item_type="book", key="publisher", metric="count")

        assert result["rows"] == [
            {
                "key": "sudamericana",
                "label": "Sudamericana",
                "count": 2,
                "rated_count": 0,
                "mean_score": None,
                "score_spread": None,
                "covers": [],
            }
        ]


@pytest.mark.anyio
async def test_year_and_decade_rank_and_null_years_are_counted_not_dropped(tmp_path: Path) -> None:
    """AC3: `year`/`decade` come from `items.year`; a null year is excluded and counted."""
    async with _fixture(tmp_path) as fx:
        dated = fx.repository.create_or_get_entry(title="Dated", creators=["X"])
        undated = fx.repository.create_or_get_entry(title="Undated", creators=["Y"])
        for entry in (dated, undated):
            fx.set_status(entry.entry_id, "read")
        fx.set_year(dated.item_id, 1994)

        by_year = fx.service.rank(item_type="book", key="year", metric="count")
        by_decade = fx.service.rank(item_type="book", key="decade", metric="count")

        # A string, not the `int` this asserted when it was written. `key` is the
        # value a client hands back to `/api/entries`, the response schema has
        # declared it a string since Sprint 065, and asserting the int here is what
        # let every `key=year` request 500 over HTTP without a test noticing.
        assert by_year["rows"] == [
            {
                "key": "1994",
                "label": "1994",
                "count": 1,
                "rated_count": 0,
                "mean_score": None,
                "score_spread": None,
                "covers": [],
            }
        ]
        assert by_year["null_count"] == 1
        assert by_decade["rows"][0]["key"] == "1990"
        assert by_decade["rows"][0]["label"] == "1990s"
        assert by_decade["null_count"] == 1


@pytest.mark.anyio
async def test_case_and_diacritic_variants_group_and_display_the_commonest_spelling(
    tmp_path: Path,
) -> None:
    """AC5: `Julio Cortázar` and `julio cortazar` are one row, labelled the commoner spelling."""
    async with _fixture(tmp_path) as fx:
        accented_1 = fx.repository.create_or_get_entry(title="A", creators=["Julio Cortázar"])
        accented_2 = fx.repository.create_or_get_entry(title="B", creators=["Julio Cortázar"])
        plain = fx.repository.create_or_get_entry(title="C", creators=["julio cortazar"])
        for entry in (accented_1, accented_2, plain):
            fx.set_status(entry.entry_id, "read")

        result = fx.service.rank(item_type="book", key="creators", metric="count")

        assert len(result["rows"]) == 1
        assert result["rows"][0]["count"] == 3
        assert result["rows"][0]["label"] == "Julio Cortázar"


@pytest.mark.anyio
async def test_suppression_omits_by_default_reports_and_is_reversible(tmp_path: Path) -> None:
    """AC6: `Various Artists` does not rank an album by default, but is reported and can return."""
    async with _fixture(tmp_path) as fx:
        compilation = fx.repository.create_or_get_entry(
            title="Now That's What I Call Music", creators=["Various Artists"], item_type="album"
        )
        real = fx.repository.create_or_get_entry(
            title="Discovery", creators=["Daft Punk"], item_type="album"
        )
        for entry in (compilation, real):
            fx.set_status(entry.entry_id, "owned")

        default = fx.service.rank(item_type="album", key="creators", metric="count")
        with_suppressed = fx.service.rank(
            item_type="album", key="creators", metric="count", include_suppressed=True
        )

        assert [row["key"] for row in default["rows"]] == ["daft punk"]
        assert default["suppressed"] == [
            {"key": "various artists", "label": "Various Artists", "count": 1}
        ]
        assert {row["key"] for row in with_suppressed["rows"]} == {"daft punk", "various artists"}


@pytest.mark.anyio
async def test_a_ranking_never_crosses_domains(tmp_path: Path) -> None:
    """No shared creator identity: the same name in two domains produces two rankings."""
    async with _fixture(tmp_path) as fx:
        book = fx.repository.create_or_get_entry(title="A Book", creators=["Shared Name"])
        album = fx.repository.create_or_get_entry(
            title="An Album", creators=["Shared Name"], item_type="album"
        )
        fx.set_status(book.entry_id, "read")
        fx.set_status(album.entry_id, "owned")

        books = fx.service.rank(item_type="book", key="creators", metric="count")
        albums = fx.service.rank(item_type="album", key="creators", metric="count")

        assert books["rows"][0]["count"] == 1
        assert albums["rows"][0]["count"] == 1


@pytest.mark.anyio
async def test_zero_score_domain_count_still_ranks(tmp_path: Path) -> None:
    """AC10 (repository half): a domain with no scored entries still produces a count ranking."""
    async with _fixture(tmp_path) as fx:
        entry = fx.repository.create_or_get_entry(title="Unrated", creators=["Nobody Rated"])
        fx.set_status(entry.entry_id, "read")

        result = fx.service.rank(item_type="book", key="creators", metric="count")

        assert result["rows"][0]["count"] == 1
        assert result["rows"][0]["mean_score"] is None


@pytest.mark.anyio
async def test_zero_score_domain_score_metric_says_so_plainly(tmp_path: Path) -> None:
    """AC10: `metric=score` returns `no_rated_groups` rather than an empty-looking table."""
    async with _fixture(tmp_path) as fx:
        entry = fx.repository.create_or_get_entry(title="Unrated", creators=["Nobody Rated"])
        fx.set_status(entry.entry_id, "read")

        result = fx.service.rank(item_type="book", key="creators", metric="score")

        assert result["rows"] == []
        assert result["no_rated_groups"] is True


@pytest.mark.anyio
async def test_an_invalid_key_is_refused_naming_the_domain(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        with pytest.raises(LibraryError) as refused:
            fx.service.rank(item_type="book", key="description", metric="count")

        assert refused.value.status_code == 422
        assert refused.value.code == "invalid_insight_key"
        assert "Book" in refused.value.message


@pytest.mark.anyio
async def test_pagination_covers_every_row_exactly_once(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        for name in ("Alice", "Bob", "Carol"):
            entry = fx.repository.create_or_get_entry(title=name, creators=[name])
            fx.set_status(entry.entry_id, "read")

        page1 = fx.service.rank(item_type="book", key="creators", metric="count", limit=2)
        assert len(page1["rows"]) == 2
        assert page1["next_cursor"] is not None

        page2 = fx.service.rank(
            item_type="book", key="creators", metric="count", limit=2, after=page1["next_cursor"]
        )
        assert len(page2["rows"]) == 1
        assert page2["next_cursor"] is None

        seen = {row["key"] for row in page1["rows"]} | {row["key"] for row in page2["rows"]}
        assert seen == {"alice", "bob", "carol"}


@pytest.mark.anyio
async def test_covers_come_from_the_rows_own_members_deterministically_ordered(
    tmp_path: Path,
) -> None:
    """Sprint 067 AC1: highest scored first, then most recently added; stable on repeat."""
    async with _fixture(tmp_path) as fx:
        best_older = fx.repository.create_or_get_entry(title="Best older", creators=["Author"])
        best_newer = fx.repository.create_or_get_entry(title="Best newer", creators=["Author"])
        middling = fx.repository.create_or_get_entry(title="Middling", creators=["Author"])
        weakest = fx.repository.create_or_get_entry(title="Weakest", creators=["Author"])
        uncovered = fx.repository.create_or_get_entry(title="Uncovered", creators=["Author"])
        for entry in (best_older, best_newer, middling, weakest, uncovered):
            fx.set_status(entry.entry_id, "read")
        fx.set_score(best_older.entry_id, 9)
        fx.set_score(best_newer.entry_id, 9)
        fx.set_score(middling.entry_id, 6)
        fx.set_score(weakest.entry_id, 2)
        for entry in (best_older, best_newer, middling, weakest):
            fx.repository.set_cover_path(entry.item_id, f"{entry.item_id}.jpg")
        with fx.app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET date_added=:d WHERE id=:id"),
                {"d": "2020-01-01T00:00:00", "id": best_older.entry_id},
            )
            connection.execute(
                text("UPDATE entries SET date_added=:d WHERE id=:id"),
                {"d": "2020-06-01T00:00:00", "id": best_newer.entry_id},
            )

        first = fx.service.rank(item_type="book", key="creators", metric="count")
        second = fx.service.rank(item_type="book", key="creators", metric="count")

        row = first["rows"][0]
        assert len(row["covers"]) == 3
        item_ids = [int(url.split("/")[3]) for url in row["covers"]]
        assert item_ids == [best_newer.item_id, best_older.item_id, middling.item_id]
        assert uncovered.item_id not in item_ids
        assert weakest.item_id not in item_ids
        assert second["rows"][0]["covers"] == row["covers"]


@pytest.mark.anyio
async def test_a_ranking_row_with_no_covered_members_returns_an_empty_list(
    tmp_path: Path,
) -> None:
    """Sprint 067 AC2 (corrected reading, DEC-134): empty when no member has a cover, not
    gated on `chooses_covers` — every shipped domain but book declares that `False` while
    still carrying real cover art, so gating on it would empty every domain's covers but
    book's."""
    async with _fixture(tmp_path) as fx:
        entry = fx.repository.create_or_get_entry(title="No cover", creators=["Author"])
        fx.set_status(entry.entry_id, "read")

        result = fx.service.rank(item_type="book", key="creators", metric="count")

        assert result["rows"][0]["covers"] == []


@pytest.mark.anyio
async def test_total_entries_and_rated_entries_honour_the_ranked_sets_filters(
    tmp_path: Path,
) -> None:
    """Sprint 067 deliverable 2: library totals for the ranked set, not a sum of rows —
    a many-valued field over-counts (one entry with two creators is two rows)."""
    async with _fixture(tmp_path) as fx:
        two_creators = fx.repository.create_or_get_entry(title="A", creators=["Alice", "Bob"])
        one_creator = fx.repository.create_or_get_entry(title="B", creators=["Carol"])
        unread = fx.repository.create_or_get_entry(title="C", creators=["Dana"])
        fx.set_status(two_creators.entry_id, "read")
        fx.set_status(one_creator.entry_id, "read")
        fx.set_status(unread.entry_id, "to_read")
        fx.set_score(two_creators.entry_id, 8)

        unfiltered = fx.service.rank(item_type="book", key="creators", metric="count")
        filtered = fx.service.rank(
            item_type="book", key="creators", metric="count", statuses=["read"]
        )

        assert sum(row["count"] for row in unfiltered["rows"]) == 4
        assert unfiltered["total_entries"] == 3
        assert unfiltered["rated_entries"] == 1
        assert filtered["total_entries"] == 2
        assert filtered["rated_entries"] == 1
