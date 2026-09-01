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
from book_tracker.application.library import LibraryError, clean_attachment_filename
from book_tracker.domain.importers import (
    BrowsableImporter,
    ImportCandidate,
    ImportInputSpec,
    ImportReadContext,
    ImportReadError,
    ImportSource,
    IncrementalImporter,
    declared_read_error,
    member_allowed,
    planned_upload,
)
from book_tracker.domain.registry import IMPORTERS
from book_tracker.infrastructure.attachments import (
    AttachmentError,
    AttachmentTooLarge,
    BlobWriter,
)
from book_tracker.infrastructure.diskspace import ensure_free_space
from book_tracker.infrastructure.offload import off_loop
from book_tracker.infrastructure.repositories import DomainRepository

#: Matches the item attachment route: one megabyte through, never the whole file
#: in memory (DEC-049).
UPLOAD_CHUNK_BYTES = 1024 * 1024

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


def _bundle_member(name: str, spec: ImportInputSpec) -> str:
    """The validated relative path of one uploaded member, or a refusal.

    Two checks, and they answer different questions. **Shape** is universal and is
    never delegated: these paths come from the client, so an absolute path, a
    backslash, a `..` or a dot-prefixed segment is refused for every connector that
    will ever exist — `.caltrash/b/1/cover.jpg` is a real file in a real library, a
    deleted book's cover that must not be imported. **Content** is the connector's,
    declared as `members`, because what belongs in a source is a fact about that
    source and not about this route (DEC-083).
    """
    if not name or name.startswith(("/", "\\")) or "\\" in name:
        raise _bad_member(name, spec)
    relative = PurePosixPath(name)
    if relative.is_absolute():
        raise _bad_member(name, spec)
    parts = relative.parts
    if any(part in ("..", ".") or part.startswith(".") for part in parts):
        raise _bad_member(name, spec)
    if not member_allowed(parts, spec.members):
        raise _bad_member(name, spec)
    return str(relative)


def _bad_member(name: str, spec: ImportInputSpec) -> "LibraryError":
    return LibraryError(
        "invalid_import_source",
        f"Uploaded member {name!r} is not something this source may contain",
        status_code=422,
        details={"member": name},
        user_message="That folder contains something Akasha did not expect.",
        action=spec.empty_state or "Choose the source folder again.",
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
    #: Every domain this connector can produce, ordered, first-declared first. A list
    #: rather than a string because one source may carry films and shows (DEC-106);
    #: the screen renders a target checkbox per entry, and none at all for one.
    item_types: list[str]
    input: ImportInputResponse
    #: The per-file ceiling on anything this import attaches, so the screen can name
    #: a file it will not send instead of spending the upload to be refused (DEC-083).
    attachment_max_bytes: int


def _published_input(spec: ImportInputSpec) -> ImportInputResponse:
    published = dict(spec.__dict__)
    published["alternate"] = (
        _published_input(spec.alternate) if spec.alternate is not None else None
    )
    return ImportInputResponse.model_validate(published)


@catalog_router.get("", response_model=list[ImporterResponse])
async def available_importers(request: Request) -> list[ImporterResponse]:
    return [
        ImporterResponse(
            id=importer.name,
            label=importer.label,
            item_types=list(importer.item_types),
            input=_published_input(importer.input),
            attachment_max_bytes=int(request.app.state.attachment_max_bytes),
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


class SkippedReason(BaseModel):
    reason: str
    count: int


class PreviewSummary(BaseModel):
    total: int
    ready: int
    errors: int
    ambiguous: int
    #: Rows for a library the reader did not tick. Their own count, never folded into
    #: `errors`: choosing not to import something is not a failure to import it.
    skipped_not_requested: int = 0
    #: Rows whose source kind maps to no registered domain at all, with the source's
    #: own word for each kind, so a title type IMDb has not published yet appears as a
    #: number on this screen rather than as a failed import.
    skipped_unsupported: int = 0
    skipped_reasons: list[SkippedReason] = Field(default_factory=list)


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


def _targets(value: object) -> tuple[str, ...] | None:
    """Which libraries this import is for, as the request stated them.

    Absent means every domain the connector declares, which is what the screen ticks
    by default and the only thing a single-domain connector can mean. A multipart
    request states them as one comma-separated field so the folder bundle and the
    file upload say it the same way; a JSON body states them as a list.

    What they *mean* is the service's business, not this route's — the service applies
    the selection so that no connector can get the filter wrong (DEC-106).
    """
    if value is None:
        return None
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, list) and all(isinstance(part, str) for part in value):
        return tuple(part.strip() for part in value if part.strip())
    raise LibraryError(
        "invalid_import_targets", "Import targets must be a list of item types", status_code=422
    )


async def _source(
    request: Request, importer_name: str
) -> tuple[ImportSource, tuple[str, ...] | None]:
    importer = IMPORTERS[importer_name]
    spec = _chosen_input(importer, request)
    if spec.kind == "directory":
        source, extras = await _bundle(request, spec, form_extras=("manifest", "targets"))
        return source, _targets(extras.get("targets"))
    if spec.kind == "upload":
        form = await request.form()
        upload = form.get(spec.field)
        if not isinstance(upload, UploadFile):
            raise LibraryError(
                "invalid_import_source", "An import file is required", status_code=422
            )
        targets = _targets(form.get("targets"))
        cap = spec.max_bytes or MAX_IMPORT_BYTES
        chunks: list[bytes] = []
        size = 0
        while chunk := await upload.read(64 * 1024):
            size += len(chunk)
            if size > cap:
                raise _too_large(spec)
            chunks.append(chunk)
        return ImportSource(data=b"".join(chunks), filename=upload.filename), targets
    try:
        body = await request.json()
        value = body.get(spec.field) if isinstance(body, dict) else None
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            raise ValueError("invalid path")
    except (ValueError, TypeError) as error:
        raise LibraryError(
            "invalid_import_source", "A library path is required", status_code=422
        ) from error
    return ImportSource(path=value), _targets(body.get("targets"))


async def _bundle(
    request: Request, spec: ImportInputSpec, *, form_extras: tuple[str, ...] = ()
) -> tuple[ImportSource, dict[str, str]]:
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
            relative = _bundle_member(upload.filename or "", spec)
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
        return ImportSource(directory=bundle, manifest=extras.get("manifest")), extras
    except BaseException:
        shutil.rmtree(bundle, ignore_errors=True)
        raise
    finally:
        await form.close()


def _too_large(spec: ImportInputSpec) -> LibraryError:
    megabytes = (spec.max_bytes or MAX_IMPORT_BYTES) // (1024 * 1024)
    # An alternate is only ever the mounted-path input today (DEC-081's one level
    # deep), which is what this sentence names; a connector with no alternate has no
    # second way in, so the refusal says only what actually happened (deliverable 5,
    # Sprint 060).
    action = (
        "Import it from a mounted path instead, using the option below the folder chooser."
        if spec.alternate is not None
        else "Export a smaller file, or split it into more than one."
    )
    return LibraryError(
        "import_too_large",
        f"Upload exceeds {megabytes} MiB or {spec.max_files or MAX_IMPORT_FILES} files",
        status_code=413,
        user_message=f"That library is larger than the {megabytes} MiB this accepts.",
        action=action,
    )


@router.post("/{importer_name}/preview", status_code=201, response_model=PreviewResponse)
async def preview(importer_name: str, request: Request) -> PreviewResponse:
    ensure_free_space(request.app.state.data_dir, request.app.state.min_free_bytes)
    import_service = service(request, importer_name)
    source, targets = await _source(request, importer_name)
    try:
        result = import_service.preview(source, targets)
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
    source, _extras = await _bundle(request, spec, form_extras=("manifest",))
    try:
        candidates = _candidates(source.manifest, spec)
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


def _candidates(manifest: str | None, spec: ImportInputSpec) -> tuple[ImportCandidate, ...]:
    """The client's offer, validated by the same rule the upload route applies."""
    try:
        rows = json.loads(manifest or "[]")
        if not isinstance(rows, list) or len(rows) > 100_000:
            raise ValueError("manifest must be a list")
        return tuple(
            ImportCandidate(path=_bundle_member(str(row["path"]), spec), size=int(row["size"]))
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


class ImportFileResponse(BaseModel):
    id: int
    item_id: int
    filename: str
    byte_size: int
    sha256: str


@router.post(
    "/{importer_name}/batches/{batch_id}/files",
    status_code=201,
    response_model=ImportFileResponse,
)
async def attach_file(importer_name: str, batch_id: str, request: Request) -> ImportFileResponse:
    """Take one file the import wants and attach it to the item it belongs to.

    One file per request, and that is the design rather than an implementation
    detail (DEC-083). Folding these into the preview bundle would bound the feature
    by the size of the whole library instead of by the size of one file, so a shelf
    of any size would eventually stop importing; here a 600-book library behaves
    exactly like an 18-book one, a file that cannot be stored costs one book rather
    than the import, and the screen can count progress honestly.
    """
    ensure_free_space(request.app.state.data_dir, request.app.state.min_free_bytes)
    import_service = service(request, importer_name)
    spec = IMPORTERS[importer_name].input
    cap = int(request.app.state.attachment_max_bytes)
    parser = _DiskSpooledMultiPart(
        request.headers,
        request.stream(),
        max_files=2,
        max_fields=4,
        max_part_size=cap + 1,
    )
    try:
        form = await parser.parse()
    except MultiPartException as error:
        raise _file_too_large(cap) from error
    try:
        offered = form.get("path")
        upload = form.get("file")
        if not isinstance(offered, str) or not isinstance(upload, UploadFile):
            raise LibraryError(
                "invalid_import_source",
                "A file and the path it was offered under are both required",
                status_code=422,
            )
        path = _bundle_member(offered, spec)
        # Resolved before a byte is read: an upload nothing wants should cost a round
        # trip, not a whole ebook.
        item_id = import_service.resolve_file(batch_id, path)
        writer = BlobWriter(request.app.state.data_dir, max_bytes=cap)
        try:
            while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                writer.write(chunk)
            stored = writer.commit()
        except AttachmentTooLarge as error:
            raise _file_too_large(cap) from error
        except AttachmentError as error:
            raise LibraryError("invalid_attachment", str(error), status_code=422) from error
        except BaseException:
            writer.abort()
            raise
        attachment = import_service.record_file(
            batch_id,
            item_id,
            filename=clean_attachment_filename(PurePosixPath(path).name) or "attachment",
            sha256=stored.sha256,
            byte_size=stored.byte_size,
        )
    finally:
        await form.close()
    return ImportFileResponse.model_validate({**attachment, "item_id": item_id})


def _file_too_large(cap: int) -> LibraryError:
    megabytes = cap // (1024 * 1024)
    return LibraryError(
        "attachment_too_large",
        f"Attachments are limited to {cap} bytes",
        status_code=413,
        user_message=f"That file is larger than the {megabytes} MB Akasha stores.",
        action="It was skipped; everything else in this import still went through.",
    )


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
    # Phase A (Sprint 059) measured this call blocking every other request for its
    # whole duration — a large batch is many synchronous SQLAlchemy writes plus a
    # per-item cover install, with not one `await` in between. `off_loop` is the one
    # seam that moves synchronous work off the loop; see its module docstring.
    try:
        result = await off_loop(
            service(request, importer_name).commit,
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
    """Queue enrichment for persisted items a provider lookup could still improve.

    Explicit and operator-driven: it only queues work, and the handler it queues fills
    empty fields only, so it can never overwrite a hand edit. Each domain is asked on
    its own identifier and its own incompleteness rule (DEC-067 row 3).
    """
    from book_tracker.application.enrichment import enqueue_enrichment_backfill

    return BackfillResponse(queued=enqueue_enrichment_backfill(request.app.state.engine))


@router.delete("/batches/{batch_id}", response_model=UndoEffectSummary)
async def undo_batch(batch_id: str, request: Request) -> UndoEffectSummary:
    from book_tracker.application.undo import UndoExpiredError, UndoService

    undo = UndoService(request.app.state.engine, data_dir=request.app.state.data_dir)
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
