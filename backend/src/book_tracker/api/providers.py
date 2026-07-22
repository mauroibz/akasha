from typing import Annotated, Any, cast

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel

from book_tracker.application.library import LibraryError
from book_tracker.application.providers import (
    InvalidResolution,
    ProvidersUnavailable,
    resolve_input,
    search_providers,
)
from book_tracker.domain.providers import Provider, SearchCandidate

router = APIRouter(prefix="/api")


class SourceRefResponse(BaseModel):
    source: str
    source_id: str


class SearchCandidateResponse(BaseModel):
    source: str
    source_id: str
    source_refs: list[SourceRefResponse]
    title: str
    subtitle: str | None
    authors: list[str]
    year: int | None
    original_year: int | None
    cover_url: str | None
    identifiers: dict[str, str]
    language: str | None
    metadata: dict[str, Any]

    @classmethod
    def from_domain(cls, candidate: SearchCandidate) -> "SearchCandidateResponse":
        return cls(
            source=candidate.source,
            source_id=candidate.source_id,
            source_refs=[
                SourceRefResponse(source=ref.source, source_id=ref.source_id)
                for ref in candidate.source_refs
            ],
            title=candidate.title,
            subtitle=candidate.subtitle,
            authors=list(candidate.authors),
            year=candidate.year,
            original_year=candidate.original_year,
            cover_url=candidate.cover_url,
            identifiers=dict(candidate.identifiers),
            language=candidate.language,
            metadata=dict(candidate.metadata),
        )


def _providers(request: Request) -> dict[str, Provider]:
    return cast(dict[str, Provider], request.app.state.providers)


@router.get("/search/resolve", response_model=list[SearchCandidateResponse])
async def resolve(
    url: Annotated[str, Query(min_length=1)], request: Request
) -> list[SearchCandidateResponse]:
    try:
        rows = await resolve_input(url, _providers(request))
    except InvalidResolution as error:
        raise LibraryError("invalid_resolution", str(error), status_code=422) from error
    except Exception as error:
        raise LibraryError(
            "provider_failure", "Metadata could not be resolved", status_code=502
        ) from error
    return [SearchCandidateResponse.from_domain(row) for row in rows]


@router.get("/search", response_model=list[SearchCandidateResponse])
async def search(
    q: Annotated[str, Query(min_length=1, max_length=300)], request: Request, response: Response
) -> list[SearchCandidateResponse]:
    try:
        rows = await search_providers(q, list(_providers(request).values()))
    except ProvidersUnavailable as error:
        raise LibraryError("providers_unavailable", str(error), status_code=503) from error
    represented = {ref.source for row in rows for ref in row.source_refs}
    if rows and len(represented) < len(_providers(request)):
        response.headers["X-Provider-Warning"] = "Some metadata providers are unavailable"
    return [SearchCandidateResponse.from_domain(row) for row in rows]
