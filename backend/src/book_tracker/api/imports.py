from typing import Annotated, Any

from fastapi import APIRouter, File, Request, UploadFile
from pydantic import BaseModel, Field

from book_tracker.application.imports import CalibreImportService, GoodreadsImportService
from book_tracker.application.library import LibraryError
from book_tracker.domain.calibre import CalibreError
from book_tracker.domain.goodreads import GoodreadsCSVError

router = APIRouter(prefix="/api/import", tags=["imports"])
enrichment_router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])
MAX_IMPORT_BYTES = 5 * 1024 * 1024


class BackfillResponse(BaseModel):
    queued: int


class ImportRecordResponse(BaseModel):
    record_id: int
    row_number: int
    goodreads_book_id: str | None = None
    calibre_book_id: str | None = None
    calibre_uuid: str | None = None
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
    description: str | None = None
    series: str | None = None
    cover_staged: bool = False
    connection_mode: str | None = None
    query_only: bool | None = None


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


class JobProgressResponse(BaseModel):
    id: str
    batch_id: str | None = None
    kind: str
    state: str
    progress: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_code: str | None = None
    attempts: int = 0
    created_at: str
    finished_at: str | None = None


class UndoEffectSummary(BaseModel):
    batch_id: str
    state: str
    reverted: int
    retained: int
    skipped: int
    reverted_entries: int = 0
    reverted_items: int = 0
    retained_items: int = 0


def service(request: Request) -> GoodreadsImportService:
    return GoodreadsImportService(request.app.state.engine, request.app.state.data_dir)


@router.post("/goodreads/preview", status_code=201, response_model=PreviewResponse)
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


@router.post("/goodreads/commit", response_model=CommitResponse)
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


class CalibrePreviewBody(BaseModel):
    library_path: str = Field(min_length=1, max_length=500)


def calibre_service(request: Request) -> CalibreImportService:
    return CalibreImportService(
        request.app.state.engine, request.app.state.data_dir, request.app.state.calibre_dir
    )


@router.post("/calibre/preview", status_code=201, response_model=PreviewResponse)
async def calibre_preview(body: CalibrePreviewBody, request: Request) -> PreviewResponse:
    try:
        result = calibre_service(request).preview(body.library_path)
    except CalibreError as error:
        raise LibraryError(error.code, str(error), status_code=422) from error
    return PreviewResponse.model_validate(result)


@router.post("/calibre/commit", response_model=CommitResponse)
async def calibre_commit(body: CommitBody, request: Request) -> CommitResponse:
    try:
        result = calibre_service(request).commit(
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


@router.get("/jobs/{job_id}", response_model=JobProgressResponse)
async def get_job_progress(job_id: str, request: Request) -> JobProgressResponse:
    from book_tracker.infrastructure.jobs import JobRepository

    repo = JobRepository(request.app.state.engine)
    job = repo.get_job(job_id)
    if job is None:
        raise LibraryError("job_not_found", "Job was not found", status_code=404)
    return JobProgressResponse.model_validate(job)


@enrichment_router.post("/backfill", status_code=202, response_model=BackfillResponse)
async def backfill_enrichment(request: Request) -> BackfillResponse:
    """Queue enrichment for persisted items an ISBN lookup could still improve.

    Explicit and operator-driven: it only queues work, and the handler it queues fills
    empty fields only, so it can never overwrite a hand edit.
    """
    from book_tracker.application.enrichment import enqueue_enrichment_backfill

    return BackfillResponse(queued=enqueue_enrichment_backfill(request.app.state.engine))


@router.delete("/batches/{batch_id}", response_model=UndoEffectSummary)
async def undo_batch(batch_id: str, request: Request) -> UndoEffectSummary:
    from book_tracker.application.undo import UndoExpiredError, UndoService

    undo = UndoService(request.app.state.engine)
    try:
        result = undo.undo(batch_id)
    except LookupError as error:
        raise LibraryError(
            "import_batch_not_found", "Import batch was not found", status_code=404
        ) from error
    except UndoExpiredError as error:
        raise LibraryError(
            "undo_expired",
            "Undo window has expired (24 hours since commit)",
            status_code=409,
        ) from error
    except ValueError as error:
        raise LibraryError("undo_not_committable", str(error), status_code=409) from error
    return UndoEffectSummary.model_validate(result)
