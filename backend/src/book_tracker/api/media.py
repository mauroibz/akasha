"""Your media over HTTP (Sprint 143, DEC-193)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from book_tracker.api.identity import CurrentUser, current_user
from book_tracker.api.library import ERRORS
from book_tracker.application.media import MediaService

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


async def media_service(user: CurrentUser, request: Request) -> MediaService:
    return MediaService(request.app.state.engine, user.effective_user_id)


Media = Annotated[MediaService, Depends(media_service)]


class MediumChoice(BaseModel):
    item_type: str
    #: `front` feeds the front of the Library; `kept` is in the library and its
    #: choosers only; `off` is shown nowhere. Nothing is deleted by any of them.
    presence: Literal["front", "kept", "off"]


class MediumResponse(MediumChoice):
    #: The domain's plural label.
    label: str
    #: Whether the person holds an entry of it, the Inbox aside.
    held: bool


class MediaBody(BaseModel):
    media: list[MediumChoice] = Field(max_length=64)


class MediaResponse(BaseModel):
    #: Every registered medium once, in the person's order.
    media: list[MediumResponse]
    #: Whether the person has saved a list; until then the list is derived from what
    #: they hold, and the first screen asks.
    chosen: bool


@router.get("/media", response_model=MediaResponse, responses=ERRORS)
def get_media(media: Media) -> MediaResponse:
    """This person's media, in their order (Sprint 143)."""
    return MediaResponse.model_validate(media.read())


@router.put("/media", response_model=MediaResponse, responses=ERRORS)
def put_media(body: MediaBody, media: Media) -> MediaResponse:
    """Replace the list; a medium it does not name is appended, kept if held, else off."""
    return MediaResponse.model_validate(media.write([row.model_dump() for row in body.media]))
