from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.normalization import normalize_text


@dataclass(frozen=True, order=True)
class SourceRef:
    source: str
    source_id: str


@dataclass(frozen=True)
class SearchCandidate:
    source: str
    source_id: str
    source_refs: tuple[SourceRef, ...]
    title: str
    subtitle: str | None
    authors: tuple[str, ...]
    year: int | None
    cover_url: str | None
    identifiers: Mapping[str, str]
    language: str | None
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class ItemPayload(SearchCandidate):
    pass


class Provider(Protocol):
    name: str
    item_type: str

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]: ...

    async def fetch(self, source_id: str) -> ItemPayload: ...


def _isbn(candidate: SearchCandidate) -> str | None:
    value = candidate.identifiers.get("isbn13") or candidate.identifiers.get("isbn")
    if not value:
        return None
    try:
        return normalize_identifier("isbn", value).normalized_value
    except InvalidIdentifier:
        return None


def _merge_group(group: Sequence[SearchCandidate]) -> SearchCandidate:
    primary = next((row for row in group if row.source == "openlibrary"), group[0])
    cover = primary.cover_url or next((row.cover_url for row in group if row.cover_url), None)
    refs = tuple(sorted({ref for row in group for ref in row.source_refs}))
    identifiers = dict(primary.identifiers)
    metadata = dict(primary.metadata)
    for row in group:
        identifiers.update(
            {key: value for key, value in row.identifiers.items() if key not in identifiers}
        )
        metadata.update({key: value for key, value in row.metadata.items() if key not in metadata})
    return replace(
        primary,
        source_refs=refs,
        cover_url=cover,
        identifiers=identifiers,
        metadata=metadata,
    )


def merge_and_rank(query: str, candidates: Sequence[SearchCandidate]) -> list[SearchCandidate]:
    groups: list[list[SearchCandidate]] = []
    keyed: dict[str, list[SearchCandidate]] = {}
    for candidate in candidates:
        isbn = _isbn(candidate)
        if isbn:
            keyed.setdefault(isbn, []).append(candidate)
        else:
            groups.append([candidate])
    groups.extend(keyed.values())
    merged = [_merge_group(group) for group in groups]
    normalized_query = normalize_text(query)
    return sorted(
        merged,
        key=lambda row: (
            normalize_text(row.title) != normalized_query,
            row.language not in {"es", "en"},
            row.cover_url is None,
            normalize_text(row.title),
            row.source,
            row.source_id,
        ),
    )
