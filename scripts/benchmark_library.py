#!/usr/bin/env python3
"""Measure library list latency against a 10,000-entry database.

Run from `backend/` so Alembic resolves:

    cd backend && UV_CACHE_DIR=/tmp/akasha-uv-cache uv run python ../scripts/benchmark_library.py

The point of this script is a verdict, not a number. `LibraryService.list_entries`
orders `title` and `sort_author` through the connection-level `normalize_text`
function (DEC-015), which no index can serve; DEC-015 deferred a stored normalized
projection "until measurement shows text sorting needs it". This is that
measurement, so every scenario prints its SQLite query plan next to its latency.

Two conditions are measured because the queue has a producer now (DEC-027):

* **idle** — nothing else touching the database;
* **contended** — a background thread draining the job queue through the real
  `JobRepository`, so every sample competes for the SQLite write lock.

The contended condition deliberately drives the queue's *database* traffic rather
than real enrichment: provider I/O happens outside the write lock by DEC-007, so
the lock contention a large import produces is claim/heartbeat/complete, which is
exactly what the drainer here performs.

Budgets under test come from technical-spec section 1: first library page p95
under 500 ms at 10,000 entries, local mutations p95 under 200 ms.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from sqlalchemy import Engine, text  # noqa: E402

from book_tracker.application.library import LibraryService  # noqa: E402
from book_tracker.config import Settings  # noqa: E402
from book_tracker.database import create_engine  # noqa: E402
from book_tracker.infrastructure.jobs import JobRepository  # noqa: E402
from book_tracker.migrations import upgrade  # noqa: E402

PAGE_SIZE = 100
FIRST_PAGE_BUDGET_MS = 500.0
SORTS = ("date_added", "score", "title", "sort_author", "year", "date_finished")
STATUSES = ("read", "reading", "to_read", "wishlist", "dropped", "unsorted")

# Accented, mixed-script, and long titles, because `normalize_text` is a Unicode
# fold and benchmarking it over pure ASCII would measure the wrong function.
TITLE_STEMS = (
    "Cien años de soledad",
    "Rayuela",
    "La invención de Morel",
    "Ficciones",
    "El Aleph",
    "Pedro Páramo",
    "Los detectives salvajes",
    "Ædificium",
    "Żywot człowieka poczciwego",
    "Übermorgen",
)
AUTHOR_STEMS = (
    "García Márquez, Gabriel",
    "Cortázar, Julio",
    "Bioy Casares, Adolfo",
    "Borges, Jorge Luis",
    "Rulfo, Juan",
    "Bolaño, Roberto",
    "Ọkpara, Chinụa",
    "Šalamun, Tomaž",
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def seed(engine: Engine, count: int) -> None:
    """Insert `count` items and entries with a realistic spread of nulls.

    Nulls matter: `list_entries` sorts through a `CASE` bucket that pushes them
    last, so a fixture without them measures a query the application never runs.
    """
    now = _now_iso()
    items: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        title = f"{TITLE_STEMS[index % len(TITLE_STEMS)]} {index:05d}"
        author = AUTHOR_STEMS[index % len(AUTHOR_STEMS)]
        metadata = {"authors": [author], "publisher": f"Editorial {index % 97}"}
        items.append(
            {
                "id": index,
                "type": "book",
                "title": title,
                "subtitle": None,
                # One year in eleven is unknown.
                "year": None if index % 11 == 0 else 1900 + (index % 126),
                "cover_path": None,
                "identifiers": "{}",
                "metadata": json.dumps(metadata),
                "created_at": now,
                "updated_at": now,
            }
        )
        status = STATUSES[index % len(STATUSES)]
        finished = None if status != "read" else f"2026-0{1 + index % 9}-1{index % 10}"
        entries.append(
            {
                "id": index,
                "user_id": 1,
                "item_id": index,
                "status": status,
                # One score in seven is unset, matching a library with unrated books.
                "score": None if index % 7 == 0 else 1 + (index % 10),
                "notes": None,
                "date_added": f"2026-0{1 + index % 9}-0{1 + index % 9}T00:00:0{index % 10}Z",
                "date_started": None,
                "date_finished": finished,
                "reread_count": 0,
                "score_provisional": index % 3 == 0,
                "suggested_status": None,
                "created_at": now,
                "updated_at": now,
            }
        )

    # Coprime with the status cycle so a shelf filter is not implicitly a status filter.
    shelf_count = 13
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO items (id, type, title, subtitle, year, cover_path,"
                " identifiers, metadata, created_at, updated_at)"
                " VALUES (:id, :type, :title, :subtitle, :year, :cover_path,"
                " :identifiers, :metadata, :created_at, :updated_at)"
            ),
            items,
        )
        connection.execute(
            text(
                "INSERT INTO entries (id, user_id, item_id, status, score, notes,"
                " date_added, date_started, date_finished, reread_count,"
                " score_provisional, suggested_status, created_at, updated_at)"
                " VALUES (:id, :user_id, :item_id, :status, :score, :notes,"
                " :date_added, :date_started, :date_finished, :reread_count,"
                " :score_provisional, :suggested_status, :created_at, :updated_at)"
            ),
            entries,
        )
        connection.execute(
            text(
                "INSERT INTO shelves (id, user_id, name, slug, created_at, updated_at)"
                " VALUES (:id, 1, :name, :slug, :created_at, :updated_at)"
            ),
            [
                {
                    "id": shelf,
                    "name": f"Shelf {shelf}",
                    "slug": f"shelf-{shelf}",
                    "created_at": now,
                    "updated_at": now,
                }
                for shelf in range(1, shelf_count + 1)
            ],
        )
        connection.execute(
            text("INSERT INTO entry_shelves (entry_id, shelf_id) VALUES (:entry_id, :shelf_id)"),
            [
                {"entry_id": index, "shelf_id": 1 + (index % shelf_count)}
                for index in range(1, count + 1)
            ],
        )
        connection.execute(text("ANALYZE"))


class QueueDrainer:
    """Drains the job queue through the real repository in a background thread.

    Every claim/heartbeat/complete is a `BEGIN IMMEDIATE` write, which is the
    contention a draining import queue actually produces against a read.
    """

    def __init__(self, engine: Engine, jobs: int) -> None:
        self.repository = JobRepository(engine)
        self.jobs = jobs
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.completed = 0

    def _run(self) -> None:
        while not self._stop.is_set():
            now = datetime.now(UTC)
            claimed = self.repository.claim(now)
            if claimed is None:
                # Requeue so contention lasts for the whole measurement window
                # rather than stopping once the seeded backlog clears.
                self.repository.enqueue(None, "enrich_item", {"item_id": self.completed % 100 + 1})
                continue
            self.repository.heartbeat(claimed.id, datetime.now(UTC))
            self.repository.complete(claimed.id, {"ok": True}, datetime.now(UTC))
            self.completed += 1

    def __enter__(self) -> "QueueDrainer":
        for index in range(self.jobs):
            self.repository.enqueue(None, "enrich_item", {"item_id": index + 1})
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=10)


def percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def measure(run: Callable[[], object], iterations: int) -> tuple[float, float, float]:
    run()  # warm the connection pool and page cache
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        run()
        samples.append((time.perf_counter() - started) * 1000)
    return (
        statistics.median(samples),
        percentile(samples, 0.95),
        max(samples),
    )


def deep_cursor(service: LibraryService, sort: str, order: str, pages: int) -> str | None:
    """Walk forward `pages` pages so the deep-page sample is a real cursor."""
    cursor: str | None = None
    for _ in range(pages):
        page = service.list_entries(sort=sort, order=order, after=cursor, limit=PAGE_SIZE)
        cursor = page.get("next_cursor")
        if cursor is None:
            break
    return cursor


def scenarios(service: LibraryService) -> Iterator[tuple[str, Callable[[], object]]]:
    for sort in SORTS:
        for order in ("asc", "desc"):
            yield (
                f"first page   sort={sort:<13} order={order}",
                lambda sort=sort, order=order: service.list_entries(  # type: ignore[misc]
                    sort=sort, order=order, limit=PAGE_SIZE
                ),
            )
    for sort in ("date_added", "title", "sort_author"):
        cursor = deep_cursor(service, sort, "desc", pages=25)
        yield (
            f"page 26      sort={sort:<13} order=desc",
            lambda sort=sort, cursor=cursor: service.list_entries(  # type: ignore[misc]
                sort=sort, order="desc", after=cursor, limit=PAGE_SIZE
            ),
        )
    yield (
        "text filter  q=soledad     order=desc",
        lambda: service.list_entries(q="soledad", sort="date_added", limit=PAGE_SIZE),
    )
    yield (
        "text filter  q=garcia      sort=sort_author",
        lambda: service.list_entries(q="garcia", sort="sort_author", limit=PAGE_SIZE),
    )
    yield (
        "shelf+status sort=title    order=asc",
        lambda: service.list_entries(
            statuses=["read"], shelves=["shelf-3"], sort="title", order="asc", limit=PAGE_SIZE
        ),
    )


def query_plans(engine: Engine, service: LibraryService) -> list[tuple[str, list[str]]]:
    """Compile each sort's real statement and ask SQLite how it will run it."""
    from sqlalchemy.dialects import sqlite

    plans: list[tuple[str, list[str]]] = []
    for sort in SORTS:
        query = service._filtered_entries(None, (), None)  # noqa: SLF001
        expression = {
            "date_added": "entries.date_added",
            "score": "entries.score",
            "title": "normalize_text(items.title)",
            "sort_author": "normalize_text(items.sort_author)",
            "year": "items.year",
            "date_finished": "entries.date_finished",
        }[sort]
        compiled = query.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True})
        statement = (
            f"{compiled} ORDER BY CASE WHEN ({expression}) IS NULL THEN 1 ELSE 0 END,"
            f" {expression} DESC, entries.id DESC LIMIT {PAGE_SIZE + 1}"
        )
        with engine.connect() as connection:
            rows = connection.execute(text(f"EXPLAIN QUERY PLAN {statement}")).all()
        plans.append((sort, [str(row[-1]) for row in rows]))
    return plans


def run(count: int, iterations: int, jobs: int) -> int:
    with tempfile.TemporaryDirectory(prefix="akasha-benchmark-") as directory:
        data_dir = Path(directory)
        settings = Settings(data_dir=data_dir)
        assert settings.database_url is not None
        upgrade(settings.database_url)
        engine = create_engine(settings)
        started = time.perf_counter()
        seed(engine, count)
        seconds = time.perf_counter() - started
        service = LibraryService(engine)
        total = service.list_entries(limit=1)["total"]

        print(f"akasha library benchmark — {count} entries seeded in {seconds:.1f}s")
        print(f"database: {settings.database_url}")
        print(f"non-unsorted entries visible to the default list: {total}")
        print(f"iterations per scenario: {iterations}\n")

        print("QUERY PLANS (first page, descending)")
        for sort, plan in query_plans(engine, service):
            print(f"  sort={sort}")
            for line in plan:
                print(f"    {line}")
        print()

        breaches: list[str] = []
        for label, condition in (("idle", None), (f"contended ({jobs} jobs queued)", jobs)):
            print(f"LATENCY — {label}")
            print(f"  {'scenario':<46}{'p50 ms':>10}{'p95 ms':>10}{'max ms':>10}")
            drainer = QueueDrainer(engine, condition) if condition else None
            context: Any = drainer if drainer else _NullContext()
            with context:
                for name, callable_ in scenarios(service):
                    p50, p95, worst = measure(callable_, iterations)
                    flag = "" if p95 < FIRST_PAGE_BUDGET_MS else "  OVER BUDGET"
                    if flag:
                        breaches.append(f"{label}: {name} p95={p95:.1f}ms")
                    print(f"  {name:<46}{p50:>10.1f}{p95:>10.1f}{worst:>10.1f}{flag}")
            if drainer:
                print(f"  jobs drained during measurement: {drainer.completed}")
            print()

        print(f"BUDGET (technical-spec section 1): first library page p95 < {FIRST_PAGE_BUDGET_MS:.0f} ms")
        if breaches:
            print("VERDICT: over budget")
            for breach in breaches:
                print(f"  {breach}")
            return 1
        print("VERDICT: every scenario is within budget")
        return 0


class _NullContext:
    def __enter__(self) -> "_NullContext":
        return self

    def __exit__(self, *_: object) -> None:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=int, default=10_000)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--jobs", type=int, default=200)
    arguments = parser.parse_args()
    return run(arguments.entries, arguments.iterations, arguments.jobs)


if __name__ == "__main__":
    raise SystemExit(main())
