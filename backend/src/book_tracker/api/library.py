import asyncio
import hashlib
import logging
from datetime import date
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi import Path as PathParam
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from book_tracker.api.identity import CurrentUser
from book_tracker.application.add import AddService
from book_tracker.application.enrichment import (
    enqueue_enrichment_backfill,
    enrichment_pending,
    provider_label,
)
from book_tracker.application.library import (
    LibraryError,
    LibraryService,
    clean_attachment_filename,
)
from book_tracker.application.outline import fetch_outline_value, outline_field
from book_tracker.application.providers import CANDIDATE_BUDGET_SECONDS, cover_candidates
from book_tracker.domain.providers import SourceRef
from book_tracker.domain.registry import DOMAINS, EntryFormat, EntryStatus, ItemTypeName
from book_tracker.domain.spec import InvalidMetadata, declares_field, validate_metadata_patch
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
from book_tracker.infrastructure.diskspace import ensure_free_space
from book_tracker.infrastructure.offload import off_loop
from book_tracker.infrastructure.providers import ProviderPayloadError
from book_tracker.infrastructure.repositories import DomainRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# One chunk in flight at a time on the way in; FileResponse does the same on the
# way out. Large enough that a 25 MiB upload is 25 reads, small enough that a
# handful of concurrent uploads is megabytes rather than hundreds of them.
UPLOAD_CHUNK_BYTES = 1024 * 1024


def library_for(request: Request, user: CurrentUser) -> LibraryService:
    return LibraryService(
        request.app.state.engine,
        user.effective_user_id,
        item_access_requires_entry=getattr(request.app.state, "auth", "off") == "on",
    )


async def service(request: Request, user: CurrentUser) -> LibraryService:
    return library_for(request, user)


Library = Annotated[LibraryService, Depends(service)]


class ShelfBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ShelfPreviewResponse(BaseModel):
    entry_id: int
    title: str
    year: int | None
    score: int | None
    cover_url: str | None


class ShelfResponse(BaseModel):
    id: int
    name: str
    slug: str
    #: The shelf's own created/renamed time (Sprint 074) -- `entry_shelves` has
    #: no timestamp of its own, so this is the nearest available signal for
    #: "recently added to", not literally the last member's addition.
    updated_at: str
    entry_count: int = 0
    #: Up to three cover URLs from the shelf's own members (Sprint 071), the same
    #: lateral top-3 join `InsightRowResponse.covers` already does (DEC-134). Empty
    #: when no member carries a cover, or when the shelf is empty.
    covers: list[str] = Field(default_factory=list)
    #: Members grouped by item type (Sprint 074 deliverable 1) — the same `GROUP BY`
    #: shape the facets block already builds for the whole library, keyed by shelf
    #: instead. An empty shelf returns `{}` here, not a missing key.
    members_by_type: dict[str, int] = Field(default_factory=dict)
    #: Up to eight members, as a shelf's ledge stands them up (Sprint 105): what an
    #: opened cover shows, beside the cover itself.
    preview: list[ShelfPreviewResponse] = Field(default_factory=list)
    #: Members with a finish date, and the mean score of the rated ones (Sprint 105).
    finished_count: int = 0
    mean_score: float | None = None


class SourceResponse(BaseModel):
    source: str
    source_id: str
    is_primary: bool


class ColumnSpecResponse(BaseModel):
    name: str
    label: str
    type: str


class FieldSpecResponse(BaseModel):
    name: str
    label: str
    type: str
    multiplicity: str
    minimum: int | None = None
    maximum: int | None = None
    #: Present only on a `rows` field: what one row of it holds.
    columns: list[ColumnSpecResponse] | None = None
    #: Whether an insights ranking may group by this field (Sprint 065).
    groupable: bool = False


class StatusSpecResponse(BaseModel):
    value: str
    label: str
    choosable: bool
    hotkey: str | None = None
    in_progress: bool = False
    planned: bool = False
    abandoned: bool = False
    finished: bool = False


class FormatSpecResponse(BaseModel):
    value: str
    label: str


class ProgressSpecResponse(BaseModel):
    """How this domain counts progress, so a screen renders a declaration.

    `total_field` names a metadata field on the *item*; it is for reading "20 / 170"
    and is never a bound (DEC-077, Sprint 040).
    """

    label: str
    unit_label: str
    total_field: str | None
    #: A `rows` field of parts and their sizes, when the domain has one (DEC-171).
    parts_field: str | None = None


class OutlinePartResponse(BaseModel):
    #: Which part: a season's number. `1` for a domain whose outline is one part.
    part: int
    #: How many episodes or chapters it has.
    size: int


class ItemTypeResponse(BaseModel):
    """What a domain says about itself, so a screen can render it without branching."""

    id: str
    label: str
    fields: list[FieldSpecResponse]
    #: The statuses this domain's entries can hold, in the order a control offers them
    #: (seam 5b). An album is not a book with different words: it has different states
    #: entirely, and the passage fields below go with the ones it does not have.
    statuses: list[StatusSpecResponse]
    default_status: str
    entry_fields: list[str]
    #: What this domain calls those fields, where a neutral word is wrong. Partial:
    #: anything absent falls back to the neutral label the client already has.
    entry_field_labels: dict[str, str]
    #: How far through one of these you are, or `None` where that means nothing.
    progress: ProgressSpecResponse | None
    formats: list[FormatSpecResponse]
    entry_panel_label: str
    #: The label counted: "Books", "Anime" (Sprint 102).
    plural_label: str
    #: Whether to offer the cover chooser at all (DEC-067 row 7).
    chooses_covers: bool


class ItemResponse(BaseModel):
    id: int
    type: str
    title: str
    subtitle: str | None
    year: int | None
    # The creator as the record credits them, then the name the library sorts it
    # under. They are different strings: García Márquez displays first-name-first
    # and sorts surname-first.
    creator: str | None
    creator_sort: str | None
    creator_sort_override: str | None
    cover_url: str | None
    metadata: dict[str, Any]
    #: What progress marks are drawn against, or `None` where nothing says how many.
    outline: list[OutlinePartResponse] | None = None
    identifiers: dict[str, str]
    sources: list[SourceResponse]


class LoanResponse(BaseModel):
    """Who has it, since when, and when it came back (Sprint 110, DEC-176)."""

    id: int
    entry_id: int
    person: str
    lent_on: str
    returned_on: str | None
    note: str | None


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
    #: How far through this one the reader is, or `None` for not recorded. Serialized
    #: even when null — these routes deliberately do not set `response_model_exclude_none`,
    #: because a client has to tell "not recorded" from "this field does not exist".
    progress: int | None
    #: Which episodes or chapters are done, by part (`{"1": [1, 2]}`), or `None` when
    #: none were ticked. When present, `progress` is their count (DEC-171).
    progress_marks: dict[str, list[int]] | None = None
    score_provisional: bool
    suggested_status: EntryStatus | None
    item: ItemResponse
    shelves: list[ShelfResponse]
    #: How you hold this copy, in the domain's declared order (DEC-059). Independent
    #: of status: a `wishlist` entry carrying `vinyl` is the pressing you mean to buy.
    formats: list[str]
    #: Where the owner keeps it, in their own words, or `None` (Sprint 110).
    location: str | None = None
    #: Place among the entries sharing this score, 1 the best (Sprint 116).
    score_rank: int | None = None
    #: The fields the owner does not remember, so they are not asked again (Sprint 124).
    unknown_fields: list[str] = []
    #: The loan that is out now, if any; the history is `/entries/{id}/loans`.
    loan: LoanResponse | None = None


class FacetsResponse(BaseModel):
    #: Whole-library totals per status, which is what the inbox badge counts.
    status_counts: dict[str, int]
    #: The same counts split by item type, because a status two domains share is
    #: not one number on a screen that lists each domain's statuses separately.
    status_counts_by_type: dict[str, dict[str, int]]
    format_counts: dict[str, int]


class EntryListResponse(BaseModel):
    items: list[EntryResponse]
    next_cursor: str | None
    total: int
    facets: FacetsResponse


class InsightRowResponse(BaseModel):
    #: The normalized grouping value — stable, and what `/api/entries`' `value` param
    #: expects back for a ranking row's "show me these" link.
    key: str
    #: The commonest original spelling among this row's members (AC5).
    label: str
    count: int
    rated_count: int
    mean_score: float | None
    score_spread: float | None
    #: Up to three cover URLs from the row's own members (Sprint 067), highest
    #: scored first. Empty when no member carries a cover, regardless of domain.
    covers: list[str]


class InsightSuppressedResponse(BaseModel):
    key: str
    label: str
    count: int


class InsightResponse(BaseModel):
    type: str
    key: str
    metric: Literal["count", "score"]
    min_rated: int
    rows: list[InsightRowResponse]
    next_cursor: str | None
    #: What a ranking left out by default, so the screen can say so rather than let
    #: the rows silently shrink (Sprint 065 deliverable 6).
    suppressed: list[InsightSuppressedResponse]
    #: True only when `metric="score"` and every group failed `min_rated` — distinct
    #: from an empty result because the domain has nothing to rank at all (AC10).
    no_rated_groups: bool
    #: Entries excluded from a `year`/`decade` ranking for having no year (AC3).
    null_count: int
    #: The ranked set's own totals (Sprint 067) — independent of `key`, and not a sum
    #: of rows, which a many-valued key over-counts.
    total_entries: int
    rated_entries: int


class ScoreDistributionResponse(BaseModel):
    type: str
    #: Index `i` is the count of entries scored `i + 1` (Sprint 073). A list rather
    #: than a dict keyed by score, since JSON object keys are strings and "ten bars
    #: in the ramp, in order" is what the client draws either way.
    counts: list[int] = Field(min_length=10, max_length=10)
    rated_count: int
    unrated_count: int


class InsightEarliestResponse(BaseModel):
    entry_id: int
    title: str
    year: int


class InsightSummaryResponse(BaseModel):
    """The figures the insights page's lead sentence reads (Sprint 102)."""

    type: str
    held: int
    #: Entries with a finish date — the Diary's measure, so the two agree.
    finished: int
    rated: int
    unrated: int
    modal_score: int | None
    earliest: InsightEarliestResponse | None


class AffectedResponse(BaseModel):
    affected: int


class SourceRefBody(BaseModel):
    source: str = Field(min_length=1, max_length=50)
    source_id: str = Field(min_length=1, max_length=200)


class ManualItemBody(BaseModel):
    item_type: ItemTypeName
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    year: int | None = Field(default=None, ge=0, le=9999)
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=100)
    identifiers: dict[str, str] = Field(default_factory=dict, max_length=20)


class EntryCreateBody(BaseModel):
    source: str | None = Field(default=None, max_length=50)
    source_id: str | None = Field(default=None, max_length=200)
    source_refs: list[SourceRefBody] = Field(default_factory=list, max_length=10)
    manual: ManualItemBody | None = None
    #: Absent means "whatever this domain's default is" — `read` for a book, `owned`
    #: for an album. The API cannot have one default, because the domains disagree.
    status: EntryStatus | None = None
    score: int | None = Field(default=None, ge=1, le=10)
    shelf_ids: list[int] = Field(default_factory=list, max_length=100)
    #: The rest of the opinion, so a book you just finished is one action rather
    #: than an add followed by an edit. Each is validated against the item's own
    #: domain, exactly as `PATCH` does — a record refuses a reread count.
    notes: str | None = None
    formats: list[str] = Field(default_factory=list, max_length=20)
    date_started: date | None = None
    date_finished: date | None = None
    reread_count: int | None = Field(default=None, ge=0)
    #: Absent on create means the column's own NULL, which is what "not recorded"
    #: is. The filter below drops a `None` nobody typed, and `0` survives it.
    progress: int | None = Field(default=None, ge=0)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)
    confirm_near_match: bool = False

    @model_validator(mode="after")
    def exactly_one_source(self) -> "EntryCreateBody":
        provider_selected = self.source is not None or self.source_id is not None
        if (self.source is None) != (self.source_id is None):
            raise ValueError("source and source_id must be provided together")
        if (self.manual is None) == (not provider_selected):
            raise ValueError("provide exactly one of manual or provider source")
        if self.manual is not None and not (self.idempotency_key or self.manual.identifiers):
            raise ValueError("manual add requires idempotency_key or an identifier")
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
    #: Three states, and `exclude_unset` is what keeps them apart: an absent key
    #: leaves the stored value alone, an explicit `null` clears it back to "not
    #: recorded", and `0` records zero — a row the owner's library actually holds.
    progress: int | None = Field(default=None, ge=0)
    #: Replaces the marks; the count follows them. A typed `progress` clears them, so
    #: sending both is refused (DEC-171).
    progress_marks: dict[str, list[int]] | None = None
    shelf_ids: list[int] | None = None
    #: Replaces the set, the way `shelf_ids` does; `[]` clears it.
    formats: list[str] | None = Field(default=None, max_length=20)
    #: Qualifies the score sent with it: `true` writes it back as provisional, which
    #: is what an undo of a provisional score needs (Sprint 109). Any score sent
    #: without it is the owner's own and confirms it, as before.
    score_provisional: bool | None = None
    #: Where it is kept; blank or `null` clears it (Sprint 110).
    location: str | None = Field(default=None, max_length=120)
    #: Why the score sent with it is what it is (Sprint 114): labels the history row
    #: this write records, or, with an unchanged score, records "still an 8".
    score_reason: Literal["reread", "time"] | None = None
    score_note: str | None = Field(default=None, max_length=280)
    #: Replaces the set of fields the owner does not remember (Sprint 124); `[]`
    #: clears it. Only `location`, `formats` and the domain's dates can be named.
    unknown_fields: list[str] | None = Field(default=None, max_length=8)

    @model_validator(mode="after")
    def required_status_when_present(self) -> "EntryPatch":
        if {"score_reason", "score_note"} & self.model_fields_set and (
            "score" not in self.model_fields_set
        ):
            raise ValueError("score_reason and score_note qualify a score; send one with them")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        if "score_provisional" in self.model_fields_set and (
            "score" not in self.model_fields_set or self.score is None
        ):
            raise ValueError("score_provisional qualifies a score; send one with it")
        return self


class ItemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    subtitle: str | None = None
    year: int | None = None
    # Sent as "" or null to drop the correction and go back to the heuristic.
    creator_sort_override: str | None = Field(default=None, max_length=300)
    # Validated against the field spec of the item's own type, not against a
    # model that would have to know every domain's vocabulary (DEC-052 seam 3).
    metadata: dict[str, Any] | None = None

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
    format: list[EntryFormat] = Field(default_factory=list)
    q: str | None = None
    location: str | None = None
    lent: bool = False


class LoanCreateBody(BaseModel):
    person: str = Field(max_length=120)
    lent_on: date
    returned_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class LoanPatch(BaseModel):
    person: str | None = Field(default=None, max_length=120)
    lent_on: date | None = None
    returned_on: date | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def required_fields_when_present(self) -> "LoanPatch":
        for name in ("person", "lent_on"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class ScoreEventResponse(BaseModel):
    """One change of a score: what it became, from what, why and when (Sprint 114)."""

    score: int | None
    previous: int | None
    #: `None` for a first score, else `time` or `reread`.
    reason: str | None
    note: str | None
    recorded_at: str


class LocationResponse(BaseModel):
    location: str
    count: int


class LoanWithEntryResponse(LoanResponse):
    entry: EntryResponse


class BulkSet(BaseModel):
    status: EntryStatus | None = None
    score: int | None = Field(default=None, ge=1, le=10)
    add_shelves: list[int] = Field(default_factory=list)
    remove_shelves: list[int] = Field(default_factory=list)
    add_formats: list[str] = Field(default_factory=list, max_length=20)
    remove_formats: list[str] = Field(default_factory=list, max_length=20)
    clear_provisional: bool = False

    @model_validator(mode="after")
    def required_status_when_present(self) -> "BulkSet":
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class BulkSelection(BaseModel):
    """The selection half of a bulk request — the one shape every bulk action
    resolves, so *Discard* understands the same `entry_ids`-or-`filter`
    selection the action bar already sends everywhere else."""

    entry_ids: list[int] | None = None
    filter: EntryFilter | None = None
    excluded_entry_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def exactly_one_selection(self) -> "BulkSelection":
        if (self.entry_ids is None) == (self.filter is None):
            raise ValueError("provide exactly one of entry_ids or filter")
        if self.entry_ids is not None and self.excluded_entry_ids:
            raise ValueError("exclusions require filter selection")
        return self


class BulkBody(BulkSelection):
    set: BulkSet


class AcceptSuggestedBody(BaseModel):
    filter: EntryFilter


@router.get("/entries", response_model=EntryListResponse, responses={400: {"model": ErrorResponse}})
def list_entries(
    library: Library,
    status: Annotated[list[EntryStatus] | None, Query()] = None,
    shelf: Annotated[list[str] | None, Query()] = None,
    format: Annotated[list[EntryFormat] | None, Query()] = None,
    #: Which domains to show. Repeated like `status`; absent means every domain.
    type: Annotated[list[ItemTypeName] | None, Query()] = None,
    q: str | None = None,
    #: A precise metadata (or `year`/`decade`) filter (Sprint 065) — how a ranking row
    #: links back to the library. Both or neither: a value with no key, or vice versa,
    #: is not a filter that means anything.
    key: str | None = None,
    value: str | None = None,
    #: Only what is kept here, exactly as written (Sprint 110).
    location: str | None = None,
    #: Only what is out on loan now.
    lent: bool = False,
    #: `missing`: only what has no cover, for the deck's *Find a cover* (Sprint 112).
    cover: Literal["missing"] | None = None,
    #: Only entries with exactly this score (Sprint 116's ranking deck).
    score: int | None = Query(default=None, ge=1, le=10),
    sort: Literal[
        "date_added", "score", "title", "creator", "year", "date_finished"
    ] = "date_added",
    order: Literal["asc", "desc"] = "desc",
    after: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> EntryListResponse:
    if (key is None) != (value is None):
        raise LibraryError(
            "invalid_insight_key", "key and value must be provided together", status_code=422
        )
    return EntryListResponse.model_validate(
        library.list_entries(
            statuses=[item.value for item in status] if status is not None else None,
            shelves=shelf or [],
            formats=[item.value for item in format or []],
            types=[item.value for item in type or []],
            key=key,
            value=value,
            location=location,
            lent=lent,
            missing_cover=cover == "missing",
            exact_score=score,
            q=q,
            sort=sort,
            order=order,
            after=after,
            limit=limit,
        )
    )


@router.get("/insights", response_model=InsightResponse, responses={422: {"model": ErrorResponse}})
def get_insights(
    library: Library,
    type: ItemTypeName,
    key: str,
    metric: Literal["count", "score"] = "count",
    min_rated: int = Query(default=2, ge=1),
    include_suppressed: bool = False,
    #: Rank inside the library's current filters (Sprint 067 deliverable 5), validated
    #: exactly as `/api/entries` validates them and forwarded to `rank()`, which has
    #: accepted them since Sprint 065.
    status: Annotated[list[EntryStatus] | None, Query()] = None,
    shelf: Annotated[list[str] | None, Query()] = None,
    format: Annotated[list[EntryFormat] | None, Query()] = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    after: str | None = None,
) -> InsightResponse:
    """Rank one domain's entries by a declared key (Sprint 065)."""
    return InsightResponse.model_validate(
        library.rank(
            item_type=type.value,
            key=key,
            metric=metric,
            min_rated=min_rated,
            include_suppressed=include_suppressed,
            statuses=[item.value for item in status] if status is not None else None,
            shelves=shelf or [],
            q=q,
            formats=[item.value for item in format or []],
            limit=limit,
            after=after,
        )
    )


@router.get(
    "/insights/scores",
    response_model=ScoreDistributionResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_score_distribution(
    library: Library,
    type: ItemTypeName,
    status: Annotated[list[EntryStatus] | None, Query()] = None,
    shelf: Annotated[list[str] | None, Query()] = None,
    format: Annotated[list[EntryFormat] | None, Query()] = None,
    q: str | None = None,
) -> ScoreDistributionResponse:
    """Per-score counts for one domain (Sprint 073 deliverable 4)."""
    return ScoreDistributionResponse.model_validate(
        library.score_distribution(
            item_type=type.value,
            statuses=[item.value for item in status] if status is not None else None,
            shelves=shelf or [],
            q=q,
            formats=[item.value for item in format or []],
        )
    )


@router.get(
    "/insights/summary",
    response_model=InsightSummaryResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_insight_summary(
    library: Library,
    type: ItemTypeName,
    status: Annotated[list[EntryStatus] | None, Query()] = None,
    shelf: Annotated[list[str] | None, Query()] = None,
    format: Annotated[list[EntryFormat] | None, Query()] = None,
    q: str | None = None,
) -> InsightSummaryResponse:
    """The lead sentence's figures for one domain (Sprint 102)."""
    return InsightSummaryResponse.model_validate(
        library.insight_summary(
            item_type=type.value,
            statuses=[item.value for item in status] if status is not None else None,
            shelves=shelf or [],
            q=q,
            formats=[item.value for item in format or []],
        )
    )


@router.post(
    "/entries",
    response_model=EntryCreateResponse,
    status_code=201,
    responses={200: {"model": EntryCreateResponse}, **ERRORS},
)
async def create_entry(
    body: EntryCreateBody,
    request: Request,
    response: Response,
    user: CurrentUser,
) -> EntryCreateResponse:
    add = AddService(
        request.app.state.engine,
        request.app.state.providers,
        user_id=user.effective_user_id,
        cover_client=request.app.state.provider_client,
        data_dir=request.app.state.data_dir,
    )
    result = await add.add(
        manual=body.manual.model_dump() if body.manual else None,
        source=body.source,
        source_id=body.source_id,
        supplied_refs=[SourceRef(value.source, value.source_id) for value in body.source_refs],
        status=body.status.value if body.status else None,
        score=body.score,
        shelf_ids=body.shelf_ids,
        entry_values={
            key: value
            for key, value in (
                ("notes", body.notes),
                ("date_started", body.date_started.isoformat() if body.date_started else None),
                ("date_finished", body.date_finished.isoformat() if body.date_finished else None),
                ("reread_count", body.reread_count),
                ("progress", body.progress),
            )
            # Only what was actually sent: `validate_entry_values` refuses a key the
            # domain does not have, and a `None` nobody typed is not a key. Note this
            # makes create and patch differ on an explicit `null`: patch clears the
            # value, create drops the key and lets the column's own NULL stand. Both
            # end at "not recorded", so the difference costs nothing.
            if value is not None
        },
        formats=body.formats,
        idempotency_key=body.idempotency_key,
        confirm_near_match=body.confirm_near_match,
    )
    if result["already_exists"]:
        response.status_code = 200
    return EntryCreateResponse.model_validate(result)


class RefileBody(BaseModel):
    source: str = Field(max_length=50)
    source_id: str = Field(max_length=200)
    source_refs: list[SourceRefBody] = Field(default_factory=list, max_length=10)


@router.post("/entries/{entry_id}/refile", response_model=EntryResponse, responses=ERRORS)
async def refile_entry(
    entry_id: int, body: RefileBody, request: Request, user: CurrentUser
) -> EntryResponse:
    """Move an entry into another library through that library's own record (Sprint 100)."""
    add = AddService(
        request.app.state.engine,
        request.app.state.providers,
        user_id=user.effective_user_id,
        cover_client=request.app.state.provider_client,
        data_dir=request.app.state.data_dir,
    )
    moved = await add.refile(
        entry_id,
        source=body.source,
        source_id=body.source_id,
        supplied_refs=[SourceRef(value.source, value.source_id) for value in body.source_refs],
    )
    return EntryResponse.model_validate(moved)


@router.patch("/entries/bulk", response_model=AffectedResponse, responses=ERRORS)
def bulk_entries(body: BulkBody, library: Library) -> AffectedResponse:
    filter_values = body.filter.model_dump(mode="json") if body.filter else None
    affected = library.bulk_update(
        entry_ids=body.entry_ids,
        filters=filter_values,
        excluded_entry_ids=body.excluded_entry_ids,
        changes=body.set.model_dump(mode="json", exclude_unset=True),
    )
    return AffectedResponse(affected=affected)


@router.post("/entries/accept-suggested", response_model=AffectedResponse)
def accept_suggested(body: AcceptSuggestedBody, library: Library) -> AffectedResponse:
    affected = library.accept_suggested(body.filter.model_dump(mode="json"))
    return AffectedResponse(affected=affected)


@router.delete("/entries/bulk", response_model=AffectedResponse, responses=ERRORS)
def bulk_delete_entries(body: BulkSelection, library: Library) -> AffectedResponse:
    """Remove the selection's entries in one transaction (triage's Discard).

    Same selection shape as `PATCH /entries/bulk`: explicit `entry_ids` or a
    server-side `filter` plus `excluded_entry_ids`, never both. Deleting has no
    `set` to send, so the body is the selection half alone.
    """
    filter_values = body.filter.model_dump(mode="json") if body.filter else None
    affected = library.bulk_delete(
        entry_ids=body.entry_ids,
        filters=filter_values,
        excluded_entry_ids=body.excluded_entry_ids,
    )
    return AffectedResponse(affected=affected)


@router.get("/now", response_model=list[EntryResponse], responses=ERRORS)
def now(library: Library) -> list[EntryResponse]:
    """Entries under way across every domain: the library's Now strip (Sprint 098)."""
    return [EntryResponse.model_validate(row) for row in library.now()]


class DiaryMonth(BaseModel):
    month: str
    counts: dict[str, int]
    entries: list[EntryResponse]


class DiaryResponse(BaseModel):
    year: int
    years: list[int]
    months: list[DiaryMonth]


class TimelineEvent(BaseModel):
    """One thing that happened: an entry finished, or its score changed (Sprint 118)."""

    kind: Literal["finished", "score"]
    #: A day for a finish; when the change was recorded for a score.
    at: str
    entry: EntryResponse
    #: The score it has (a finish) or was given (a change); `previous` what it was.
    score: int | None
    previous: int | None = None
    reason: str | None = None
    note: str | None = None


class TimelineResponse(BaseModel):
    events: list[TimelineEvent]
    next_cursor: str | None


@router.get("/diary/timeline", response_model=TimelineResponse, responses=ERRORS)
def diary_timeline(
    library: Library,
    before: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> TimelineResponse:
    """Every finish and score change across years and libraries, newest first."""
    return TimelineResponse.model_validate(library.timeline(before=before, limit=limit))


class ReviewBest(BaseModel):
    entry: EntryResponse
    score: int
    at: str


class ReviewChange(BaseModel):
    entry: EntryResponse
    score: int | None
    previous: int | None
    reason: str | None
    note: str | None
    at: str


class ReviewLeader(BaseModel):
    name: str
    count: int


class ReviewQuote(BaseModel):
    text: str
    title: str
    entry_id: int
    at: str


class YearReviewResponse(BaseModel):
    """One year read back across every library (Sprint 120, DEC-178)."""

    year: int
    finished: int
    #: What was finished, per item type.
    counts: dict[str, int]
    best: list[ReviewBest]
    #: Index `i` counts the finishes scored `i + 1` then.
    scores: list[int] = Field(min_length=10, max_length=10)
    #: Index `i` counts the finishes in month `i + 1`.
    months: list[int] = Field(min_length=12, max_length=12)
    leader: ReviewLeader | None
    changes: list[ReviewChange]
    quote: ReviewQuote | None


@router.get("/diary/{year}/review", response_model=YearReviewResponse, responses=ERRORS)
def year_review(
    library: Library, year: Annotated[int, PathParam(ge=1000, le=9999)]
) -> YearReviewResponse:
    return YearReviewResponse.model_validate(library.year_review(year))


class RevisitCard(BaseModel):
    entry: EntryResponse
    #: When the score it has was given or last looked at, or `None` when unknown.
    scored_at: str | None


class RevisitResponse(BaseModel):
    """Old scores to look at again, oldest first (Sprint 121, DEC-178)."""

    cards: list[RevisitCard]
    total: int


class GapsResponse(BaseModel):
    """Finished entries missing a finish date or a format (Sprint 125, DEC-179)."""

    entries: list[EntryResponse]
    total: int


@router.get("/gaps", response_model=GapsResponse)
def gaps(library: Library) -> GapsResponse:
    return GapsResponse.model_validate(library.gaps())


@router.get("/revisit", response_model=RevisitResponse)
def revisit(library: Library) -> RevisitResponse:
    return RevisitResponse.model_validate(library.revisit())


@router.get("/diary", response_model=DiaryResponse, responses=ERRORS)
def diary(
    library: Library, year: Annotated[int | None, Query(ge=1000, le=9999)] = None
) -> DiaryResponse:
    """What was finished in a year, by month (Sprint 098); this year when not asked.

    Resolved per request: a default in the signature is evaluated once, at import, and
    a server running across New Year would keep showing the old one.
    """
    return DiaryResponse.model_validate(library.diary(year or date.today().year))


@router.get("/search/library", response_model=list[EntryResponse], responses=ERRORS)
def search_library(
    q: Annotated[str, Query(min_length=1, max_length=300)], library: Library
) -> list[EntryResponse]:
    """Your entries for a query, best first: the command bar's library half (Sprint 094)."""
    return [EntryResponse.model_validate(row) for row in library.search_entries(q)]


@router.get("/entries/{entry_id}", response_model=EntryResponse, responses=ERRORS)
def get_entry(entry_id: int, library: Library) -> EntryResponse:
    return EntryResponse.model_validate(library.get_entry(entry_id))


@router.patch("/entries/{entry_id}", response_model=EntryResponse, responses=ERRORS)
def update_entry(entry_id: int, body: EntryPatch, library: Library) -> EntryResponse:
    return EntryResponse.model_validate(
        library.update_entry(entry_id, body.model_dump(mode="json", exclude_unset=True))
    )


class DuplicatePairResponse(BaseModel):
    """Two entries that look like one work entered twice (Sprint 113)."""

    a: EntryResponse
    b: EntryResponse
    reason: str


class PairBody(BaseModel):
    a: int
    b: int


class MergeBody(BaseModel):
    keep: int
    drop: int


class RankBody(BaseModel):
    entry_ids: list[int] = Field(max_length=1000)


@router.put("/entries/rank", response_model=list[EntryResponse], responses=ERRORS)
def rank_entries(body: RankBody, library: Library) -> list[EntryResponse]:
    """Put entries that share a score in order, best first (Sprint 116, DEC-176)."""
    return [EntryResponse.model_validate(row) for row in library.rank_entries(body.entry_ids)]


@router.get("/duplicates", response_model=list[DuplicatePairResponse])
def list_duplicates(library: Library) -> list[DuplicatePairResponse]:
    """Possible duplicates, from stored data only (Sprint 113, DEC-176)."""
    return [DuplicatePairResponse.model_validate(row) for row in library.duplicate_candidates()]


@router.post("/duplicates/dismiss", status_code=204, responses=ERRORS)
def dismiss_duplicate(body: PairBody, library: Library) -> Response:
    library.dismiss_duplicate(body.a, body.b)
    return Response(status_code=204)


@router.delete("/duplicates/dismiss", status_code=204, responses=ERRORS)
def undismiss_duplicate(body: PairBody, library: Library) -> Response:
    library.undismiss_duplicate(body.a, body.b)
    return Response(status_code=204)


@router.post("/duplicates/merge", response_model=EntryResponse, responses=ERRORS)
def merge_duplicates(body: MergeBody, library: Library) -> EntryResponse:
    """Fold `drop` into `keep`; nothing the owner wrote is lost (Sprint 113)."""
    return EntryResponse.model_validate(library.merge_entries(body.keep, body.drop))


@router.get(
    "/entries/{entry_id}/score-history",
    response_model=list[ScoreEventResponse],
    responses=ERRORS,
)
def score_history(entry_id: int, library: Library) -> list[ScoreEventResponse]:
    """How this entry's score changed, oldest first (Sprint 114, DEC-176)."""
    return [ScoreEventResponse.model_validate(row) for row in library.score_history(entry_id)]


@router.get("/entries/{entry_id}/loans", response_model=list[LoanResponse], responses=ERRORS)
def entry_loans(entry_id: int, library: Library) -> list[LoanResponse]:
    return [LoanResponse.model_validate(row) for row in library.entry_loans(entry_id)]


@router.post(
    "/entries/{entry_id}/loans", status_code=201, response_model=LoanResponse, responses=ERRORS
)
def lend_entry(entry_id: int, body: LoanCreateBody, library: Library) -> LoanResponse:
    return LoanResponse.model_validate(library.lend(entry_id, body.model_dump(mode="json")))


@router.patch("/loans/{loan_id}", response_model=LoanResponse, responses=ERRORS)
def update_loan(loan_id: int, body: LoanPatch, library: Library) -> LoanResponse:
    return LoanResponse.model_validate(
        library.update_loan(loan_id, body.model_dump(mode="json", exclude_unset=True))
    )


@router.delete("/loans/{loan_id}", status_code=204, responses=ERRORS)
def delete_loan(loan_id: int, library: Library) -> Response:
    library.delete_loan(loan_id)
    return Response(status_code=204)


@router.get("/loans", response_model=list[LoanWithEntryResponse])
def list_loans(library: Library, open: bool = False) -> list[LoanWithEntryResponse]:
    """The owner's loans with their entries, longest out first (Sprint 110)."""
    return [LoanWithEntryResponse.model_validate(row) for row in library.loans(open_only=open)]


@router.get("/locations", response_model=list[LocationResponse])
def list_locations(library: Library) -> list[LocationResponse]:
    """The places the owner has written, most used first (Sprint 110)."""
    return [LocationResponse.model_validate(row) for row in library.locations()]


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, library: Library) -> Response:
    library.delete_entry(entry_id)
    return Response(status_code=204)


@router.get(
    "/items/{item_id}",
    response_model=ItemResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
)
def get_item(item_id: int, library: Library) -> ItemResponse:
    return ItemResponse.model_validate(library.get_item(item_id))


@router.patch(
    "/items/{item_id}",
    response_model=ItemResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
)
def update_item(item_id: int, body: ItemPatch, library: Library) -> ItemResponse:
    changes = body.model_dump(exclude_unset=True)
    if body.metadata is not None:
        item_type = str(library.get_item(item_id)["type"])
        domain = DOMAINS.get(item_type)
        if domain is None:
            raise LibraryError("unknown_item_type", f"No domain describes {item_type!r}")
        try:
            changes["metadata"] = validate_metadata_patch(domain, body.metadata)
        except InvalidMetadata as error:
            raise LibraryError("invalid_metadata", str(error), status_code=422) from error
    return ItemResponse.model_validate(library.update_item(item_id, changes))


@router.get("/item-types", response_model=list[ItemTypeResponse])
def list_item_types() -> list[ItemTypeResponse]:
    """The domains this build knows, and the metadata fields each one declares."""
    return [
        ItemTypeResponse(
            id=domain.item_type,
            label=domain.label,
            fields=[
                FieldSpecResponse(
                    **{key: value for key, value in vars(field).items() if key != "columns"},
                    columns=[ColumnSpecResponse(**vars(column)) for column in field.columns]
                    if field.columns
                    else None,
                )
                for field in domain.fields
            ],
            statuses=[StatusSpecResponse(**vars(status)) for status in domain.statuses],
            default_status=domain.default_status,
            entry_fields=sorted(domain.entry_fields),
            entry_field_labels=dict(domain.entry_field_labels),
            progress=(
                ProgressSpecResponse(**vars(domain.progress))
                if domain.progress is not None
                else None
            ),
            formats=[FormatSpecResponse(**vars(row)) for row in domain.formats],
            entry_panel_label=domain.entry_panel_label,
            plural_label=domain.plural_label,
            chooses_covers=domain.chooses_covers,
        )
        for domain in DOMAINS.values()
    ]


@router.get("/items/{item_id}/cover", responses=ERRORS, response_model=None)
def get_cover(item_id: int, request: Request, user: CurrentUser) -> Response:
    item = library_for(request, user).get_item(item_id)
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
async def list_cover_candidates(
    item_id: int, request: Request, user: CurrentUser
) -> CoverCandidates:
    """Other editions of this work, offered as covers to choose from.

    Only ever reached because a chooser was opened. Nothing here runs while a library
    page renders, which is the invariant that keeps cached pages provider-free.
    """
    library = library_for(request, user)
    item = await off_loop(library.get_item, item_id)
    domain = DOMAINS.get(str(item["type"]))
    if domain is not None and not domain.chooses_covers:
        # Asked of the domain rather than branched on the type. The screen already hides
        # the control, and this is the same rule on the way in, so a client that asks
        # anyway gets an answer instead of a provider request that cannot help.
        return CoverCandidates(candidates=[], reason="not_supported")
    provider = request.app.state.providers.get("openlibrary")
    if provider is None:
        return CoverCandidates(candidates=[], reason="provider_disabled")
    edition_id, isbn = await off_loop(library.cover_lookup, item_id)
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
    user: CurrentUser,
    cover: Annotated[UploadFile | None, File()] = None,
) -> ItemResponse:
    """Replace a cover, either with an upload or with a candidate the owner picked.

    One endpoint rather than two because the write is identical past the point the bytes
    are obtained: same validation, same atomic install, same recovery of the previous
    cover if anything fails.
    """
    library = library_for(request, user)
    await off_loop(library.get_item, item_id)
    await off_loop(ensure_free_space, request.app.state.data_dir, request.app.state.min_free_bytes)
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
    previous = await off_loop(_read_if_present, target)
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
            prepared = await off_loop(
                prepare_uploaded_cover, upload[0], upload[1], request.app.state.data_dir
            )
        await off_loop(_record_cover, request, prepared, item_id, user)
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
    return ItemResponse.model_validate(await off_loop(library.get_item, item_id))


def _read_if_present(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


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
def list_attachments(item_id: int, library: Library) -> AttachmentList:
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
    user: CurrentUser,
) -> AttachmentResponse:
    """Take an opaque file and store it by the digest of its contents.

    The uploaded name is never trusted as a path. `os.path.basename` strips any
    directory a client put in front of it, and even that is belt-and-braces: the
    name is stored in the database and the blob is addressed by its own hash, so
    there is no code path where this string reaches the filesystem (DEC-048).
    """
    library = library_for(request, user)
    # Before a single chunk is read: an upload to an item that is not here should
    # cost nothing, not 25 MiB of transfer followed by a 404.
    await off_loop(library.ensure_item, item_id)
    await off_loop(ensure_free_space, request.app.state.data_dir, request.app.state.min_free_bytes)

    cap = request.app.state.attachment_max_bytes
    filename = clean_attachment_filename(file.filename or "") or "attachment"
    writer = BlobWriter(request.app.state.data_dir, max_bytes=cap)
    try:
        while chunk := await file.read(UPLOAD_CHUNK_BYTES):
            # Written straight through to disk. The previous version read the
            # whole upload into one string, so a 25 MiB file was a 25 MiB
            # allocation per concurrent request on a machine where a cover is
            # 39 KB (DEC-049).
            await off_loop(writer.write, chunk)
        stored = await off_loop(writer.commit)
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
        await off_loop(
            library.record_attachment,
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
def download_attachment(
    item_id: int, attachment_id: int, request: Request, user: CurrentUser
) -> Response:
    """Serve an opaque blob in the only way that is safe from this origin.

    Everything the application served before this endpoint had been re-encoded to
    a JPEG by the cover pipeline, so content type was never attacker-controlled.
    It is here, and the SPA shares this origin, so an uploaded HTML or SVG opened
    inline could script the application against its own API. The three headers
    below are what stop that, and none of them is optional (DEC-048).
    """
    row = library_for(request, user).get_attachment(item_id, attachment_id)
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
def rename_attachment(
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
def delete_attachment(
    item_id: int, attachment_id: int, request: Request, user: CurrentUser
) -> Response:
    library_for(request, user).delete_attachment(
        item_id, attachment_id, data_dir=request.app.state.data_dir
    )
    return Response(status_code=204)


@router.post(
    "/items/{item_id}/refresh",
    response_model=ItemResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
)
async def refresh_item(
    item_id: int, body: RefreshBody, request: Request, user: CurrentUser
) -> ItemResponse:
    library = library_for(request, user)
    provider, source_id = await off_loop(_primary_provider, request, library, item_id)
    payload = await _fetch_from_provider(provider, source_id)
    metadata = dict(payload.metadata)
    metadata["creators"] = list(payload.creators)
    # The same domain question the add path asks (DEC-125): a provider may report a
    # language for a domain with nowhere to put one, and refresh must not store it under
    # a name the domain does not have.
    refreshed_domain = DOMAINS.get(str(getattr(provider, "item_type", "")))
    if (
        payload.language is not None
        and refreshed_domain is not None
        and declares_field(refreshed_domain, "language")
    ):
        metadata["language"] = payload.language
    refreshed = await off_loop(
        library.overwrite_provider_fields,
        item_id,
        {
            "title": payload.title,
            "subtitle": payload.subtitle,
            "year": payload.year,
            "metadata": metadata,
        },
    )
    if await _install_cover_from_payload(request, payload, item_id, user):
        refreshed = await off_loop(library.get_item, item_id)
    return ItemResponse.model_validate(refreshed)


class FillResponse(BaseModel):
    item: ItemResponse
    #: The names of the fields this fill wrote; empty when the provider had nothing new.
    filled: list[str]
    #: Which provider answered, as a person reads its name, when one was asked.
    provider: str | None = None
    #: Background lookups queued instead, for an item with no provider source.
    queued: int = 0


@router.post("/items/{item_id}/fill", response_model=FillResponse, responses=ERRORS)
async def fill_item(item_id: int, request: Request, user: CurrentUser) -> FillResponse:
    """Fill the item's empty fields from its provider, and nothing else (Sprint 109).

    `refresh_item` overwrites behind a confirmation; this never replaces a value, so
    it asks for none. An item with no provider source (an import that matched on an
    ISBN alone) has nothing to fetch from directly, so its domain's enrichment is
    queued for it instead, which fills the same way in the background.
    """
    library = library_for(request, user)
    try:
        provider, source_id = await off_loop(_primary_provider, request, library, item_id)
    except LibraryError as error:
        # No source to fetch from, or one this deployment has no provider for (a
        # hand-entered item's own `manual` source): the domain's enrichment is the
        # other way a provider can be asked about it.
        if error.code not in ("refresh_unavailable", "provider_disabled"):
            raise

        queued = await off_loop(
            partial(
                enqueue_enrichment_backfill,
                request.app.state.engine,
                item_ids=[item_id],
                requested=True,
            )
        )
        # A lookup already waiting answers the same request, so it counts.
        if not queued and await off_loop(enrichment_pending, request.app.state.engine, item_id):
            queued = 1
        item = await off_loop(library.get_item, item_id)
        return FillResponse(item=ItemResponse.model_validate(item), filled=[], queued=queued)
    payload = await _fetch_from_provider(provider, source_id)
    metadata = dict(payload.metadata)
    metadata["creators"] = list(payload.creators)
    domain = DOMAINS.get(str(getattr(provider, "item_type", "")))
    if payload.language is not None and domain is not None and declares_field(domain, "language"):
        metadata["language"] = payload.language
    item, filled = await off_loop(
        library.fill_empty_provider_fields,
        item_id,
        {"subtitle": payload.subtitle, "year": payload.year, "metadata": metadata},
    )
    if not item.get("cover_url") and await _install_cover_from_payload(
        request, payload, item_id, user
    ):
        item = await off_loop(library.get_item, item_id)
        filled.append("cover")
    return FillResponse(
        item=ItemResponse.model_validate(item),
        filled=filled,
        provider=provider_label(provider.name),
    )


@router.post(
    "/items/{item_id}/outline",
    response_model=ItemResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
)
async def fetch_outline(item_id: int, request: Request, user: CurrentUser) -> ItemResponse:
    """Fetch the season list or chapter count an item has none of (Sprint 107, DEC-171).

    Only on request, and only into an empty field: an item that already has one is
    returned as it is, so a chapter count the owner typed is never replaced.
    """
    library = library_for(request, user)
    item = await off_loop(library.get_item, item_id)
    domain = DOMAINS.get(str(item["type"]))
    if domain is None:
        raise LibraryError("unknown_item_type", f"No domain describes {item['type']!r}")
    field = outline_field(domain)
    if field is not None and item["metadata"].get(field) not in (None, [], ""):
        return ItemResponse.model_validate(item)
    try:
        primary: tuple[str, str] | None = await off_loop(library.primary_source, item_id)
    except LibraryError:
        primary = None
    value = await fetch_outline_value(
        domain, item["identifiers"], primary, request.app.state.providers
    )
    assert field is not None  # fetch_outline_value refuses a domain without one
    try:
        patch = validate_metadata_patch(domain, {field: value})
    except InvalidMetadata as error:
        raise LibraryError("provider_failure", str(error), status_code=502) from error
    return ItemResponse.model_validate(
        await off_loop(library.update_item, item_id, {"metadata": patch})
    )


def _primary_provider(request: Request, library: LibraryService, item_id: int) -> tuple[Any, str]:
    """The provider and source id a refresh or cover fetch reads from.

    Shared so the two actions refuse on the same two conditions, the same way:
    an item with no provider source, or one whose source names a provider this
    deployment does not have enabled.
    """
    source, source_id = library.primary_source(item_id)
    provider = request.app.state.providers.get(source)
    if provider is None:
        raise LibraryError("provider_disabled", "Metadata provider is not enabled", status_code=422)
    return provider, source_id


async def _fetch_from_provider(provider: Any, source_id: str) -> Any:
    try:
        return await provider.fetch(source_id)
    except Exception as error:
        raise LibraryError(
            "provider_failure", "Metadata could not be fetched", status_code=502
        ) from error


async def _install_cover_from_payload(
    request: Request, payload: Any, item_id: int, user: CurrentUser
) -> bool:
    """Try each cover url the payload offers, in order; install the first that works.

    Returns whether one was installed, so a caller that only touched the cover
    (`fetch_cover`) knows whether to report `cover_unavailable`, and a caller that
    also wrote other fields (`refresh_item`) knows whether to re-read the item.
    """
    cover_urls = ([payload.cover_url] if payload.cover_url else []) + list(
        payload.cover_fallback_urls
    )
    for cover_url in cover_urls:
        try:
            prepared = await prepare_cover(
                request.app.state.provider_client, cover_url, request.app.state.data_dir
            )
        except CoverError:
            continue
        try:
            await off_loop(_record_cover, request, prepared, item_id, user)
        except CoverError:
            continue
        return True
    return False


def _record_cover(request: Request, prepared: Path, item_id: int, user: CurrentUser) -> None:
    install_cover(prepared, request.app.state.data_dir, item_id)
    DomainRepository(request.app.state.engine, user.effective_user_id).set_cover_path(
        item_id, f"covers/{item_id}.jpg"
    )


@router.post(
    "/items/{item_id}/cover/fetch",
    response_model=ItemResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
)
async def fetch_cover(item_id: int, request: Request, user: CurrentUser) -> ItemResponse:
    """Install a cover from the item's own primary provider, and nothing else.

    `Refresh from provider` already does this as a side effect, but only after
    overwriting every other provider-managed field and behind a confirmation
    dialog — the wrong shape for the one case this exists for: a cover that
    never installed at add time (a transient fetch failure, a since-fixed
    provider outage) and nothing else about the record is wrong. Nothing here
    is destructive, so unlike refresh it needs no confirmation and no
    `overwrite` flag.
    """
    library = library_for(request, user)
    provider, source_id = await off_loop(_primary_provider, request, library, item_id)
    payload = await _fetch_from_provider(provider, source_id)
    if not await _install_cover_from_payload(request, payload, item_id, user):
        raise LibraryError(
            "cover_unavailable", "The provider has no cover for this item", status_code=422
        )
    return ItemResponse.model_validate(await off_loop(library.get_item, item_id))


class ShelfSuggestionResponse(BaseModel):
    """A shelf the library already implies (Sprint 119, DEC-176)."""

    #: What it groups on (`creator:…`, `series:…`, `work:…`), to accept or dismiss it by.
    key: str
    kind: Literal["creator", "series", "work"]
    name: str
    reason: str
    members: list[ShelfPreviewResponse]


class SuggestionKeyBody(BaseModel):
    key: str = Field(min_length=1, max_length=500)


@router.get("/shelves/suggestions", response_model=list[ShelfSuggestionResponse])
def shelf_suggestions(library: Library) -> list[ShelfSuggestionResponse]:
    """Shelves proposed from what the library holds; no provider is asked."""
    return [ShelfSuggestionResponse.model_validate(row) for row in library.shelf_suggestions()]


@router.post(
    "/shelves/suggestions/accept",
    status_code=201,
    response_model=ShelfResponse,
    responses=ERRORS,
)
def accept_shelf_suggestion(body: SuggestionKeyBody, library: Library) -> ShelfResponse:
    return ShelfResponse.model_validate(library.accept_shelf_suggestion(body.key))


@router.post("/shelves/suggestions/dismiss", status_code=204, responses=ERRORS)
def dismiss_shelf_suggestion(body: SuggestionKeyBody, library: Library) -> Response:
    library.dismiss_shelf_suggestion(body.key)
    return Response(status_code=204)


@router.get("/shelves", response_model=list[ShelfResponse])
def list_shelves(library: Library) -> list[ShelfResponse]:
    return [ShelfResponse.model_validate(value) for value in library.list_shelves()]


@router.post("/shelves", status_code=201, response_model=ShelfResponse, responses=ERRORS)
def create_shelf(body: ShelfBody, library: Library) -> ShelfResponse:
    return ShelfResponse.model_validate(library.create_shelf(body.name))


@router.patch("/shelves/{shelf_id}", response_model=ShelfResponse, responses=ERRORS)
def rename_shelf(shelf_id: int, body: ShelfBody, library: Library) -> ShelfResponse:
    return ShelfResponse.model_validate(library.rename_shelf(shelf_id, body.name))


@router.delete("/shelves/{shelf_id}", status_code=204)
def delete_shelf(shelf_id: int, library: Library) -> Response:
    library.delete_shelf(shelf_id)
    return Response(status_code=204)


class SavedViewBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    query: str = Field(default="", max_length=2000)


class SavedViewResponse(BaseModel):
    id: int
    name: str
    query: str


@router.get("/views", response_model=list[SavedViewResponse])
def list_views(library: Library) -> list[SavedViewResponse]:
    return [SavedViewResponse.model_validate(value) for value in library.list_views()]


@router.post("/views", status_code=201, response_model=SavedViewResponse, responses=ERRORS)
def save_view(body: SavedViewBody, library: Library) -> SavedViewResponse:
    return SavedViewResponse.model_validate(library.save_view(body.name, body.query))


@router.delete("/views/{view_id}", status_code=204, responses=ERRORS)
def delete_view(view_id: int, library: Library) -> Response:
    library.delete_view(view_id)
    return Response(status_code=204)
