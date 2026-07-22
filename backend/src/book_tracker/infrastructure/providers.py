import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef


class ProviderPayloadError(ValueError):
    pass


MAX_PROVIDER_BYTES = 2 * 1024 * 1024


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


def _year(value: object) -> int | None:
    try:
        text = str(value)
        return int(text[:4]) if len(text) >= 4 else None
    except (TypeError, ValueError):
        return None


def _isbn(values: list[object]) -> dict[str, str]:
    for value in values:
        try:
            normalized = normalize_identifier("isbn", str(value))
            return {"isbn13": normalized.normalized_value}
        except InvalidIdentifier:
            continue
    return {}


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
        return [
            candidate
            for row in docs
            if isinstance(row, dict)
            if (candidate := self._candidate(row))
        ]

    async def fetch(self, source_id: str) -> ItemPayload:
        row = await self._json(f"https://openlibrary.org/books/{source_id}.json")
        title = row.get("title")
        if not title:
            raise ProviderPayloadError("Open Library edition has no title")
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
        cover_ids = row.get("covers", [])
        cover = cover_ids[0] if isinstance(cover_ids, list) and cover_ids else None
        publisher = next(
            (str(value).strip() for value in row.get("publishers", []) if str(value).strip()), None
        )
        subjects = row.get("subjects") or work.get("subjects") or []
        metadata = {
            "authors": list(authors),
            "publisher": publisher,
            "language": _language(row.get("languages")),
            "page_count": row.get("number_of_pages"),
            "description": _description(row.get("description"))
            or _description(work.get("description")),
            "subjects": [str(value) for value in subjects if value],
            "series": next(iter(row.get("series", [])), None),
            "original_year": _year(
                work.get("first_publish_date") or work.get("created", {}).get("value")
            ),
        }
        metadata = {
            key: value for key, value in metadata.items() if value not in (None, "", [], {})
        }
        cover_url = None
        if cover:
            cover_url = f"https://covers.openlibrary.org/b/id/{cover}-L.jpg?default=false"
        elif source_id:
            cover_url = f"https://covers.openlibrary.org/b/olid/{source_id}-L.jpg?default=false"
        elif identifiers.get("isbn13"):
            cover_url = (
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
            cover_url=cover_url,
            identifiers=identifiers,
            language=_language(row.get("languages")),
            metadata=metadata,
            original_year=metadata.get("original_year"),
        )

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
            rows.append(
                SearchCandidate(
                    source=self.name,
                    source_id=edition_id,
                    source_refs=(SourceRef(self.name, edition_id),),
                    title=str(entry["title"]),
                    subtitle=str(entry["subtitle"]) if entry.get("subtitle") else None,
                    authors=(),
                    year=_year(entry.get("publish_date")),
                    cover_url=None,
                    identifiers=_isbn(
                        list(entry.get("isbn_13", [])) + list(entry.get("isbn_10", []))
                    ),
                    language=_language(entry.get("languages")),
                    metadata={},
                )
            )
        return sorted(
            rows,
            key=lambda row: (
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
