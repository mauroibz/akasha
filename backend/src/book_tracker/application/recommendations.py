"""Suggestion rounds: seed, select, store, enrich, answer (Sprint 133, DEC-183).

A round is one person's request to one source about one entry (More like this) or
about their taste. The `recommend` job asks the source once, stores what it chose
less what the person already has or turned down, then resolves the first
`RecommendationSpec.enrich_top` through the domain's own `resolve`, every provider
request held to the daily budgets. `enrich_suggestion` resolves one more on demand.

Shared layer: which domain a round is about is read from the registry and never
named here, and which object answers a source name is the `SourceRegistry`'s.
Reading suggestions never calls a provider; only the two jobs do.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from book_tracker.application.library import LibraryError
from book_tracker.domain.identity import Identifier, InvalidIdentifier, normalize_identifier
from book_tracker.domain.normalization import normalize_text
from book_tracker.domain.providers import Provider, SearchCandidate
from book_tracker.domain.recommendations import (
    Candidate,
    NotConfigured,
    ProviderBudgetSpent,
    RecommendationSource,
    Seed,
    SourceError,
    SourceRegistry,
    TasteEntry,
    TasteProfile,
)
from book_tracker.domain.registry import DOMAINS
from book_tracker.domain.spec import (
    Domain,
    InvalidMetadata,
    declares_field,
    validate_metadata_patch,
)
from book_tracker.infrastructure.covers import CoverError, install_cover, prepare_cover
from book_tracker.infrastructure.jobs import JobRepository, RateLimiter
from book_tracker.infrastructure.offload import off_loop
from book_tracker.infrastructure.quota import ProviderQuota
from book_tracker.infrastructure.repositories import (
    DomainRepository,
    IdentityConflict,
    SourceIdentity,
)

logger = logging.getLogger(__name__)

RECOMMEND_JOB = "recommend"
ENRICH_SUGGESTION_JOB = "enrich_suggestion"
#: How many candidates a round asks its source for.
SELECT_LIMIT = 12
#: A round this recent is shown again rather than asked again, unless refreshed.
REUSE_WITHIN = timedelta(days=1)
ANSWERS = ("want", "not_for_me", "seen")
#: A round in one of these states is finished; the others are on their way.
FINISHED = ("done", "failed", "over_budget", "not_configured")
#: The ones not worth showing again instead of asking: a failure or a refusal may
#: be over by now.
_NOT_REUSED = ("failed", "over_budget", "not_configured")
#: How many entries each part of a taste profile holds.
PROFILE_SIZE = 20


def budget_key(source: str) -> str:
    """The `provider_usage` row a source's rounds are counted under."""
    return f"recommend:{source}"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _norm(value: str | None) -> str:
    return normalize_text(value) if value else ""


# --- What is already known: the library, and what was turned down ------------------


@dataclass
class _Works:
    """Works matched by identity, or by title with a year or creator that agrees.

    Each work carries a value: `True` for what a round leaves out, an item id for
    what an earlier round already resolved.
    """

    identities: dict[tuple[str, str], Any]
    titles: dict[str, list[tuple[int | None, str, Any]]]

    def find(
        self, title: str, year: int | None, creator: str | None, ids: Mapping[str, str]
    ) -> Any:
        for kind, value in ids.items():
            found = self.identities.get((kind.casefold(), str(value).strip()))
            if found is not None:
                return found
            try:
                identifier = normalize_identifier(kind, str(value))
            except InvalidIdentifier:
                continue
            found = self.identities.get((identifier.kind, identifier.normalized_value))
            if found is not None:
                return found
        wanted = _norm(creator)
        for known_year, known_creator, found in self.titles.get(_norm(title), ()):
            if wanted and known_creator:
                if wanted == known_creator:
                    return found
                continue
            if year is not None and known_year is not None:
                if abs(year - known_year) <= 1:
                    return found
                continue
            # Nothing contradicts a title match inside one library.
            return found
        return None

    def add(
        self,
        title: str,
        year: int | None,
        creator: str | None,
        ids: Mapping[str, str],
        value: Any = True,
    ) -> None:
        for kind, identity in ids.items():
            self.identities.setdefault((kind.casefold(), str(identity).strip()), value)
        self.titles.setdefault(_norm(title), []).append((year, _norm(creator), value))


def _known(connection: Connection, user_id: int, item_type: str) -> _Works:
    """What a new round leaves out: the library in this domain, and *not for me*."""
    known = _Works({}, {})
    params = {"user": user_id, "type": item_type}
    mine = "SELECT e.item_id FROM entries e JOIN items i ON i.id = e.item_id" + (
        " WHERE e.user_id = :user AND i.type = :type"
    )
    for kind, value in connection.execute(
        text(f"SELECT kind, normalized_value FROM item_identifiers WHERE item_id IN ({mine})"),
        params,
    ):
        known.identities[(str(kind), str(value))] = True
    for source, source_id in connection.execute(
        text(f"SELECT source, source_id FROM item_sources WHERE item_id IN ({mine})"), params
    ):
        known.identities[(str(source).casefold(), str(source_id))] = True
    for title, year, creator in connection.execute(
        text(
            "SELECT i.title, i.year, i.creator_primary FROM entries e"
            " JOIN items i ON i.id = e.item_id WHERE e.user_id = :user AND i.type = :type"
        ),
        params,
    ):
        known.titles.setdefault(_norm(title), []).append((year, _norm(creator), True))
    for title, year, creator, ids in connection.execute(
        text(
            "SELECT title, year, creator, external_ids_json FROM suggestions"
            " WHERE user_id = :user AND item_type = :type AND answer = 'not_for_me'"
        ),
        params,
    ):
        known.add(title, year, creator, _json_object(ids))
    return known


def _resolved(connection: Connection, user_id: int, item_type: str) -> _Works:
    """What earlier rounds already found, so a work suggested again costs no request."""
    resolved = _Works({}, {})
    for title, year, creator, ids, item_id in connection.execute(
        text(
            "SELECT title, year, creator, external_ids_json, item_id FROM suggestions"
            " WHERE user_id = :user AND item_type = :type AND enrichment = 'enriched'"
            " AND item_id IS NOT NULL ORDER BY id DESC"
        ),
        {"user": user_id, "type": item_type},
    ):
        resolved.add(title, year, creator, _json_object(ids), int(item_id))
    return resolved


def _json_object(value: object) -> dict[str, Any]:
    try:
        loaded = json.loads(str(value)) if value else {}
    except ValueError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


# --- Storage --------------------------------------------------------------------------


_SUGGESTION_COLUMNS = (
    "s.id, s.round_id, s.item_type, r.source, s.title, s.year, s.creator,"
    " s.external_ids_json, s.reason, s.source_score, s.display_json, s.enrichment,"
    " s.item_id, s.answer, s.answered_at, s.created_at,"
    " (SELECT e.id FROM entries e WHERE e.user_id = s.user_id AND e.item_id = s.item_id)"
)


def _suggestion(row: Sequence[Any]) -> dict[str, Any]:
    (
        suggestion_id,
        round_id,
        item_type,
        source,
        title,
        year,
        creator,
        external_ids,
        reason,
        source_score,
        display,
        enrichment,
        item_id,
        answer,
        answered_at,
        created_at,
        entry_id,
    ) = row
    # An item pruned from the shared cache took its link with it (the foreign key
    # sets it NULL); the suggestion is found again on the next enrich.
    if enrichment == "enriched" and item_id is None:
        enrichment = "pending"
    return {
        "id": suggestion_id,
        "round_id": round_id,
        "item_type": item_type,
        "source": source,
        "title": title,
        "year": year,
        "creator": creator,
        "external_ids": _json_object(external_ids),
        "reason": {"signal": source, "text": reason} if reason else None,
        "source_score": source_score,
        "display": _json_object(display),
        "enrichment": enrichment,
        "item_id": item_id,
        "entry_id": entry_id,
        "answer": answer,
        "answered_at": answered_at,
        "created_at": created_at,
    }


class SuggestionStore:
    """One person's rounds and suggestions. Every read is scoped to them."""

    def __init__(self, engine: Engine, user_id: int) -> None:
        self.engine = engine
        self.user_id = user_id

    def create_round(
        self,
        item_type: str,
        seed_entry_id: int | None,
        source: str,
        *,
        status: str = "queued",
        error: str | None = None,
    ) -> int:
        now = _now()
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    "INSERT INTO suggestion_rounds (user_id, item_type, seed_entry_id, source,"
                    " status, error, created_at, finished_at)"
                    " VALUES (:user, :type, :seed, :source, :status, :error, :now, :finished)"
                ),
                {
                    "user": self.user_id,
                    "type": item_type,
                    "seed": seed_entry_id,
                    "source": source,
                    "status": status,
                    "error": error,
                    "now": now,
                    "finished": now if status in FINISHED else None,
                },
            )
            return int(result.lastrowid or 0)

    def set_round(self, round_id: int, status: str, *, error: str | None = None) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE suggestion_rounds SET status = :status, error = :error,"
                    " finished_at = :finished WHERE id = :id AND user_id = :user"
                ),
                {
                    "status": status,
                    "error": error,
                    "finished": _now() if status in FINISHED else None,
                    "id": round_id,
                    "user": self.user_id,
                },
            )

    def reusable_round(self, seed_entry_id: int, source: str, now: datetime) -> int | None:
        since = (now - REUSE_WITHIN).isoformat().replace("+00:00", "Z")
        with self.engine.connect() as connection:
            found = connection.execute(
                text(
                    "SELECT id FROM suggestion_rounds WHERE user_id = :user"
                    " AND seed_entry_id = :seed AND source = :source AND created_at >= :since"
                    " AND status NOT IN ('failed', 'over_budget', 'not_configured')"
                    " ORDER BY created_at DESC, id DESC LIMIT 1"
                ),
                {"user": self.user_id, "seed": seed_entry_id, "source": source, "since": since},
            ).scalar()
        return int(found) if found is not None else None

    def round(self, round_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT id, item_type, seed_entry_id, source, status, error, created_at,"
                    " finished_at FROM suggestion_rounds WHERE id = :id AND user_id = :user"
                ),
                {"id": round_id, "user": self.user_id},
            ).first()
            if row is None:
                return None
            suggestions = connection.execute(
                text(
                    f"SELECT {_SUGGESTION_COLUMNS} FROM suggestions s"
                    " JOIN suggestion_rounds r ON r.id = s.round_id"
                    " WHERE s.round_id = :id AND s.user_id = :user ORDER BY s.id"
                ),
                {"id": round_id, "user": self.user_id},
            ).all()
        keys = ("id", "item_type", "seed_entry_id", "source", "status", "error")
        return {
            **dict(zip(keys, row[:6], strict=True)),
            "created_at": row[6],
            "finished_at": row[7],
            "suggestions": [_suggestion(suggestion) for suggestion in suggestions],
        }

    def store(
        self, round_id: int, item_type: str, candidates: Iterable[Candidate]
    ) -> tuple[list[int], int]:
        """Keep what is new to this person; return the ids stored and how many dropped.

        Dropped: what their library already holds in this domain (by identity, or by
        title with a year or creator that agrees), what they answered *not for me*,
        and a second mention of the same work in this round. A work an earlier round
        already resolved is stored resolved, to the same item, without a request.
        """
        now = _now()
        stored: list[int] = []
        dropped = 0
        with self.engine.begin() as connection:
            known = _known(connection, self.user_id, item_type)
            resolved = _resolved(connection, self.user_id, item_type)
            for candidate in candidates:
                title = candidate.title.strip()
                ids = {str(k): str(v) for k, v in candidate.external_ids.items() if v}
                if not title or known.find(title, candidate.year, candidate.creator, ids):
                    dropped += 1
                    continue
                known.add(title, candidate.year, candidate.creator, ids)
                item_id = resolved.find(title, candidate.year, candidate.creator, ids)
                result = connection.execute(
                    text(
                        "INSERT INTO suggestions (round_id, user_id, item_type, title, year,"
                        " creator, external_ids_json, reason, source_score, display_json,"
                        " enrichment, item_id, created_at) VALUES (:round, :user, :type, :title,"
                        " :year, :creator, :ids, :reason, :score, :display, :enrichment, :item,"
                        " :now)"
                    ),
                    {
                        "round": round_id,
                        "user": self.user_id,
                        "type": item_type,
                        "title": title,
                        "year": candidate.year,
                        "creator": candidate.creator,
                        "ids": json.dumps(ids, ensure_ascii=False),
                        "reason": candidate.reason,
                        "score": candidate.source_score,
                        "display": json.dumps(dict(candidate.display), ensure_ascii=False),
                        "enrichment": "pending" if item_id is None else "enriched",
                        "item": item_id,
                        "now": now,
                    },
                )
                stored.append(int(result.lastrowid or 0))
        return stored, dropped

    def suggestions(
        self, *, seed_entry_id: int | None, item_type: str | None, limit: int
    ) -> list[dict[str, Any]]:
        """Unanswered suggestions worth showing, newest round first.

        Unresolved candidates are left out (the domain could not find them, and a
        model's invention must never be shown), and so is anything since added to
        the library.
        """
        clauses = [
            "s.user_id = :user",
            "s.answer IS NULL",
            "s.enrichment <> 'unresolved'",
            "NOT EXISTS (SELECT 1 FROM entries e WHERE e.user_id = s.user_id"
            " AND e.item_id = s.item_id)",
        ]
        params: dict[str, Any] = {"user": self.user_id}
        if seed_entry_id is not None:
            clauses.append("r.seed_entry_id = :seed")
            params["seed"] = seed_entry_id
        if item_type is not None:
            clauses.append("s.item_type = :type")
            params["type"] = item_type
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"SELECT {_SUGGESTION_COLUMNS} FROM suggestions s"
                    " JOIN suggestion_rounds r ON r.id = s.round_id"
                    f" WHERE {' AND '.join(clauses)}"
                    " ORDER BY s.created_at DESC, s.round_id DESC, s.id LIMIT :scan"
                ),
                {**params, "scan": limit * 4},
            ).all()
        # A work two rounds both suggested is shown once, from the newer round.
        shown: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for row in rows:
            suggestion = _suggestion(row)
            key = (
                ("item", suggestion["item_id"])
                if suggestion["item_id"] is not None
                else ("title", _norm(suggestion["title"]), suggestion["year"])
            )
            if key in seen:
                continue
            seen.add(key)
            shown.append(suggestion)
            if len(shown) == limit:
                break
        return shown

    def suggestion(self, suggestion_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    f"SELECT {_SUGGESTION_COLUMNS} FROM suggestions s"
                    " JOIN suggestion_rounds r ON r.id = s.round_id"
                    " WHERE s.id = :id AND s.user_id = :user"
                ),
                {"id": suggestion_id, "user": self.user_id},
            ).first()
        return _suggestion(row) if row is not None else None

    def set_enrichment(self, suggestion_id: int, state: str, item_id: int | None = None) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE suggestions SET enrichment = :state, item_id = :item"
                    " WHERE id = :id AND user_id = :user"
                ),
                {"state": state, "item": item_id, "id": suggestion_id, "user": self.user_id},
            )

    def set_answer(self, suggestion_id: int, answer: str | None) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE suggestions SET answer = :answer, answered_at = :at"
                    " WHERE id = :id AND user_id = :user"
                ),
                {
                    "answer": answer,
                    "at": _now() if answer is not None else None,
                    "id": suggestion_id,
                    "user": self.user_id,
                },
            )


def round_owner(engine: Engine, round_id: int) -> tuple[int, str] | None:
    """Whose round this is and its status, for a job that knows only the id."""
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT user_id, status FROM suggestion_rounds WHERE id = :id"),
            {"id": round_id},
        ).first()
    return (int(row[0]), str(row[1])) if row is not None else None


def suggestion_owner(engine: Engine, suggestion_id: int) -> int | None:
    with engine.connect() as connection:
        found = connection.execute(
            text("SELECT user_id FROM suggestions WHERE id = :id"), {"id": suggestion_id}
        ).scalar()
    return int(found) if found is not None else None


# --- The seed and the taste profile, from stored data ----------------------------------


def seed_for_entry(engine: Engine, user_id: int, entry_id: int) -> Seed | None:
    """One of this person's entries as a seed, or `None` when it is not theirs."""
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT e.id, i.id, i.type, i.title, i.year, i.metadata FROM entries e"
                " JOIN items i ON i.id = e.item_id WHERE e.id = :entry AND e.user_id = :user"
            ),
            {"entry": entry_id, "user": user_id},
        ).first()
        if row is None:
            return None
        ids: dict[str, str] = {}
        for source, source_id in connection.execute(
            text("SELECT source, source_id FROM item_sources WHERE item_id = :item"),
            {"item": row[1]},
        ):
            ids[str(source)] = str(source_id)
        for kind, value in connection.execute(
            text("SELECT kind, value FROM item_identifiers WHERE item_id = :item"),
            {"item": row[1]},
        ):
            ids[str(kind)] = str(value)
    metadata = _json_object(row[5])
    creators = metadata.get("creators")
    return Seed(
        item_type=str(row[2]),
        entry_id=int(row[0]),
        item_id=int(row[1]),
        title=str(row[3]),
        year=row[4],
        creators=tuple(str(name) for name in creators if isinstance(name, str))
        if isinstance(creators, list)
        else (),
        external_ids=ids,
        metadata=metadata,
    )


def taste_profile(engine: Engine, user_id: int, domain: Domain) -> TasteProfile:
    """Top scores, recent finishes, turned-down suggestions and the pile, in one library.

    Titles, creators, years and scores only. Which statuses count as finished or
    waiting is the domain's `StatusSpec`, as in the ranked pile.
    """
    finished = [status.value for status in domain.statuses if status.finished]
    planned = [status.value for status in domain.statuses if status.planned]
    params: dict[str, Any] = {"user": user_id, "type": domain.item_type, "size": PROFILE_SIZE}
    base = (
        "SELECT i.title, i.year, i.creator_primary, e.score FROM entries e"
        " JOIN items i ON i.id = e.item_id WHERE e.user_id = :user AND i.type = :type"
    )

    def statuses(prefix: str, values: Sequence[str]) -> str:
        for index, value in enumerate(values):
            params[f"{prefix}{index}"] = value
        return ", ".join(f":{prefix}{index}" for index in range(len(values))) or "NULL"

    def entries(rows: Iterable[Sequence[Any]]) -> tuple[TasteEntry, ...]:
        return tuple(TasteEntry(str(row[0]), row[1], row[2], row[3]) for row in rows)

    with engine.connect() as connection:
        top = connection.execute(
            text(f"{base} AND e.score IS NOT NULL ORDER BY e.score DESC, e.id DESC LIMIT :size"),
            params,
        ).all()
        recent = connection.execute(
            text(
                f"{base} AND e.status IN ({statuses('f', finished)})"
                " AND e.date_finished IS NOT NULL ORDER BY e.date_finished DESC, e.id DESC"
                " LIMIT :size"
            ),
            params,
        ).all()
        waiting = connection.execute(
            text(
                f"{base} AND e.status IN ({statuses('p', planned)})"
                " ORDER BY e.date_added DESC, e.id DESC LIMIT :size"
            ),
            params,
        ).all()
        dismissed = connection.execute(
            text(
                "SELECT title, year, creator, NULL FROM suggestions WHERE user_id = :user"
                " AND item_type = :type AND answer = 'not_for_me'"
                " ORDER BY answered_at DESC, id DESC LIMIT :size"
            ),
            params,
        ).all()
    return TasteProfile(
        item_type=domain.item_type,
        top_scored=entries(top),
        recent_finishes=entries(recent),
        dismissed=entries(dismissed),
        waiting=entries(waiting),
    )


# --- Starting a round, and answering -------------------------------------------------


def start_round(
    engine: Engine,
    registry: SourceRegistry,
    user_id: int,
    entry_id: int,
    *,
    source: str | None = None,
    refresh: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """*More like this* on one entry: a recent round again, or a new one queued."""
    seed = seed_for_entry(engine, user_id, entry_id)
    if seed is None:
        raise LibraryError("entry_not_found", "Entry was not found", status_code=404)
    domain = DOMAINS.get(seed.item_type)
    spec = domain.recommendation if domain is not None else None
    if domain is None or spec is None or not spec.sources:
        raise LibraryError(
            "no_recommendation_source",
            "Nothing suggests things for this library yet",
            status_code=409,
        )
    if source is None:
        source = next((name for name in spec.sources if registry.configured(name)), None)
        source = source or spec.sources[0]
    elif source not in spec.sources:
        raise LibraryError(
            "unknown_recommendation_source",
            f"{domain.plural_label} are not suggested by {source!r}",
            status_code=422,
            details={"sources": list(spec.sources)},
        )
    store = SuggestionStore(engine, user_id)
    moment = now or datetime.now(UTC)
    if not refresh:
        recent = store.reusable_round(entry_id, source, moment)
        if recent is not None:
            found = store.round(recent)
            assert found is not None
            return found
    answering = registry.get(source)
    if not isinstance(answering, RecommendationSource):
        hint = (
            answering.hint
            if isinstance(answering, NotConfigured)
            else f"No source named {source!r} is built in"
        )
        round_id = store.create_round(
            seed.item_type, entry_id, source, status="not_configured", error=hint
        )
    else:
        round_id = store.create_round(seed.item_type, entry_id, source)
        JobRepository(engine).enqueue(None, RECOMMEND_JOB, {"round_id": round_id}, user_id=user_id)
    found = store.round(round_id)
    assert found is not None
    return found


def planned_status(domain: Domain) -> str | None:
    """Where *Want* puts a suggestion: the domain's first waiting status."""
    return next((status.value for status in domain.statuses if status.planned), None)


def answer_suggestion(
    engine: Engine, user_id: int, suggestion_id: int, answer: str | None
) -> dict[str, Any]:
    """Record an answer. *Want* adds the resolved item as a planned entry first."""
    store = SuggestionStore(engine, user_id)
    found = store.suggestion(suggestion_id)
    if found is None:
        raise LibraryError("suggestion_not_found", "Suggestion was not found", status_code=404)
    if answer == "want":
        domain = DOMAINS.get(found["item_type"])
        status = planned_status(domain) if domain is not None else None
        if status is None:
            raise LibraryError(
                "no_planned_status", "This library has nowhere to keep what you want next"
            )
        if found["enrichment"] != "enriched" or found["item_id"] is None:
            raise LibraryError(
                "suggestion_not_resolved",
                "This suggestion has not been found in a provider yet",
            )
        try:
            DomainRepository(engine, user_id).create_entry_for_item(found["item_id"], status)
        except LookupError as error:
            raise LibraryError(
                "suggestion_not_resolved", "This suggestion's record is gone"
            ) from error
    store.set_answer(suggestion_id, answer)
    after = store.suggestion(suggestion_id)
    assert after is not None
    return after


def queue_enrichment(
    engine: Engine, user_id: int, suggestion_id: int
) -> tuple[dict[str, Any], str | None]:
    """Resolve one suggestion in the background, unless it already is."""
    store = SuggestionStore(engine, user_id)
    found = store.suggestion(suggestion_id)
    if found is None:
        raise LibraryError("suggestion_not_found", "Suggestion was not found", status_code=404)
    if found["enrichment"] != "pending":
        return found, None
    job_id = JobRepository(engine).enqueue(
        None, ENRICH_SUGGESTION_JOB, {"suggestion_id": suggestion_id}, user_id=user_id
    )
    return found, job_id


# --- Enrichment: the domain's resolve, under the provider budgets ---------------------


class _Budgeted:
    """A provider whose every request is counted against its daily budget first.

    The domain's `resolve` receives these, so whatever it asks, no request goes out
    over a provider's quota: a spent budget raises `ProviderBudgetSpent` before the
    call, and each call made is recorded.
    """

    _METERED = frozenset({"search", "fetch", "fetch_by_identifier"})

    def __init__(
        self,
        provider: Provider,
        quota: ProviderQuota | None,
        rate_limiter: RateLimiter | None,
    ) -> None:
        self._provider = provider
        self._quota = quota
        self._rate_limiter = rate_limiter
        self.name = provider.name
        self.item_type = provider.item_type

    async def _spend(self) -> None:
        now = datetime.now(UTC)
        if self._quota is not None:
            if not await off_loop(self._quota.allows, self.name, now):
                raise ProviderBudgetSpent(self.name)
            await off_loop(self._quota.record, self.name, now)
        if self._rate_limiter is not None:
            while not self._rate_limiter.acquire(datetime.now(UTC)):
                await asyncio.sleep(0.05)

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._provider, name)
        if name not in self._METERED or not callable(target):
            return target

        async def metered(*args: Any, **kwargs: Any) -> Any:
            await self._spend()
            return await target(*args, **kwargs)

        return metered

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        await self._spend()
        return await self._provider.search(query, limit)


class SuggestionEnricher:
    """Finds one suggestion in its domain's providers and caches what it found."""

    def __init__(
        self,
        engine: Engine,
        providers: Mapping[str, Any],
        *,
        quota: ProviderQuota | None = None,
        rate_limiter: RateLimiter | None = None,
        cover_client: httpx.AsyncClient | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.engine = engine
        self.providers = providers
        self.quota = quota
        self.rate_limiter = rate_limiter
        self.cover_client = cover_client
        self.data_dir = data_dir

    def _serving(self, domain: Domain) -> dict[str, Provider]:
        serving = {
            name: provider
            for name, provider in self.providers.items()
            if getattr(provider, "item_type", None) == domain.item_type
        }
        order = list(domain.identity.source_preference)
        ranked = sorted(
            serving, key=lambda name: (order.index(name) if name in order else len(order), name)
        )
        return {name: _Budgeted(serving[name], self.quota, self.rate_limiter) for name in ranked}

    async def enrich(self, user_id: int, suggestion_id: int) -> str:
        """Resolve a pending suggestion; returns its enrichment state afterwards.

        Raises `ProviderBudgetSpent` when a provider's budget ran out mid-way: the
        suggestion stays `pending`, and the caller stops asking for the rest. Any
        other provider failure also leaves it `pending`, for a later try.
        """
        store = SuggestionStore(self.engine, user_id)
        found = await off_loop(store.suggestion, suggestion_id)
        if found is None:
            return "missing"
        if found["enrichment"] != "pending":
            return str(found["enrichment"])
        domain = DOMAINS.get(found["item_type"])
        spec = domain.recommendation if domain is not None else None
        if domain is None or spec is None:
            return "pending"
        candidate = Candidate(
            title=found["title"],
            year=found["year"],
            creator=found["creator"],
            external_ids=found["external_ids"],
            reason=(found["reason"] or {}).get("text", ""),
            source_score=found["source_score"],
            display=found["display"],
        )
        try:
            record = await spec.resolve(candidate, self._serving(domain))
        except ProviderBudgetSpent:
            raise
        except Exception as error:  # noqa: BLE001 - a provider failure waits for a retry
            logger.warning(
                "suggestion could not be resolved",
                extra={"suggestion": suggestion_id, "error": type(error).__name__},
            )
            return "pending"
        if record is None:
            await off_loop(store.set_enrichment, suggestion_id, "unresolved")
            return "unresolved"
        item_id = await self._cache(domain, user_id, record)
        if item_id is None:
            return "pending"
        await off_loop(store.set_enrichment, suggestion_id, "enriched", item_id)
        return "enriched"

    async def _cache(self, domain: Domain, user_id: int, record: SearchCandidate) -> int | None:
        metadata: dict[str, Any] = {**record.metadata, "creators": list(record.creators)}
        if record.language and declares_field(domain, "language"):
            metadata["language"] = record.language
        try:
            metadata = validate_metadata_patch(domain, metadata)
        except InvalidMetadata as error:
            logger.warning("resolved record does not fit its domain", extra={"error": str(error)})
            return None
        identifiers: list[Identifier] = []
        for kind, value in record.identifiers.items():
            try:
                identifiers.append(normalize_identifier(kind, value))
            except InvalidIdentifier:
                continue
        refs = record.source_refs or ()
        sources = [
            SourceIdentity(ref.source, ref.source_id, ref.source == record.source) for ref in refs
        ] or [SourceIdentity(record.source, record.source_id, True)]
        repository = DomainRepository(self.engine, user_id)
        try:
            item_id: int = await off_loop(
                lambda: repository.cache_item(
                    title=record.title,
                    subtitle=record.subtitle,
                    year=record.year,
                    metadata=metadata,
                    identifiers=identifiers,
                    sources=sources,
                    creator_sort=record.creator_sort,
                    item_type=domain.item_type,
                )
            )
        except IdentityConflict:
            logger.warning("resolved record names two cached items")
            return None
        await self._install_cover(repository, item_id, record)
        return item_id

    def _has_cover(self, item_id: int) -> bool:
        with self.engine.connect() as connection:
            return bool(
                connection.execute(
                    text("SELECT cover_path FROM items WHERE id = :id"), {"id": item_id}
                ).scalar()
            )

    async def _install_cover(
        self, repository: DomainRepository, item_id: int, record: SearchCandidate
    ) -> None:
        """The record's cover, when the cached item has none: wanting it later is whole."""
        if self.cover_client is None or self.data_dir is None:
            return
        if await off_loop(self._has_cover, item_id):
            return
        data_dir = self.data_dir
        for url in ([record.cover_url] if record.cover_url else []) + list(
            record.cover_fallback_urls
        ):
            try:
                prepared = await prepare_cover(self.cover_client, url, data_dir)
            except CoverError:
                continue
            try:
                await off_loop(install_cover, prepared, data_dir, item_id)
                await off_loop(repository.set_cover_path, item_id, f"covers/{item_id}.jpg")
            except (CoverError, LookupError):
                prepared.unlink(missing_ok=True)
            return


# --- The two jobs ----------------------------------------------------------------------


class RecommendHandler:
    """`recommend`: ask the round's source once, store, enrich the top few."""

    def __init__(
        self,
        engine: Engine,
        registry: SourceRegistry,
        enricher: SuggestionEnricher,
        *,
        round_quota: ProviderQuota | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.engine = engine
        self.registry = registry
        self.enricher = enricher
        self.round_quota = round_quota
        self.clock = clock
        self.repo = JobRepository(engine)

    async def process(self, job_id: str, now: datetime) -> dict[str, Any]:
        job = await off_loop(self.repo.get_job, job_id)
        round_id = (job or {}).get("payload", {}).get("round_id")
        owner = await off_loop(round_owner, self.engine, int(round_id)) if round_id else None
        if job is None or owner is None:
            return {"state": "failed", "error": "Round was not found", "error_code": "not_found"}
        user_id, status = owner
        store = SuggestionStore(self.engine, user_id)
        progress: dict[str, Any] = {"round_id": round_id, "status": status}
        if status in FINISHED:
            return {"state": "succeeded", "progress": progress}
        if status in ("queued", "selecting"):
            outcome = await self._select(job_id, store, int(round_id), progress)
            if outcome is not None:
                return outcome
        return await self._enrich_top(job_id, store, int(round_id), progress)

    async def _finish(
        self,
        store: SuggestionStore,
        round_id: int,
        progress: dict[str, Any],
        status: str,
        error: str | None,
    ) -> dict[str, Any]:
        await off_loop(store.set_round, round_id, status, error=error)
        progress.update(status=status, error=error)
        return {"state": "succeeded", "progress": progress}

    async def _select(
        self, job_id: str, store: SuggestionStore, round_id: int, progress: dict[str, Any]
    ) -> dict[str, Any] | None:
        found = await off_loop(store.round, round_id)
        assert found is not None
        name = str(found["source"])
        source = self.registry.get(name)
        if not isinstance(source, RecommendationSource):
            hint = source.hint if isinstance(source, NotConfigured) else f"No source named {name!r}"
            return await self._finish(store, round_id, progress, "not_configured", hint)
        domain = DOMAINS.get(str(found["item_type"]))
        if domain is None:
            return await self._finish(
                store, round_id, progress, "failed", "This library no longer exists"
            )
        moment = self.clock()
        key = budget_key(name)
        if self.round_quota is not None:
            if not await off_loop(self.round_quota.allows, key, moment):
                limit = self.round_quota.limits.get(key)
                return await self._finish(
                    store,
                    round_id,
                    progress,
                    "over_budget",
                    f"{name} has answered its {limit} rounds for today; it answers again"
                    " tomorrow (UTC)",
                )
            await off_loop(self.round_quota.record, key, moment)
        await off_loop(store.set_round, round_id, "selecting")
        progress["status"] = "selecting"
        await off_loop(self.repo.record_progress, job_id, progress)
        seed_entry_id = found["seed_entry_id"]
        seed = (
            await off_loop(seed_for_entry, self.engine, store.user_id, int(seed_entry_id))
            if seed_entry_id is not None
            else None
        ) or Seed(item_type=domain.item_type)
        profile = await off_loop(taste_profile, self.engine, store.user_id, domain)
        try:
            candidates = list(await source.select(seed, profile, SELECT_LIMIT))
        except SourceError as error:
            return await self._finish(store, round_id, progress, "failed", str(error)[:500])
        except Exception as error:  # noqa: BLE001 - recorded on the round, not retried
            logger.warning("recommendation source failed", extra={"source": name})
            return await self._finish(
                store,
                round_id,
                progress,
                "failed",
                f"{name} could not answer ({type(error).__name__})",
            )
        stored, dropped = await off_loop(
            store.store, round_id, domain.item_type, candidates[:SELECT_LIMIT]
        )
        await off_loop(store.set_round, round_id, "enriching")
        progress.update(status="enriching", stored=len(stored), dropped=dropped)
        await off_loop(self.repo.record_progress, job_id, progress)
        return None

    async def _enrich_top(
        self, job_id: str, store: SuggestionStore, round_id: int, progress: dict[str, Any]
    ) -> dict[str, Any]:
        found = await off_loop(store.round, round_id)
        assert found is not None
        domain = DOMAINS.get(str(found["item_type"]))
        spec = domain.recommendation if domain is not None else None
        top = found["suggestions"][: spec.enrich_top if spec is not None else 0]
        enriched = 0
        note: str | None = None
        for suggestion in top:
            try:
                state = await self.enricher.enrich(store.user_id, int(suggestion["id"]))
            except ProviderBudgetSpent as error:
                note = f"{error}; the rest wait until someone opens them"
                break
            enriched += state == "enriched"
            progress["enriched"] = enriched
            await off_loop(self.repo.record_progress, job_id, progress)
        progress["enriched"] = enriched
        return await self._finish(store, round_id, progress, "done", note)


class EnrichSuggestionHandler:
    """`enrich_suggestion`: resolve one suggestion someone opened."""

    def __init__(self, engine: Engine, enricher: SuggestionEnricher) -> None:
        self.engine = engine
        self.enricher = enricher
        self.repo = JobRepository(engine)

    async def process(self, job_id: str, now: datetime) -> dict[str, Any]:
        job = await off_loop(self.repo.get_job, job_id)
        suggestion_id = (job or {}).get("payload", {}).get("suggestion_id")
        user_id = (
            await off_loop(suggestion_owner, self.engine, int(suggestion_id))
            if suggestion_id
            else None
        )
        if job is None or user_id is None:
            return {
                "state": "failed",
                "error": "Suggestion was not found",
                "error_code": "not_found",
            }
        progress: dict[str, Any] = {"suggestion_id": suggestion_id}
        try:
            progress["enrichment"] = await self.enricher.enrich(user_id, int(suggestion_id))
        except ProviderBudgetSpent as error:
            progress.update(enrichment="pending", error=str(error))
        return {"state": "succeeded", "progress": progress}
