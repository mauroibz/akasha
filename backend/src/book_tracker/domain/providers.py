from collections import Counter
from collections.abc import Callable, Mapping, Sequence
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
    original_year: int | None = None
    cover_fallback_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class ItemPayload(SearchCandidate):
    """A fetched record, plus whether it is provably the edition that was asked for.

    `edition_match` is set by `fetch_by_isbn`, which is the only caller that has both
    a requested ISBN and the raw provider row carrying every identifier the record
    holds. It is `None` for payloads reached any other way — a search selection or an
    explicit refresh — where there is no requested edition to verify against.
    """

    edition_match: str | None = None


class Provider(Protocol):
    name: str
    item_type: str

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]: ...

    async def fetch(self, source_id: str) -> ItemPayload: ...


def isbn_identity(candidate: SearchCandidate) -> str | None:
    """Books' cross-provider identity: an ISBN is globally unique, so it can group."""
    value = candidate.identifiers.get("isbn13") or candidate.identifiers.get("isbn")
    if not value:
        return None
    try:
        return normalize_identifier("isbn", value).normalized_value
    except InvalidIdentifier:
        return None


def no_shared_identity(_candidate: SearchCandidate) -> None:
    """Albums have no cross-provider identity, and that is a complete answer.

    DEC-052 observed barcode `888837168625` on three distinct releases. A barcode is
    therefore not an edition key, and there is no other global identifier a second
    provider would carry — so the correct behaviour is to merge nothing rather than
    to merge on a weaker key.
    """
    return None


@dataclass(frozen=True)
class IdentityStrategy:
    """How a domain decides two candidates are the same record, and who wins a merge.

    `identity_key` returning `None` means *never merge this candidate*. Both halves are
    per-domain: the grouping key, and the source order that picks the primary row of a
    group and breaks ranking ties.
    """

    identity_key: Callable[[SearchCandidate], str | None]
    source_preference: tuple[str, ...]


SOURCE_PREFERENCE = ("openlibrary", "googlebooks")
BOOK_IDENTITY = IdentityStrategy(isbn_identity, SOURCE_PREFERENCE)
ALBUM_IDENTITY = IdentityStrategy(no_shared_identity, ("musicbrainz",))


def _source_rank(source: str, preference: Sequence[str]) -> tuple[int, str]:
    """Product spec 4.3 prefers Open Library's record; alphabetical order does not."""
    if source in preference:
        return (preference.index(source), "")
    return (len(preference), source)


def _merge_group(group: Sequence[SearchCandidate], preference: Sequence[str]) -> SearchCandidate:
    primary = min(group, key=lambda row: _source_rank(row.source, preference))
    cover = primary.cover_url or next((row.cover_url for row in group if row.cover_url), None)
    refs = tuple(sorted({ref for row in group for ref in row.source_refs}))
    identifiers = dict(primary.identifiers)
    metadata = dict(primary.metadata)

    def missing(value: object) -> bool:
        return value is None or value == "" or value == [] or value == {}

    for row in group:
        identifiers.update(
            {
                key: value
                for key, value in row.identifiers.items()
                if key not in identifiers or missing(identifiers[key])
            }
        )
        metadata.update(
            {
                key: value
                for key, value in row.metadata.items()
                if not missing(value) and (key not in metadata or missing(metadata[key]))
            }
        )
    return replace(
        primary,
        source_refs=refs,
        cover_url=cover,
        identifiers=identifiers,
        metadata=metadata,
        original_year=primary.original_year
        or next((row.original_year for row in group if row.original_year), None),
    )


def merge_and_rank(
    query: str,
    candidates: Sequence[SearchCandidate],
    *,
    identity: IdentityStrategy,
) -> list[SearchCandidate]:
    """Merge duplicate records and rank without discarding provider relevance.

    What counts as a duplicate is the domain's to say (`identity`), not this function's:
    books group on ISBN, albums group on nothing at all.

    Providers already rank their own results; re-sorting them by title threw that away
    and buried the obvious answer under alphabetically earlier noise. Each candidate
    keeps the position its provider gave it, the providers interleave by position so
    neither one monopolises the top of the list, and the deliberately dumb signals from
    product spec 4.3 — exact title match, language, cover presence — only break ties
    between results the providers ranked equally.
    """
    seen_per_source: Counter[str] = Counter()
    positions: list[int] = []
    for candidate in candidates:
        positions.append(seen_per_source[candidate.source])
        seen_per_source[candidate.source] += 1

    groups: list[list[tuple[int, SearchCandidate]]] = []
    keyed: dict[str, list[tuple[int, SearchCandidate]]] = {}
    for position, candidate in zip(positions, candidates, strict=True):
        key = identity.identity_key(candidate)
        if key is not None:
            keyed.setdefault(key, []).append((position, candidate))
        else:
            groups.append([(position, candidate)])
    groups.extend(keyed.values())

    # A result merged from both providers takes the best rank either one gave it.
    ranked = [
        (
            min(position for position, _row in group),
            _merge_group([row for _position, row in group], identity.source_preference),
        )
        for group in groups
    ]
    normalized_query = normalize_text(query)
    ranked.sort(
        key=lambda entry: (
            entry[0],
            normalize_text(entry[1].title) != normalized_query,
            entry[1].language not in {"es", "en"},
            entry[1].cover_url is None,
            _source_rank(entry[1].source, identity.source_preference),
            entry[1].source_id,
        )
    )
    return [row for _position, row in ranked]
