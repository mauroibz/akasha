from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef


class ProviderPayloadError(ValueError):
    pass


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
    code = str(values[0]).casefold()
    return {"spa": "es", "eng": "en"}.get(code, code[:2])


class OpenLibraryProvider:
    name = "openlibrary"
    item_type = "book"
    enabled = True

    def __init__(self, client: httpx.AsyncClient, contact: str) -> None:
        self.client = client
        self.headers = {"User-Agent": f"Akasha/0.1 ({contact})"}

    async def _json(self, url: str, **params: str | int) -> Mapping[str, Any]:
        response = await self.client.get(url, params=params, headers=self.headers)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ProviderPayloadError("Open Library returned a non-object payload")
        return body

    def _candidate(self, row: Mapping[str, Any]) -> SearchCandidate | None:
        editions = row.get("edition_key")
        source_id = str(editions[0]) if isinstance(editions, list) and editions else ""
        if not source_id or not row.get("title"):
            return None
        cover_id = row.get("cover_i")
        metadata: dict[str, Any] = {}
        if row.get("first_publish_year") is not None:
            metadata["original_year"] = row["first_publish_year"]
        return SearchCandidate(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title=str(row["title"]),
            subtitle=str(row["subtitle"]) if row.get("subtitle") else None,
            authors=tuple(str(value) for value in row.get("author_name", [])),
            year=None,
            cover_url=(
                f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None
            ),
            identifiers=_isbn(list(row.get("isbn", []))),
            language=_language(row.get("language")),
            metadata=metadata,
        )

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        body = await self._json(
            "https://openlibrary.org/search.json",
            q=query,
            limit=min(limit, 20),
            fields=(
                "key,title,subtitle,author_name,first_publish_year,isbn,cover_i,"
                "language,edition_key"
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
        authors = tuple(
            str(value.get("name") or value.get("key", "")).removeprefix("/authors/")
            for value in row.get("authors", [])
            if isinstance(value, dict)
        )
        identifiers = _isbn(list(row.get("isbn_13", [])) + list(row.get("isbn_10", [])))
        cover_ids = row.get("covers", [])
        cover = cover_ids[0] if isinstance(cover_ids, list) and cover_ids else None
        metadata = {
            "authors": list(authors),
            "publishers": row.get("publishers", []),
            "page_count": row.get("number_of_pages"),
        }
        return ItemPayload(
            source=self.name,
            source_id=source_id,
            source_refs=(SourceRef(self.name, source_id),),
            title=str(title),
            subtitle=str(row["subtitle"]) if row.get("subtitle") else None,
            authors=authors,
            year=_year(row.get("publish_date")),
            cover_url=(f"https://covers.openlibrary.org/b/id/{cover}-L.jpg" if cover else None),
            identifiers=identifiers,
            language=_language(row.get("languages")),
            metadata=metadata,
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
        )

    async def _get(self, url: str, **params: str | int) -> Mapping[str, Any]:
        if not self.enabled:
            raise RuntimeError("Google Books is disabled")
        response = await self.client.get(url, params={**params, "key": self.api_key})
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ProviderPayloadError("Google Books returned a non-object payload")
        return body

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
