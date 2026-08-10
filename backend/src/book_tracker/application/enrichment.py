"""Enrichment handler: fills empty item metadata from providers without overwriting."""

from __future__ import annotations

import json
import logging
from collections.abc import Collection, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from book_tracker.domain.providers import ItemPayload
from book_tracker.infrastructure.covers import CoverError, install_cover, prepare_cover
from book_tracker.infrastructure.jobs import JobRepository, RateLimiter
from book_tracker.infrastructure.models import (
    ImportBatchRow,
    ImportEffectRow,
    ImportRecordRow,
    ItemRow,
)
from book_tracker.infrastructure.providers import ProviderPayloadError

logger = logging.getLogger(__name__)

# Open Library first, Google Books as the fallback: Open Library carries edition-level
# identity, Google Books carries better Spanish-language coverage (product spec 4.2).
PROVIDER_ORDER = ("openlibrary", "googlebooks")
PROVIDER_LABELS = {"openlibrary": "Open Library", "googlebooks": "Google Books"}


def _label(name: str) -> str:
    return PROVIDER_LABELS.get(name, name)


def _is_usable(payload: ItemPayload) -> bool:
    """A payload that carries no year, no cover, and no metadata fills nothing."""
    return bool(
        payload.year is not None
        or payload.cover_url
        or any(value not in (None, "", [], {}) for value in payload.metadata.values())
    )


class EnrichmentHandler:
    """Processes enrich_item jobs: fetches provider data and fills only empty fields.

    Never overwrites existing user data or manual edits (AC6).
    Records import_effects for each fill so undo covers async enrichment (AC5).
    Skips processing entirely if the batch has been undone (AC5 late-job guard).
    """

    def __init__(
        self,
        engine: Engine,
        providers: Mapping[str, Any],
        *,
        rate_limiter: RateLimiter | None = None,
        cover_client: httpx.AsyncClient | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.engine = engine
        self.providers = providers
        self.rate_limiter = rate_limiter
        self.cover_client = cover_client
        self.data_dir = data_dir
        self.repo = JobRepository(engine)

    async def _fetch(
        self, isbn: str
    ) -> tuple[ItemPayload | None, str | None, dict[str, Any] | None]:
        """Try each provider in order, returning the first usable payload.

        Failures are never swallowed: every attempt contributes a sentence to the
        reason recorded on the job row (DEC-025, technical spec 6.2).
        """
        reasons: list[str] = []
        unreachable = False
        for name in PROVIDER_ORDER:
            provider = self.providers.get(name)
            if provider is None:
                reasons.append(f"{_label(name)} is not configured.")
                continue
            try:
                payload = await provider.fetch_by_isbn(isbn)
            except ProviderPayloadError as error:
                unreachable = unreachable or error.code in {
                    "provider_unreachable",
                    "provider_http_error",
                }
                reasons.append(f"{error}.")
                logger.warning(
                    "enrichment provider miss",
                    extra={"provider": name, "isbn": isbn, "code": error.code},
                )
                continue
            except (TimeoutError, httpx.HTTPError, OSError) as error:
                unreachable = True
                reasons.append(f"{_label(name)} could not be reached ({type(error).__name__}).")
                logger.warning(
                    "enrichment provider unreachable",
                    extra={"provider": name, "isbn": isbn, "error": type(error).__name__},
                )
                continue
            if not _is_usable(payload):
                reasons.append(f"{_label(name)} returned no usable metadata for ISBN {isbn}.")
                continue
            return payload, name, None

        failure = {
            "state": "failed",
            "error": " ".join(reasons)[:500],
            "error_code": "enrichment_provider_unavailable"
            if unreachable
            else "enrichment_no_data",
        }
        return None, None, failure

    async def process(self, job_id: str, now: datetime) -> dict[str, Any]:
        """Process one enrichment job. Returns a result dict with 'state' key."""
        job = self.repo.get_job(job_id)
        if job is None:
            return {"state": "failed", "error": "Job was not found", "error_code": "job_not_found"}
        payload = job["payload"]
        batch_id = job.get("batch_id")
        item_id = payload.get("item_id")

        # Late-job guard: if the batch has been undone, cancel this job
        if batch_id is not None:
            with Session(self.engine) as session:
                batch = session.get(ImportBatchRow, batch_id)
                if batch is not None and batch.state == "undone":
                    self.repo.cancel(job_id)
                    return {"state": "cancelled"}

        # Fetch provider data
        isbn = payload.get("isbn")
        if not isbn:
            return {
                "state": "failed",
                "error": "This item has no ISBN to look up",
                "error_code": "no_isbn",
            }

        if not any(self.providers.get(name) for name in PROVIDER_ORDER):
            return {
                "state": "failed",
                "error": "No metadata provider is configured",
                "error_code": "enrichment_not_configured",
            }

        # Apply rate limiting if configured
        if self.rate_limiter is not None and not self.rate_limiter.acquire(now):
            return {
                "state": "failed",
                "error": "Provider rate limit reached; the job will be retried",
                "error_code": "rate_limited",
            }

        payload_data, source_name, failure = await self._fetch(isbn)
        if payload_data is None:
            assert failure is not None
            return failure

        # Fill only empty fields
        filled: list[str] = []
        needs_cover = False
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            session = Session(bind=connection)
            try:
                item = session.get(ItemRow, item_id)
                if item is not None:
                    needs_cover = not item.cover_path
                if item is None:
                    connection.rollback()
                    return {
                        "state": "failed",
                        "error": f"Item {item_id} no longer exists",
                        "error_code": "item_not_found",
                    }

                before: dict[str, Any] = {}
                after: dict[str, Any] = {}

                # Year
                if item.year is None and payload_data.year is not None:
                    before["year"] = None
                    item.year = payload_data.year
                    after["year"] = payload_data.year
                    filled.append("year")

                # Metadata fields
                metadata = json.loads(item.metadata_json)
                for key, value in payload_data.metadata.items():
                    if value in (None, "", [], {}):
                        continue
                    current = metadata.get(key)
                    if current in (None, "", [], {}):
                        before[f"metadata.{key}"] = current
                        metadata[key] = value
                        after[f"metadata.{key}"] = value
                        filled.append(f"metadata.{key}")

                if after:
                    item.metadata_json = json.dumps(metadata, ensure_ascii=False)
                    item.updated_at = now_iso
                    session.flush()

                    # Record import effect for undo coverage
                    if batch_id is not None:
                        record_id = session.scalar(
                            select(ImportRecordRow.id)
                            .where(
                                ImportRecordRow.batch_id == batch_id,
                                ImportRecordRow.matched_item_id == item_id,
                            )
                            .order_by(ImportRecordRow.id)
                            .limit(1)
                        )
                        if record_id is not None:
                            session.add(
                                ImportEffectRow(
                                    batch_id=batch_id,
                                    record_id=record_id,
                                    effect_type="fill_empty",
                                    entity_type="item",
                                    entity_id=str(item_id),
                                    before_values=json.dumps(before, ensure_ascii=False),
                                    after_values=json.dumps(after, ensure_ascii=False),
                                )
                            )
                            session.flush()

                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                session.close()

        # Cover work happens after the write lock is released: it is remote and image
        # work, and a failed cover must never undo a successful metadata fill.
        if needs_cover and await self._install_cover(item_id, payload_data):
            filled.append("cover")

        return {"state": "succeeded", "progress": {"filled": filled, "provider": source_name}}

    async def _install_cover(self, item_id: int, payload: ItemPayload) -> bool:
        """Download and install a cover for an item that has none. Never fatal."""
        if self.cover_client is None or self.data_dir is None:
            return False
        urls = [url for url in (payload.cover_url, *payload.cover_fallback_urls) if url]
        for url in urls:
            try:
                prepared = await prepare_cover(self.cover_client, url, self.data_dir)
            except CoverError:
                continue
            try:
                install_cover(prepared, self.data_dir, item_id)
            except CoverError:
                return False
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE items SET cover_path=:path, updated_at=:now "
                        "WHERE id=:id AND (cover_path IS NULL OR cover_path='')"
                    ),
                    {
                        "path": f"covers/{item_id}.jpg",
                        "now": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "id": item_id,
                    },
                )
            return True
        if urls:
            logger.warning("enrichment could not install a cover", extra={"item_id": item_id})
        return False


def enqueue_enrichment_backfill(
    engine: Engine, *, batch_id: str | None = None, item_ids: Collection[int] | None = None
) -> int:
    """Queue enrichment for persisted items an ISBN lookup could still improve.

    Every enrichment job failed between Sprint 011 and Sprint 014, so libraries imported
    in that window hold rows with an ISBN and nothing else. This is the explicit path
    back: it only ever queues work, and the handler it queues fills empty fields only.

    `item_ids` restricts the scan. An importer passes the rows its own batch touched, so
    a four-row import does not attribute seven jobs — three of them for books it never
    saw — to its batch and its progress display.
    """
    if item_ids is not None and not item_ids:
        return 0
    rows = _backfillable_items(engine, item_ids)
    repository = JobRepository(engine)
    for item_id, isbn in rows:
        repository.enqueue(batch_id, "enrich_item", {"item_id": item_id, "isbn": isbn})
    return len(rows)


def _backfillable_items(
    engine: Engine, item_ids: Collection[int] | None = None
) -> list[tuple[int, str]]:
    scope = ""
    parameters: dict[str, Any] = {}
    if item_ids is not None:
        # Bound and parameterised rather than interpolated.
        placeholders = ", ".join(f":item_{index}" for index, _ in enumerate(item_ids))
        scope = f"AND items.id IN ({placeholders})"
        parameters = {f"item_{index}": value for index, value in enumerate(item_ids)}
    with engine.connect() as connection:
        result = connection.execute(
            text(
                f"""
                SELECT items.id AS item_id, MIN(ident.normalized_value) AS isbn
                FROM items
                JOIN item_identifiers AS ident
                  ON ident.item_id = items.id AND ident.kind = 'isbn'
                WHERE (
                        items.cover_path IS NULL
                     OR items.cover_path = ''
                     OR items.year IS NULL
                     OR json_extract(items.metadata, '$.publisher') IS NULL
                     OR json_extract(items.metadata, '$.page_count') IS NULL
                     OR json_extract(items.metadata, '$.description') IS NULL
                  )
                  AND NOT EXISTS (
                        SELECT 1 FROM jobs
                        WHERE jobs.kind = 'enrich_item'
                          AND jobs.state IN ('queued', 'running')
                          AND json_extract(jobs.payload, '$.item_id') = items.id
                  )
                  {scope}
                GROUP BY items.id
                ORDER BY items.id
                """
            ),
            parameters,
        )
        return [(row.item_id, row.isbn) for row in result]
