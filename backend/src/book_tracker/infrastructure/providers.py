import asyncio
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef


class ProviderPayloadError(ValueError):
    """A provider answered, but not with data we can use.

    `code` is the stable machine-readable reason; the message is written for a person
    reading a failed enrichment job.
    """

    def __init__(self, message: str, *, code: str = "provider_payload_invalid") -> None:
        super().__init__(message)
        self.code = code


MAX_PROVIDER_BYTES = 2 * 1024 * 1024
# Undated search results are resolved against `/works/{id}/editions.json`. Bounded so a
# 20-result search never opens 20 simultaneous connections to Open Library.
WORK_RESOLUTION_CONCURRENCY = 5


def create_provider_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """Build the shared client every provider uses.

    Tests construct it with a replay transport so they exercise the same redirect and
    timeout behaviour the application runs with.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(5),
        limits=httpx.Limits(max_connections=10),
        # `https://openlibrary.org/isbn/{isbn}.json` answers 302 to the edition record.
        # Without this a redirect passes `raise_for_status` and then fails JSON parsing.
        follow_redirects=True,
        transport=transport,
    )


async def _bounded_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: Mapping[str, str | int],
    headers: Mapping[str, str] | None = None,
) -> Mapping[str, Any]:
    async with client.stream("GET", url, params=params, headers=headers) as response:
        response.raise_for_status()
        declared = int(response.headers.get("content-length", "0"))
        if declared > MAX_PROVIDER_BYTES:
            raise ProviderPayloadError("Provider response exceeds byte limit")
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_PROVIDER_BYTES:
                raise ProviderPayloadError("Provider response exceeds byte limit")
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderPayloadError("Provider returned malformed JSON") from error
    if not isinstance(decoded, dict):
        raise ProviderPayloadError("Provider returned a non-object payload")
    return decoded


_YEAR_PATTERN = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")


def _year(value: object) -> int | None:
    """Read a publication year out of whatever shape a provider used.

    Open Library publishes edition dates as `"1984"`, `"1984-03"`, and `"Mar 09, 2005"`
    alike. Taking the first four characters read the last of those as `"Mar "` and threw
    the year away, which is why most search results arrived without one.
    """
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value if 1000 <= value <= 2999 else None
    match = _YEAR_PATTERN.search(str(value))
    return int(match.group(1)) if match else None


def _isbn(values: list[object]) -> dict[str, str]:
    for value in values:
        try:
            normalized = normalize_identifier("isbn", str(value))
            return {"isbn13": normalized.normalized_value}
        except InvalidIdentifier:
            continue
    return {}


def isbn13_set(values: Iterable[object]) -> frozenset[str]:
    """Every value that normalizes to an ISBN13, not only the first.

    `_isbn` keeps the first parseable value because that is what a payload's single
    `identifiers["isbn13"]` slot can hold. Verifying that a candidate really is the
    edition that was asked for needs all of them: a volume commonly lists its ISBN10
    and its ISBN13, and either may come first.
    """
    found: set[str] = set()
    for value in values:
        try:
            found.add(normalize_identifier("isbn", str(value)).normalized_value)
        except InvalidIdentifier:
            continue
    return frozenset(found)


EDITION_CONFIRMED = "confirmed"
EDITION_CONTRADICTED = "contradicted"
EDITION_UNVERIFIABLE = "unverifiable"


def classify_edition(candidate_isbns: Iterable[object], requested_isbn: str) -> str:
    """Decide whether a fetched candidate is provably the edition that was requested.

    Three outcomes, not two, and the third is the common one for Google Books: a
    scanned library volume frequently exposes only a barcode
    (`OTHER: UOM:39015008575477`) and no ISBN at all, so nothing in its own payload
    either confirms or denies that it is the edition the ISBN asked for.
    """
    found = isbn13_set(candidate_isbns)
    if not found:
        return EDITION_UNVERIFIABLE
    try:
        wanted = normalize_identifier("isbn", requested_isbn).normalized_value
    except InvalidIdentifier:
        return EDITION_UNVERIFIABLE
    return EDITION_CONFIRMED if wanted in found else EDITION_CONTRADICTED


def _language(value: object) -> str | None:
    values = value if isinstance(value, list) else [value]
    if not values or values[0] is None:
        return None
    first = values[0]
    if isinstance(first, dict):
        first = first.get("key") or first.get("code")
    if not first:
        return None
    code = str(first).casefold()
    if code.startswith("/languages/"):
        code = code.removeprefix("/languages/")
    return {"spa": "es", "eng": "en"}.get(code, code[:2])


def _description(value: object) -> str | None:
    if isinstance(value, dict):
        value = value.get("value")
    return str(value).strip() if value else None


def _keys(values: object, prefix: str) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        str(value.get("key", "")).removeprefix(prefix)
        for value in values
        if isinstance(value, dict) and value.get("key")
    ]


class OpenLibraryProvider:
    name = "openlibrary"
    item_type = "book"
    enabled = True

    def __init__(self, client: httpx.AsyncClient, contact: str) -> None:
        self.client = client
        self.headers = {"User-Agent": f"Akasha/0.1 ({contact})"}

    async def _json(self, url: str, **params: str | int) -> Mapping[str, Any]:
        return await _bounded_json(self.client, url, params=params, headers=self.headers)

    def _candidate(self, row: Mapping[str, Any]) -> SearchCandidate | None:
        nested = row.get("editions")
        nested_docs = nested.get("docs", []) if isinstance(nested, dict) else []
        edition = nested_docs[0] if isinstance(nested_docs, list) and nested_docs else {}
        editions = row.get("edition_key")
        source_id = str(edition.get("key", "")).removeprefix("/books/")
        if not source_id:
            source_id = str(editions[0]) if isinstance(editions, list) and editions else ""
        if not source_id or not row.get("title"):
            return None
        cover_id = edition.get("cover_i") or row.get("cover_i")
        metadata: dict[str, Any] = {}
        if row.get("first_publish_year") is not None:
            metadata["original_year"] = row["first_publish_year"]
        return SearchCandidate(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title=str(row["title"]),
            subtitle=str(row["subtitle"]) if row.get("subtitle") else None,
            authors=tuple(
                str(value) for value in edition.get("author_name", row.get("author_name", []))
            ),
            year=_year(edition.get("publish_date")),
            cover_url=(
                f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None
            ),
            identifiers=_isbn(list(edition.get("isbn", row.get("isbn", [])))),
            language=_language(edition.get("language", row.get("language"))),
            metadata=metadata,
            original_year=_year(row.get("first_publish_year")),
        )

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        body = await self._json(
            "https://openlibrary.org/search.json",
            q=query,
            limit=min(limit, 20),
            fields=(
                "key,title,subtitle,author_name,first_publish_year,isbn,cover_i,"
                "language,edition_key,editions,editions.key,editions.title,editions.subtitle,"
                "editions.author_name,editions.publish_date,editions.isbn,editions.language,"
                "editions.cover_i"
            ),
        )
        docs = body.get("docs", [])
        if not isinstance(docs, list):
            raise ProviderPayloadError("Open Library docs must be a list")
        # Pair each candidate with the work it came from. Rows that yield no candidate
        # are dropped, so building the two lists separately would misalign them.
        paired = [
            (str(row.get("key", "")).removeprefix("/works/"), candidate)
            for row in docs
            if isinstance(row, dict)
            if (candidate := self._candidate(row))
        ]
        return await self._resolve_missing_years(paired)

    async def _resolve_missing_years(
        self, paired: list[tuple[str, SearchCandidate]]
    ) -> list[SearchCandidate]:
        """Fill the edition year on every result the search response left undated.

        This used to run for the first row only, so results 2..20 reached the picker
        without a year. Every undated row is resolved now, concurrently and behind a
        semaphore so a 20-result search cannot fan out 20 simultaneous requests at
        Open Library.
        """
        gate = asyncio.Semaphore(WORK_RESOLUTION_CONCURRENCY)

        async def resolve(
            index: int, work_id: str, candidate: SearchCandidate
        ) -> tuple[int, SearchCandidate]:
            if candidate.year is not None or not work_id:
                return index, candidate
            async with gate:
                try:
                    editions = await self.resolve_work(work_id, limit=20)
                except (httpx.HTTPError, ProviderPayloadError):
                    return index, candidate
            edition = next((row for row in editions if row.year is not None), None)
            if edition is None:
                return index, candidate
            return index, replace(
                edition,
                title=candidate.title,
                subtitle=candidate.subtitle or edition.subtitle,
                authors=candidate.authors,
                cover_url=edition.cover_url or candidate.cover_url,
                original_year=candidate.original_year,
                metadata=candidate.metadata,
            )

        resolved = await asyncio.gather(
            *(
                resolve(index, work_id, candidate)
                for index, (work_id, candidate) in enumerate(paired)
            )
        )
        # Ordering is the provider's relevance ordering and must survive the fan-out.
        return [candidate for _index, candidate in sorted(resolved, key=lambda row: row[0])]

    async def fetch(self, source_id: str) -> ItemPayload:
        row = await self._json(f"https://openlibrary.org/books/{source_id}.json")
        return await self._edition_payload(row, source_id)

    async def _edition_payload(
        self, row: Mapping[str, Any], source_id: str, requested_isbn: str | None = None
    ) -> ItemPayload:
        title = row.get("title")
        if not title:
            raise ProviderPayloadError(
                "Open Library edition has no title", code="edition_incomplete"
            )
        author_ids = _keys(row.get("authors"), "/authors/")
        author_records = []
        for author_id in author_ids:
            try:
                author_records.append(
                    await self._json(f"https://openlibrary.org/authors/{author_id}.json")
                )
            except (httpx.HTTPError, ProviderPayloadError):
                author_records.append({})
        authors = tuple(
            str(record.get("name") or author_id)
            for author_id, record in zip(author_ids, author_records, strict=True)
        )
        work_ids = _keys(row.get("works"), "/works/")
        work = (
            await self._json(f"https://openlibrary.org/works/{work_ids[0]}.json")
            if work_ids
            else {}
        )
        identifiers = _isbn(list(row.get("isbn_13", [])) + list(row.get("isbn_10", [])))
        edition_covers = row.get("covers", [])
        work_covers = work.get("covers", [])
        cover_ids = edition_covers if edition_covers else work_covers
        cover = cover_ids[0] if isinstance(cover_ids, list) and cover_ids else None
        publisher = next(
            (str(value).strip() for value in row.get("publishers", []) if str(value).strip()), None
        )
        subjects = row.get("subjects") or work.get("subjects") or []
        created = work.get("created")
        created_value = created.get("value") if isinstance(created, dict) else created
        original_year = _year(work.get("first_publish_date") or created_value)
        metadata = {
            "authors": list(authors),
            "publisher": publisher,
            "language": _language(row.get("languages")),
            "page_count": row.get("number_of_pages"),
            "description": _description(row.get("description"))
            or _description(work.get("description")),
            "subjects": [str(value) for value in subjects if value],
            "series": next(iter(row.get("series", [])), None),
            "original_year": original_year,
        }
        metadata = {
            key: value for key, value in metadata.items() if value not in (None, "", [], {})
        }
        cover_urls: list[str] = []
        if cover:
            cover_urls.append(f"https://covers.openlibrary.org/b/id/{cover}-L.jpg?default=false")
        if source_id:
            cover_urls.append(
                f"https://covers.openlibrary.org/b/olid/{source_id}-L.jpg?default=false"
            )
        if identifiers.get("isbn13"):
            cover_urls.append(
                f"https://covers.openlibrary.org/b/isbn/{identifiers['isbn13']}-L.jpg?default=false"
            )
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title=str(title),
            subtitle=str(row["subtitle"]) if row.get("subtitle") else None,
            authors=authors,
            year=_year(row.get("publish_date")),
            cover_url=cover_urls[0] if cover_urls else None,
            identifiers=identifiers,
            language=_language(row.get("languages")),
            metadata=metadata,
            original_year=original_year,
            cover_fallback_urls=tuple(cover_urls[1:]),
            # Every ISBN the edition record carries, not just the one that fits the
            # payload's single identifier slot.
            edition_match=(
                None
                if requested_isbn is None
                else classify_edition(
                    list(row.get("isbn_13", [])) + list(row.get("isbn_10", [])), requested_isbn
                )
            ),
        )

    async def fetch_by_isbn(self, isbn: str) -> ItemPayload:
        """Fetch edition data by ISBN. Used by background enrichment.

        `/books/{id}.json` accepts an OLID only and answers 404 for an ISBN, so this
        goes through `/isbn/{isbn}.json`, which redirects to the edition record.
        """
        try:
            row = await self._json(f"https://openlibrary.org/isbn/{isbn}.json")
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise ProviderPayloadError(
                    f"Open Library has no edition for ISBN {isbn}", code="edition_not_found"
                ) from error
            raise ProviderPayloadError(
                f"Open Library returned HTTP {error.response.status_code} for ISBN {isbn}",
                code="provider_http_error",
            ) from error
        except httpx.HTTPError as error:
            raise ProviderPayloadError(
                f"Open Library could not be reached for ISBN {isbn}", code="provider_unreachable"
            ) from error
        key = str(row.get("key", ""))
        if not key.startswith("/books/"):
            # `/isbn/` can redirect to a work rather than an edition; `items.year` must
            # never be populated from work-level data.
            raise ProviderPayloadError(
                f"Open Library resolved ISBN {isbn} to {key or 'no record'}, not an edition",
                code="edition_not_found",
            )
        return await self._edition_payload(row, key.removeprefix("/books/"), isbn)

    async def resolve_work(self, work_id: str, limit: int = 20) -> list[SearchCandidate]:
        body = await self._json(
            f"https://openlibrary.org/works/{work_id}/editions.json", limit=min(limit, 20)
        )
        entries = body.get("entries", [])
        rows: list[SearchCandidate] = []
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            edition_id = str(entry.get("key", "")).removeprefix("/books/")
            if not edition_id or not entry.get("title"):
                continue
            cover_ids = entry.get("covers", [])
            cover_id = cover_ids[0] if isinstance(cover_ids, list) and cover_ids else None
            identifiers = _isbn(list(entry.get("isbn_13", [])) + list(entry.get("isbn_10", [])))
            cover_url = (
                f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg?default=false"
                if cover_id
                else f"https://covers.openlibrary.org/b/olid/{edition_id}-L.jpg?default=false"
            )
            rows.append(
                SearchCandidate(
                    source=self.name,
                    source_id=edition_id,
                    source_refs=(SourceRef(self.name, edition_id),),
                    title=str(entry["title"]),
                    subtitle=str(entry["subtitle"]) if entry.get("subtitle") else None,
                    authors=(),
                    year=_year(entry.get("publish_date")),
                    cover_url=cover_url,
                    identifiers=identifiers,
                    language=_language(entry.get("languages")),
                    metadata={},
                )
            )
        return sorted(
            rows,
            key=lambda row: (
                row.year is None,
                row.cover_url is None,
                not bool(row.identifiers),
                row.language not in {"es", "en"},
                row.source_id,
            ),
        )


def _google_cover(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url.replace("http://", "https://", 1))
    query = [
        (key, "3" if key == "zoom" else value)
        for key, value in parse_qsl(parts.query)
        if key != "edge"
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class GoogleBooksProvider:
    name = "googlebooks"
    item_type = "book"

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self.client = client
        self.api_key = api_key
        self.enabled = bool(api_key)

    def _candidate(self, row: Mapping[str, Any]) -> SearchCandidate | None:
        info = row.get("volumeInfo")
        if not row.get("id") or not isinstance(info, dict) or not info.get("title"):
            return None
        identifiers = _isbn(
            [
                value.get("identifier")
                for value in info.get("industryIdentifiers", [])
                if isinstance(value, dict)
            ]
        )
        source_id = str(row["id"])
        authors = tuple(str(value) for value in info.get("authors", []))
        metadata = {
            "authors": list(authors),
            "publisher": info.get("publisher"),
            "page_count": info.get("pageCount"),
            "description": info.get("description"),
            "subjects": info.get("categories"),
        }
        metadata = {
            key: value for key, value in metadata.items() if value not in (None, "", [], {})
        }
        images = info.get("imageLinks", {})
        return SearchCandidate(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title=str(info["title"]),
            subtitle=str(info["subtitle"]) if info.get("subtitle") else None,
            authors=authors,
            year=_year(info.get("publishedDate")),
            cover_url=_google_cover(images.get("thumbnail") if isinstance(images, dict) else None),
            identifiers=identifiers,
            language=_language(info.get("language")),
            metadata=metadata,
            original_year=None,
        )

    async def _get(self, url: str, **params: str | int) -> Mapping[str, Any]:
        if not self.enabled:
            raise RuntimeError("Google Books is disabled")
        return await _bounded_json(self.client, url, params={**params, "key": self.api_key})

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        body = await self._get(
            "https://www.googleapis.com/books/v1/volumes", q=query, maxResults=min(limit, 20)
        )
        items = body.get("items", [])
        if not isinstance(items, list):
            raise ProviderPayloadError("Google Books items must be a list")
        return [
            candidate
            for row in items
            if isinstance(row, dict)
            if (candidate := self._candidate(row))
        ]

    async def fetch(self, source_id: str) -> ItemPayload:
        row = await self._get(f"https://www.googleapis.com/books/v1/volumes/{source_id}")
        candidate = self._candidate(row)
        if candidate is None:
            raise ProviderPayloadError("Google Books volume is incomplete")
        return ItemPayload(**candidate.__dict__)

    async def fetch_by_isbn(self, isbn: str) -> ItemPayload:
        """Fetch edition data by ISBN. Used by background enrichment.

        This is an `isbn:` *search*, not a lookup by identifier, so the volume that
        comes back is whatever ranked first and is not guaranteed to carry the ISBN
        that was asked for. `edition_match` records whether it does.
        """
        body = await self._get(
            "https://www.googleapis.com/books/v1/volumes", q=f"isbn:{isbn}", maxResults=1
        )
        items = body.get("items", [])
        if not isinstance(items, list) or not items:
            raise ProviderPayloadError("Google Books found no volume for ISBN")
        row = items[0]
        candidate = self._candidate(row)
        if candidate is None:
            raise ProviderPayloadError("Google Books volume is incomplete")
        info = row.get("volumeInfo", {})
        carried = [
            value.get("identifier")
            for value in info.get("industryIdentifiers", [])
            if isinstance(value, dict)
        ]
        return ItemPayload(**candidate.__dict__, edition_match=classify_edition(carried, isbn))
