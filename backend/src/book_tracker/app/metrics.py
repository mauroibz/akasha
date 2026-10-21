"""`/metrics` in Prometheus text format, when `AKASHA_METRICS=on` (Sprint 101).

Written by hand rather than through a client library: five families, all read from
state the application already keeps (the jobs table, the provider observations, the
request timings), so a dependency would add more than it saved.
"""

from collections import defaultdict

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from book_tracker.config import Settings


class RequestTimings:
    """Count and total seconds per method, route template and status."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, int], list[float]] = defaultdict(lambda: [0, 0.0])

    def record(self, method: str, route: str, status: int, seconds: float) -> None:
        row = self._rows[(method, route, status)]
        row[0] += 1
        row[1] += seconds

    def rows(self) -> list[tuple[str, str, int, int, float]]:
        return [
            (method, route, status, int(count), total)
            for (method, route, status), (count, total) in sorted(self._rows.items())
        ]


def _label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render(app: FastAPI) -> str:
    lines: list[str] = []
    with app.state.engine.connect() as connection:
        queued = connection.execute(
            text(
                "SELECT state, COUNT(*) FROM jobs"
                " WHERE state IN ('queued', 'running') GROUP BY state"
            )
        ).all()
        outcomes = connection.execute(
            text("SELECT kind, state, COUNT(*) FROM jobs GROUP BY kind, state ORDER BY kind, state")
        ).all()
    depth = dict(queued)
    lines += [
        "# HELP akasha_job_queue_depth Jobs waiting or running.",
        "# TYPE akasha_job_queue_depth gauge",
    ]
    for state in ("queued", "running"):
        lines.append(f'akasha_job_queue_depth{{state="{state}"}} {depth.get(state, 0)}')
    lines += ["# HELP akasha_jobs Jobs on record by kind and state.", "# TYPE akasha_jobs gauge"]
    for kind, state, count in outcomes:
        lines.append(f'akasha_jobs{{kind="{_label(kind)}",state="{_label(state)}"}} {count}')

    totals = app.state.provider_observations.totals()
    lines += [
        "# HELP akasha_provider_calls_total Provider calls by outcome since start.",
        "# TYPE akasha_provider_calls_total counter",
    ]
    for name, (ok, error, _seconds) in sorted(totals.items()):
        lines.append(f'akasha_provider_calls_total{{provider="{_label(name)}",outcome="ok"}} {ok}')
        lines.append(
            f'akasha_provider_calls_total{{provider="{_label(name)}",outcome="error"}} {error}'
        )
    lines += [
        "# HELP akasha_provider_call_seconds Time spent in provider calls.",
        "# TYPE akasha_provider_call_seconds summary",
    ]
    for name, (ok, error, seconds) in sorted(totals.items()):
        lines.append(f'akasha_provider_call_seconds_sum{{provider="{_label(name)}"}} {seconds:.6f}')
        lines.append(
            f'akasha_provider_call_seconds_count{{provider="{_label(name)}"}} {ok + error}'
        )

    lines += [
        "# HELP akasha_request_seconds API request latency by route template.",
        "# TYPE akasha_request_seconds summary",
    ]
    for method, route, status, count, seconds in app.state.request_timings.rows():
        labels = f'method="{method}",route="{_label(route)}",status="{status}"'
        lines.append(f"akasha_request_seconds_sum{{{labels}}} {seconds:.6f}")
        lines.append(f"akasha_request_seconds_count{{{labels}}} {count}")
    return "\n".join(lines) + "\n"


def install_metrics(app: FastAPI, configured: Settings) -> None:
    app.state.request_timings = RequestTimings()
    if configured.metrics != "on":
        return

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(render(app), media_type="text/plain; version=0.0.4")
