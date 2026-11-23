"""Suggestions over HTTP (Sprint 133, DEC-183 points 4-7).

`POST /api/entries/{id}/more-like-this` queues a round (or shows a recent one again);
the rest read and answer what rounds stored. Every read is stored data only: no
provider and no source is consulted to render a suggestion. Progress reaches a page
through the event stream, as the `recommend` job's progress.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from book_tracker.api.identity import CurrentUser, current_user
from book_tracker.api.library import ERRORS
from book_tracker.application.library import LibraryError
from book_tracker.application.recommendations import (
    SuggestionStore,
    answer_suggestion,
    queue_enrichment,
    start_round,
)
from book_tracker.domain.registry import ItemTypeName

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])

RoundStatus = Literal[
    "queued", "selecting", "enriching", "done", "failed", "over_budget", "not_configured"
]
Enrichment = Literal["pending", "enriched", "unresolved"]
Answer = Literal["want", "not_for_me", "seen"]


class SuggestionReason(BaseModel):
    """Why the source chose it, in the ranked pile's shape: the signal is the source."""

    signal: str
    text: str


class SuggestionSeed(BaseModel):
    """The entry a round was about: what a suggestion is *more like*."""

    entry_id: int
    title: str


class SuggestionResponse(BaseModel):
    id: int
    round_id: int
    item_type: ItemTypeName
    #: The recommendation source that chose it.
    source: str
    title: str
    year: int | None
    creator: str | None
    external_ids: dict[str, str]
    reason: SuggestionReason | None
    source_score: float | None
    #: What the source gave for showing it (a poster URL, an overview), as given.
    display: dict[str, Any]
    #: `pending` until the domain finds it in a provider; `unresolved` when it could not.
    enrichment: Enrichment
    #: The shared item it resolved to, once `enriched`.
    item_id: int | None
    #: This person's entry on that item, once they have one (after *Want*).
    entry_id: int | None
    #: The stored cover of the item it resolved to, served to the person it was
    #: suggested to (Sprint 134); `None` until resolved or when it has none.
    cover_url: str | None = None
    #: The entry its round was seeded by, while it exists.
    seed: SuggestionSeed | None = None
    answer: Answer | None
    answered_at: str | None
    created_at: str


class RoundResponse(BaseModel):
    id: int
    item_type: ItemTypeName
    seed_entry_id: int | None
    source: str
    status: RoundStatus
    #: Why a round failed, was refused or is not configured; on a `done` round, why
    #: some of its top candidates are still pending.
    error: str | None
    created_at: str
    finished_at: str | None
    suggestions: list[SuggestionResponse]


class EnrichResponse(BaseModel):
    suggestion: SuggestionResponse
    #: The queued `enrich_suggestion` job, or `None` when nothing was left to do.
    job_id: str | None


class AnswerBody(BaseModel):
    #: `want` adds the resolved item as a planned entry; `null` takes an answer back.
    answer: Answer | None = Field(...)


def _store(request: Request, user: CurrentUser) -> SuggestionStore:
    return SuggestionStore(
        request.app.state.engine,
        user.effective_user_id,
        embedding_model=getattr(request.app.state, "embedding_model", None),
    )


Store = Annotated[SuggestionStore, Depends(_store)]


@router.post(
    "/entries/{entry_id}/more-like-this",
    response_model=RoundResponse,
    status_code=202,
    responses={422: {"description": "Not a source of this library"}, **ERRORS},
)
def more_like_this(
    entry_id: int,
    request: Request,
    user: CurrentUser,
    source: Annotated[str | None, Query(max_length=50)] = None,
    refresh: bool = False,
) -> RoundResponse:
    """A round seeded by one entry: queued, or the last one under a day old."""
    found = start_round(
        request.app.state.engine,
        request.app.state.recommendation_sources,
        user.effective_user_id,
        entry_id,
        source=source,
        refresh=refresh,
        embedding_model=getattr(request.app.state, "embedding_model", None),
    )
    return RoundResponse.model_validate(found)


@router.get("/suggestions", response_model=list[SuggestionResponse], responses=ERRORS)
def suggestions(
    store: Store,
    seed_entry_id: int | None = None,
    item_type: ItemTypeName | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SuggestionResponse]:
    """Unanswered suggestions worth showing, newest first; stored data only."""
    return [
        SuggestionResponse.model_validate(row)
        for row in store.suggestions(
            seed_entry_id=seed_entry_id,
            item_type=item_type.value if item_type is not None else None,
            limit=limit,
        )
    ]


@router.get("/suggestion-rounds/{round_id}", response_model=RoundResponse, responses=ERRORS)
def suggestion_round(round_id: int, store: Store) -> RoundResponse:
    found = store.round(round_id)
    if found is None:
        raise LibraryError("round_not_found", "Round was not found", status_code=404)
    return RoundResponse.model_validate(found)


@router.post(
    "/suggestions/{suggestion_id}/enrich",
    response_model=EnrichResponse,
    status_code=202,
    responses={200: {"model": EnrichResponse}, **ERRORS},
)
def enrich_suggestion(
    suggestion_id: int, request: Request, response: Response, user: CurrentUser
) -> EnrichResponse:
    """Find a pending suggestion in its providers now; 200 when there is nothing to do."""
    found, job_id = queue_enrichment(
        request.app.state.engine, user.effective_user_id, suggestion_id
    )
    if job_id is None:
        response.status_code = 200
    return EnrichResponse(suggestion=SuggestionResponse.model_validate(found), job_id=job_id)


@router.patch("/suggestions/{suggestion_id}", response_model=SuggestionResponse, responses=ERRORS)
def answer(
    suggestion_id: int,
    request: Request,
    user: CurrentUser,
    body: Annotated[AnswerBody, Body()],
) -> SuggestionResponse:
    return SuggestionResponse.model_validate(
        answer_suggestion(
            request.app.state.engine, user.effective_user_id, suggestion_id, body.answer
        )
    )
