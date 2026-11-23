"""Gentle goals (Sprint 103, DEC-169).

A goal is a count per month or per year for one domain. It is something to aim at,
never something to keep up with: progress is a count of finished entries by month,
months count together, and nothing here computes "behind". Picks are the domain's
ranked pile (Sprint 132), each with the reasons it was picked.

Shared layer: no status or domain is named here. `planned` comes from `StatusSpec`,
and whether a domain can have a goal at all comes from its `entry_fields`.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.library import LibraryError, LibraryService
from book_tracker.application.ranking import rank_pile
from book_tracker.domain.registry import DOMAINS

Period = Literal["month", "year"]


class GoalError(LibraryError):
    """A refusal from the goals layer, in the shared error envelope."""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class GoalService:
    def __init__(self, engine: Engine, user_id: int) -> None:
        self.engine = engine
        self.user_id = user_id

    def _supported(self, item_type: str) -> None:
        domain = DOMAINS.get(item_type)
        if domain is None or "date_finished" not in domain.entry_fields:
            raise GoalError(
                "goal_not_supported",
                "A goal counts finish dates, and this library records none",
                status_code=422,
                details={"item_type": item_type},
            )

    def list_goals(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT item_type, count, period, suggest FROM goals "
                    "WHERE user_id = :user ORDER BY item_type"
                ),
                {"user": self.user_id},
            ).all()
        return [_goal(row) for row in rows]

    def _goal_for(self, item_type: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT item_type, count, period, suggest FROM goals "
                    "WHERE user_id = :user AND item_type = :type"
                ),
                {"user": self.user_id, "type": item_type},
            ).first()
        return _goal(row) if row is not None else None

    def set_goal(
        self, item_type: str, *, count: int, period: Period, suggest: bool
    ) -> dict[str, Any]:
        """Set this domain's goal; setting it again replaces it."""
        self._supported(item_type)
        if not 1 <= count <= 999:
            raise GoalError(
                "validation_error",
                "A goal is between 1 and 999",
                status_code=422,
                details={"field": "count"},
            )
        now = _now()
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO goals (user_id, item_type, count, period, suggest, created_at, "
                    "updated_at) VALUES (:user, :type, :count, :period, :suggest, :now, :now) "
                    "ON CONFLICT (user_id, item_type) DO UPDATE SET count = excluded.count, "
                    "period = excluded.period, suggest = excluded.suggest, "
                    "updated_at = excluded.updated_at"
                ),
                {
                    "user": self.user_id,
                    "type": item_type,
                    "count": count,
                    "period": period,
                    "suggest": suggest,
                    "now": now,
                },
            )
        return {"item_type": item_type, "count": count, "period": period, "suggest": suggest}

    def delete_goal(self, item_type: str) -> None:
        with self.engine.begin() as connection:
            deleted = connection.execute(
                text("DELETE FROM goals WHERE user_id = :user AND item_type = :type"),
                {"user": self.user_id, "type": item_type},
            ).rowcount
        if not deleted:
            raise GoalError("goal_not_found", "There is no goal for this library", status_code=404)

    def progress(self, item_type: str, year: int) -> dict[str, Any]:
        """Finished entries in `year`, by month. `target` is the year's whole aim.

        A monthly goal's target is twelve months of it: a slow month leaves room that
        a later one fills, which is the whole of "you can catch up".
        """
        self._supported(item_type)
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT CAST(substr(e.date_finished, 6, 2) AS INTEGER), count(*) "
                    "FROM entries e JOIN items i ON i.id = e.item_id "
                    "WHERE e.user_id = :user AND i.type = :type "
                    "AND e.date_finished LIKE :prefix GROUP BY 1"
                ),
                {"user": self.user_id, "type": item_type, "prefix": f"{year:04d}-%"},
            ).all()
        months = [0] * 12
        for month, count in rows:
            if month and 1 <= month <= 12:
                months[month - 1] = count
        goal = self._goal_for(item_type)
        target = None
        if goal is not None:
            target = goal["count"] * 12 if goal["period"] == "month" else goal["count"]
        return {
            "item_type": item_type,
            "year": year,
            "months": months,
            "total": sum(months),
            "target": target,
        }

    def picks(self, item_type: str, *, limit: int = 6) -> list[dict[str, Any]]:
        """This library's pile, ranked, each pick with its reasons (Sprint 132).

        The ranked pile (`application/ranking.py`) replaced the two orders this used
        to alternate, a favourite creator's and the longest waiting: both are signals
        of the ranking now, beside a series, a subject and what was set aside.
        """
        self._supported(item_type)
        ranked = rank_pile(self.engine, self.user_id, item_type, limit)
        entries = LibraryService(self.engine, self.user_id).get_entries(
            [pick["entry_id"] for pick in ranked]
        )
        return [
            {"entry": entry, "score": pick["score"], "reasons": pick["reasons"]}
            for pick, entry in zip(ranked, entries, strict=True)
        ]


def _goal(row: Any) -> dict[str, Any]:
    return {"item_type": row[0], "count": row[1], "period": row[2], "suggest": bool(row[3])}
