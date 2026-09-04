"""The export routes.

Streamed rather than buffered, for the reason the attachment download is
(Sprint 022): the deployment target is a ZimaBoard and a whole-library dump is
the same class of object. `StreamingResponse` over a generator keeps peak memory
flat against library size, which the sprint requires be measured rather than
asserted.

`GET /api/export` is the lossless JSON path (unchanged since Sprint 024) plus the
`?format=csv` alias. `GET /api/exports` and `GET /api/export/{view}` are Sprint
068's addition: the declared, registry-derived views every domain gets a door
through, the export analogue of `GET /api/importers`.
"""

from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from book_tracker.application.export import export_json, stream_export_view
from book_tracker.application.library import LibraryError
from book_tracker.domain.registry import REGISTERED_EXPORTS, ItemTypeName, find_export_view
from book_tracker.domains.book.goodreads import EXPORT as GOODREADS_EXPORT
from book_tracker.infrastructure.models import EntryRow, ItemRow

router = APIRouter(prefix="/api")


class ExportViewResponse(BaseModel):
    """One declared view, shaped like `ImporterResponse` (DEC-080's pattern, pointed
    the other way): a screen renders this without knowing which view it is holding."""

    id: str
    label: str
    item_types: list[str]
    media_type: str
    lossless: bool
    guide: list[str]
    help_url: str | None = None
    carries: list[str]
    #: How many entries this view would write for the library as it stands, summed
    #: over every domain it carries.
    count: int


@router.get("/export")
async def export(
    request: Request, format: Literal["json", "csv"] = Query(default="json")
) -> StreamingResponse:
    engine = request.app.state.engine
    if format == "csv":
        return StreamingResponse(
            stream_export_view(engine, GOODREADS_EXPORT, GOODREADS_EXPORT.item_types[0]),
            media_type=GOODREADS_EXPORT.media_type,
            headers={"Content-Disposition": f'attachment; filename="{GOODREADS_EXPORT.filename}"'},
        )
    return StreamingResponse(
        export_json(engine),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="akasha-export.json"'},
    )


@router.get("/exports", response_model=list[ExportViewResponse])
async def available_exports(request: Request) -> list[ExportViewResponse]:
    engine = request.app.state.engine
    with Session(engine) as session:
        counts: dict[str, int] = {}
        for item_type, count in session.execute(
            select(ItemRow.type, func.count(EntryRow.id))
            .join(EntryRow, EntryRow.item_id == ItemRow.id)
            .group_by(ItemRow.type)
        ).all():
            counts[item_type] = count
    return [
        ExportViewResponse(
            id=view.name,
            label=view.label,
            item_types=list(view.item_types),
            media_type=view.media_type,
            lossless=view.lossless,
            guide=list(view.guide),
            help_url=view.help_url,
            carries=list(view.carries),
            count=sum(counts.get(item_type, 0) for item_type in view.item_types),
        )
        for view in REGISTERED_EXPORTS
    ]


@router.get("/export/{view}")
async def export_view_route(view: str, request: Request, type: ItemTypeName) -> StreamingResponse:
    resolved = find_export_view(type.value, view)
    if resolved is None:
        raise LibraryError(
            "export_view_not_found",
            f"No export view named {view!r} for {type.value!r}",
            status_code=404,
        )
    engine = request.app.state.engine
    return StreamingResponse(
        stream_export_view(engine, resolved, type.value),
        media_type=resolved.media_type,
        headers={"Content-Disposition": f'attachment; filename="{resolved.filename}"'},
    )
