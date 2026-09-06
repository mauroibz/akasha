"""Sprint 065 deliverable 7: `/api/entries` gains a precise `key`/`value` filter.

A new file, not an extension of `test_library_api.py` — the sprint doc names
`test_library_queries.py` as though it already existed, but it didn't; this is the
first thing in it. Covers the shared mechanism with `test_insights.py`'s `rank()`
(AC8: a ranking row must show *exactly* the entries behind its number).
"""

from pathlib import Path

import httpx
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


@pytest.mark.anyio
async def test_key_value_returns_exactly_the_ranked_members(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        cortazar_1 = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        cortazar_2 = repository.create_or_get_entry(
            title="Bestiario", creators=("julio cortazar", "Someone Else")
        )
        other = repository.create_or_get_entry(title="Other", creators=("Someone Else",))
        with app.state.engine.begin() as connection:
            for entry in (cortazar_1, cortazar_2, other):
                connection.execute(
                    text("UPDATE entries SET status='read' WHERE id=:id"), {"id": entry.entry_id}
                )

        service = LibraryService(app.state.engine)
        ranked = service.rank(item_type="book", key="creators", metric="count")
        cortazar_row = next(row for row in ranked["rows"] if row["key"] == "julio cortazar")

        filtered = service.list_entries(types=["book"], key="creators", value="julio cortazar")

        titles = {item["item"]["title"] for item in filtered["items"]}
        assert titles == {"Rayuela", "Bestiario"}
        assert len(filtered["items"]) == cortazar_row["count"]


@pytest.mark.anyio
async def test_key_value_filters_over_http(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        match = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        other = repository.create_or_get_entry(title="Other", creators=("Someone Else",))
        with app.state.engine.begin() as connection:
            for entry in (match, other):
                connection.execute(
                    text("UPDATE entries SET status='read' WHERE id=:id"), {"id": entry.entry_id}
                )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/entries",
                params={"type": "book", "key": "creators", "value": "julio cortazar"},
            )
    assert response.status_code == 200
    titles = [item["item"]["title"] for item in response.json()["items"]]
    assert titles == ["Rayuela"]


@pytest.mark.anyio
async def test_key_requires_exactly_one_type(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        service = LibraryService(app.state.engine)
        with pytest.raises(LibraryError) as refused:
            service.list_entries(types=[], key="creators", value="x")
    assert refused.value.status_code == 422


@pytest.mark.anyio
async def test_an_undeclared_key_is_refused(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        service = LibraryService(app.state.engine)
        with pytest.raises(LibraryError) as refused:
            service.list_entries(types=["book"], key="description", value="x")
    assert refused.value.code == "invalid_insight_key"


# --------------------------------------------------------------------------------------
# Sprint 071 deliverable 1: `list_shelves` gains up to three covers per shelf, the same
# lateral top-3 join DEC-134 built and benchmarked for insights rows.
# --------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_shelves_returns_up_to_three_covers_highest_scored_first(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        service = LibraryService(app.state.engine)
        shelf = service.create_shelf("Favorites")

        best = repository.create_or_get_entry(title="Best", creators=["Author"])
        middling = repository.create_or_get_entry(title="Middling", creators=["Author"])
        weakest = repository.create_or_get_entry(title="Weakest", creators=["Author"])
        uncovered = repository.create_or_get_entry(title="Uncovered", creators=["Author"])
        for entry, score in ((best, 9), (middling, 6), (weakest, 2), (uncovered, 8)):
            with app.state.engine.begin() as connection:
                connection.execute(
                    text("UPDATE entries SET status='read', score=:score WHERE id=:id"),
                    {"score": score, "id": entry.entry_id},
                )
        for entry in (best, middling, weakest):
            repository.set_cover_path(entry.item_id, f"{entry.item_id}.jpg")

        for entry in (best, middling, weakest, uncovered):
            service.update_entry(entry.entry_id, {"shelf_ids": [shelf["id"]]})

        shelves = service.list_shelves()
        row = next(row for row in shelves if row["id"] == shelf["id"])
        assert len(row["covers"]) == 3
        item_ids = [int(url.split("/")[3]) for url in row["covers"]]
        assert item_ids == [best.item_id, middling.item_id, weakest.item_id]
        assert uncovered.item_id not in item_ids


@pytest.mark.anyio
async def test_a_shelf_with_no_covered_members_returns_an_empty_list(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        service = LibraryService(app.state.engine)
        shelf = service.create_shelf("Favorites")
        entry = repository.create_or_get_entry(title="Uncovered", creators=["Author"])
        service.update_entry(entry.entry_id, {"shelf_ids": [shelf["id"]]})

        shelves = service.list_shelves()
        row = next(row for row in shelves if row["id"] == shelf["id"])
        assert row["covers"] == []


@pytest.mark.anyio
async def test_an_empty_shelf_returns_an_empty_covers_list(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        service = LibraryService(app.state.engine)
        shelf = service.create_shelf("Empty")

        shelves = service.list_shelves()
        row = next(row for row in shelves if row["id"] == shelf["id"])
        assert row["covers"] == []


# --------------------------------------------------------------------------------------
# Sprint 073 deliverable 4: `score_distribution` — the one backend addition, a
# `GROUP BY score` over the same filtered set `rank()` ranks.
# --------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_score_distribution_counts_by_score_and_the_unrated_tail(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        service = LibraryService(app.state.engine)
        eight_a = repository.create_or_get_entry(title="A", creators=["X"])
        eight_b = repository.create_or_get_entry(title="B", creators=["X"])
        three = repository.create_or_get_entry(title="C", creators=["X"])
        unrated = repository.create_or_get_entry(title="D", creators=["X"])
        service.update_entry(eight_a.entry_id, {"status": "read", "score": 8})
        service.update_entry(eight_b.entry_id, {"status": "read", "score": 8})
        service.update_entry(three.entry_id, {"status": "read", "score": 3})
        service.update_entry(unrated.entry_id, {"status": "read"})

        distribution = service.score_distribution(item_type="book")

        assert len(distribution["counts"]) == 10
        assert distribution["counts"][7] == 2  # index 7 == score 8
        assert distribution["counts"][2] == 1  # index 2 == score 3
        assert sum(distribution["counts"]) == 3
        assert distribution["rated_count"] == 3
        assert distribution["unrated_count"] == 1
        assert distribution["type"] == "book"


@pytest.mark.anyio
async def test_score_distribution_honours_type_and_the_four_filters(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        service = LibraryService(app.state.engine)

        book = repository.create_or_get_entry(
            title="Rayuela", creators=["Julio Cortázar"], item_type="book"
        )
        album = repository.create_or_get_entry(
            title="Discovery", creators=["Daft Punk"], item_type="album"
        )
        service.update_entry(book.entry_id, {"status": "read", "score": 9})
        service.update_entry(album.entry_id, {"status": "owned", "score": 5})

        # type: an album's score never reaches a book's distribution.
        book_only = service.score_distribution(item_type="book")
        assert book_only["counts"][8] == 1
        assert sum(book_only["counts"]) == 1

        # status
        by_status = service.score_distribution(item_type="book", statuses=["reading"])
        assert sum(by_status["counts"]) == 0

        # shelf
        shelf = service.create_shelf("Favorites")
        by_shelf_absent = service.score_distribution(item_type="book", shelves=[shelf["slug"]])
        assert sum(by_shelf_absent["counts"]) == 0
        service.update_entry(book.entry_id, {"shelf_ids": [shelf["id"]]})
        by_shelf_present = service.score_distribution(item_type="book", shelves=[shelf["slug"]])
        assert sum(by_shelf_present["counts"]) == 1

        # format
        service.update_entry(book.entry_id, {"formats": ["physical"]})
        by_format_absent = service.score_distribution(item_type="book", formats=["digital"])
        assert sum(by_format_absent["counts"]) == 0
        by_format_present = service.score_distribution(item_type="book", formats=["physical"])
        assert sum(by_format_present["counts"]) == 1

        # q
        no_match = service.score_distribution(item_type="book", q="nonexistent")
        assert sum(no_match["counts"]) == 0
        match = service.score_distribution(item_type="book", q="rayuela")
        assert sum(match["counts"]) == 1
