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

import json
from collections import defaultdict
from collections.abc import Sequence, Set
from datetime import UTC, date, datetime, tzinfo
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.goals import GoalService
from book_tracker.application.library import LibraryService
from book_tracker.application.ranking import rank_pile
from book_tracker.application.recommendations import SuggestionStore
from book_tracker.domain.registry import DOMAINS

#: How deep *Up next* goes.
NEXT_LIMIT = 5
#: Rows in *Lately* at its largest; eight at its default size.
LATELY_LIMIT = 10
#: Suggestions on Home's *More like this*: the most its L size shows.
SUGGESTED = 8
#: Covers in a library's year (Sprint 138): a goal of 24 or fewer fills its slots, and
#: a year without a goal shows at most this many; `total` still counts them all.
YEAR_COVERS = 48
#: Covers on a shelf's module, its members changed last first.
SHELF_COVERS = 24
#: How much deeper the timeline and the pile are read when some media are out of the
#: front, so the band and Up next still fill from what is left.
FRONT_DEPTH = 8
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
    def __init__(
        self,
        engine: Engine,
        user_id: int,
        library: LibraryService,
        *,
        embedding_model: str | None = None,
    ) -> None:
        self.engine = engine
        self.user_id = user_id
        self.library = library
        #: The configured embedding endpoint's, for Up next's similarity (Sprint 136).
        self.embedding_model = embedding_model

    def home(
        self,
        today: date,
        hidden: Set[str] = frozenset(),
        zone: tzinfo = UTC,
        *,
        years: Sequence[str] = (),
        shelves: Sequence[str] = (),
        front: Set[str] | None = None,
    ) -> dict[str, Any]:
        """Every shown module's payload. `years` and `shelves` are the members of the two
        module families (Sprint 138) the person shows, in their order: item types, and
        shelf ids as the layout keys carry them. `front` is the media the person keeps in
        front (Sprint 143): what is under way, what happened lately, what is next and what
        the greeting names are theirs alone; `None` is every medium."""
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
        now = [entry for entry in self.library.now() if _in(front, entry)]

        def shown(module: str) -> bool:
            return module not in hidden

        return {
            "greeting": self._greeting(today, now, by_status, finished, goals, front),
            # The Library's two bands: layout items since Sprint 150, so a removed one
            # is not drawn. What is under way is read either way, for the greeting.
            "now": now if shown("now") else [],
            "next": self._next(today, front) if shown("next") else [],
            "lately": self._lately(zone, front) if shown("lately") else [],
            "question": self._question() if shown("question") else None,
            "suggested": self._suggested() if shown("suggested") else None,
            "library_years": self._library_years(today, years, finished, goals),
            "shelf_modules": self._shelf_modules(shelves),
        }

    def _library_years(
        self, today: date, years: Sequence[str], finished: Sequence[Any], goals: GoalService
    ) -> list[dict[str, Any]]:
        """Each shown library's year: what it finished, in order, and its goal if any.

        A library with neither a finish this year nor a goal is left out, so Home draws
        nothing for it.
        """
        mine = {goal["item_type"]: goal for goal in self._goals(goals)} if years else {}
        rows: list[dict[str, Any]] = []
        for item_type in years:
            domain = DOMAINS.get(item_type)
            if domain is None or "date_finished" not in domain.entry_fields:
                continue
            done = [row for row in finished if row[2] == item_type]
            goal = mine.get(item_type)
            if not done and goal is None:
                continue
            rows.append(
                {
                    "item_type": item_type,
                    "year": today.year,
                    "total": len(done),
                    "goal": None
                    if goal is None
                    else {
                        "item_type": item_type,
                        "period": goal["period"],
                        "count": goal["count"],
                        "target": _target(goal),
                        "done": len(done),
                    },
                    "covers": [_cover(row) for row in done[:YEAR_COVERS]],
                }
            )
        return rows

    def _shelf_modules(self, shelves: Sequence[str]) -> list[dict[str, Any]]:
        """Each shown shelf: its name, how many it holds, and the covers changed last."""
        ids = [int(shelf) for shelf in shelves if shelf.isdigit()]
        if not ids:
            return []
        params: dict[str, Any] = {"user": self.user_id, "covers": SHELF_COVERS}
        names = ", ".join(f":s{index}" for index in range(len(ids)))
        params.update({f"s{index}": shelf_id for index, shelf_id in enumerate(ids)})
        with self.engine.connect() as connection:
            heads = connection.execute(
                text(
                    "SELECT s.id, s.name, s.slug, count(es.entry_id) FROM shelves s"
                    " LEFT JOIN entry_shelves es ON es.shelf_id = s.id"
                    f" WHERE s.user_id = :user AND s.id IN ({names}) GROUP BY s.id"
                ),
                params,
            ).all()
            members = connection.execute(
                text(
                    "SELECT shelf_id, entry_id, item_id, type, title, cover_path, updated_at,"
                    " score FROM ("
                    " SELECT es.shelf_id, e.id AS entry_id, i.id AS item_id, i.type, i.title,"
                    " i.cover_path, i.updated_at, e.score, row_number() OVER ("
                    "  PARTITION BY es.shelf_id ORDER BY e.updated_at DESC, e.id DESC) AS place"
                    " FROM entry_shelves es JOIN entries e ON e.id = es.entry_id"
                    " JOIN items i ON i.id = e.item_id"
                    f" WHERE e.user_id = :user AND es.shelf_id IN ({names})"
                    ") WHERE place <= :covers ORDER BY shelf_id, place"
                ),
                params,
            ).all()
        covers: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in members:
            covers[row[0]].append(_cover(row[1:]))
        found = {
            shelf_id: {
                "id": shelf_id,
                "name": name,
                "slug": slug,
                "entry_count": count,
                "covers": covers[shelf_id],
            }
            for shelf_id, name, slug, count in heads
        }
        return [found[shelf_id] for shelf_id in ids if shelf_id in found]

    def _suggested(self) -> list[dict[str, Any]]:
        """*More like this*: the newest suggestions found and unanswered (Sprint 134).

        Stored rows only; no source and no provider is asked to render Home.
        """
        return SuggestionStore(self.engine, self.user_id).suggestions(
            seed_entry_id=None, item_type=None, limit=SUGGESTED, enriched_only=True
        )

    def _lately(self, zone: tzinfo = UTC, front: Set[str] | None = None) -> list[dict[str, Any]]:
        """Finishes, score changes and additions, newest first (Sprint 131).

        Finishes and changes are the Diary's own timeline. Additions are counted per
        day, newest entry named, so an import of three hundred is one row, not eight;
        the Inbox's unsorted entries are left to the Inbox. The day is the person's
        own (`zone`, Sprint 132): an evening import west of Greenwich is one day.
        """
        # With some media out of the front, read deeper so that what is left still fills
        # the band: the timeline is across every medium.
        depth = LATELY_LIMIT if front is None else LATELY_LIMIT * FRONT_DEPTH
        timeline = [
            event
            for event in self.library.timeline(limit=depth)["events"]
            if _in(front, event["entry"])
        ][:LATELY_LIMIT]
        days = self._days_added(zone, front)
        added = self.library.get_entries([entry_id for _n, entry_id, _at in days])
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
            for (n, _entry_id, at), entry in zip(days, added, strict=True)
        )
        rows.sort(key=lambda row: str(row["at"]), reverse=True)
        return rows[:LATELY_LIMIT]

    def _days_added(
        self, zone: tzinfo, front: Set[str] | None = None
    ) -> list[tuple[int, int, str]]:
        """`(count, newest entry id, newest date_added)` per local day, newest first.

        SQL counts per UTC hour, which a local day is made of whole in any zone on a
        whole-hour offset; each hour is placed by its newest addition, converted with
        the zone's own rules, so a change of clocks is honoured. A day-only
        `date_added` is that day wherever the person is.
        """
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT n, entry_id, at FROM ("
                    " SELECT e.id AS entry_id, e.date_added AS at,"
                    "  count(*) OVER (PARTITION BY substr(e.date_added, 1, 13)) AS n,"
                    "  row_number() OVER (PARTITION BY substr(e.date_added, 1, 13)"
                    "  ORDER BY e.date_added DESC, e.id DESC) AS place"
                    " FROM entries e JOIN items i ON i.id = e.item_id"
                    " WHERE e.user_id = :user AND e.status != :unsorted"
                    " AND (:every OR i.type IN (SELECT value FROM json_each(:types)))"
                    ") WHERE place = 1 ORDER BY at DESC, entry_id DESC LIMIT :hours"
                ),
                {
                    "user": self.user_id,
                    "unsorted": UNSORTED,
                    "every": front is None,
                    "types": json.dumps(sorted(front or ())),
                    # A local day is at most 25 UTC hours; one day more than shown.
                    "hours": 25 * (LATELY_LIMIT + 1),
                },
            ).all()
        days: dict[str, tuple[int, int, str]] = {}
        for count, entry_id, at in rows:
            day = _local_day(str(at), zone)
            # Hours come newest first, so a day's first hour names its newest entry.
            newest = days.get(day)
            days[day] = (
                (newest[0] + count, newest[1], newest[2]) if newest else (count, entry_id, at)
            )
        return list(days.values())[:LATELY_LIMIT]

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

    def _greeting(
        self,
        today: date,
        now: list[dict[str, Any]],
        by_status: Sequence[Any],
        finished: Sequence[Any],
        goals: GoalService,
        front: Set[str] | None = None,
    ) -> dict[str, Any]:
        planned = {
            (domain.item_type, status.value)
            for domain in DOMAINS.values()
            for status in domain.statuses
            if status.planned
        }
        done = _done_by_type(finished)
        mine = [goal for goal in self._goals(goals) if front is None or goal["item_type"] in front]
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

    def _next(self, today: date, front: Set[str] | None = None) -> list[dict[str, Any]]:
        """Five from the pile, every library's ranked together (Sprint 132); of the media
        in front only (Sprint 143), read deeper so the five are still five."""
        ranked = rank_pile(
            self.engine,
            self.user_id,
            None,
            NEXT_LIMIT if front is None else NEXT_LIMIT * FRONT_DEPTH,
            today=today,
            embedding_model=self.embedding_model,
        )
        entries = self.library.get_entries([pick["entry_id"] for pick in ranked])
        return [
            {"entry": entry, "score": pick["score"], "reasons": pick["reasons"]}
            for pick, entry in zip(ranked, entries, strict=True)
            if _in(front, entry)
        ][:NEXT_LIMIT]


def _in(front: Set[str] | None, entry: dict[str, Any]) -> bool:
    """Whether an entry's medium is in front; every medium is when none are named."""
    return front is None or entry["item"]["type"] in front


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


def _local_day(at: str, zone: tzinfo) -> str:
    """The person's day for a stored timestamp; a bare date is already a day."""
    if len(at) <= 10:
        return at[:10]
    try:
        moment = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        return at[:10]
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(zone).date().isoformat()


def _done_by_type(finished: Sequence[Any]) -> dict[str, int]:
    done: dict[str, int] = defaultdict(int)
    for row in finished:
        done[row[2]] += 1
    return done


def _target(goal: dict[str, Any]) -> int:
    count: int = goal["count"]
    return count * 12 if goal["period"] == "month" else count
