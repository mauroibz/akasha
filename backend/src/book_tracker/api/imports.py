from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import UploadFile

from book_tracker.application.imports import ImportService
from book_tracker.application.library import LibraryError
from book_tracker.domain.importers import ImportReadError, ImportSource
from book_tracker.domain.registry import IMPORTERS

router = APIRouter(prefix="/api/import", tags=["imports"])
catalog_router = APIRouter(prefix="/api/importers", tags=["imports"])
enrichment_router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])
MAX_IMPORT_BYTES = 5 * 1024 * 1024


class BackfillResponse(BaseModel):
    queued: int


class ImportInputResponse(BaseModel):
    kind: str
    label: str
    field: str
    accept: str | None = None
    placeholder: str | None = None
    help: str | None = None


class ImporterResponse(BaseModel):
    id: str
    label: str
    item_type: str
    input: ImportInputResponse


@catalog_router.get("", response_model=list[ImporterResponse])
async def available_importers() -> list[ImporterResponse]:
    return [
        ImporterResponse(
            id=importer.name,
            label=importer.label,
            item_type=importer.item_type,
            input=ImportInputResponse.model_validate(importer.input.__dict__),
        )
        for importer in IMPORTERS.values()
    ]


class ImportRecordResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_id: int
    row_number: int
    title: str
    creators: list[str]
    suggested_status: str | None = None
    score: int | None = None
    score_provisional: bool = False
    shelves: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    planned_action: str
    match_kind: str
    candidates: list[int]
    item: dict[str, Any]
    entry: dict[str, Any]
    source_fields: dict[str, Any]
    cover_staged: bool = False


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
    #: Everything waiting in triage after this commit, not only the rows it created.
    unsorted_entries: int


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


def service(request: Request, importer_name: str) -> ImportService:
    importer = IMPORTERS.get(importer_name)
    if importer is None:
        raise LibraryError("importer_not_found", "Importer was not found", status_code=404)
    return ImportService(
        request.app.state.engine,
        request.app.state.data_dir,
        request.app.state.calibre_dir,
        importer,
    )


async def _source(request: Request, importer_name: str) -> ImportSource:
    importer = IMPORTERS[importer_name]
    if importer.input.kind == "upload":
        form = await request.form()
        upload = form.get(importer.input.field)
        if not isinstance(upload, UploadFile):
            raise LibraryError(
                "invalid_import_source", "An import file is required", status_code=422
            )
        chunks: list[bytes] = []
        size = 0
        while chunk := await upload.read(64 * 1024):
            size += len(chunk)
            if size > MAX_IMPORT_BYTES:
                raise LibraryError(
                    "import_too_large",
                    f"{importer.label} source exceeds 5 MiB",
                    status_code=413,
                )
            chunks.append(chunk)
        return ImportSource(data=b"".join(chunks), filename=upload.filename)
    try:
        body = await request.json()
        value = body.get(importer.input.field) if isinstance(body, dict) else None
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            raise ValueError("invalid path")
    except (ValueError, TypeError) as error:
        raise LibraryError(
            "invalid_import_source", "A library path is required", status_code=422
        ) from error
    return ImportSource(path=value)


@router.post("/{importer_name}/preview", status_code=201, response_model=PreviewResponse)
async def preview(importer_name: str, request: Request) -> PreviewResponse:
    import_service = service(request, importer_name)
    try:
        result = import_service.preview(await _source(request, importer_name))
    except ImportReadError as error:
        raise LibraryError(
            error.code, str(error), status_code=422, details=error.details
        ) from error
    return PreviewResponse.model_validate(result)


@router.post("/{importer_name}/commit", response_model=CommitResponse)
async def commit(importer_name: str, body: CommitBody, request: Request) -> CommitResponse:
    try:
        result = service(request, importer_name).commit(
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
