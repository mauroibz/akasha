"""The one seam where synchronous work leaves the event loop (Sprint 059).

Every handler in this application is `async def`, and until this sprint every
SQLite write, Pillow decode/resize and disk write ran directly on the event loop
regardless — Phase A measured a large import commit stalling every other request
for the whole call (`docs/decisions.md`, the Sprint 059 verdict). This module is
deliberately the *only* place that crosses a thread boundary: grepping for
`off_loop` finds every path Phase A named, and a later reader adding a new one
finds this comment rather than a second helper.

Bounded rather than anyio's own default limiter (40 threads): this application has
exactly one writer process and one SQLite file, so a burst of offloaded work does
not go faster for having more threads — it only queues more writers behind the
same `PRAGMA busy_timeout` (`database.py`). Four keeps a couple of imports or a
backfill from serializing behind each other while bounding worst-case thread and
connection fan-out on a machine sized like the one this ships for (technical
spec §4: a ZimaBoard-class home server, not a pool of cores to spend).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

import anyio

OFFLOAD_WORKERS = 4

_limiter = anyio.CapacityLimiter(OFFLOAD_WORKERS)


async def off_loop[**P, T](func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Run a synchronous callable on a worker thread, bounded by `OFFLOAD_WORKERS`."""
    return await anyio.to_thread.run_sync(partial(func, *args, **kwargs), limiter=_limiter)
