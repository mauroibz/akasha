"""Sprint 103: gentle goals, underneath (DEC-169).

A goal per person and domain, progress by month of finish date with months counting
together, and picks drawn from the domain's declared planned status.
"""

from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from test_insights import _fixture

from book_tracker.application.goals import GoalError, GoalService
from book_tracker.domain.registry import DOMAINS


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _set(fx: object, entry_id: int, **values: object) -> None:
    assignments = ", ".join(f"{name} = :{name}" for name in values)
    with fx.app.state.engine.begin() as connection:  # type: ignore[attr-defined]
        connection.execute(
            text(f"UPDATE entries SET {assignments} WHERE id = :id"), {**values, "id": entry_id}
        )


def _goals(fx: object) -> GoalService:
    return GoalService(fx.app.state.engine, 1)  # type: ignore[attr-defined]


def test_four_domains_declare_a_planned_status_and_albums_none() -> None:
    planned = {
        domain.item_type: [status.value for status in domain.statuses if status.planned]
        for domain in DOMAINS.values()
    }
    assert planned == {
        "book": ["to_read"],
        "album": [],
        "anime": ["plan_to_watch"],
        "movie": ["watchlist"],
        "series": ["plan_to_watch"],
    }


@pytest.mark.anyio
async def test_a_goal_round_trips(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        goals = _goals(fx)
        assert goals.list_goals() == []

        set_once = goals.set_goal("book", count=2, period="month", suggest=True)
        assert set_once == {"item_type": "book", "count": 2, "period": "month", "suggest": True}
        goals.set_goal("book", count=20, period="year", suggest=False)
        goals.set_goal("movie", count=4, period="month", suggest=True)
        assert goals.list_goals() == [
            {"item_type": "book", "count": 20, "period": "year", "suggest": False},
            {"item_type": "movie", "count": 4, "period": "month", "suggest": True},
        ]

        goals.delete_goal("movie")
        assert [goal["item_type"] for goal in goals.list_goals()] == ["book"]
        with pytest.raises(GoalError) as missing:
            goals.delete_goal("movie")
        assert missing.value.status_code == 404


@pytest.mark.anyio
async def test_a_domain_with_no_finish_date_cannot_have_a_goal(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        with pytest.raises(GoalError) as refused:
            _goals(fx).set_goal("album", count=1, period="month", suggest=True)
        assert refused.value.status_code == 422
        assert refused.value.code == "goal_not_supported"


@pytest.mark.anyio
async def test_progress_counts_by_month_of_finish_date(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        finished = [
            "2026-01-05",
            "2026-01-20",
            "2026-03-02",
            "2026-03-09",
            "2026-03-30",
            "2025-12-31",
        ]
        for index, day in enumerate(finished):
            created = fx.repository.create_or_get_entry(title=f"B{index}", creators=["A"])
            _set(fx, created.entry_id, status="read", date_finished=day)
        # Another domain's finish never counts toward a book goal.
        film = fx.repository.create_or_get_entry(title="Film", creators=["D"], item_type="movie")
        _set(fx, film.entry_id, status="watched", date_finished="2026-01-10")
        goals = _goals(fx)
        goals.set_goal("book", count=2, period="month", suggest=True)

        progress = goals.progress("book", 2026)

        assert progress == {
            "item_type": "book",
            "year": 2026,
            "months": [2, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "total": 5,
            "target": 24,
        }
        goals.set_goal("book", count=30, period="year", suggest=True)
        assert goals.progress("book", 2026)["target"] == 30


@pytest.mark.anyio
async def test_picks_come_from_the_planned_status_with_a_reason(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        # Two rated books by a favourite, so a waiting book by her is a creator pick.
        for title, score in (("Loved 1", 9), ("Loved 2", 8)):
            created = fx.repository.create_or_get_entry(title=title, creators=["Le Guin"])
            _set(fx, created.entry_id, status="read", score=score)
        favourite = fx.repository.create_or_get_entry(
            title="Waiting by Le Guin", creators=["Le Guin"]
        )
        oldest = fx.repository.create_or_get_entry(title="Waiting longest", creators=["Nobody"])
        newer = fx.repository.create_or_get_entry(title="Waiting less", creators=["Someone"])
        dropped = fx.repository.create_or_get_entry(title="Not planned", creators=["Le Guin"])
        _set(fx, favourite.entry_id, status="to_read", date_added="2026-05-01T00:00:00Z")
        _set(fx, oldest.entry_id, status="to_read", date_added="2023-03-01T00:00:00Z")
        _set(fx, newer.entry_id, status="to_read", date_added="2025-01-01T00:00:00Z")
        _set(fx, dropped.entry_id, status="dropped")

        picks = _goals(fx).picks("book", limit=5)

        assert [(pick["entry"]["item"]["title"], pick["reason"]) for pick in picks] == [
            ("Waiting by Le Guin", "creator"),
            ("Waiting longest", "waiting"),
            ("Waiting less", "waiting"),
        ]
        assert picks[0]["creator"] == "Le Guin"
        assert picks[0]["mean_score"] == 8.5
        assert picks[1]["since"] == "2023-03-01T00:00:00Z"
        assert _goals(fx).picks("book", limit=5) == picks


@pytest.mark.anyio
async def test_goal_routes_and_isolation(tmp_path: Path) -> None:
    async with _fixture(tmp_path) as fx:
        transport = httpx.ASGITransport(app=fx.app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            put = await client.put(
                "/api/goals/book", json={"count": 2, "period": "month", "suggest": True}
            )
            assert put.status_code == 200, put.text
            assert (await client.get("/api/goals")).json() == [put.json()]
            progress = await client.get("/api/goals/book/progress", params={"year": 2026})
            assert progress.json()["target"] == 24
            assert (await client.get("/api/goals/book/picks")).status_code == 200
            refused = await client.put(
                "/api/goals/album", json={"count": 1, "period": "month", "suggest": True}
            )
            assert refused.status_code == 422
            assert refused.json()["error"]["code"] == "goal_not_supported"
            too_many = await client.put(
                "/api/goals/book", json={"count": 0, "period": "month", "suggest": True}
            )
            assert too_many.status_code == 422
            assert (await client.delete("/api/goals/book")).status_code == 204
            assert (await client.get("/api/goals")).json() == []
        # Another person never sees one person's goal.
        _goals(fx).set_goal("book", count=2, period="month", suggest=True)
        assert GoalService(fx.app.state.engine, 2).list_goals() == []  # type: ignore[attr-defined]
