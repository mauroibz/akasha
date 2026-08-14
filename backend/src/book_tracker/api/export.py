"""The export routes.

Streamed rather than buffered, for the reason the attachment download is
(Sprint 022): the deployment target is a ZimaBoard and a whole-library dump is
the same class of object. `StreamingResponse` over a generator keeps peak memory
flat against library size, which the sprint requires be measured rather than
asserted.
"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from book_tracker.application.export import export_json

router = APIRouter(prefix="/api")


@router.get("/export")
async def export(request: Request) -> StreamingResponse:
    return StreamingResponse(
        export_json(request.app.state.engine),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="akasha-export.json"'},
    )
