"""Lit days over HTTP (Sprint 147, DEC-193): the Journal's *Every day* widget."""

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from book_tracker.api.identity import CurrentUser, current_user
from book_tracker.api.library import ERRORS, EntryResponse, library_for
from book_tracker.application.lit_days import LitDayService, parse_day

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


async def lit_day_service(request: Request, user: CurrentUser) -> LitDayService:
    return LitDayService(
        request.app.state.engine, user.effective_user_id, library_for(request, user)
    )


LitDays = Annotated[LitDayService, Depends(lit_day_service)]


def today_for(request: Request, name: str | None = None) -> date:
    """Today where the person is: their zone when they name a known one, else the
    server's `TZ`, else UTC. The same rule the Library's front uses."""
    for candidate in (name, getattr(request.app.state, "timezone", None), "UTC"):
        if not candidate:
            continue
        try:
            return datetime.now(ZoneInfo(candidate)).date()
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return datetime.now(ZoneInfo("UTC")).date()


class LitDay(BaseModel):
    #: `YYYY-MM-DD`.
    day: str
    #: What the day was for; empty when it was lit for nothing in particular.
    entries: list[EntryResponse]


class LitDaysResponse(BaseModel):
    #: Only the days that are lit, oldest first.
    days: list[LitDay]


class LightBody(BaseModel):
    #: The entries the day was for; none lights it for nothing in particular.
    entry_ids: list[int] = Field(default_factory=list, max_length=24)


@router.get("/lit-days", response_model=LitDaysResponse, responses=ERRORS)
def list_lit_days(
    lit: LitDays,
    start: Annotated[str, Query(alias="from", max_length=10)],
    end: Annotated[str, Query(alias="to", max_length=10)],
) -> LitDaysResponse:
    """The lit days of a week or a month; at most 62 days at a time."""
    return LitDaysResponse.model_validate({"days": lit.days(parse_day(start), parse_day(end))})


@router.put("/lit-days/{day}", response_model=LitDay, responses=ERRORS)
def light_day(
    day: str,
    body: LightBody,
    lit: LitDays,
    request: Request,
    tz: Annotated[str | None, Query(max_length=64)] = None,
) -> LitDay:
    """Light a day by hand, saying what it was for or nothing; a day to come is refused."""
    return LitDay.model_validate(lit.light(parse_day(day), body.entry_ids, today_for(request, tz)))


@router.delete("/lit-days/{day}", status_code=204, responses=ERRORS)
def unlight_day(day: str, lit: LitDays) -> Response:
    """Take everything off a day."""
    lit.unlight(parse_day(day))
    return Response(status_code=204)
