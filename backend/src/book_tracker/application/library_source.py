"""*From your library*: the nearest things already waiting (Sprint 136, DEC-183 point 7).

A recommendation source whose candidates are the person's own entries: those in the
seed's library that wait in a planned status (or where *Want* would have put them,
for a library with no planned status), ordered by the cosine similarity of their
stored vectors to the seed's. It asks no metadata provider: its picks are cached
items already, stored found. The only request it may make is to the embedding
endpoint, once, for a seed that has no current vector yet; the round fails with the
endpoint's reason if that fails.

Because its picks are already in the library, the source declares `from_library`:
the round keeps them instead of dropping them as already held, and a screen opens
them instead of offering *Want* (the answer refuses one already held).

Shared layer: the statuses are the domain's `StatusSpec` and `want_status`; no
domain is named here.
"""

from __future__ import annotations

import heapq
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.embeddings import Embedder, load_vectors, similarity, unpack
from book_tracker.application.recommendations import want_status
from book_tracker.domain.recommendations import Candidate, Seed, SourceError, TasteProfile
from book_tracker.domain.registry import DOMAINS
from book_tracker.domain.spec import Domain
from book_tracker.infrastructure.embedding_clients import PROVIDER_LABELS
from book_tracker.infrastructure.offload import off_loop

NAME = "library"
LABEL = "From your library"
#: What a screen says the endpoint is sent; nothing about the person.
SENDS = (
    "Each item's title, creator, year, subjects or genres and description; nothing"
    " about you, your scores or your notes."
)
NOT_CONFIGURED_HINT = (
    "From your library needs embeddings. Set AKASHA_RECS_EMBEDDINGS_KEY (or"
    " GEMINI_API_KEY for the default provider, Gemini) in the server's environment and"
    " restart; AKASHA_RECS_EMBEDDINGS_PROVIDER=openai chooses an OpenAI-compatible"
    " endpoint such as Voyage. The Claude API has no embeddings."
)


def waiting_statuses(domain: Domain) -> list[str]:
    """What counts as waiting: the planned statuses, and where *Want* puts a thing."""
    statuses = [status.value for status in domain.statuses if status.planned]
    wanted = want_status(domain)
    if wanted is not None and wanted not in statuses:
        statuses.append(wanted)
    return statuses


def _since(value: Any) -> str | None:
    try:
        return f"{date.fromisoformat(str(value)[:10]):%b %Y}"
    except (TypeError, ValueError):
        return None


def nearest_waiting(
    engine: Engine, model: str, entry_id: int, limit: int
) -> list[dict[str, Any]] | None:
    """The `limit` waiting entries nearest the seed entry's item, nearest first.

    `None` when the seed has no current vector. Each answer carries the entry, its
    item, title, first year, creator, when it was added, and its similarity. One
    query over the person's waiting entries in that library, then a dot product
    each in plain Python (a 10,000-item library answers well under 300 ms).
    """
    with engine.connect() as connection:
        seed = connection.execute(
            text(
                "SELECT e.user_id, e.item_id, i.type FROM entries e"
                " JOIN items i ON i.id = e.item_id WHERE e.id = :id"
            ),
            {"id": entry_id},
        ).first()
        if seed is None:
            return []
        user_id, item_id, item_type = seed
        domain = DOMAINS.get(str(item_type))
        if domain is None:
            return []
        seed_vector = load_vectors(connection, model, [int(item_id)]).get(int(item_id))
        if seed_vector is None:
            return None
        statuses = waiting_statuses(domain)
        if not statuses:
            return []
        params: dict[str, Any] = {
            "user": user_id,
            "type": item_type,
            "seed": entry_id,
            "model": model,
        }
        for index, value in enumerate(statuses):
            params[f"s{index}"] = value
        rows = connection.execute(
            text(
                "SELECT e.id, e.item_id, i.title,"
                " COALESCE(CAST(json_extract(i.metadata, '$.original_year') AS INTEGER), i.year),"
                " i.creator_primary, e.date_added, v.vector FROM entries e"
                " JOIN items i ON i.id = e.item_id"
                " JOIN item_embeddings v ON v.item_id = e.item_id AND v.model = :model"
                " WHERE e.user_id = :user AND i.type = :type AND e.id <> :seed"
                f" AND e.status IN ({', '.join(f':s{i}' for i in range(len(statuses)))})"
            ),
            params,
        ).all()
    scored = (
        (similarity(seed_vector, unpack(bytes(row[6]))), row) for row in rows if row[1] != item_id
    )
    best = heapq.nlargest(limit, scored, key=lambda pair: (pair[0], -pair[1][0]))
    return [
        {
            "entry_id": int(row[0]),
            "item_id": int(row[1]),
            "title": str(row[2]),
            "year": row[3],
            "creator": row[4],
            "since": _since(row[5]),
            "similarity": round(score, 4),
        }
        for score, row in best
    ]


class LibrarySource:
    """The person's own waiting entries nearest the seed, by stored embeddings."""

    name = NAME
    label = LABEL
    from_library = True
    resolved_only = False
    retention = None
    attribution = None

    def __init__(self, engine: Engine, embedder: Embedder) -> None:
        self.engine = engine
        self.embedder = embedder

    @property
    def about(self) -> dict[str, str]:
        client = self.embedder.client
        return {
            "provider": client.provider,
            "provider_label": PROVIDER_LABELS.get(client.provider, client.provider),
            "model": client.model,
            "sends": SENDS,
        }

    async def select(self, seed: Seed, profile: TasteProfile, limit: int) -> Sequence[Candidate]:
        if seed.entry_id is None or seed.item_id is None:
            return []
        # A seed added a moment ago may not be embedded yet: one request, now.
        await self.embedder.ensure([seed.item_id])
        found = await off_loop(
            nearest_waiting, self.engine, self.embedder.model, seed.entry_id, limit
        )
        if found is None:
            raise SourceError(
                f"{seed.title or 'This'} could not be embedded yet; try again later",
                code="not_embedded",
            )
        return [
            Candidate(
                title=row["title"],
                year=row["year"],
                creator=row["creator"],
                item_id=row["item_id"],
                source_score=row["similarity"],
                # The sheet is titled "More like <seed>" and the row says it is on
                # your list: the reason is what differs per row, in Up next's words.
                reason=f"Waiting since {row['since']}" if row["since"] else "",
            )
            for row in found
        ]
