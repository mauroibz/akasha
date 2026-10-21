"""Gentle goals (Sprint 103, DEC-169).

A goal is a count per month or per year for one domain. It is something to aim at,
never something to keep up with: progress is a count of finished entries by month,
months count together, and nothing here computes "behind". Picks are entries waiting
in the domain's declared *planned* status, each with the reason it was picked.

Shared layer: no status or domain is named here. `planned` comes from `StatusSpec`,
and whether a domain can have a goal at all comes from its `entry_fields`.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.library import LibraryError, LibraryService
from book_tracker.domain.registry import DOMAINS

Period = Literal["month", "year"]

#: A creator whose average reaches this, over at least `CREATOR_RATINGS` rated
#: entries in the same domain, makes their waiting entries a *creator* pick.
CREATOR_MEAN = 8.0
CREATOR_RATINGS = 2


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
        """Waiting entries, each with why: a favourite creator's, or the longest waiting.

        The two orders alternate so neither reason crowds out the other, and both are
        total orders (ties break on entry id), so the same library gives the same picks.
        """
        self._supported(item_type)
        planned = [status.value for status in DOMAINS[item_type].statuses if status.planned]
        if not planned:
            return []
        marks = ", ".join(f":status{index}" for index in range(len(planned)))
        params: dict[str, Any] = {"user": self.user_id, "type": item_type}
        params.update({f"status{index}": value for index, value in enumerate(planned)})
        with self.engine.connect() as connection:
            favourites = connection.execute(
                text(
                    "SELECT e.id, i.creator_primary, fav.mean FROM entries e "
                    "JOIN items i ON i.id = e.item_id "
                    "JOIN (SELECT i2.creator_primary_normalized AS creator, avg(e2.score) AS mean "
                    "      FROM entries e2 JOIN items i2 ON i2.id = e2.item_id "
                    "      WHERE e2.user_id = :user AND i2.type = :type AND e2.score IS NOT NULL "
                    "      AND i2.creator_primary_normalized IS NOT NULL "
                    "      GROUP BY i2.creator_primary_normalized "
                    "      HAVING count(*) >= :ratings AND avg(e2.score) >= :mean) fav "
                    "  ON fav.creator = i.creator_primary_normalized "
                    f"WHERE e.user_id = :user AND i.type = :type AND e.status IN ({marks}) "
                    "ORDER BY fav.mean DESC, e.id ASC"
                ),
                {**params, "ratings": CREATOR_RATINGS, "mean": CREATOR_MEAN},
            ).all()
            waiting = connection.execute(
                text(
                    "SELECT e.id, e.date_added FROM entries e JOIN items i ON i.id = e.item_id "
                    f"WHERE e.user_id = :user AND i.type = :type AND e.status IN ({marks}) "
                    "ORDER BY e.date_added ASC, e.id ASC"
                ),
                params,
            ).all()
        creator_picks = [
            {
                "entry_id": row[0],
                "reason": "creator",
                "creator": row[1],
                "mean_score": round(row[2], 1),
            }
            for row in favourites
        ]
        waiting_picks = [
            {"entry_id": row[0], "reason": "waiting", "since": row[1]} for row in waiting
        ]
        chosen: list[dict[str, Any]] = []
        seen: set[int] = set()
        while (creator_picks or waiting_picks) and len(chosen) < limit:
            for source in (creator_picks, waiting_picks):
                while source and source[0]["entry_id"] in seen:
                    source.pop(0)
                if source and len(chosen) < limit:
                    pick = source.pop(0)
                    seen.add(pick["entry_id"])
                    chosen.append(pick)
        library = LibraryService(self.engine, self.user_id)
        return [
            {
                "entry": library.get_entry(pick["entry_id"]),
                "reason": pick["reason"],
                "creator": pick.get("creator"),
                "mean_score": pick.get("mean_score"),
                "since": pick.get("since"),
            }
            for pick in chosen
        ]


def _goal(row: Any) -> dict[str, Any]:
    return {"item_type": row[0], "count": row[1], "period": row[2], "suggest": bool(row[3])}
