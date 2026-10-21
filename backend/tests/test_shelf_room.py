"""Sprint 105: what the shelves room needs from GET /api/shelves.

A preview of each shelf's members (title, year, score, cover), and the two
figures its line of character reads: how many are finished, and the mean score.
"""

from pathlib import Path

import pytest
from sqlalchemy import text
from test_insights import _fixture


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_shelves_carry_a_preview_and_their_figures(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        shelf = fx.service.create_shelf("Latin American")
        empty = fx.service.create_shelf("Empty")
        made = []
        for index in range(10):
            created = fx.repository.create_or_get_entry(title=f"Book {index}", creators=["A"])
            fx.set_year(created.item_id, 1960 + index)
            made.append(created)
            fx.service.update_entry(created.entry_id, {"shelf_ids": [shelf["id"]]})
        fx.set_score(made[3].entry_id, 10)
        fx.set_score(made[7].entry_id, 6)
        with fx.app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET date_finished='2026-01-01' WHERE id IN (:a, :b)"),
                {"a": made[3].entry_id, "b": made[5].entry_id},
            )

        by_name = {row["name"]: row for row in fx.service.list_shelves()}

        room = by_name["Latin American"]
        assert room["finished_count"] == 2
        assert room["mean_score"] == 8.0
        preview = room["preview"]
        assert len(preview) == 8
        # Highest scored first, then the most recently added.
        assert [row["title"] for row in preview[:2]] == ["Book 3", "Book 7"]
        assert preview[0] == {
            "entry_id": made[3].entry_id,
            "title": "Book 3",
            "year": 1963,
            "score": 10,
            "cover_url": None,
        }
        assert by_name["Empty"]["preview"] == []
        assert by_name["Empty"]["finished_count"] == 0
        assert by_name["Empty"]["mean_score"] is None
        assert empty["name"] == "Empty"
