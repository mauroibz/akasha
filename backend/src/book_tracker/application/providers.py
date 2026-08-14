import asyncio
import logging
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import parse_qs, urlsplit

from book_tracker.domain.domains import DEFAULT_DOMAIN, Domain
from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.providers import Provider, SearchCandidate, merge_and_rank
from book_tracker.infrastructure.providers import INTERACTIVE_ATTEMPTS

logger = logging.getLogger(__name__)


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
    timeout_seconds: float = 5,
) -> list[SearchCandidate]:
    results = await asyncio.gather(
        *(_search_one(provider, query, limit, timeout_seconds) for provider in providers)
    )
    if results and not any(success for success, _rows in results):
        raise ProvidersUnavailable("Every enabled metadata provider failed")
    candidates = [row for _success, rows in results for row in rows]
    return merge_and_rank(query, candidates, identity=domain.identity)[:limit]


async def resolve_input(value: str, providers: dict[str, Provider]) -> list[SearchCandidate]:
    cleaned = value.strip()
    try:
        isbn = normalize_identifier("isbn", cleaned).normalized_value
    except InvalidIdentifier:
        isbn = None
    if isbn:
        return await search_providers(f"isbn:{isbn}", list(providers.values()), timeout_seconds=5)

    parsed = urlsplit(cleaned)
    host = (parsed.hostname or "").casefold()
    openlibrary = providers.get("openlibrary")
    google = providers.get("googlebooks")
    book = re.fullmatch(r"/books/(OL\d+M)/?", parsed.path)
    work = re.fullmatch(r"/works/(OL\d+W)/?", parsed.path)
    if host in {"openlibrary.org", "www.openlibrary.org"} and book and openlibrary:
        return [await openlibrary.fetch(book.group(1))]
    if host in {"openlibrary.org", "www.openlibrary.org"} and work and openlibrary:
        resolver: Any = openlibrary
        return list(await resolver.resolve_work(work.group(1)))
    if (host == "books.google.com" or host.endswith(".books.google.com")) and google:
        source_id = parse_qs(parsed.query).get("id", [""])[0]
        if source_id:
            return [await google.fetch(source_id)]
    raise InvalidResolution("Use an ISBN, Open Library edition/work URL, or Google Books URL")


# The shared client allows 5s, which suits a search someone is watching. A chooser is
# opened deliberately and Open Library was measured answering a single edition record in
# 11.3s during Sprint 020's walkthrough, so the candidate path gets its own budget: a
# ten-second wait is tolerable, a failed chooser is not.
CANDIDATE_TIMEOUT_SECONDS = 10.0
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
