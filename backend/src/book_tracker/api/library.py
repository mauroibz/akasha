from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field, model_validator

from book_tracker.application.library import LibraryService
from book_tracker.domain.types import EntryStatus

router = APIRouter(prefix="/api")


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


class SourceResponse(BaseModel):
    source: str
    source_id: str
    is_primary: bool


class ItemResponse(BaseModel):
    id: int
    type: str
    title: str
    subtitle: str | None
    year: int | None
    sort_author: str | None
    cover_path: str | None
    metadata: dict[str, Any]
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
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def required_title_when_present(self) -> "ItemPatch":
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null")
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


@router.get("/items/{item_id}", response_model=ItemResponse, responses=ERRORS)
async def get_item(item_id: int, library: Library) -> ItemResponse:
    return ItemResponse.model_validate(library.get_item(item_id))


@router.patch("/items/{item_id}", response_model=ItemResponse, responses=ERRORS)
async def update_item(item_id: int, body: ItemPatch, library: Library) -> ItemResponse:
    return ItemResponse.model_validate(
        library.update_item(item_id, body.model_dump(exclude_unset=True))
    )


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
