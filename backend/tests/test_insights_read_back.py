"""Sprint 102: the insights page read back as prose.

The summary that carries the lead sentence, subjects folded across provider
qualifiers, and grouping values with nothing to say (`{'`) left out.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from test_insights import _fixture


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _finish(fx: object, entry_id: int, day: str) -> None:
    with fx.app.state.engine.begin() as connection:  # type: ignore[attr-defined]
        connection.execute(
            text("UPDATE entries SET date_finished=:day WHERE id=:id"), {"day": day, "id": entry_id}
        )


@pytest.mark.anyio
async def test_subjects_fold_a_trailing_general_qualifier(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        spellings = ["Fiction", "Fiction, general", "FICTION / General", "Fiction / Literary"]
        for index, subject in enumerate(spellings):
            created = fx.repository.create_or_get_entry(title=f"T{index}", creators=["A"])
            fx.set_status(created.entry_id, "read")
            fx.set_metadata_field(created.item_id, "subjects", [subject])

        result = fx.service.rank(item_type="book", key="subjects", metric="count")

        by_key = {row["key"]: row for row in result["rows"]}
        assert by_key["fiction"]["count"] == 3
        assert by_key["fiction"]["label"] == "Fiction"
        # A real second level is a different subject, not a qualifier.
        assert by_key["fiction literary"]["count"] == 1

        # The folded row still opens the library on all three of its members.
        listed = fx.service.list_entries(
            statuses=None, shelves=[], types=["book"], key="subjects", value="fiction"
        )
        assert len(listed["items"]) == 3


@pytest.mark.anyio
async def test_a_value_with_no_letters_or_digits_is_not_a_row(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        broken = fx.repository.create_or_get_entry(title="Broken", creators=["A"])
        fine = fx.repository.create_or_get_entry(title="Fine", creators=["B"])
        for entry in (broken, fine):
            fx.set_status(entry.entry_id, "read")
        fx.set_metadata_field(broken.item_id, "language", "{'")
        fx.set_metadata_field(fine.item_id, "language", "es")

        result = fx.service.rank(item_type="book", key="language", metric="count")

        assert [row["key"] for row in result["rows"]] == ["es"]


@pytest.mark.anyio
async def test_summary_carries_the_lead_sentence_figures(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        rows = [("Old", 1955, 8, "2026-01-02"), ("Mid", 1990, 8, None), ("New", 2015, 6, None)]
        made = []
        for title, year, score, finished in rows:
            created = fx.repository.create_or_get_entry(title=title, creators=["A"])
            fx.set_status(created.entry_id, "read")
            fx.set_year(created.item_id, year)
            fx.set_score(created.entry_id, score)
            if finished:
                _finish(fx, created.entry_id, finished)
            made.append(created)
        unrated = fx.repository.create_or_get_entry(title="Unrated", creators=["B"])
        fx.set_status(unrated.entry_id, "to_read")

        summary = fx.service.insight_summary(item_type="book")

        assert summary == {
            "type": "book",
            "held": 4,
            "finished": 1,
            "rated": 3,
            "unrated": 1,
            "modal_score": 8,
            "earliest": {"entry_id": made[0].entry_id, "title": "Old", "year": 1955},
        }

        # The same filters as every other insight: narrowed to `to_read`.
        narrowed = fx.service.insight_summary(item_type="book", statuses=["to_read"])
        assert narrowed["held"] == 1
        assert narrowed["modal_score"] is None
        assert narrowed["earliest"] is None


@pytest.mark.anyio
async def test_summary_route(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        created = fx.repository.create_or_get_entry(title="Only", creators=["A"])
        fx.set_status(created.entry_id, "read")
        transport = ASGITransport(app=fx.app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/insights/summary", params={"type": "book"})
            assert response.status_code == 200
            assert response.json()["held"] == 1
            refused = await client.get("/api/insights/summary", params={"type": "nope"})
            assert refused.status_code == 422
