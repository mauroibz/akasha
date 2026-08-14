"""The export routes.

Streamed rather than buffered, for the reason the attachment download is
(Sprint 022): the deployment target is a ZimaBoard and a whole-library dump is
the same class of object. `StreamingResponse` over a generator keeps peak memory
flat against library size, which the sprint requires be measured rather than
asserted.
"""

from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from book_tracker.application.export import export_csv, export_json

router = APIRouter(prefix="/api")


@router.get("/export")
async def export(
    request: Request, format: Literal["json", "csv"] = Query(default="json")
) -> StreamingResponse:
    engine = request.app.state.engine
    if format == "csv":
        return StreamingResponse(
            export_csv(engine),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="akasha-export.csv"'},
        )
    return StreamingResponse(
        export_json(engine),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="akasha-export.json"'},
    )
