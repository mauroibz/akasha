import asyncio
import logging
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import parse_qs, urlsplit

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.providers import Provider, SearchCandidate, merge_and_rank

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
    limit: int = 20,
    timeout_seconds: float = 5,
) -> list[SearchCandidate]:
    results = await asyncio.gather(
        *(_search_one(provider, query, limit, timeout_seconds) for provider in providers)
    )
    if results and not any(success for success, _rows in results):
        raise ProvidersUnavailable("Every enabled metadata provider failed")
    return merge_and_rank(query, [row for _success, rows in results for row in rows])[:limit]


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
