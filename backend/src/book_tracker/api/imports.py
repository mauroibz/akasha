import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from book_tracker.application.imports import ImportService
from book_tracker.application.library import LibraryError
from book_tracker.domain.importers import (
    BrowsableImporter,
    ImportCandidate,
    ImportInputSpec,
    ImportReadContext,
    ImportReadError,
    ImportSource,
    IncrementalImporter,
    declared_read_error,
    planned_upload,
)
from book_tracker.domain.registry import IMPORTERS
from book_tracker.infrastructure.repositories import DomainRepository

router = APIRouter(prefix="/api/import", tags=["imports"])
catalog_router = APIRouter(prefix="/api/importers", tags=["imports"])
enrichment_router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_FILES = 1000


class _DiskSpooledMultiPart(MultiPartParser):
    """Every uploaded part on disk, whatever its size.

    Starlette spools a part to disk only past 1 MiB, which is the wrong shape for a
    folder: a cover averages a few hundred kilobytes, so an entire library of them
    would sit in memory at once and peak would track the shelf rather than the file.
    `SpooledTemporaryFile` rolls over when `max_size > 0` and the write exceeds it, so
    1 is "roll immediately" — 0 means *never* roll, which is the trap here.
    """

    spool_max_size = 1


#: What a Calibre bundle is allowed to contain. Anything else is refused before a byte
#: is written: these paths come from the client, and `.caltrash/b/1/cover.jpg` is a real
#: file in a real library — a deleted book's cover, which must not be imported.
def _bundle_member(name: str) -> str:
    """The validated relative path of one uploaded member, or a refusal."""
    if not name or name.startswith(("/", "\\")) or "\\" in name:
        raise _bad_member(name)
    relative = PurePosixPath(name)
    if relative.is_absolute():
        raise _bad_member(name)
    parts = relative.parts
    if any(part in ("..", ".") or part.startswith(".") for part in parts):
        raise _bad_member(name)
    if parts == ("metadata.db",):
        return "metadata.db"
    if len(parts) >= 2 and parts[-1] == "cover.jpg":
        return str(relative)
    raise _bad_member(name)


def _bad_member(name: str) -> "LibraryError":
    return LibraryError(
        "invalid_import_source",
        f"Uploaded member {name!r} is not part of a Calibre library",
        status_code=422,
        details={"member": name},
        user_message="That folder contains something Akasha did not expect.",
        action="Choose the Calibre library folder itself — the one that holds metadata.db.",
    )


class BackfillResponse(BaseModel):
    queued: int


class ImportInputResponse(BaseModel):
    kind: str
    label: str
    field: str
    accept: str | None = None
    placeholder: str | None = None
    help: str | None = None
    #: Ordered steps, rendered as a list. Never markup: see `ImportInputSpec`.
    guide: list[str] = Field(default_factory=list)
    empty_state: str | None = None
    help_url: str | None = None
    browsable: bool = False
    incremental: bool = False
    accepts_files: bool = False
    max_bytes: int | None = None
    max_files: int | None = None
    #: A second way into the same connector, rendered beneath the primary. One deep.
    alternate: "ImportInputResponse | None" = None


class ImportPlanResponse(BaseModel):
    """Which offered members are worth uploading, and how many were skipped."""

    wanted: list[str] = Field(default_factory=list)
    holding: int = 0
    reason: str | None = None


class ImportBrowseResponse(BaseModel):
    """One level of a browsable connector's source. Relative names only."""

    path: str
    parent: str | None = None
    directories: list[str] = Field(default_factory=list)
    importable: bool = False


class ImporterResponse(BaseModel):
    id: str
    label: str
    item_type: str
    input: ImportInputResponse


def _published_input(spec: ImportInputSpec) -> ImportInputResponse:
    published = dict(spec.__dict__)
    published["alternate"] = (
        _published_input(spec.alternate) if spec.alternate is not None else None
    )
    return ImportInputResponse.model_validate(published)


@catalog_router.get("", response_model=list[ImporterResponse])
async def available_importers() -> list[ImporterResponse]:
    return [
        ImporterResponse(
            id=importer.name,
            label=importer.label,
            item_type=importer.item_type,
            input=_published_input(importer.input),
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


def read_failure(importer: object, error: ImportReadError) -> LibraryError:
    """Publish a reader's refusal, with whatever the reader can act on.

    Routed through `declared_read_error` so a code outside the connector's declared
    vocabulary is republished under one stable code instead of leaking an unknown
    vocabulary to the client (DEC-080).
    """
    published = declared_read_error(importer, error)  # type: ignore[arg-type]
    return LibraryError(
        published.code,
        str(published),
        status_code=422,
        details=published.details,
        user_message=published.user_message,
        action=published.action,
    )


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


def _inputs(importer: object) -> tuple[ImportInputSpec, ...]:
    """The ways into this connector: its primary, then its alternate if it has one."""
    spec: ImportInputSpec = importer.input  # type: ignore[attr-defined]
    return (spec,) if spec.alternate is None else (spec, spec.alternate)


def _chosen_input(importer: object, request: Request) -> ImportInputSpec:
    """Which declared input this request is using.

    A connector with an alternate is reached two ways on one route, so the content type
    decides rather than the declaration: a body of parts is the file or folder input, a
    JSON body is the path one (DEC-081).
    """
    posted_parts = request.headers.get("content-type", "").startswith("multipart/form-data")
    wanted = ("upload", "directory") if posted_parts else ("path",)
    for spec in _inputs(importer):
        if spec.kind in wanted:
            return spec
    raise LibraryError(
        "invalid_import_source",
        "This importer does not accept a source submitted that way",
        status_code=422,
    )


async def _source(request: Request, importer_name: str) -> ImportSource:
    importer = IMPORTERS[importer_name]
    spec = _chosen_input(importer, request)
    if spec.kind == "directory":
        return await _bundle(request, spec)
    if spec.kind == "upload":
        form = await request.form()
        upload = form.get(spec.field)
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
        value = body.get(spec.field) if isinstance(body, dict) else None
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            raise ValueError("invalid path")
    except (ValueError, TypeError) as error:
        raise LibraryError(
            "invalid_import_source", "A library path is required", status_code=422
        ) from error
    return ImportSource(path=value)


async def _bundle(
    request: Request, spec: ImportInputSpec, *, form_extras: tuple[str, ...] = ()
) -> ImportSource:
    """Stream an uploaded folder to disk as a library the reader already understands.

    Members land under `<bundle>/library/...` rather than at the root so the connector
    can point the ordinary adapter at the parent and reuse its confinement unchanged.
    The caller owns the returned directory and removes it.
    """
    max_bytes = spec.max_bytes or MAX_IMPORT_BYTES
    max_files = spec.max_files or MAX_IMPORT_FILES
    parser = _DiskSpooledMultiPart(
        request.headers,
        request.stream(),
        max_files=max_files + 1,
        max_fields=8,
        max_part_size=max_bytes,
    )
    try:
        form = await parser.parse()
    except MultiPartException as error:
        raise _too_large(spec) from error

    bundle = Path(tempfile.mkdtemp(prefix="akasha-import-"))
    try:
        total = 0
        written = 0
        for upload in form.getlist(spec.field):
            if not isinstance(upload, UploadFile):
                continue
            relative = _bundle_member(upload.filename or "")
            written += 1
            if written > max_files:
                raise _too_large(spec)
            target = bundle / "library" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as sink:
                while chunk := await upload.read(64 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise _too_large(spec)
                    sink.write(chunk)
        extras = {name: value for name in form_extras if isinstance(value := form.get(name), str)}
        if not (bundle / "library" / "metadata.db").is_file():
            raise LibraryError(
                "invalid_import_source",
                "The uploaded folder holds no metadata.db",
                status_code=422,
                user_message="That folder is not a Calibre library.",
                action=(
                    "Choose the folder that holds metadata.db — usually the one Calibre "
                    "calls your Calibre Library."
                ),
            )
        return ImportSource(directory=bundle, manifest=extras.get("manifest"))
    except BaseException:
        shutil.rmtree(bundle, ignore_errors=True)
        raise
    finally:
        await form.close()


def _too_large(spec: ImportInputSpec) -> LibraryError:
    megabytes = (spec.max_bytes or MAX_IMPORT_BYTES) // (1024 * 1024)
    return LibraryError(
        "import_too_large",
        f"Upload exceeds {megabytes} MiB or {spec.max_files or MAX_IMPORT_FILES} files",
        status_code=413,
        user_message=f"That library is larger than the {megabytes} MiB this accepts.",
        action="Import it from a mounted path instead, using the option below the folder chooser.",
    )


@router.post("/{importer_name}/preview", status_code=201, response_model=PreviewResponse)
async def preview(importer_name: str, request: Request) -> PreviewResponse:
    import_service = service(request, importer_name)
    source = await _source(request, importer_name)
    try:
        result = import_service.preview(source)
    except ImportReadError as error:
        raise read_failure(IMPORTERS[importer_name], error) from error
    finally:
        # Staging has already copied whatever the batch needs into `/data/imports`,
        # so an uploaded bundle has no reason to outlive the request — including when
        # the read failed, where leaving it behind would be a slow disk leak.
        if source.directory is not None:
            shutil.rmtree(source.directory, ignore_errors=True)
    return PreviewResponse.model_validate(result)


@router.post("/{importer_name}/plan", response_model=ImportPlanResponse)
async def plan(importer_name: str, request: Request) -> ImportPlanResponse:
    """Say which of the offered files are worth sending, before they are sent.

    The client uploads the cheap half of the source — for Calibre, `metadata.db` — plus
    a manifest of what it is holding back. The connector answers from identities the
    library already has, because the client cannot hash: `crypto.subtle` is undefined on
    the plain-HTTP LAN origin this is served from (DEC-082).
    """
    importer = IMPORTERS.get(importer_name)
    if (
        importer is None
        or not importer.input.incremental
        or not isinstance(importer, IncrementalImporter)
    ):
        raise LibraryError(
            "importer_not_incremental",
            "This importer cannot plan an upload",
            status_code=404,
        )
    spec = _chosen_input(importer, request)
    source = await _bundle(request, spec, form_extras=("manifest",))
    try:
        candidates = _candidates(source.manifest)
        result = planned_upload(
            candidates,
            importer.plan(
                source,
                candidates,
                DomainRepository(request.app.state.engine),
                ImportReadContext(path_root=request.app.state.calibre_dir),
            ),
        )
    except ImportReadError as error:
        raise read_failure(importer, error) from error
    except ValueError as error:
        raise LibraryError("invalid_import_plan", str(error), status_code=500) from error
    finally:
        if source.directory is not None:
            shutil.rmtree(source.directory, ignore_errors=True)
    return ImportPlanResponse(
        wanted=list(result.wanted), holding=result.holding, reason=result.reason
    )


def _candidates(manifest: str | None) -> tuple[ImportCandidate, ...]:
    """The client's offer, validated by the same rule the upload route applies."""
    try:
        rows = json.loads(manifest or "[]")
        if not isinstance(rows, list) or len(rows) > 100_000:
            raise ValueError("manifest must be a list")
        return tuple(
            ImportCandidate(path=_bundle_member(str(row["path"])), size=int(row["size"]))
            for row in rows
        )
    except (TypeError, KeyError, ValueError, json.JSONDecodeError) as error:
        if isinstance(error, LibraryError):  # pragma: no cover - defensive
            raise
        raise LibraryError(
            "invalid_import_source",
            "The upload manifest is malformed",
            status_code=422,
            user_message="Akasha could not read what your browser offered to send.",
            action="Choose the folder again.",
        ) from error


@router.get("/{importer_name}/browse", response_model=ImportBrowseResponse)
async def browse(
    importer_name: str,
    request: Request,
    path: str = Query("", max_length=500),
) -> ImportBrowseResponse:
    """List what one folder under a browsable connector's source holds.

    Read-only and confined by the connector itself, which resolves the request exactly
    as its reader would — the picker cannot walk anywhere a preview could not open.
    """
    importer = IMPORTERS.get(importer_name)
    # Browsing may be declared by the alternate rather than the primary: Calibre leads
    # with a folder chooser and keeps the mount picker underneath it (DEC-081).
    browsable = importer is not None and any(spec.browsable for spec in _inputs(importer))
    if importer is None or not browsable or not isinstance(importer, BrowsableImporter):
        raise LibraryError(
            "importer_not_browsable", "This importer has no browsable source", status_code=404
        )
    try:
        result = importer.browse(path, ImportReadContext(path_root=request.app.state.calibre_dir))
    except ImportReadError as error:
        raise read_failure(importer, error) from error
    return ImportBrowseResponse.model_validate(result.__dict__)


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
