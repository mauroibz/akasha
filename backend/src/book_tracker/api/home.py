"""Home over HTTP (Sprint 130, DEC-183): one read for every module on the screen."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from book_tracker.api.identity import CurrentUser, current_user
from book_tracker.api.library import ERRORS, EntryResponse, library_for
from book_tracker.application.home import HomeService
from book_tracker.application.home_layout import HomeLayoutService, defaults

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


async def service(request: Request, user: CurrentUser) -> HomeService:
    return HomeService(request.app.state.engine, user.effective_user_id, library_for(request, user))


Home = Annotated[HomeService, Depends(service)]


async def layout_service(user: CurrentUser, request: Request) -> HomeLayoutService:
    return HomeLayoutService(request.app.state.engine, user.effective_user_id)


Layouts = Annotated[HomeLayoutService, Depends(layout_service)]


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


class HomeLatelyRow(BaseModel):
    """A finish, a change of score, or the entries added on one day (Sprint 131)."""

    kind: Literal["finished", "score", "added"]
    #: A day for a finish; when it was recorded for a change or an addition.
    at: str
    #: For an addition, the newest entry added that day.
    entry: EntryResponse
    score: int | None
    previous: int | None
    #: Entries added that day; 1 for a finish or a change.
    count: int


class HomeTidy(BaseModel):
    #: Pairs that look like one work entered twice.
    duplicates: int
    #: Entries without a cover, the Inbox aside.
    without_cover: int
    #: Entries in a status their domain declares finished, with no score.
    unscored: int
    #: The same per library, in registry order, only those with some: the library
    #: Tidy up links to opens one domain at a time.
    unscored_by_type: dict[str, int]


class HomeQuestion(BaseModel):
    """One question from Play: an old score to look at again, else a gap to fill."""

    kind: Literal["revisit", "gap"]
    entry: EntryResponse
    #: When the score was given or last looked at, for a revisit.
    scored_at: str | None


class HomeShelf(BaseModel):
    id: int
    name: str
    slug: str
    entry_count: int


class HomeLoan(BaseModel):
    id: int
    person: str
    lent_on: str
    entry: EntryResponse


class HomeLent(BaseModel):
    #: Open loans in all; `loans` holds the five out longest.
    total: int
    loans: list[HomeLoan]


class HomeResponse(BaseModel):
    """Every module's payload. A module the person hid is empty or `null`, unread."""

    greeting: HomeGreeting
    now: list[EntryResponse]
    next: list[HomeNext]
    year: HomeYear | None
    domains: list[HomeDomainTile]
    lately: list[HomeLatelyRow] | None
    tidy: HomeTidy | None
    question: HomeQuestion | None
    shelves: list[HomeShelf] | None
    lent: HomeLent | None


@router.get("/home", response_model=HomeResponse, responses=ERRORS)
def home(service: Home, layouts: Layouts) -> HomeResponse:
    """Every module of Home from stored data; no provider is consulted.

    Today is resolved per request, so a server running across midnight moves on.
    """
    return HomeResponse.model_validate(service.home(date.today(), layouts.hidden()))


class HomeModuleLayout(BaseModel):
    #: One of Home's module keys; an unknown one is refused on write.
    module: str
    #: How wide on a wide screen (S 3, M 5, L 7 of 12 columns), and how much it shows.
    size: Literal["S", "M", "L"]
    hidden: bool = False


class HomeLayoutBody(BaseModel):
    modules: list[HomeModuleLayout] = Field(max_length=64)


class HomeLayoutResponse(BaseModel):
    #: Every module, in order; one the stored layout did not name is appended.
    modules: list[HomeModuleLayout]
    #: What *Reset* restores.
    defaults: list[HomeModuleLayout]


@router.get("/home/layout", response_model=HomeLayoutResponse, responses=ERRORS)
def get_layout(layouts: Layouts) -> HomeLayoutResponse:
    """This person's Home layout (Sprint 131); the default until one is saved."""
    return HomeLayoutResponse.model_validate({"modules": layouts.read(), "defaults": defaults()})


@router.put("/home/layout", response_model=HomeLayoutResponse, responses=ERRORS)
def put_layout(body: HomeLayoutBody, layouts: Layouts) -> HomeLayoutResponse:
    """Replace this person's layout; an unknown module, or one named twice, is refused."""
    saved = layouts.write([row.model_dump() for row in body.modules])
    return HomeLayoutResponse.model_validate({"modules": saved, "defaults": defaults()})
