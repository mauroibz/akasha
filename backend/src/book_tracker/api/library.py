import asyncio
import hashlib
import logging
from datetime import date
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from book_tracker.application.add import AddService
from book_tracker.application.library import (
    LibraryError,
    LibraryService,
    clean_attachment_filename,
)
from book_tracker.application.providers import CANDIDATE_BUDGET_SECONDS, cover_candidates
from book_tracker.domain.providers import SourceRef
from book_tracker.domain.types import EntryStatus
from book_tracker.infrastructure.attachments import (
    AttachmentError,
    AttachmentTooLarge,
    BlobWriter,
    blob_path,
)
from book_tracker.infrastructure.covers import (
    CoverError,
    install_cover,
    prepare_cover,
    prepare_uploaded_cover,
)
from book_tracker.infrastructure.providers import ProviderPayloadError
from book_tracker.infrastructure.repositories import DomainRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# One chunk in flight at a time on the way in; FileResponse does the same on the
# way out. Large enough that a 25 MiB upload is 25 reads, small enough that a
# handful of concurrent uploads is megabytes rather than hundreds of them.
UPLOAD_CHUNK_BYTES = 1024 * 1024


async def service(request: Request) -> LibraryService:
    return LibraryService(request.app.state.engine)


Library = Annotated[LibraryService, Depends(service)]


class ShelfBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ShelfResponse(BaseModel):
    id: int
    name: str
    slug: str
    entry_count: int = 0


class SourceResponse(BaseModel):
    source: str
    source_id: str
    is_primary: bool


class BookMetadataResponse(BaseModel):
    authors: list[str] = Field(default_factory=list)
    publisher: str | None = None
    language: str | None = None
    page_count: int | None = None
    description: str | None = None
    subjects: list[str] = Field(default_factory=list)
    series: str | None = None
    original_year: int | None = None


class BookMetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authors: list[str] | None = None
    publisher: str | None = None
    language: str | None = None
    page_count: int | None = Field(default=None, ge=1)
    description: str | None = None
    subjects: list[str] | None = None
    series: str | None = None
    original_year: int | None = Field(default=None, ge=0, le=9999)


class ItemResponse(BaseModel):
    id: int
    type: str
    title: str
    subtitle: str | None
    year: int | None
    sort_author: str | None
    cover_url: str | None
    metadata: BookMetadataResponse
    identifiers: dict[str, str]
    sources: list[SourceResponse]


class EntryResponse(BaseModel):
    id: int
    item_id: int
    status: EntryStatus
    score: int | None
    notes: str | None
    date_added: str
    date_started: str | None
    date_finished: str | None
    reread_count: int
    score_provisional: bool
    suggested_status: EntryStatus | None
    item: ItemResponse
    shelves: list[ShelfResponse]


class FacetsResponse(BaseModel):
    status_counts: dict[str, int]


class EntryListResponse(BaseModel):
    items: list[EntryResponse]
    next_cursor: str | None
    total: int
    facets: FacetsResponse


class AffectedResponse(BaseModel):
    affected: int


class SourceRefBody(BaseModel):
    source: str = Field(min_length=1, max_length=50)
    source_id: str = Field(min_length=1, max_length=200)


class ManualItemBody(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    authors: list[str] = Field(default_factory=list, max_length=50)
    year: int | None = Field(default=None, ge=0, le=9999)
    publisher: str | None = Field(default=None, max_length=300)
    language: str | None = Field(default=None, max_length=20)
    isbn: str | None = Field(default=None, max_length=40)


class EntryCreateBody(BaseModel):
    source: str | None = Field(default=None, max_length=50)
    source_id: str | None = Field(default=None, max_length=200)
    source_refs: list[SourceRefBody] = Field(default_factory=list, max_length=10)
    manual: ManualItemBody | None = None
    status: EntryStatus = EntryStatus.READ
    score: int | None = Field(default=None, ge=1, le=10)
    shelf_ids: list[int] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)
    confirm_near_match: bool = False

    @model_validator(mode="after")
    def exactly_one_source(self) -> "EntryCreateBody":
        provider_selected = self.source is not None or self.source_id is not None
        if (self.source is None) != (self.source_id is None):
            raise ValueError("source and source_id must be provided together")
        if (self.manual is None) == (not provider_selected):
            raise ValueError("provide exactly one of manual or provider source")
        if self.manual is not None and not (self.idempotency_key or self.manual.isbn):
            raise ValueError("manual add requires idempotency_key or ISBN")
        return self


class EntryCreateResponse(BaseModel):
    entry: EntryResponse
    already_exists: bool
    near_matches: list[int]


ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Requested resource was not found"},
    409: {"model": ErrorResponse, "description": "Domain conflict"},
}


class EntryPatch(BaseModel):
    status: EntryStatus | None = None
    score: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None
    date_started: date | None = None
    date_finished: date | None = None
    reread_count: int | None = Field(default=None, ge=0)
    shelf_ids: list[int] | None = None

    @model_validator(mode="after")
    def required_status_when_present(self) -> "EntryPatch":
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class ItemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    subtitle: str | None = None
    year: int | None = None
    metadata: BookMetadataPatch | None = None

    @model_validator(mode="after")
    def required_title_when_present(self) -> "ItemPatch":
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null")
        return self


class RefreshBody(BaseModel):
    overwrite: bool

    @model_validator(mode="after")
    def confirmed(self) -> "RefreshBody":
        if not self.overwrite:
            raise ValueError("overwrite confirmation is required")
        return self


class EntryFilter(BaseModel):
    status: list[EntryStatus] | None = None
    shelf: list[str] = Field(default_factory=list)
    q: str | None = None


class BulkSet(BaseModel):
    status: EntryStatus | None = None
    score: int | None = Field(default=None, ge=1, le=10)
    add_shelves: list[int] = Field(default_factory=list)
    remove_shelves: list[int] = Field(default_factory=list)
    clear_provisional: bool = False

    @model_validator(mode="after")
    def required_status_when_present(self) -> "BulkSet":
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class BulkBody(BaseModel):
    entry_ids: list[int] | None = None
    filter: EntryFilter | None = None
    excluded_entry_ids: list[int] = Field(default_factory=list)
    set: BulkSet

    @model_validator(mode="after")
    def exactly_one_selection(self) -> "BulkBody":
        if (self.entry_ids is None) == (self.filter is None):
            raise ValueError("provide exactly one of entry_ids or filter")
        if self.entry_ids is not None and self.excluded_entry_ids:
            raise ValueError("exclusions require filter selection")
        return self


class AcceptSuggestedBody(BaseModel):
    filter: EntryFilter


@router.get("/entries", response_model=EntryListResponse, responses={400: {"model": ErrorResponse}})
async def list_entries(
    library: Library,
    status: Annotated[list[EntryStatus] | None, Query()] = None,
    shelf: Annotated[list[str] | None, Query()] = None,
    q: str | None = None,
    sort: Literal[
        "date_added", "score", "title", "sort_author", "year", "date_finished"
    ] = "date_added",
    order: Literal["asc", "desc"] = "desc",
    after: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> EntryListResponse:
    return EntryListResponse.model_validate(
        library.list_entries(
            statuses=[value.value for value in status] if status is not None else None,
            shelves=shelf or [],
            q=q,
            sort=sort,
            order=order,
            after=after,
            limit=limit,
        )
    )


@router.post(
    "/entries",
    response_model=EntryCreateResponse,
    status_code=201,
    responses={200: {"model": EntryCreateResponse}, **ERRORS},
)
async def create_entry(
    body: EntryCreateBody, request: Request, response: Response
) -> EntryCreateResponse:
    add = AddService(
        request.app.state.engine,
        request.app.state.providers,
        cover_client=request.app.state.provider_client,
        data_dir=request.app.state.data_dir,
    )
    result = await add.add(
        manual=body.manual.model_dump() if body.manual else None,
        source=body.source,
        source_id=body.source_id,
        supplied_refs=[SourceRef(value.source, value.source_id) for value in body.source_refs],
        status=body.status.value,
        score=body.score,
        shelf_ids=body.shelf_ids,
        idempotency_key=body.idempotency_key,
        confirm_near_match=body.confirm_near_match,
    )
    if result["already_exists"]:
        response.status_code = 200
    return EntryCreateResponse.model_validate(result)


@router.patch("/entries/bulk", response_model=AffectedResponse, responses=ERRORS)
async def bulk_entries(body: BulkBody, library: Library) -> AffectedResponse:
    filter_values = body.filter.model_dump(mode="json") if body.filter else None
    affected = library.bulk_update(
        entry_ids=body.entry_ids,
        filters=filter_values,
        excluded_entry_ids=body.excluded_entry_ids,
        changes=body.set.model_dump(mode="json", exclude_unset=True),
    )
    return AffectedResponse(affected=affected)


@router.post("/entries/accept-suggested", response_model=AffectedResponse)
async def accept_suggested(body: AcceptSuggestedBody, library: Library) -> AffectedResponse:
    affected = library.accept_suggested(body.filter.model_dump(mode="json"))
    return AffectedResponse(affected=affected)


@router.get("/entries/{entry_id}", response_model=EntryResponse, responses=ERRORS)
async def get_entry(entry_id: int, library: Library) -> EntryResponse:
    return EntryResponse.model_validate(library.get_entry(entry_id))


@router.patch("/entries/{entry_id}", response_model=EntryResponse, responses=ERRORS)
async def update_entry(entry_id: int, body: EntryPatch, library: Library) -> EntryResponse:
    return EntryResponse.model_validate(
        library.update_entry(entry_id, body.model_dump(mode="json", exclude_unset=True))
    )


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(entry_id: int, library: Library) -> Response:
    library.delete_entry(entry_id)
    return Response(status_code=204)


@router.get(
    "/items/{item_id}",
    response_model=ItemResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
)
async def get_item(item_id: int, library: Library) -> ItemResponse:
    return ItemResponse.model_validate(library.get_item(item_id))


@router.patch(
    "/items/{item_id}",
    response_model=ItemResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
)
async def update_item(item_id: int, body: ItemPatch, library: Library) -> ItemResponse:
    changes = body.model_dump(exclude_unset=True)
    if body.metadata is not None:
        changes["metadata"] = body.metadata.model_dump(exclude_unset=True)
    return ItemResponse.model_validate(library.update_item(item_id, changes))


@router.get("/items/{item_id}/cover", responses=ERRORS, response_model=None)
async def get_cover(item_id: int, request: Request) -> Response:
    item = LibraryService(request.app.state.engine).get_item(item_id)
    if not item["cover_url"]:
        raise LibraryError("cover_not_found", "Cover was not found", status_code=404)
    target = request.app.state.data_dir / "covers" / f"{item_id}.jpg"
    if not target.is_file():
        raise LibraryError("cover_not_found", "Cover was not found", status_code=404)
    return Response(
        content=target.read_bytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )


class CoverCandidate(BaseModel):
    cover_url: str
    source_id: str
    title: str
    year: int | None = None


class CoverCandidates(BaseModel):
    candidates: list[CoverCandidate]
    reason: str | None = None


@router.get(
    "/items/{item_id}/cover-candidates",
    response_model=CoverCandidates,
    responses=ERRORS,
)
async def list_cover_candidates(item_id: int, request: Request) -> CoverCandidates:
    """Other editions of this work, offered as covers to choose from.

    Only ever reached because a chooser was opened. Nothing here runs while a library
    page renders, which is the invariant that keeps cached pages provider-free.
    """
    library = LibraryService(request.app.state.engine)
    library.get_item(item_id)
    provider = request.app.state.providers.get("openlibrary")
    if provider is None:
        return CoverCandidates(candidates=[], reason="provider_disabled")
    edition_id, isbn = library.cover_lookup(item_id)
    if not edition_id and not isbn:
        return CoverCandidates(candidates=[], reason="no_provider_reference")
    try:
        rows = await asyncio.wait_for(
            cover_candidates(provider, edition_id=edition_id, isbn=isbn),
            CANDIDATE_BUDGET_SECONDS,
        )
    except ProviderPayloadError as error:
        # The distinction is the code, not the exception type, and it matters in both
        # directions. Open Library answering 404 for an ISBN it does not carry is an
        # answer, and calling that unreachable sends the reader after a network problem
        # that is not there. But the same exception also carries genuine transport
        # failures, and calling those "no candidates" quietly blames the data for an
        # outage. Sprint 020's walkthrough produced both mistakes in turn.
        unreachable = error.code in {"provider_unreachable", "provider_http_error"}
        logger.info("no cover candidates", extra={"item_id": item_id, "code": error.code})
        return CoverCandidates(
            candidates=[],
            reason="provider_unavailable" if unreachable else "no_candidates",
        )
    except Exception:
        logger.warning("cover candidates unavailable", extra={"item_id": item_id})
        return CoverCandidates(candidates=[], reason="provider_unavailable")
    return CoverCandidates(
        candidates=[
            CoverCandidate(
                cover_url=row.cover_url,
                source_id=row.source_id,
                title=row.title,
                year=row.year,
            )
            for row in rows
            if row.cover_url
        ],
        reason=None if rows else "no_candidates",
    )


class ChosenCover(BaseModel):
    cover_url: str


@router.post(
    "/items/{item_id}/cover",
    response_model=ItemResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
)
async def replace_cover(
    item_id: int,
    request: Request,
    cover: Annotated[UploadFile | None, File()] = None,
) -> ItemResponse:
    """Replace a cover, either with an upload or with a candidate the owner picked.

    One endpoint rather than two because the write is identical past the point the bytes
    are obtained: same validation, same atomic install, same recovery of the previous
    cover if anything fails.
    """
    library = LibraryService(request.app.state.engine)
    library.get_item(item_id)
    chosen: str | None = None
    upload: tuple[bytes, str] | None = None
    if cover is None:
        try:
            chosen = ChosenCover.model_validate(await request.json()).cover_url
        except Exception as error:
            raise LibraryError(
                "invalid_cover", "Provide a cover file or a cover_url", status_code=422
            ) from error
    else:
        upload = (await cover.read(10 * 1024 * 1024 + 1), cover.content_type or "")
    target = request.app.state.data_dir / "covers" / f"{item_id}.jpg"
    previous = target.read_bytes() if target.is_file() else None
    try:
        if chosen is not None:
            # `prepare_cover` carries the host allowlist and the placeholder-banner
            # guard, so a chosen URL cannot fetch an arbitrary host or install a
            # provider's "image not available" strip.
            prepared = await prepare_cover(
                request.app.state.provider_client, chosen, request.app.state.data_dir
            )
        else:
            assert upload is not None
            prepared = prepare_uploaded_cover(upload[0], upload[1], request.app.state.data_dir)
        install_cover(prepared, request.app.state.data_dir, item_id)
        DomainRepository(request.app.state.engine).set_cover_path(item_id, f"covers/{item_id}.jpg")
    except CoverError as error:
        raise LibraryError("invalid_cover", str(error), status_code=422) from error
    except Exception:
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            recovery = target.with_suffix(".recovery.tmp")
            recovery.write_bytes(previous)
            recovery.replace(target)
        raise
    return ItemResponse.model_validate(library.get_item(item_id))


class AttachmentResponse(BaseModel):
    id: int
    filename: str
    byte_size: int
    sha256: str
    created_at: str


class AttachmentList(BaseModel):
    attachments: list[AttachmentResponse]


@router.get(
    "/items/{item_id}/attachments",
    response_model=AttachmentList,
    responses=ERRORS,
)
async def list_attachments(item_id: int, library: Library) -> AttachmentList:
    return AttachmentList(
        attachments=[
            AttachmentResponse.model_validate(row) for row in library.list_attachments(item_id)
        ]
    )


@router.post(
    "/items/{item_id}/attachments",
    response_model=AttachmentResponse,
    status_code=201,
    responses=ERRORS,
)
async def add_attachment(
    item_id: int,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> AttachmentResponse:
    """Take an opaque file and store it by the digest of its contents.

    The uploaded name is never trusted as a path. `os.path.basename` strips any
    directory a client put in front of it, and even that is belt-and-braces: the
    name is stored in the database and the blob is addressed by its own hash, so
    there is no code path where this string reaches the filesystem (DEC-048).
    """
    library = LibraryService(request.app.state.engine)
    # Before a single chunk is read: an upload to an item that is not here should
    # cost nothing, not 25 MiB of transfer followed by a 404.
    library.ensure_item(item_id)

    cap = request.app.state.attachment_max_bytes
    filename = clean_attachment_filename(file.filename or "") or "attachment"
    writer = BlobWriter(request.app.state.data_dir, max_bytes=cap)
    try:
        while chunk := await file.read(UPLOAD_CHUNK_BYTES):
            # Written straight through to disk. The previous version read the
            # whole upload into one string, so a 25 MiB file was a 25 MiB
            # allocation per concurrent request on a machine where a cover is
            # 39 KB (DEC-049).
            writer.write(chunk)
        stored = writer.commit()
    except AttachmentTooLarge as error:
        raise LibraryError(
            "attachment_too_large",
            f"Attachments are limited to {cap} bytes",
            status_code=413,
        ) from error
    except AttachmentError as error:
        raise LibraryError("invalid_attachment", str(error), status_code=422) from error
    except BaseException:
        # A disconnected client must not leave its partial upload behind.
        writer.abort()
        raise

    return AttachmentResponse.model_validate(
        library.record_attachment(
            item_id,
            filename=filename,
            sha256=stored.sha256,
            byte_size=stored.byte_size,
        )
    )


@router.get(
    "/items/{item_id}/attachments/{attachment_id}",
    responses=ERRORS,
    response_model=None,
)
async def download_attachment(item_id: int, attachment_id: int, request: Request) -> Response:
    """Serve an opaque blob in the only way that is safe from this origin.

    Everything the application served before this endpoint had been re-encoded to
    a JPEG by the cover pipeline, so content type was never attacker-controlled.
    It is here, and the SPA shares this origin, so an uploaded HTML or SVG opened
    inline could script the application against its own API. The three headers
    below are what stop that, and none of them is optional (DEC-048).
    """
    row = LibraryService(request.app.state.engine).get_attachment(item_id, attachment_id)
    try:
        target = blob_path(request.app.state.data_dir, row["sha256"])
    except AttachmentError as error:
        raise LibraryError(
            "attachment_not_found", "Attachment was not found", status_code=404
        ) from error
    if not target.is_file():
        raise LibraryError("attachment_not_found", "Attachment was not found", status_code=404)
    quoted = quote(row["filename"])
    tag = _attachment_etag(row)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        "X-Content-Type-Options": "nosniff",
        # Not `immutable` any more. The blob genuinely never changes, but this
        # response is not the blob: it carries the filename, and the filename is
        # editable, so a year of `immutable` left an already-downloaded file
        # saving under a name the owner had since corrected (DEC-049). The
        # validator covers digest and name together, so an untouched file still
        # costs a 304 with no body while a renamed one can no longer match.
        "Cache-Control": "private, max-age=0, must-revalidate",
        "ETag": tag,
    }
    if _matches(request.headers.get("if-none-match"), tag):
        return Response(status_code=304, headers=headers)
    # Streamed off disk rather than `read_bytes()`, for the same reason the
    # upload is: the file is up to 25 MiB and the box it serves from is a
    # ZimaBoard. FileResponse only fills in headers it was not given, so the
    # validator above is the one that ships.
    return FileResponse(
        target,
        media_type="application/octet-stream",
        headers=headers,
    )


def _attachment_etag(row: dict[str, object]) -> str:
    """Identifies the response, not the file: bytes and name both move it."""
    seed = f"{row['sha256']}:{row['filename']}".encode()
    return f'"{hashlib.sha256(seed).hexdigest()[:32]}"'


def _matches(header: str | None, tag: str) -> bool:
    """`If-None-Match` is a list, and any member may be marked weak."""
    if not header:
        return False
    for candidate in header.split(","):
        cleaned = candidate.strip()
        if cleaned.startswith("W/"):
            cleaned = cleaned[2:]
        if cleaned in {tag, "*"}:
            return True
    return False


class AttachmentRename(BaseModel):
    filename: str


@router.patch(
    "/items/{item_id}/attachments/{attachment_id}",
    response_model=AttachmentResponse,
    responses=ERRORS,
)
async def rename_attachment(
    item_id: int,
    attachment_id: int,
    payload: AttachmentRename,
    library: Library,
) -> AttachmentResponse:
    """Rename an attached file. One database write; the bytes are not involved."""
    return AttachmentResponse.model_validate(
        library.rename_attachment(item_id, attachment_id, filename=payload.filename)
    )


@router.delete(
    "/items/{item_id}/attachments/{attachment_id}",
    status_code=204,
    responses=ERRORS,
    response_model=None,
)
async def delete_attachment(item_id: int, attachment_id: int, request: Request) -> Response:
    LibraryService(request.app.state.engine).delete_attachment(
        item_id, attachment_id, data_dir=request.app.state.data_dir
    )
    return Response(status_code=204)


@router.post(
    "/items/{item_id}/refresh",
    response_model=ItemResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
)
async def refresh_item(item_id: int, body: RefreshBody, request: Request) -> ItemResponse:
    library = LibraryService(request.app.state.engine)
    source, source_id = library.primary_source(item_id)
    provider = request.app.state.providers.get(source)
    if provider is None:
        raise LibraryError("provider_disabled", "Metadata provider is not enabled", status_code=422)
    try:
        payload = await provider.fetch(source_id)
    except Exception as error:
        raise LibraryError(
            "provider_failure", "Metadata could not be fetched", status_code=502
        ) from error
    metadata = dict(payload.metadata)
    metadata["authors"] = list(payload.authors)
    if payload.language is not None:
        metadata["language"] = payload.language
    prepared = None
    cover_urls = ([payload.cover_url] if payload.cover_url else []) + list(
        payload.cover_fallback_urls
    )
    for cover_url in cover_urls:
        try:
            prepared = await prepare_cover(
                request.app.state.provider_client, cover_url, request.app.state.data_dir
            )
            break
        except CoverError:
            prepared = None
    refreshed = library.overwrite_provider_fields(
        item_id,
        {
            "title": payload.title,
            "subtitle": payload.subtitle,
            "year": payload.year,
            "metadata": metadata,
        },
    )
    if prepared is not None:
        try:
            install_cover(prepared, request.app.state.data_dir, item_id)
            DomainRepository(request.app.state.engine).set_cover_path(
                item_id, f"covers/{item_id}.jpg"
            )
            refreshed = library.get_item(item_id)
        except CoverError:
            pass
    return ItemResponse.model_validate(refreshed)


@router.get("/shelves", response_model=list[ShelfResponse])
async def list_shelves(library: Library) -> list[ShelfResponse]:
    return [ShelfResponse.model_validate(value) for value in library.list_shelves()]


@router.post("/shelves", status_code=201, response_model=ShelfResponse, responses=ERRORS)
async def create_shelf(body: ShelfBody, library: Library) -> ShelfResponse:
    return ShelfResponse.model_validate(library.create_shelf(body.name))


@router.patch("/shelves/{shelf_id}", response_model=ShelfResponse, responses=ERRORS)
async def rename_shelf(shelf_id: int, body: ShelfBody, library: Library) -> ShelfResponse:
    return ShelfResponse.model_validate(library.rename_shelf(shelf_id, body.name))


@router.delete("/shelves/{shelf_id}", status_code=204)
async def delete_shelf(shelf_id: int, library: Library) -> Response:
    library.delete_shelf(shelf_id)
    return Response(status_code=204)
