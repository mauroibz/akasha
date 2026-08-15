from datetime import UTC, datetime
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
from book_tracker.domain.domains import DEFAULT_DOMAIN, DOMAINS
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
    creators: list[str]
    credit: str | None
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
            creators=list(candidate.creators),
            credit=candidate.credit,
            year=candidate.year,
            original_year=candidate.original_year,
            cover_url=candidate.cover_url,
            identifiers=dict(candidate.identifiers),
            language=candidate.language,
            metadata=dict(candidate.metadata),
        )


def _providers(request: Request) -> dict[str, Provider]:
    return cast(dict[str, Provider], request.app.state.providers)


def _providers_for(request: Request, item_type: str) -> dict[str, Provider]:
    """Only the providers that serve this domain.

    This is what makes "adding an album spends no book-provider request" structural
    rather than a matter of care: a search never reaches a provider whose `item_type`
    is not the one being searched for.
    """
    return {
        name: provider
        for name, provider in _providers(request).items()
        if getattr(provider, "item_type", DEFAULT_DOMAIN.item_type) == item_type
    }


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


@router.get("/search/preview", response_model=SearchCandidateResponse)
async def preview(
    request: Request,
    source: Annotated[str, Query(min_length=1, max_length=50)],
    source_id: Annotated[str, Query(min_length=1, max_length=200)],
) -> SearchCandidateResponse:
    """One candidate's full record, fetched without adding anything.

    A search result carries an identity — title, creators, year, language, ISBNs —
    but not a description, a page count or a tracklist: those live in the per-item
    fetch that used to run only at add time, which is why the confirm screen had
    nothing to show. This is that fetch, on demand and writing nothing.

    It follows `search`'s quota rule rather than enrichment's (DEC-045): the spend is
    recorded and never blocked, because somebody is waiting for this one. It is a
    request per press, so the screen asks rather than fetching on every click.
    """
    provider = _providers(request).get(source)
    if provider is None:
        raise LibraryError("unknown_provider", f"No provider named {source!r}", status_code=422)
    quota = getattr(request.app.state, "provider_quota", None)
    if quota is not None:
        quota.record(source, datetime.now(UTC))
    try:
        payload = await provider.fetch(source_id)
    except Exception as error:
        raise LibraryError(
            "provider_failure", "Metadata could not be fetched", status_code=502
        ) from error
    return SearchCandidateResponse.from_domain(payload)


@router.get("/search", response_model=list[SearchCandidateResponse])
async def search(
    q: Annotated[str, Query(min_length=1, max_length=300)],
    request: Request,
    response: Response,
    type: Annotated[str, Query(max_length=50)] = DEFAULT_DOMAIN.item_type,
) -> list[SearchCandidateResponse]:
    domain = DOMAINS.get(type)
    if domain is None:
        raise LibraryError("unknown_item_type", f"No domain named {type!r}", status_code=422)
    providers = _providers_for(request, domain.item_type)
    if not providers:
        raise LibraryError(
            "providers_unavailable",
            f"No metadata provider is configured for {domain.label.lower()}s",
            status_code=503,
        )
    # Search records what it spends but is never blocked by a daily budget (DEC-045).
    # The last request of a day belongs to the person waiting for a result, not to
    # background enrichment, which can defer to tomorrow without anyone noticing.
    quota = getattr(request.app.state, "provider_quota", None)
    if quota is not None:
        moment = datetime.now(UTC)
        for name in providers:
            quota.record(name, moment)
    try:
        rows = await search_providers(q, list(providers.values()), domain=domain)
    except ProvidersUnavailable as error:
        raise LibraryError("providers_unavailable", str(error), status_code=503) from error
    represented = {ref.source for row in rows for ref in row.source_refs}
    if rows and len(represented) < len(providers):
        response.headers["X-Provider-Warning"] = "Some metadata providers are unavailable"
    return [SearchCandidateResponse.from_domain(row) for row in rows]
