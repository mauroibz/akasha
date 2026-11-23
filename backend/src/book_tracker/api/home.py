"""Home over HTTP (Sprint 130, DEC-183): one read for every module on the screen."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from book_tracker.api.identity import CurrentUser, current_user
from book_tracker.api.library import ERRORS, EntryResponse, library_for
from book_tracker.application.home import HomeService

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


async def service(request: Request, user: CurrentUser) -> HomeService:
    return HomeService(request.app.state.engine, user.effective_user_id, library_for(request, user))


Home = Annotated[HomeService, Depends(service)]


class HomeActive(BaseModel):
    """The entry most recently touched among those under way."""

    entry: EntryResponse
    #: "Day N": 1 on the day it started; `None` when no start date is recorded.
    day: int | None


class HomeGoalCount(BaseModel):
    item_type: str
    #: The year's whole aim (a monthly goal times twelve).
    target: int
    #: Finished so far this year.
    count: int


class HomeGreeting(BaseModel):
    #: The server's today, `YYYY-MM-DD`.
    today: str
    active: HomeActive | None
    #: Entries across every library, the Inbox's unsorted ones aside.
    entries: int
    #: Entries waiting in a status their domain declares `planned`.
    pile: int
    goals: list[HomeGoalCount]


class HomeNext(BaseModel):
    entry: EntryResponse
    reason: Literal["creator", "waiting"]
    creator: str | None = None
    mean_score: float | None = None
    since: str | None = None


class HomeCover(BaseModel):
    entry_id: int
    item_id: int
    item_type: str
    title: str
    cover_url: str | None
    score: int | None


class HomeMonth(BaseModel):
    #: 1 for January.
    month: int
    #: Everything finished that month, per item type and in all.
    count: int
    counts: dict[str, int]
    #: In the order finished; at most 24 even when `count` is more.
    covers: list[HomeCover]


class HomeYearGoal(BaseModel):
    item_type: str
    period: Literal["month", "year"]
    count: int
    target: int
    done: int


class HomeYear(BaseModel):
    year: int
    months: list[HomeMonth] = Field(min_length=12, max_length=12)
    goals: list[HomeYearGoal]


class HomeDomainTile(BaseModel):
    item_type: str
    #: Entries in this library, the Inbox's unsorted ones aside.
    count: int
    #: Per status, in the domain's declared order.
    status_counts: dict[str, int]
    #: Index `i` counts the entries scored `i + 1`.
    scores: list[int] = Field(min_length=10, max_length=10)
    mean_score: float | None
    #: Up to three, best scored first.
    covers: list[HomeCover]
    without_cover: int


class HomeResponse(BaseModel):
    greeting: HomeGreeting
    now: list[EntryResponse]
    next: list[HomeNext]
    year: HomeYear
    domains: list[HomeDomainTile]


@router.get("/home", response_model=HomeResponse, responses=ERRORS)
def home(service: Home) -> HomeResponse:
    """Every module of Home from stored data; no provider is consulted.

    Today is resolved per request, so a server running across midnight moves on.
    """
    return HomeResponse.model_validate(service.home(date.today()))
