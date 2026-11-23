"""The pile, ranked, over HTTP (Sprint 132, DEC-186).

`GET /api/pile` is the ranking Home's *Up next* and a goal's picks read: waiting
entries, the most likely wanted next first, each with the reasons that put it there.
Stored data only; no provider is consulted.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from book_tracker.api.identity import CurrentUser, current_user
from book_tracker.api.library import ERRORS, EntryResponse, library_for
from book_tracker.application.library import LibraryService
from book_tracker.application.ranking import rank_pile
from book_tracker.domain.registry import ItemTypeName

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


class PileReason(BaseModel):
    """One signal that fired, as a sentence naming its evidence."""

    signal: Literal["series", "creator", "affinity", "waiting", "goal", "set_aside", "similarity"]
    text: str


class PilePick(BaseModel):
    entry: EntryResponse
    #: The ranking's points: comparable within one answer, not a rating.
    score: float
    #: Only the signals that fired, the strongest first.
    reasons: list[PileReason]


def with_entries(library: LibraryService, ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ranked picks with their entries, read in one batch."""
    entries = library.get_entries([pick["entry_id"] for pick in ranked])
    return [
        {"entry": entry, "score": pick["score"], "reasons": pick["reasons"]}
        for pick, entry in zip(ranked, entries, strict=True)
    ]


@router.get("/pile", response_model=list[PilePick], responses=ERRORS)
def pile(
    request: Request,
    user: CurrentUser,
    item_type: Annotated[ItemTypeName | None, Query(alias="type")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PilePick]:
    """Waiting entries ranked from the library's own data; every library when no type."""
    ranked = rank_pile(
        request.app.state.engine,
        user.effective_user_id,
        item_type.value if item_type is not None else None,
        limit,
        embedding_model=getattr(request.app.state, "embedding_model", None),
    )
    return [
        PilePick.model_validate(pick) for pick in with_entries(library_for(request, user), ranked)
    ]
