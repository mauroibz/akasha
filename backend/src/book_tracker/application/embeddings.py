"""A vector of each item's stored text, kept current (Sprint 136, DEC-183 point 7).

```text
TEXT    title, creator, year (the work's first year where known), then the
        domain's declared `RankingSpec.text_fields` in their order
  -> HASH   SHA-256 of that text; a stored vector of another hash or model is stale
  -> EMBED  `embed_items`: stale and missing ones, 32 to a request, eight requests a
            job, every request counted against the `embeddings` daily budget
  -> STORE  `item_embeddings`: float32, scaled to unit length (cosine is a dot)
  -> READ   the library source, the pile's similarity signal, a round's order
```

The job runs after an enrichment filled something (an item's text became known),
after a suggestion's item was cached, and from the hourly maintenance pass, which
catches anything else that changed (an edit, an import without enrichment). It
embeds only items someone holds an entry on or was suggested: the cache's other
rows are pruned, not embedded.

Shared layer: which fields make the text is the domain's declaration; no domain or
field is named here (technical spec 6.6). Reading vectors never calls the endpoint;
only the job and a round of the library source (for a seed not yet embedded) do.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import sys
from array import array
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from book_tracker.domain.recommendations import SourceError
from book_tracker.domain.registry import DOMAINS
from book_tracker.domain.spec import Domain
from book_tracker.infrastructure.embedding_clients import BATCH_SIZE, EmbeddingClient
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.offload import off_loop
from book_tracker.infrastructure.quota import ProviderQuota

logger = logging.getLogger(__name__)

EMBED_JOB = "embed_items"
#: The `provider_usage` row embedding requests are counted under, and the key of
#: `AKASHA_PROVIDER_DAILY_LIMITS` that bounds them.
BUDGET = "embeddings"
#: Requests a day unless configured: 32,000 items, more than a first pass over a
#: large library needs, and a cap on what a mistake could spend.
DEFAULT_DAILY_REQUESTS = 1000
#: Requests one job makes before it hands over to a follow-up, so other work runs
#: between them.
BATCHES_PER_JOB = 8
#: A description beyond this says nothing more about likeness, and costs tokens.
TEXT_CHARACTERS = 2000
#: Vectors are written little-endian whatever the host is.
_SWAP = sys.byteorder != "little"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# --- The text, and what a vector is stored as --------------------------------------


def _words(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(part).strip() for part in value if str(part).strip())
    if isinstance(value, str | int | float) and not isinstance(value, bool):
        return " ".join(str(value).split())
    return ""


def embedding_text(
    domain: Domain,
    title: str,
    creator: str | None,
    year: int | None,
    metadata: Mapping[str, Any],
) -> str:
    """The text an item is embedded from, in a fixed order.

    Title; its creators (the metadata's list, else the stored primary creator); the
    work's first year (`original_year`) before the item's own; then each declared
    text field as "Label: value". Nothing about a person: no score, note or date.
    """
    lines = [" ".join(title.split())]
    creators = _words(metadata.get("creators")) or (creator or "").strip()
    if creators:
        lines.append(f"By {creators}")
    first = metadata.get("original_year")
    shown_year = first if isinstance(first, int) and not isinstance(first, bool) else year
    if shown_year:
        lines.append(str(shown_year))
    labels = {spec.name: spec.label for spec in domain.fields}
    for name in domain.ranking.text_fields:
        value = _words(metadata.get(name))
        if value:
            lines.append(f"{labels.get(name, name)}: {value}")
    return "\n".join(lines)[:TEXT_CHARACTERS]


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def pack(vector: Sequence[float]) -> bytes:
    """A vector as little-endian float32, scaled to unit length."""
    norm = math.sqrt(math.sumprod(vector, vector)) or 1.0
    packed = array("f", (value / norm for value in vector))
    if _SWAP:
        packed.byteswap()
    return packed.tobytes()


def unpack(blob: bytes) -> array[float]:
    vector = array("f")
    vector.frombytes(blob)
    if _SWAP:
        vector.byteswap()
    return vector


def similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two stored (unit-length) vectors: their dot product."""
    if len(a) != len(b):
        return 0.0
    return float(math.sumprod(a, b))


def centroid(vectors: Iterable[Sequence[float]]) -> array[float] | None:
    """The unit-length mean of some vectors: what they have in common."""
    total: list[float] | None = None
    for vector in vectors:
        if total is None:
            total = list(vector)
        elif len(vector) == len(total):
            total = [a + b for a, b in zip(total, vector, strict=True)]
    if total is None:
        return None
    return unpack(pack(total))


# --- What is stored ------------------------------------------------------------------


def load_vectors(
    connection: Connection, model: str, item_ids: Iterable[int]
) -> dict[int, array[float]]:
    """The stored vectors of these items for this model; an item without one is absent."""
    ids = sorted({int(item_id) for item_id in item_ids})
    found: dict[int, array[float]] = {}
    # SQLite's variable limit is 32,766; a page of 900 keeps any build happy.
    for start in range(0, len(ids), 900):
        page = ids[start : start + 900]
        params: dict[str, Any] = {"model": model}
        names = []
        for index, item_id in enumerate(page):
            params[f"i{index}"] = item_id
            names.append(f":i{index}")
        for item_id, blob in connection.execute(
            text(
                "SELECT item_id, vector FROM item_embeddings WHERE model = :model"
                f" AND item_id IN ({', '.join(names)})"
            ),
            params,
        ):
            found[int(item_id)] = unpack(bytes(blob))
    return found


def _texts(connection: Connection, where: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    return [
        tuple(row)
        for row in connection.execute(
            text(
                "SELECT i.id, i.type, i.title, i.creator_primary, i.year, i.metadata,"
                " ie.model, ie.text_hash FROM items i"
                " LEFT JOIN item_embeddings ie ON ie.item_id = i.id"
                f" WHERE {where} ORDER BY i.id"
            ),
            params,
        ).all()
    ]


def _stale(rows: Iterable[Sequence[Any]], model: str, limit: int) -> list[tuple[int, str, str]]:
    stale: list[tuple[int, str, str]] = []
    for item_id, item_type, title, creator, year, metadata, stored_model, stored_hash in rows:
        domain = DOMAINS.get(str(item_type))
        if domain is None:
            continue
        try:
            loaded = json.loads(metadata) if metadata else {}
        except ValueError:
            loaded = {}
        body = embedding_text(
            domain, str(title), creator, year, loaded if isinstance(loaded, dict) else {}
        )
        digest = text_hash(body)
        if stored_model == model and stored_hash == digest:
            continue
        stale.append((int(item_id), body, digest))
        if len(stale) == limit:
            break
    return stale


def pending_texts(engine: Engine, model: str, limit: int) -> list[tuple[int, str, str]]:
    """Items someone holds or was suggested whose vector is missing or stale.

    `(item_id, text, text_hash)`, lowest id first, at most `limit`. Stale means
    another model, or a text that has changed since it was embedded.
    """
    with engine.connect() as connection:
        rows = _texts(
            connection,
            "EXISTS (SELECT 1 FROM entries e WHERE e.item_id = i.id)"
            " OR EXISTS (SELECT 1 FROM suggestions s WHERE s.item_id = i.id)",
            {},
        )
    return _stale(rows, model, limit)


def texts_for(engine: Engine, model: str, item_ids: Iterable[int]) -> list[tuple[int, str, str]]:
    """These items' texts, where their vector is missing or stale."""
    ids = sorted({int(item_id) for item_id in item_ids})
    if not ids:
        return []
    params = {f"i{index}": item_id for index, item_id in enumerate(ids)}
    with engine.connect() as connection:
        rows = _texts(connection, f"i.id IN ({', '.join(':' + name for name in params)})", params)
    return _stale(rows, model, len(ids))


def store_vectors(
    engine: Engine, model: str, rows: Sequence[tuple[int, str, Sequence[float]]]
) -> None:
    """Keep `(item_id, text_hash, vector)` rows, replacing what an item had."""
    now = _now()
    with engine.begin() as connection:
        for item_id, digest, vector in rows:
            connection.execute(
                text(
                    "INSERT INTO item_embeddings (item_id, model, dims, vector, text_hash,"
                    " created_at) VALUES (:item, :model, :dims, :vector, :hash, :now)"
                    " ON CONFLICT (item_id) DO UPDATE SET model = excluded.model,"
                    " dims = excluded.dims, vector = excluded.vector,"
                    " text_hash = excluded.text_hash, created_at = excluded.created_at"
                ),
                {
                    "item": item_id,
                    "model": model,
                    "dims": len(vector),
                    "vector": pack(vector),
                    "hash": digest,
                    "now": now,
                },
            )


# --- Asking the endpoint -------------------------------------------------------------


class Embedder:
    """The configured endpoint, held to its daily budget, writing what it answers."""

    def __init__(
        self, engine: Engine, client: EmbeddingClient, quota: ProviderQuota | None = None
    ) -> None:
        self.engine = engine
        self.client = client
        self.quota = quota

    @property
    def model(self) -> str:
        return self.client.identity

    async def embed(self, rows: Sequence[tuple[int, str, str]]) -> bool:
        """Embed and store `(item_id, text, hash)` rows in one request.

        False when the day's budget is spent (nothing was asked). A failing
        endpoint raises its `SourceError`.
        """
        if not rows:
            return True
        now = datetime.now(UTC)
        if self.quota is not None:
            if not await off_loop(self.quota.allows, BUDGET, now):
                return False
            await off_loop(self.quota.record, BUDGET, now)
        vectors = await self.client.embed([body for _item, body, _hash in rows])
        if len(vectors) != len(rows) or len({len(vector) for vector in vectors}) > 1:
            raise SourceError("The embedding endpoint answered vectors of mixed sizes")
        await off_loop(
            store_vectors,
            self.engine,
            self.model,
            [
                (item_id, digest, vector)
                for (item_id, _body, digest), vector in zip(rows, vectors, strict=True)
            ],
        )
        return True

    async def ensure(self, item_ids: Iterable[int]) -> None:
        """Embed these items now if their vector is missing or stale (a round's seed)."""
        rows = await off_loop(texts_for, self.engine, self.model, list(item_ids))
        for start in range(0, len(rows), BATCH_SIZE):
            if not await self.embed(rows[start : start + BATCH_SIZE]):
                return


def request_embedding(engine: Engine) -> str | None:
    """Queue an `embed_items` job unless one is already waiting."""
    with engine.connect() as connection:
        waiting = connection.execute(
            text("SELECT 1 FROM jobs WHERE kind = :kind AND state = 'queued' LIMIT 1"),
            {"kind": EMBED_JOB},
        ).first()
    if waiting is not None:
        return None
    return JobRepository(engine).enqueue(None, EMBED_JOB, {})


def request_if_needed(engine: Engine, model: str, now: datetime) -> str | None:
    """The maintenance pass: queue a job when anything is missing or stale."""
    if not pending_texts(engine, model, 1):
        return None
    return request_embedding(engine)


def after_change(engine: Engine, model: str | None) -> Callable[[int], object] | None:
    """What an enrichment or a cached suggestion calls once an item's text is known."""
    if model is None:
        return None

    def changed(_item_id: int) -> object:
        return request_embedding(engine)

    return changed


class EmbedItemsHandler:
    """`embed_items`: missing and stale vectors, a batch per request, under budget."""

    def __init__(self, engine: Engine, embedder: Embedder | None) -> None:
        self.engine = engine
        self.embedder = embedder
        self.repo = JobRepository(engine)

    async def process(self, job_id: str, now: datetime) -> dict[str, Any]:
        if self.embedder is None:
            return {"state": "succeeded", "progress": {"embedded": 0, "configured": False}}
        progress: dict[str, Any] = {"embedded": 0}
        for _batch in range(BATCHES_PER_JOB):
            rows = await off_loop(pending_texts, self.engine, self.embedder.model, BATCH_SIZE)
            if not rows:
                return {"state": "succeeded", "progress": progress}
            try:
                asked = await self.embedder.embed(rows)
            except SourceError as error:
                return {"state": "failed", "error": str(error)[:200], "error_code": error.code}
            if not asked:
                progress["note"] = "today's embedding budget is spent"
                return {"state": "succeeded", "progress": progress}
            progress["embedded"] += len(rows)
            await off_loop(self.repo.record_progress, job_id, progress)
        # More may remain: a follow-up takes it, after whatever else is waiting.
        if await off_loop(pending_texts, self.engine, self.embedder.model, 1):
            await off_loop(request_embedding, self.engine)
        return {"state": "succeeded", "progress": progress}
