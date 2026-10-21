"""`GET /api/events`: the current person's jobs as Server-Sent Events (Sprint 089).

The import page used to poll its preview every two seconds, and nothing else in the
application could tell that background work was running. One stream per open tab now
carries every change to that person's jobs. The server reads the jobs table once a
second per connection, which on a single-user home server costs less than the polls
it replaces; a connection lives for `event_stream_seconds` and then ends, and the
browser's EventSource reconnects by itself, so no connection outlives its welcome.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from book_tracker.api.identity import CurrentUser
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.offload import off_loop

router = APIRouter(prefix="/api", tags=["events"])

#: How long one connection lives before the browser reconnects.
DEFAULT_STREAM_SECONDS = 300.0
POLL_SECONDS = 1.0
KEEPALIVE_SECONDS = 15.0


@router.get("/events", response_class=StreamingResponse, response_model=None)
async def events(request: Request, user: CurrentUser) -> StreamingResponse:
    lifetime = float(getattr(request.app.state, "event_stream_seconds", DEFAULT_STREAM_SECONDS))
    repo = JobRepository(request.app.state.engine)
    user_id = user.effective_user_id

    async def stream() -> AsyncIterator[str]:
        deadline = time.monotonic() + lifetime
        last_sent = time.monotonic()
        cursor: str | None = None
        # `since` is inclusive so two changes in the same microsecond are both seen;
        # what was already sent at the cursor's moment is not sent twice.
        sent_at_cursor: set[tuple[str, str]] = set()
        yield "retry: 3000\n\n"
        while time.monotonic() < deadline:
            if await request.is_disconnected():
                return
            for job in await off_loop(repo.changes_for_user, user_id, since=cursor):
                key = (job["id"], job["updated_at"])
                if key in sent_at_cursor:
                    continue
                if job["updated_at"] != cursor:
                    sent_at_cursor.clear()
                cursor = job["updated_at"]
                sent_at_cursor.add(key)
                last_sent = time.monotonic()
                yield f"event: job\ndata: {json.dumps(job, ensure_ascii=False)}\n\n"
            if time.monotonic() - last_sent > KEEPALIVE_SECONDS:
                last_sent = time.monotonic()
                yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
