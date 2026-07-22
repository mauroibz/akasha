from typing import Annotated, Any

from fastapi import APIRouter, File, Request, UploadFile
from pydantic import BaseModel, Field

from book_tracker.application.imports import GoodreadsImportService
from book_tracker.application.library import LibraryError
from book_tracker.domain.goodreads import GoodreadsCSVError

router = APIRouter(prefix="/api/import/goodreads", tags=["imports"])
MAX_IMPORT_BYTES = 5 * 1024 * 1024


class ImportRecordResponse(BaseModel):
    record_id: int
    row_number: int
    goodreads_book_id: str
    title: str
    authors: list[str]
    isbn: str | None
    suggested_status: str | None
    score: int | None
    score_provisional: bool
    shelves: list[str]
    errors: list[dict[str, Any]]
    planned_action: str
    match_kind: str
    candidates: list[int]
    publisher: str | None = None
    page_count: int | None = None
    year: int | None = None
    original_year: int | None = None
    date_finished: str | None = None
    date_added: str | None = None
    review: str | None = None
    reread_count: int = 0


class PreviewSummary(BaseModel):
    total: int
    ready: int
    errors: int
    ambiguous: int


class PreviewResponse(BaseModel):
    batch_id: str
    fingerprint: str
    state: str
    summary: PreviewSummary
    records: list[ImportRecordResponse]


class AmbiguityChoice(BaseModel):
    record_id: int
    item_id: int | None = None


class CommitBody(BaseModel):
    batch_id: str
    choices: list[AmbiguityChoice] = Field(default_factory=list)


class CommitResponse(BaseModel):
    batch_id: str
    state: str
    created_items: int
    created_entries: int
    unchanged_entries: int


def service(request: Request) -> GoodreadsImportService:
    return GoodreadsImportService(request.app.state.engine, request.app.state.data_dir)


@router.post("/preview", status_code=201, response_model=PreviewResponse)
async def preview(request: Request, file: Annotated[UploadFile, File()]) -> PreviewResponse:
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(64 * 1024):
        size += len(chunk)
        if size > MAX_IMPORT_BYTES:
            raise LibraryError("import_too_large", "Goodreads CSV exceeds 5 MiB", status_code=413)
        chunks.append(chunk)
    try:
        result = service(request).preview(b"".join(chunks), file.filename or "goodreads.csv")
    except GoodreadsCSVError as error:
        raise LibraryError(
            error.code, str(error), status_code=422, details=error.details
        ) from error
    return PreviewResponse.model_validate(result)


@router.post("/commit", response_model=CommitResponse)
async def commit(body: CommitBody, request: Request) -> CommitResponse:
    try:
        result = service(request).commit(
            body.batch_id,
            {choice.record_id: choice.model_dump(exclude={"record_id"}) for choice in body.choices},
        )
    except LookupError as error:
        raise LibraryError(
            "import_batch_not_found", "Import preview was not found", status_code=404
        ) from error
    except ValueError as error:
        code = "unresolved_ambiguities" if str(error).startswith("[") else str(error)
        raise LibraryError(code, "Import preview cannot be committed", status_code=409) from error
    return CommitResponse.model_validate(result)
