#!/usr/bin/env python3
"""Measure first-library-page latency while a real background task runs.

Sprint 059, Phase A. Every handler in `backend/src/book_tracker/` is `async def`, and
no synchronous work — a bulk import commit, a Pillow decode/resize, a chunked disk
write and hash — has ever left the event loop. `scripts/benchmark_library.py` measures
SQLite write-lock contention against a synthetic drainer running in the same process;
it says nothing about whether the loop itself stalls, because it never runs the real
ASGI server and never issues a second concurrent HTTP request while the first is being
handled. This script does exactly that: it drives one of three realistic background
tasks against a **running** Akasha server over real HTTP, while a second client polls
`GET /api/entries` (the first library page) in a tight loop and records the latency
distribution it sees.

Run against a server already listening (built and started by
`scripts/measure_event_loop.sh`, which also applies the CPU constraint and watches the
container's own Docker healthcheck):

    uv run --project backend python scripts/measure_event_loop.py \\
        --base-url http://127.0.0.1:18080 --scenario import

Three scenarios, matching the sprint's Required context:

* **import**    — a Goodreads CSV commit of `--rows` books. Exercises
  `ImportService.commit`'s synchronous per-record writes.
* **covers**    — repeated cover uploads (`POST /api/items/{id}/cover`), exercising the
  same `PIL` decode/convert/resize/save `prepare_uploaded_cover` calls the enrichment
  backfill's `prepare_cover` makes; enrichment itself waits on real provider network
  the harness cannot reproduce, so the CPU-bound half of that path is measured directly
  here, the same way DEC-036's harness measured SQLite contention through the queue's
  DB traffic rather than real provider I/O.
* **attachment** — repeated large-file uploads (`POST /api/items/{id}/attachments`),
  exercising `BlobWriter`'s chunked hash-and-write.

Each scenario first seeds a realistic-size library (a Goodreads import, unmeasured)
before its own timed background task begins, except **import** itself, whose seed *is*
the measured operation.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

import httpx

FIRST_PAGE_BUDGET_MS = 500.0
# A Goodreads commit lands every row as `unsorted` (Triage) rather than sorted into the
# library — real usage triages it away over time, which this synthetic seed never does.
# `list_entries` excludes `unsorted` when no status filter is given (`application/library.py`
# line ~640), so the un-triaged default view of a freshly-seeded library is always empty.
# Asking for `unsorted` explicitly reaches the seeded rows through the same query path —
# same sort, same pagination, same cursor — which is what this harness needs, not a
# specific status mix.
LIBRARY_PAGE_PARAMS = {"limit": 100, "status": "unsorted"}
GOODREADS_HEADER = [
    "Book Id",
    "Title",
    "Author",
    "Additional Authors",
    "ISBN",
    "ISBN13",
    "My Rating",
    "Publisher",
    "Number of Pages",
    "Year Published",
    "Original Publication Year",
    "Date Read",
    "Date Added",
    "Bookshelves",
    "Exclusive Shelf",
    "My Review",
    "Read Count",
]


def _isbn13(sequence: int) -> str:
    """A valid ISBN-13 check digit, same formula as `domain/identity.py::_isbn10_to_13`."""
    prefix = f"978{sequence:09d}"
    check = (10 - sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(prefix)) % 10) % 10
    return f"{prefix}{check}"


def goodreads_csv(rows: int) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(GOODREADS_HEADER)
    for index in range(1, rows + 1):
        writer.writerow(
            [
                str(10_000 + index),
                f"Event Loop Drill {index:06d}",
                "Sprint Fifty-Nine",
                "",
                '=""',
                f'="{_isbn13(index)}"',
                "0",
                "Akasha Press",
                "300",
                "2020",
                "2020",
                "",
                "2026/01/01",
                "to-read",
                "to-read",
                "",
                "0",
            ]
        )
    return buffer.getvalue().encode("utf-8")


def jpeg_bytes(seed: int) -> bytes:
    """A real, decodable JPEG — a solid color plus a seed-derived pixel so no two are
    byte-identical, which matters for `BlobWriter`'s content addressing."""
    from PIL import Image

    image = Image.new("RGB", (900, 1200), (seed % 256, (seed * 7) % 256, (seed * 13) % 256))
    output = io.BytesIO()
    image.save(output, "JPEG", quality=90)
    return output.getvalue()


def percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


@dataclass
class Sampler:
    """Polls the first library page on a background thread until told to stop."""

    client: httpx.Client
    samples: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.perf_counter()
            try:
                response = self.client.get("/api/entries", params=LIBRARY_PAGE_PARAMS)
                response.raise_for_status()
            except httpx.HTTPError as error:
                self.errors.append(str(error))
                continue
            finally:
                self.samples.append((time.perf_counter() - started) * 1000)
            time.sleep(0.02)

    def __enter__(self) -> "Sampler":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        assert self._thread is not None
        self._thread.join(timeout=30)


class HealthWatcher:
    """Polls a container's own Docker healthcheck status while a scenario runs.

    `docker inspect` is the same signal an operator's `docker compose ps` shows, and
    it is what acceptance criterion 5 is actually about — a client-side timing of
    `/api/health/ready` proves the endpoint is slow, not that Docker ever acted on it.
    """

    def __init__(self, container: str | None, interval: float = 1.0) -> None:
        self.container = container
        self.interval = interval
        self.statuses: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                status = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        "{{.State.Health.Status}}",
                        self.container,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=True,
                ).stdout.strip()
                self.statuses.append(status)
            except (subprocess.SubprocessError, OSError):
                pass
            self._stop.wait(self.interval)

    def __enter__(self) -> "HealthWatcher":
        if self.container:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def ever_unhealthy(self) -> bool:
        return "unhealthy" in self.statuses


def wait_healthy(client: httpx.Client, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = client.get("/api/health/ready", timeout=5.0)
            if response.status_code == 200:
                return
        except httpx.HTTPError as error:
            last_error = error
        time.sleep(1.0)
    raise RuntimeError(f"server never became ready: {last_error}")


def warm_up(client: httpx.Client) -> None:
    """One untimed page request: connection-pool setup and query-plan compilation are
    real costs, but they are paid once per process lifetime, not once per request —
    counting the first one in the sample would measure process startup, not the
    background task's interference."""
    client.get("/api/entries", params=LIBRARY_PAGE_PARAMS)


def commit_goodreads_import(client: httpx.Client, rows: int) -> str:
    """Preview then commit a synthetic Goodreads export. Returns the batch id."""
    csv_bytes = goodreads_csv(rows)
    preview = client.post(
        "/api/import/goodreads/preview",
        files={"file": ("goodreads_library_export.csv", csv_bytes, "text/csv")},
        timeout=120.0,
    )
    preview.raise_for_status()
    batch_id = preview.json()["batch_id"]
    commit = client.post(
        "/api/import/goodreads/commit",
        json={"batch_id": batch_id, "choices": []},
        timeout=300.0,
    )
    commit.raise_for_status()
    return batch_id


def first_item_ids(client: httpx.Client, count: int) -> list[int]:
    """Up to 200 item ids — `/api/entries`' own page-size ceiling — good enough to
    cycle through for a repeated-write scenario that does not need every seeded row."""
    response = client.get(
        "/api/entries",
        params={"limit": min(count, 200), "sort": "date_added", "order": "asc", "status": "unsorted"},
    )
    response.raise_for_status()
    return [entry["item"]["id"] for entry in response.json()["items"]]


def run_import_scenario(client: httpx.Client, sampler: Sampler, rows: int) -> float:
    started = time.perf_counter()
    with sampler:
        commit_goodreads_import(client, rows)
    return time.perf_counter() - started


def run_covers_scenario(
    client: httpx.Client, sampler: Sampler, seed_rows: int, min_duration: float, max_ops: int
) -> tuple[float, int]:
    commit_goodreads_import(client, seed_rows)
    item_ids = first_item_ids(client, seed_rows)
    installed = 0
    started = time.perf_counter()
    with sampler:
        while (time.perf_counter() - started) < min_duration and installed < max_ops:
            item_id = item_ids[installed % len(item_ids)]
            response = client.post(
                f"/api/items/{item_id}/cover",
                files={"cover": ("cover.jpg", jpeg_bytes(installed), "image/jpeg")},
                timeout=30.0,
            )
            response.raise_for_status()
            installed += 1
    return time.perf_counter() - started, installed


def run_attachment_scenario(
    client: httpx.Client,
    sampler: Sampler,
    seed_rows: int,
    file_mb: int,
    min_duration: float,
    max_ops: int,
) -> tuple[float, int]:
    commit_goodreads_import(client, seed_rows)
    item_id = first_item_ids(client, 1)[0]
    uploaded = 0
    started = time.perf_counter()
    with sampler:
        while (time.perf_counter() - started) < min_duration and uploaded < max_ops:
            payload = os.urandom(file_mb * 1024 * 1024)
            response = client.post(
                f"/api/items/{item_id}/attachments",
                files={"file": (f"attachment-{uploaded}.bin", payload, "application/octet-stream")},
                timeout=60.0,
            )
            response.raise_for_status()
            uploaded += 1
    return time.perf_counter() - started, uploaded


def report(scenario: str, sampler: Sampler, background_seconds: float, extra: str) -> bool:
    samples = sampler.samples
    print(f"\nSCENARIO: {scenario}")
    print(f"  background task: {background_seconds:.2f}s   {extra}")
    print(f"  library-page samples during the task: {len(samples)}   errors: {len(sampler.errors)}")
    if not samples:
        print("  NO SAMPLES — background task finished before a single page request landed")
        return False
    p50 = statistics.median(samples)
    p95 = percentile(samples, 0.95)
    worst = max(samples)
    within_budget = p95 < FIRST_PAGE_BUDGET_MS
    flag = "" if within_budget else "  OVER BUDGET"
    print(f"  first-page latency   p50={p50:.1f}ms  p95={p95:.1f}ms  max={worst:.1f}ms{flag}")
    if sampler.errors:
        print(f"  sample errors (first 3): {sampler.errors[:3]}")
    return within_budget and not sampler.errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--scenario", choices=["import", "covers", "attachment"], required=True)
    parser.add_argument("--cpus", default="unconstrained", help="Label only — printed, not enforced here.")
    parser.add_argument("--container", default=None, help="Container name/id to watch via `docker inspect`.")
    parser.add_argument("--rows", type=int, default=5000, help="Library size for the import scenario / seed.")
    parser.add_argument("--seed-rows", type=int, default=3000, help="Seed size for covers/attachment.")
    parser.add_argument("--cover-count", type=int, default=300)
    parser.add_argument("--min-duration", type=float, default=5.0)
    parser.add_argument("--attachment-mb", type=int, default=20)
    parser.add_argument("--attachment-count", type=int, default=20)
    arguments = parser.parse_args()

    with httpx.Client(base_url=arguments.base_url, timeout=30.0) as client:
        wait_healthy(client)
        warm_up(client)
        print(f"akasha event-loop benchmark — scenario={arguments.scenario} cpus={arguments.cpus}")
        sampler = Sampler(client=httpx.Client(base_url=arguments.base_url))
        watcher = HealthWatcher(arguments.container)
        with watcher:
            if arguments.scenario == "import":
                seconds = run_import_scenario(client, sampler, arguments.rows)
                extra = f"rows={arguments.rows}"
            elif arguments.scenario == "covers":
                seconds, count = run_covers_scenario(
                    client, sampler, arguments.seed_rows, arguments.min_duration, arguments.cover_count
                )
                extra = f"covers installed={count} (seed={arguments.seed_rows})"
            else:
                seconds, count = run_attachment_scenario(
                    client,
                    sampler,
                    arguments.seed_rows,
                    arguments.attachment_mb,
                    arguments.min_duration,
                    arguments.attachment_count,
                )
                extra = f"uploads={count} x {arguments.attachment_mb}MiB (seed={arguments.seed_rows})"
        sampler.client.close()

        ok = report(arguments.scenario, sampler, seconds, extra)
        if watcher.ever_unhealthy():
            print(f"  DOCKER HEALTH: reported unhealthy at some point ({watcher.statuses})")
            ok = False
        elif arguments.container:
            print(f"  docker health samples: {watcher.statuses}")

        print(f"\nBUDGET: first library page p95 < {FIRST_PAGE_BUDGET_MS:.0f} ms, and no unhealthy report")
        print("VERDICT: within budget" if ok else "VERDICT: over budget or unhealthy")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
