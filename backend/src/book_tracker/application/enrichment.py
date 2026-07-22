"""Enrichment handler: fills empty item metadata from providers without overwriting."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from book_tracker.infrastructure.jobs import JobRepository, RateLimiter
from book_tracker.infrastructure.models import (
    ImportBatchRow,
    ImportEffectRow,
    ImportRecordRow,
    ItemRow,
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
    ) -> None:
        self.engine = engine
        self.providers = providers
        self.rate_limiter = rate_limiter
        self.repo = JobRepository(engine)

    async def process(self, job_id: str, now: datetime) -> dict[str, Any]:
        """Process one enrichment job. Returns a result dict with 'state' key."""
        job = self.repo.get_job(job_id)
        if job is None:
            return {"state": "failed", "error": "job_not_found"}
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
            return {"state": "failed", "error": "no_isbn"}

        provider = self.providers.get("openlibrary")
        if provider is None:
            return {"state": "failed", "error": "no_provider"}

        # Apply rate limiting if configured
        if self.rate_limiter is not None and not self.rate_limiter.acquire(now):
            return {"state": "failed", "error": "rate_limited"}

        try:
            payload_data = await provider.fetch_by_isbn(isbn)
        except Exception as exc:
            return {"state": "failed", "error": str(exc)[:200]}

        # Fill only empty fields
        filled: list[str] = []
        now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            session = Session(bind=connection)
            try:
                item = session.get(ItemRow, item_id)
                if item is None:
                    connection.rollback()
                    return {"state": "failed", "error": "item_not_found"}

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

        return {"state": "succeeded", "progress": {"filled": filled}}