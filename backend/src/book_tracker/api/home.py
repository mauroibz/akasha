"""Home over HTTP (Sprint 130, DEC-183): one read for every module on the screen."""

from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from book_tracker.api.identity import CurrentUser, current_user
from book_tracker.api.library import ERRORS, EntryResponse, library_for
from book_tracker.api.pile import PilePick
from book_tracker.api.suggestions import SuggestionResponse
from book_tracker.application.home import HomeService
from book_tracker.application.home_layout import SHELF, YEAR, HomeLayoutService

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


async def service(request: Request, user: CurrentUser) -> HomeService:
    return HomeService(
        request.app.state.engine,
        user.effective_user_id,
        library_for(request, user),
        embedding_model=getattr(request.app.state, "embedding_model", None),
    )


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


class HomeCover(BaseModel):
    entry_id: int
    item_id: int
    item_type: str
    title: str
    cover_url: str | None
    score: int | None


class HomeYearGoal(BaseModel):
    item_type: str
    period: Literal["month", "year"]
    count: int
    target: int
    done: int


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


class HomeQuestion(BaseModel):
    """One question from Play: an old score to look at again, else a gap to fill."""

    kind: Literal["revisit", "gap"]
    entry: EntryResponse
    #: When the score was given or last looked at, for a revisit.
    scored_at: str | None


class HomeLibraryYear(BaseModel):
    """One library's year on Home (Sprint 138, DEC-192): the Diary goal band's grid."""

    item_type: str
    year: int
    #: Finished this year, all of them.
    total: int
    #: The library's goal, when it has one.
    goal: HomeYearGoal | None
    #: In the order finished; at most 48 even when `total` is more.
    covers: list[HomeCover]


class HomeShelfModule(BaseModel):
    """A shelf placed on Home (Sprint 138): its name, size and latest covers."""

    id: int
    name: str
    slug: str
    entry_count: int
    #: Its members changed last first; at most 24.
    covers: list[HomeCover]


class HomeResponse(BaseModel):
    """The Library's bands and every showcase's payload (Sprint 141, DEC-193). A showcase
    the person hid is empty or `null`, unread."""

    greeting: HomeGreeting
    now: list[EntryResponse]
    #: The pile ranked across libraries (Sprint 132): five, each with its reasons.
    next: list[PilePick]
    #: What was finished, rescored and added, newest first: the Library's second band.
    lately: list[HomeLatelyRow]
    question: HomeQuestion | None
    #: *More like this* (Sprint 134): the newest suggestions found and unanswered,
    #: across libraries, from storage.
    suggested: list[SuggestionResponse] | None
    #: The libraries' years the person shows (`year:<item type>` modules), in their
    #: order; a library with no finish this year and no goal is left out.
    library_years: list[HomeLibraryYear]
    #: The shelves the person placed on Home (`shelf:<id>` modules), in their order.
    shelf_modules: list[HomeShelfModule]


def _zone(request: Request, name: str | None) -> ZoneInfo:
    """The client's zone when it names a known one, else the server's TZ, else UTC."""
    for candidate in (name, getattr(request.app.state, "timezone", None), "UTC"):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return ZoneInfo("UTC")


@router.get("/home", response_model=HomeResponse, responses=ERRORS)
def home(
    request: Request,
    service: Home,
    layouts: Layouts,
    tz: Annotated[str | None, Query(max_length=64)] = None,
) -> HomeResponse:
    """Every module of Home from stored data; no provider is consulted.

    `tz` is the person's IANA zone (the client sends its own): their today, and the
    day an addition counts under in *Lately* (Sprint 132). Without a known one, the
    server's `TZ`. Today is resolved per request, so a server running across midnight
    moves on.
    """
    zone = _zone(request, tz)
    today = _today(zone)
    layout = layouts.read()
    hidden = {row["module"] for row in layout if row["hidden"]}

    def shown(prefix: str) -> list[str]:
        return [
            row["module"][len(prefix) :]
            for row in layout
            if row["module"].startswith(prefix) and not row["hidden"]
        ]

    return HomeResponse.model_validate(
        service.home(today, hidden, zone, years=shown(YEAR), shelves=shown(SHELF))
    )


def _today(zone: ZoneInfo) -> date:
    """Today where the person is."""
    return datetime.now(zone).date()


class HomeModuleLayout(BaseModel):
    #: One of Home's module keys, or a family member: `year:<item type>`, a library's
    #: year, or `shelf:<shelf id>` (Sprint 138). An unknown one is refused on write.
    module: str
    #: How wide on a wide screen (S 3, M 5, L 7 of 12 columns), and how much it shows.
    size: Literal["S", "M", "L"]
    hidden: bool = False
    #: A family member's name in *Edit home*; `None` for a fixed module. Ignored on write.
    label: str | None = None


class HomeLayoutBody(BaseModel):
    modules: list[HomeModuleLayout] = Field(max_length=512)


class HomeLayoutResponse(BaseModel):
    #: Every module, in order; one the stored layout did not name is appended.
    modules: list[HomeModuleLayout]
    #: What *Reset* restores.
    defaults: list[HomeModuleLayout]


@router.get("/home/layout", response_model=HomeLayoutResponse, responses=ERRORS)
def get_layout(layouts: Layouts) -> HomeLayoutResponse:
    """This person's Home layout (Sprint 131); the default until one is saved."""
    return HomeLayoutResponse.model_validate(
        {"modules": layouts.read(), "defaults": layouts.defaults()}
    )


@router.put("/home/layout", response_model=HomeLayoutResponse, responses=ERRORS)
def put_layout(body: HomeLayoutBody, layouts: Layouts) -> HomeLayoutResponse:
    """Replace this person's layout; an unknown module, or one named twice, is refused."""
    saved = layouts.write([row.model_dump() for row in body.modules])
    return HomeLayoutResponse.model_validate({"modules": saved, "defaults": layouts.defaults()})
