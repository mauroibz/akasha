import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from book_tracker.domain.providers import Provider, SearchCandidate, merge_and_rank
from book_tracker.domain.registry import DEFAULT_DOMAIN, DOMAINS
from book_tracker.domain.spec import Domain
from book_tracker.infrastructure.providers import INTERACTIVE_ATTEMPTS, ProviderPayloadError

logger = logging.getLogger(__name__)


# How long anyone waiting on a provider is made to wait. Open Library was measured
# answering a single edition record in 11.3s during Sprint 020's walkthrough, and Kitsu
# answering a search in 3.5-5.8s on 2026-09-02; ten seconds covers a healthy provider
# having a slow moment, and a failed search or a failed chooser is worse than a slow one.
# It bounds one provider's answer, not their sum — a search runs them concurrently.
CANDIDATE_TIMEOUT_SECONDS = 10.0


class ProvidersUnavailable(RuntimeError):
    pass


class InvalidResolution(ValueError):
    pass


async def _search_one(
    provider: Provider, query: str, limit: int, timeout_seconds: float
) -> tuple[bool, list[SearchCandidate]]:
    try:
        rows = await asyncio.wait_for(provider.search(query, limit), timeout_seconds)
        return True, rows
    except Exception as error:
        logger.warning(
            "provider search failed",
            extra={"provider": provider.name, "error": type(error).__name__},
        )
        return False, []


async def search_providers(
    query: str,
    providers: Sequence[Provider],
    *,
    domain: Domain = DEFAULT_DOMAIN,
    limit: int = 20,
    # Five seconds sat below what a healthy provider takes: five live Kitsu searches on
    # 2026-09-02 measured 3.5-5.8 s, so two of five were dropped as failures while Kitsu
    # was the anime domain's only working provider (DEC-125). The providers run
    # concurrently, so this bounds the slowest answer rather than their sum.
    timeout_seconds: float = CANDIDATE_TIMEOUT_SECONDS,
) -> list[SearchCandidate]:
    results = await asyncio.gather(
        *(_search_one(provider, query, limit, timeout_seconds) for provider in providers)
    )
    if results and not any(success for success, _rows in results):
        raise ProvidersUnavailable("Every enabled metadata provider failed")
    candidates = [row for _success, rows in results for row in rows]
    return merge_and_rank(query, candidates, identity=domain.identity)[:limit]


async def resolve_input(value: str, providers: dict[str, Provider]) -> list[SearchCandidate]:
    """Turn something pasted into the add box into candidates.

    What a string *means* is the domain's to say (DEC-052 seam 6): an ISBN and an
    Open Library URL belong to books, a MusicBrainz release-group URL to albums, and
    this function only spends what the recognizing domain asks for.
    """
    cleaned = value.strip()
    last_miss: ProviderPayloadError | None = None
    for domain in DOMAINS.values():
        try:
            match = domain.recognize(cleaned)
        except Exception as error:
            # One domain must not be able to break another's add box. This loop asks
            # every registered domain in turn, so a recognizer that raises would end the
            # loop and deny every domain after it its turn — a domain added by one team
            # silently breaking a domain added by another. The recognizer is still
            # wrong, and `test_domain_conformance.py` is what says so; here it is only
            # this domain's mistake.
            logger.warning(
                "domain recognizer failed",
                extra={"item_type": domain.item_type, "error": type(error).__name__},
            )
            continue
        if match is None:
            continue
        if match.action == "search":
            candidates = [
                provider
                for provider in providers.values()
                if getattr(provider, "item_type", DEFAULT_DOMAIN.item_type) == domain.item_type
            ]
            return await search_providers(match.value, candidates, domain=domain, timeout_seconds=5)
        provider = providers.get(match.provider)
        if provider is None:
            continue
        if match.action == "work":
            resolver: Any = provider
            return list(await resolver.resolve_work(match.value))
        try:
            return [await provider.fetch(match.value)]
        except ProviderPayloadError as error:
            # A typed miss is an answer about *this* domain's catalogue, not about
            # the URL: the movie recognizer claims every IMDb title link, and its
            # film guard refusing a series entity is exactly the case the series
            # domain exists for. Offer the next domain its turn. Anything else — an
            # outage, throttling, garbage — is the resolve's failure, not an
            # invitation for the next domain to guess.
            if error.code != "record_not_found":
                raise
            logger.info(
                "domain refused a URL it recognized; trying the next",
                extra={"item_type": domain.item_type, "value": match.value},
            )
            last_miss = error
            continue
    if last_miss is not None:
        # Every domain that recognized the URL refused it: the record genuinely
        # does not exist anywhere this build can look. The last refusal is the
        # answer, exactly as it was before the fall-through existed.
        raise last_miss
    raise InvalidResolution(
        "Use an ISBN, an Open Library edition/work URL, a Google Books URL, "
        "or a MusicBrainz release group URL"
    )


# The chooser is opened deliberately and does not block the page behind it, so it can
# wait a little — but only a little, and only once. Two attempts at ten seconds under a
# single overall budget: if Open Library is having a bad minute the dialog says so
# quickly and the reader can reopen it, rather than holding a spinner for a minute.
CANDIDATE_BUDGET_SECONDS = 15.0


async def cover_candidates(
    openlibrary: Any,
    *,
    edition_id: str | None = None,
    isbn: str | None = None,
    limit: int = 20,
) -> list[SearchCandidate]:
    """The other editions of this work, as cover options.

    Affordable because of what DEC-044 measured: the work an edition belongs to already
    lists its siblings, and enrichment has fetched that record for every book anyway, so
    discovering candidates adds no request to the enrichment path. This function runs
    only when a chooser is opened, never while a library page renders.

    Reached from an Open Library edition id when the item has one, and otherwise from an
    ISBN — which matters, because an item added through Google Books has no Open Library
    source and would otherwise get nothing. That lookup is Open Library's, so it spends
    no metered quota either way.
    """
    work: str | None = None
    if edition_id:
        work = await openlibrary.work_id(
            edition_id, timeout=CANDIDATE_TIMEOUT_SECONDS, attempts=INTERACTIVE_ATTEMPTS
        )
    if work is None and isbn:
        payload = await openlibrary.fetch_by_isbn(isbn)
        work = await openlibrary.work_id(
            payload.source_id, timeout=CANDIDATE_TIMEOUT_SECONDS, attempts=INTERACTIVE_ATTEMPTS
        )
    if work is None:
        return []

    rows = await openlibrary.resolve_work(
        work, limit=limit, timeout=CANDIDATE_TIMEOUT_SECONDS, attempts=INTERACTIVE_ATTEMPTS
    )
    seen: set[str] = set()
    candidates: list[SearchCandidate] = []
    for row in rows:
        # `resolve_work` falls back to an `/b/olid/` URL for an edition with no cover
        # id, which is a plausible string and a 404. Offering those puts blank,
        # clickable tiles in the grid — the walkthrough chose one and got a 422 — so
        # only an edition whose record carries a real cover id is a candidate.
        if not row.cover_url or "/b/id/" not in row.cover_url:
            continue
        # Several editions of a work commonly share one scanned cover; showing it three
        # times reads as a bug rather than as choice.
        if row.cover_url in seen:
            continue
        seen.add(row.cover_url)
        candidates.append(row)
    return candidates
