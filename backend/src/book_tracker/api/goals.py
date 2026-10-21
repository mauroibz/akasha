"""Gentle goals over HTTP (Sprint 103, DEC-169)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from book_tracker.api.identity import CurrentUser
from book_tracker.api.library import ERRORS, EntryResponse, ErrorResponse
from book_tracker.application.goals import GoalService
from book_tracker.domain.registry import ItemTypeName

router = APIRouter(prefix="/api")

REFUSED: dict[int | str, dict[str, object]] = {
    **ERRORS,
    422: {"model": ErrorResponse, "description": "This library records no finish date"},
}


async def service(request: Request, user: CurrentUser) -> GoalService:
    return GoalService(request.app.state.engine, user.effective_user_id)


Goals = Annotated[GoalService, Depends(service)]


class GoalBody(BaseModel):
    count: int = Field(ge=1, le=999)
    period: Literal["month", "year"]
    #: Whether the Diary offers picks from what is waiting.
    suggest: bool = True


class GoalResponse(BaseModel):
    item_type: str
    count: int
    period: Literal["month", "year"]
    suggest: bool


class GoalProgressResponse(BaseModel):
    item_type: str
    year: int
    #: Entries finished in each month of `year`, January first.
    months: list[int] = Field(min_length=12, max_length=12)
    total: int
    #: The year's whole aim (a monthly goal times twelve), or `None` with no goal.
    target: int | None


class GoalPickResponse(BaseModel):
    entry: EntryResponse
    reason: Literal["creator", "waiting"]
    #: For a *creator* pick: whose, and their average in this library.
    creator: str | None = None
    mean_score: float | None = None
    #: For a *waiting* pick: when it was added.
    since: str | None = None


@router.get("/goals", response_model=list[GoalResponse])
def list_goals(goals: Goals) -> list[GoalResponse]:
    return [GoalResponse.model_validate(goal) for goal in goals.list_goals()]


@router.put("/goals/{item_type}", response_model=GoalResponse, responses=REFUSED)
def set_goal(item_type: ItemTypeName, body: GoalBody, goals: Goals) -> GoalResponse:
    return GoalResponse.model_validate(
        goals.set_goal(item_type.value, count=body.count, period=body.period, suggest=body.suggest)
    )


@router.delete("/goals/{item_type}", status_code=204, responses=REFUSED)
def delete_goal(item_type: ItemTypeName, goals: Goals) -> Response:
    goals.delete_goal(item_type.value)
    return Response(status_code=204)


@router.get("/goals/{item_type}/progress", response_model=GoalProgressResponse, responses=REFUSED)
def goal_progress(
    item_type: ItemTypeName, goals: Goals, year: int = Query(ge=1, le=9999)
) -> GoalProgressResponse:
    return GoalProgressResponse.model_validate(goals.progress(item_type.value, year))


@router.get("/goals/{item_type}/picks", response_model=list[GoalPickResponse], responses=REFUSED)
def goal_picks(
    item_type: ItemTypeName, goals: Goals, limit: int = Query(default=6, ge=1, le=24)
) -> list[GoalPickResponse]:
    return [
        GoalPickResponse.model_validate(pick) for pick in goals.picks(item_type.value, limit=limit)
    ]
