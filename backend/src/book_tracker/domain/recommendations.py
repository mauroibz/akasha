"""Recommendations: select, then enrich (Sprint 133, DEC-183 points 4-7).

```text
SEED      one entry (More like this) or the person's taste profile
  -> SELECT a source picks a short list in one request, for one domain
  -> STORE  the candidates, less what is already in the library or was turned down
  -> ENRICH the domain's own resolve finds the top few in its providers, under budget
  -> ANSWER Want (a planned entry), Not for me, Seen it
```

A source never crawls a provider to choose what to suggest: it chooses in one request
(TMDB's recommendations for a film, one model call, a similarity query over stored
vectors), and providers are spent only on candidates already chosen, through the
domain's `resolve`.

This module holds the shapes. A domain declares `RecommendationSpec` on its `Domain`;
which object backs a source name is configuration, held in a `SourceRegistry` the
application builds at start (`app/recommendations.py`). The shared layers never ask
which domain they hold (technical spec 6.6).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from book_tracker.domain.normalization import normalize_text
from book_tracker.domain.providers import Provider, SearchCandidate

_EMPTY: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class Seed:
    """What a round is about: one entry, or (with no entry) the person's taste.

    `external_ids` are the seed item's identifiers and provider sources together,
    kind to value (`{"imdb": "tt0047478", "wikidata": "Q189540"}`), so a source keyed
    on any of them can find its own id without a provider request.
    """

    item_type: str
    entry_id: int | None = None
    item_id: int | None = None
    title: str | None = None
    year: int | None = None
    creators: tuple[str, ...] = ()
    external_ids: Mapping[str, str] = _EMPTY
    metadata: Mapping[str, Any] = _EMPTY
    #: What the domain tells this source about itself (`RecommendationSpec.source_options`
    #: for the round's source): TMDB reads `media`, so the source never asks which
    #: library it holds.
    options: Mapping[str, str] = _EMPTY

    @property
    def is_profile(self) -> bool:
        return self.entry_id is None


@dataclass(frozen=True)
class TasteEntry:
    """One line of a taste profile: what a source may be told about a work."""

    title: str
    year: int | None = None
    creator: str | None = None
    score: int | None = None


@dataclass(frozen=True)
class TasteProfile:
    """The person's taste in one library, from stored data only.

    Titles, creators, years and scores, nothing else: this is what a source that
    sends it anywhere (Sprint 135's model) is allowed to send.
    """

    item_type: str
    #: Highest scores first.
    top_scored: tuple[TasteEntry, ...] = ()
    #: Most recently finished first.
    recent_finishes: tuple[TasteEntry, ...] = ()
    #: Suggestions answered *not for me*, newest first.
    dismissed: tuple[TasteEntry, ...] = ()
    #: The pile, so a source does not suggest what is already waiting.
    waiting: tuple[TasteEntry, ...] = ()


@dataclass(frozen=True)
class Candidate:
    """One thing a source suggests, before any provider has been asked about it.

    `reason` is one sentence a person reads ("Often watched together"); the API
    publishes it as `{signal: <source>, text}`, the ranked pile's reason shape
    (DEC-186). `display` is whatever else the source knows that a sheet may show
    (a poster URL, an overview); it is stored, never interpreted.
    """

    title: str
    year: int | None = None
    creator: str | None = None
    external_ids: Mapping[str, str] = _EMPTY
    reason: str = ""
    source_score: float | None = None
    display: Mapping[str, Any] = _EMPTY


@dataclass(frozen=True)
class Selection:
    """A source's answer when it learned something about the seed on the way.

    `seed_ids` are identifiers of the seed's own item the source had to look up
    (TMDB's id, found through `/find` from an IMDb id); the round keeps them on the
    item, so the next round on it asks once. A source with nothing to add answers
    a plain sequence of candidates instead.
    """

    candidates: Sequence[Candidate]
    seed_ids: Mapping[str, str] = field(default_factory=dict)


class SourceError(Exception):
    """A source could not answer: unreachable, refused, or an unreadable reply.

    The round records the message and fails; nothing retries it behind the person's
    back, because a round is something a person asked for and is waiting on.
    """

    def __init__(self, message: str, *, code: str = "source_failed") -> None:
        super().__init__(message)
        self.code = code


class ProviderBudgetSpent(Exception):
    """A provider's daily budget is spent; resolving stops and the rest waits."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"{provider} is out of requests for today")
        self.provider = provider


@dataclass(frozen=True)
class NotConfigured:
    """A source this build knows, missing the configuration it needs.

    Reported, never raised: a round asked of it is stored `not_configured` with
    `hint` as its reason, so a screen can say how to turn it on.
    """

    name: str
    hint: str
    #: How long this source's suggestions may be kept, known without its
    #: configuration: rows stored while it was configured are still pruned.
    retention: timedelta | None = None
    #: What a screen calls it ("TMDB").
    label: str = ""
    #: The line its terms ask for wherever its suggestions are shown.
    attribution: str | None = None
    #: Whether its picks are shown only once resolved (a model's, Sprint 135).
    resolved_only: bool = False
    #: What Settings says about it while it is off (which provider, which model).
    about: Mapping[str, str] | None = None


@runtime_checkable
class RecommendationSource(Protocol):
    """Chooses candidates for one seed in one request (DEC-183 point 4).

    `select` is called once per round. It must not call a metadata provider per
    candidate: resolving is the domain's, under the provider budgets, afterwards.
    Raise `SourceError` for a failure the round should record. It may answer a
    `Selection` instead of a plain sequence when it learned the seed's own ids.

    A source may also carry `label` (what a screen calls it), `retention` (a
    `timedelta`: how long its rows may be kept, after which the maintenance pass
    deletes them), `attribution` (the line its terms ask for beside its rows),
    `resolved_only` (true when a candidate may be an invention, so the round resolves
    every candidate and a screen shows only those found; Sprint 135) and `about` (a
    few facts Settings shows); each is read with a default when absent.
    """

    name: str

    async def select(
        self, seed: Seed, profile: TasteProfile, limit: int
    ) -> Sequence[Candidate] | Selection: ...


#: How a domain finds a candidate in its own providers. It receives only the
#: providers serving the domain, each already held to its daily budget (a spent one
#: raises `ProviderBudgetSpent`), and answers with the record found or `None` when
#: nothing matches, which stores the candidate `unresolved`.
Resolve = Callable[[Candidate, Mapping[str, Provider]], Awaitable[SearchCandidate | None]]


@dataclass(frozen=True)
class RecommendationSpec:
    """Which sources may suggest this domain's things, and how to resolve them.

    `sources` are names in the source registry, in the order a screen offers them;
    the first configured one answers a round that names none. `enrich_top` is how
    many of a round's candidates are resolved straight away; the rest wait until
    someone opens one. `source_options` is what the domain tells each source about
    itself (TMDB's `media`), handed over on the seed. `want_status` is where *Want*
    puts a suggestion; `None` means the domain's first planned status. Albums have
    no planned status, so they will name their `wishlist` here (Sprint 135).
    """

    sources: tuple[str, ...]
    resolve: Resolve
    enrich_top: int = 3
    source_options: Mapping[str, Mapping[str, str]] = _EMPTY
    want_status: str | None = None


class SourceRegistry:
    """Every recommendation source this build knows, keyed by name.

    Filled at start from configuration: a source with its configuration is the
    source itself, one without is a `NotConfigured` naming what is missing.
    """

    def __init__(self, sources: Iterable[RecommendationSource | NotConfigured] = ()) -> None:
        self._sources: dict[str, RecommendationSource | NotConfigured] = {}
        for source in sources:
            self.register(source)

    def register(self, source: RecommendationSource | NotConfigured) -> None:
        self._sources[source.name] = source

    def get(self, name: str) -> RecommendationSource | NotConfigured | None:
        return self._sources.get(name)

    def configured(self, name: str) -> bool:
        return isinstance(self._sources.get(name), RecommendationSource)

    def names(self) -> tuple[str, ...]:
        return tuple(self._sources)

    def describe(self, name: str) -> dict[str, Any]:
        """What a screen needs to offer a source: its label, and whether it can answer."""
        found = self._sources.get(name)
        label = getattr(found, "label", "") or name
        configured = isinstance(found, RecommendationSource)
        hint = (
            found.hint
            if isinstance(found, NotConfigured)
            else None
            if configured
            else f"No source named {name!r} is built in"
        )
        about = getattr(found, "about", None)
        return {
            "name": name,
            "label": label,
            "configured": configured,
            "hint": hint,
            "resolved_only": self.resolved_only(name),
            "about": dict(about) if about else None,
        }

    def resolved_only(self, name: str) -> bool:
        return bool(getattr(self._sources.get(name), "resolved_only", False))

    def attribution(self, name: str) -> str | None:
        return getattr(self._sources.get(name), "attribution", None)

    def retention(self, name: str) -> timedelta | None:
        return getattr(self._sources.get(name), "retention", None)


#: How far apart two years may be once the creator agrees: a release abroad, years
#: after the premiere, is the same film.
CREATOR_YEAR_SLACK = 3


def same_work(candidate: Candidate, record: SearchCandidate) -> bool:
    """Whether a provider's record is plausibly the work a source named.

    The title must match once normalized (case, accents, punctuation); a creator both
    sides give must be among the record's; a year both sides give may differ by one
    (festival versus release) from the record's year or its original year (a book's
    record is an edition: Ficciones 1983, first 1944), or by up to three when a
    creator both sides give agrees (Cinemeta dates Kurosawa's films by their US
    release: *Red Beard* 1968 for 1965). Anything looser resolves a model's invention
    to a real stranger, which is the failure DEC-183 point 7 forbids.
    """
    if normalize_text(candidate.title) != normalize_text(record.title):
        return False
    agreed = False
    if candidate.creator and record.creators:
        wanted = normalize_text(candidate.creator)
        if wanted not in {normalize_text(name) for name in record.creators}:
            return False
        agreed = True
    slack = CREATOR_YEAR_SLACK if agreed else 1
    years = [year for year in (record.year, record.original_year) if year is not None]
    return (
        candidate.year is None
        or not years
        or any(abs(candidate.year - year) <= slack for year in years)
    )


def resolve_by_identity_or_search(
    identity_kinds: Sequence[str] = (), *, with_creator: bool = False
) -> Resolve:
    """The common resolve: an identifier the candidate carries, else a title search.

    For each of `identity_kinds` the candidate carries, providers answering
    `fetch_by_identifier` are asked in order; a miss moves on. A provider that
    declares `identifier_kinds` is asked only for those, so no budgeted request is
    spent on a kind it refuses before it would send anything. Then each provider
    is searched for the title alone (a creator appended hides films from a title
    search), or with the creator after it where the domain says that narrows a
    search (`with_creator`: books and albums, whose one-word titles are many works),
    and the first record that is `same_work` wins, the creator and year checked
    there. A provider that failed, with no match elsewhere, propagates its error
    (the pick stays pending) rather than answering `None` (unresolved for good).
    A spent budget always propagates: it is not a miss.
    """
    kinds = tuple(identity_kinds)

    async def resolve(
        candidate: Candidate, providers: Mapping[str, Provider]
    ) -> SearchCandidate | None:
        for kind in kinds:
            value = candidate.external_ids.get(kind)
            if not value:
                continue
            for provider in providers.values():
                fetch = getattr(provider, "fetch_by_identifier", None)
                if fetch is None:
                    continue
                answers = getattr(provider, "identifier_kinds", None)
                if answers is not None and kind not in answers:
                    continue
                try:
                    record = await fetch(kind, value)
                except ProviderBudgetSpent:
                    raise
                except Exception:  # noqa: BLE001 - a miss by identifier falls back to search
                    continue
                if isinstance(record, SearchCandidate) and record.title:
                    return record
        query = (
            f"{candidate.title} {candidate.creator}"
            if with_creator and candidate.creator
            else candidate.title
        )
        last_error: Exception | None = None
        for provider in providers.values():
            try:
                rows = await provider.search(query, 5)
            except ProviderBudgetSpent:
                raise
            except Exception as error:  # noqa: BLE001 - the next provider may answer
                last_error = error
                continue
            for row in rows:
                if same_work(candidate, row):
                    return row
        # `None` stores the pick unresolved for good, so it means every provider
        # answered and none knew it. One that failed may have been the one that did:
        # the failure propagates and the pick stays pending, to be tried again
        # (Sprint 135: Cinemeta failing after Wikidata's Spanish labels).
        if last_error is not None:
            raise last_error
        return None

    return resolve
