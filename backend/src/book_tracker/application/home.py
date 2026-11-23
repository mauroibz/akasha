"""Home, read in one go (Sprints 130-131, DEC-183).

Home is the screen Akasha opens on: what is under way, what is next, the year, one
tile per library, and since Sprint 131 what happened lately, what needs tidying, one
question, shelves and loans. Every module reads stored data only -- no provider is
consulted while a page renders -- and the whole screen is one request. A module the
person hid is not read at all.

Shared layer: no domain or status is named here. Under way, waiting and finished come
from each domain's `StatusSpec` flags; whether a domain can hold a goal comes from its
`entry_fields`; which domains exist comes from the registry.
"""

from collections import defaultdict
from collections.abc import Sequence, Set
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.goals import GoalService
from book_tracker.application.library import LibraryService
from book_tracker.application.ranking import rank_pile
from book_tracker.domain.registry import DOMAINS

#: How deep *Up next* goes.
NEXT_LIMIT = 5
#: Covers returned per month of the year; `count` still counts them all.
MONTH_COVERS = 24
#: Covers on a library tile.
TILE_COVERS = 3
#: Rows in *Lately* at its largest; eight at its default size.
LATELY_LIMIT = 10
#: Shelves in the *Shelves* module.
SHELF_LIMIT = 8
#: Loans listed in *Lent out*; `total` still counts them all.
LENT_LIMIT = 5
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

    def home(self, today: date, hidden: Set[str] = frozenset()) -> dict[str, Any]:
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
        # The greeting names what is under way, so this is read even when On now is hidden.
        now = self.library.now()

        def shown(module: str) -> bool:
            return module not in hidden

        return {
            "greeting": self._greeting(today, now, by_status, finished, goals),
            "now": now if shown("now") else [],
            "next": self._next(today) if shown("next") else [],
            "year": self._year(today, finished, goals) if shown("year") else None,
            "domains": self._domains(by_status, histogram, best) if shown("libraries") else [],
            "lately": self._lately() if shown("lately") else None,
            "tidy": self._tidy() if shown("tidy") else None,
            "question": self._question() if shown("question") else None,
            "shelves": self._shelves() if shown("shelves") else None,
            "lent": self._lent() if shown("lent") else None,
        }

    def _lately(self) -> list[dict[str, Any]]:
        """Finishes, score changes and additions, newest first (Sprint 131).

        Finishes and changes are the Diary's own timeline. Additions are counted per
        day, newest entry named, so an import of three hundred is one row, not eight;
        the Inbox's unsorted entries are left to the Inbox.
        """
        timeline = self.library.timeline(limit=LATELY_LIMIT)["events"]
        with self.engine.connect() as connection:
            days = connection.execute(
                text(
                    "SELECT day, n, entry_id, at FROM ("
                    " SELECT substr(e.date_added, 1, 10) AS day, e.id AS entry_id,"
                    "  e.date_added AS at, count(*) OVER (PARTITION BY substr(e.date_added, 1, 10))"
                    "  AS n, row_number() OVER (PARTITION BY substr(e.date_added, 1, 10)"
                    "  ORDER BY e.date_added DESC, e.id DESC) AS place"
                    " FROM entries e WHERE e.user_id = :user AND e.status != :unsorted"
                    ") WHERE place = 1 ORDER BY day DESC LIMIT :limit"
                ),
                {"user": self.user_id, "unsorted": UNSORTED, "limit": LATELY_LIMIT},
            ).all()
        added = self.library.get_entries([row[2] for row in days])
        rows: list[dict[str, Any]] = [
            {
                "kind": event["kind"],
                "at": event["at"],
                "entry": event["entry"],
                "score": event["score"],
                "previous": event["previous"],
                "count": 1,
            }
            for event in timeline
            if event["entry"]["status"] != UNSORTED
        ]
        rows.extend(
            {"kind": "added", "at": at, "entry": entry, "score": None, "previous": None, "count": n}
            for (_day, n, _entry_id, at), entry in zip(days, added, strict=True)
        )
        rows.sort(key=lambda row: str(row["at"]), reverse=True)
        return rows[:LATELY_LIMIT]

    def _tidy(self) -> dict[str, Any]:
        """What *Tidy up* counts: pairs, entries without a cover, finished but unscored.

        The cover count is the covers deck's own filter (the Inbox aside). The unscored
        count is each domain's declared finished status with no score, per domain as
        well, because the library it links to opens one domain at a time.
        """
        finished = [
            (domain.item_type, status.value)
            for domain in DOMAINS.values()
            for status in domain.statuses
            if status.finished
        ]
        params: dict[str, Any] = {"user": self.user_id, "unsorted": UNSORTED}
        clauses = []
        for index, (item_type, status) in enumerate(finished):
            params[f"type{index}"] = item_type
            params[f"status{index}"] = status
            clauses.append(f"(i.type = :type{index} AND e.status = :status{index})")
        unscored = f"sum(e.score IS NULL AND ({' OR '.join(clauses)}))" if clauses else "0"
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT i.type, sum(i.cover_path IS NULL OR i.cover_path = ''),"
                    f" {unscored} FROM entries e JOIN items i ON i.id = e.item_id"
                    " WHERE e.user_id = :user AND e.status != :unsorted GROUP BY i.type"
                ),
                params,
            ).all()
        by_type = {item_type: count or 0 for item_type, _covers, count in rows}
        return {
            "duplicates": self.library.duplicate_count(),
            "without_cover": sum(covers or 0 for _type, covers, _count in rows),
            "unscored": sum(by_type.values()),
            "unscored_by_type": {
                item_type: by_type[item_type] for item_type in DOMAINS if by_type.get(item_type)
            },
        }

    def _question(self) -> dict[str, Any] | None:
        """One question from Play: an old score to look at again, else a gap to fill."""
        cards = self.library.revisit(limit=1)["cards"]
        if cards:
            return {
                "kind": "revisit",
                "entry": cards[0]["entry"],
                "scored_at": cards[0]["scored_at"],
            }
        gaps = self.library.gaps(limit=1)["entries"]
        if gaps:
            return {"kind": "gap", "entry": gaps[0], "scored_at": None}
        return None

    def _shelves(self) -> list[dict[str, Any]]:
        """Shelves holding something, the one whose members were touched last first.

        A membership has no timestamp of its own, so a member's own last change is the
        nearest signal of a shelf in use.
        """
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT s.id, s.name, s.slug, count(*), max(e.updated_at)"
                    " FROM shelves s JOIN entry_shelves es ON es.shelf_id = s.id"
                    " JOIN entries e ON e.id = es.entry_id"
                    " WHERE s.user_id = :user GROUP BY s.id"
                    " ORDER BY max(e.updated_at) DESC, count(*) DESC, s.id LIMIT :limit"
                ),
                {"user": self.user_id, "limit": SHELF_LIMIT},
            ).all()
        return [
            {"id": shelf_id, "name": name, "slug": slug, "entry_count": count}
            for shelf_id, name, slug, count, _used in rows
        ]

    def _lent(self) -> dict[str, Any]:
        """What is out now, longest out first."""
        loans = self.library.loans(open_only=True)
        return {
            "total": len(loans),
            "loans": [
                {
                    "id": loan["id"],
                    "person": loan["person"],
                    "lent_on": loan["lent_on"],
                    "entry": loan["entry"],
                }
                for loan in loans[:LENT_LIMIT]
            ],
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
        mine = self._goals(goals)
        active, goal = _greeting_pair(now, mine)
        return {
            "today": today.isoformat(),
            "active": {"entry": active, "day": _day_of(active, today)} if active else None,
            "entries": sum(row[2] for row in by_status if row[0] in DOMAINS),
            "pile": sum(row[2] for row in by_status if (row[0], row[1]) in planned),
            "goals": [
                {
                    "item_type": goal["item_type"],
                    "target": _target(goal),
                    "count": done.get(goal["item_type"], 0),
                }
            ]
            if goal
            else [],
        }

    def _goals(self, goals: GoalService) -> list[dict[str, Any]]:
        """This person's goals, in registry order, for domains that still exist."""
        mine = {goal["item_type"]: goal for goal in goals.list_goals()}
        return [mine[item_type] for item_type in DOMAINS if item_type in mine]

    def _next(self, today: date) -> list[dict[str, Any]]:
        """Five from the pile, every library's ranked together (Sprint 132)."""
        ranked = rank_pile(self.engine, self.user_id, None, NEXT_LIMIT, today=today)
        entries = self.library.get_entries([pick["entry_id"] for pick in ranked])
        return [
            {"entry": entry, "score": pick["score"], "reasons": pick["reasons"]}
            for pick, entry in zip(ranked, entries, strict=True)
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


def _greeting_pair(
    now: list[dict[str, Any]], goals: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """What the greeting names and the goal beside it, always of one library.

    The first goal (registry order) whose library has something under way names that
    library's most recently touched entry. Without one, the most recently touched entry
    overall, beside its own library's goal if it has one. With nothing under way, the
    lead goal alone.
    """
    for goal in goals:
        for entry in now:
            if entry["item"]["type"] == goal["item_type"]:
                return entry, goal
    if now:
        lead = now[0]
        own = next((goal for goal in goals if goal["item_type"] == lead["item"]["type"]), None)
        return lead, own
    return None, goals[0] if goals else None


def _done_by_type(finished: Sequence[Any]) -> dict[str, int]:
    done: dict[str, int] = defaultdict(int)
    for row in finished:
        done[row[2]] += 1
    return done


def _target(goal: dict[str, Any]) -> int:
    count: int = goal["count"]
    return count * 12 if goal["period"] == "month" else count
