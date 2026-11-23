"""Home, read in one go (Sprint 130, DEC-183).

Home is the screen Akasha opens on: what is under way, what is next, the year, and
one tile per library. Every module reads stored data only -- no provider is consulted
while a page renders -- and the whole screen is one request.

Shared layer: no domain or status is named here. Under way, waiting and finished come
from each domain's `StatusSpec` flags; whether a domain can hold a goal comes from its
`entry_fields`; which domains exist comes from the registry.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.goals import GoalService
from book_tracker.application.library import LibraryService
from book_tracker.domain.registry import DOMAINS

#: How deep *Up next* goes.
NEXT_LIMIT = 5
#: Covers returned per month of the year; `count` still counts them all.
MONTH_COVERS = 24
#: Covers on a library tile.
TILE_COVERS = 3
#: The status every domain has for what an import left unsorted (technical spec 6.6).
#: The library hides it by default, so Home's counts do too.
UNSORTED = "unsorted"


def _cover_url(item_id: int, cover_path: str | None, updated_at: str) -> str | None:
    if not cover_path:
        return None
    return f"/api/items/{item_id}/cover?v={updated_at.replace(':', '').replace('-', '')}"


def _cover(row: Any) -> dict[str, Any]:
    entry_id, item_id, item_type, title, cover_path, updated_at, score = row[:7]
    return {
        "entry_id": entry_id,
        "item_id": item_id,
        "item_type": item_type,
        "title": title,
        "cover_url": _cover_url(item_id, cover_path, updated_at),
        "score": score,
    }


def _day_of(entry: dict[str, Any], today: date) -> int | None:
    """ "Day N of …": 1 on the day it started, or `None` without a usable start date."""
    started = entry.get("date_started")
    if not started:
        return None
    try:
        start = date.fromisoformat(str(started)[:10])
    except ValueError:
        return None
    day = (today - start).days + 1
    return day if day >= 1 else None


class HomeService:
    def __init__(self, engine: Engine, user_id: int, library: LibraryService) -> None:
        self.engine = engine
        self.user_id = user_id
        self.library = library

    def home(self, today: date) -> dict[str, Any]:
        params = {"user": self.user_id, "unsorted": UNSORTED}
        with self.engine.connect() as connection:
            by_status = connection.execute(
                text(
                    "SELECT i.type, e.status, count(*), count(e.score), sum(e.score),"
                    " sum(i.cover_path IS NULL)"
                    " FROM entries e JOIN items i ON i.id = e.item_id"
                    " WHERE e.user_id = :user AND e.status != :unsorted GROUP BY 1, 2"
                ),
                params,
            ).all()
            histogram = connection.execute(
                text(
                    "SELECT i.type, e.score, count(*) FROM entries e"
                    " JOIN items i ON i.id = e.item_id"
                    " WHERE e.user_id = :user AND e.status != :unsorted"
                    " AND e.score IS NOT NULL GROUP BY 1, 2"
                ),
                params,
            ).all()
            best = connection.execute(
                text(
                    "SELECT entry_id, item_id, type, title, cover_path, updated_at, score FROM ("
                    " SELECT e.id AS entry_id, i.id AS item_id, i.type, i.title, i.cover_path,"
                    " i.updated_at, e.score, row_number() OVER (PARTITION BY i.type"
                    "  ORDER BY e.score IS NULL, e.score DESC, e.date_finished IS NULL,"
                    "  e.date_finished DESC, e.id DESC) AS rank"
                    " FROM entries e JOIN items i ON i.id = e.item_id"
                    " WHERE e.user_id = :user AND e.status != :unsorted"
                    " AND i.cover_path IS NOT NULL"
                    ") WHERE rank <= :covers ORDER BY type, rank"
                ),
                {**params, "covers": TILE_COVERS},
            ).all()
            finished = connection.execute(
                text(
                    "SELECT e.id, i.id, i.type, i.title, i.cover_path, i.updated_at, e.score,"
                    " CAST(substr(e.date_finished, 6, 2) AS INTEGER)"
                    " FROM entries e JOIN items i ON i.id = e.item_id"
                    " WHERE e.user_id = :user AND e.date_finished LIKE :prefix"
                    " ORDER BY e.date_finished, e.id"
                ),
                {"user": self.user_id, "prefix": f"{today.year:04d}-%"},
            ).all()

        goals = GoalService(self.engine, self.user_id)
        now = self.library.now()
        return {
            "greeting": self._greeting(today, now, by_status, finished, goals),
            "now": now,
            "next": self._next(goals),
            "year": self._year(today, finished, goals),
            "domains": self._domains(by_status, histogram, best),
        }

    def _greeting(
        self,
        today: date,
        now: list[dict[str, Any]],
        by_status: Sequence[Any],
        finished: Sequence[Any],
        goals: GoalService,
    ) -> dict[str, Any]:
        planned = {
            (domain.item_type, status.value)
            for domain in DOMAINS.values()
            for status in domain.statuses
            if status.planned
        }
        done = _done_by_type(finished)
        return {
            "today": today.isoformat(),
            "active": {"entry": now[0], "day": _day_of(now[0], today)} if now else None,
            "entries": sum(row[2] for row in by_status if row[0] in DOMAINS),
            "pile": sum(row[2] for row in by_status if (row[0], row[1]) in planned),
            "goals": [
                {
                    "item_type": goal["item_type"],
                    "target": _target(goal),
                    "count": done.get(goal["item_type"], 0),
                }
                for goal in self._goals(goals)
            ],
        }

    def _goals(self, goals: GoalService) -> list[dict[str, Any]]:
        """This person's goals, in registry order, for domains that still exist."""
        mine = {goal["item_type"]: goal for goal in goals.list_goals()}
        return [mine[item_type] for item_type in DOMAINS if item_type in mine]

    def _next(self, goals: GoalService) -> list[dict[str, Any]]:
        """Five from the pile: each domain's goal-picks order, the domains taken in turn.

        A placeholder order until Sprint 132 ranks the pile.
        """
        queues = [
            goals.pick_reasons(item_type, limit=NEXT_LIMIT)
            for item_type, domain in DOMAINS.items()
            if any(status.planned for status in domain.statuses)
        ]
        chosen: list[dict[str, Any]] = []
        while len(chosen) < NEXT_LIMIT and any(queues):
            for queue in queues:
                if queue and len(chosen) < NEXT_LIMIT:
                    chosen.append(queue.pop(0))
        entries = self.library.get_entries([pick["entry_id"] for pick in chosen])
        return [
            {
                "entry": entry,
                "reason": pick["reason"],
                "creator": pick.get("creator"),
                "mean_score": pick.get("mean_score"),
                "since": pick.get("since"),
            }
            for pick, entry in zip(chosen, entries, strict=True)
        ]

    def _year(self, today: date, finished: Sequence[Any], goals: GoalService) -> dict[str, Any]:
        months: list[dict[str, Any]] = [
            {"month": month, "count": 0, "counts": {}, "covers": []} for month in range(1, 13)
        ]
        for row in finished:
            month = row[7]
            if not month or not 1 <= month <= 12:
                continue
            bucket = months[month - 1]
            bucket["count"] += 1
            bucket["counts"][row[2]] = bucket["counts"].get(row[2], 0) + 1
            if len(bucket["covers"]) < MONTH_COVERS:
                bucket["covers"].append(_cover(row))
        done = _done_by_type(finished)
        return {
            "year": today.year,
            "months": months,
            "goals": [
                {
                    "item_type": goal["item_type"],
                    "period": goal["period"],
                    "count": goal["count"],
                    "target": _target(goal),
                    "done": done.get(goal["item_type"], 0),
                }
                for goal in self._goals(goals)
            ],
        }

    @staticmethod
    def _domains(
        by_status: Sequence[Any], histogram: Sequence[Any], best: Sequence[Any]
    ) -> list[dict[str, Any]]:
        statuses: dict[str, dict[str, int]] = defaultdict(dict)
        rated: dict[str, int] = defaultdict(int)
        total: dict[str, int] = defaultdict(int)
        coverless: dict[str, int] = defaultdict(int)
        for item_type, status, count, scored, score_sum, without in by_status:
            statuses[item_type][status] = count
            rated[item_type] += scored
            total[item_type] += score_sum or 0
            coverless[item_type] += without or 0
        scores: dict[str, list[int]] = defaultdict(lambda: [0] * 10)
        for item_type, score, count in histogram:
            if 1 <= score <= 10:
                scores[item_type][score - 1] = count
        covers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in best:
            covers[row[2]].append(_cover(row))
        tiles = []
        for item_type, domain in DOMAINS.items():
            counts = statuses.get(item_type)
            if not counts:
                continue
            ordered = {
                status.value: counts[status.value]
                for status in domain.statuses
                if status.value in counts
            }
            tiles.append(
                {
                    "item_type": item_type,
                    "count": sum(counts.values()),
                    "status_counts": ordered,
                    "scores": scores[item_type],
                    "mean_score": round(total[item_type] / rated[item_type], 2)
                    if rated[item_type]
                    else None,
                    "covers": covers[item_type],
                    "without_cover": coverless[item_type],
                }
            )
        return tiles


def _done_by_type(finished: Sequence[Any]) -> dict[str, int]:
    done: dict[str, int] = defaultdict(int)
    for row in finished:
        done[row[2]] += 1
    return done


def _target(goal: dict[str, Any]) -> int:
    count: int = goal["count"]
    return count * 12 if goal["period"] == "month" else count
