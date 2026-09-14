"""The search_import_rows job (Sprint 083 D3).

One job per searching-connector preview walks the batch's rows in `row_number`
order and searches **the row's own domain's providers** for each — one row at a
time, no concurrency across rows, respecting public-API rate limits (the owner's
explicit "secuencial y async"). Each row's merged top-N becomes proposals in
the store the confirm flow reads.

The domain is the row's own, resolved from the record's `item_type` with the
connector's declared types as the fallback — never named here. This handler is
a shared layer (AC9): it runs for whichever connector declared the search job,
and a provider that serves another domain is never even asked (the interactive
search's `_providers_for` rule, applied to the row).

Failure containment is the design (D3.3): a row whose providers all fail is
`search_failed` on the job's progress and stays confirmable-by-discard; the job
never dead-letters for per-row provider errors, only for systemic ones. A
provider over its daily budget defers the whole job without spending an attempt
— background work is *budgeted*, not recorded-never-blocked (DEC-045's split,
restated for this sprint because per-row searches are enrichment-shaped, not
interactive-shaped).

The quota consult is per provider per row: a capped provider is skipped for the
row, and when no provider remains the job defers to tomorrow's window rather
than burning attempts.
"""

import asyncio
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from book_tracker.application.providers import search_providers
from book_tracker.domain.importers import Importer
from book_tracker.domain.providers import SearchCandidate
from book_tracker.domain.registry import DOMAINS, IMPORTERS
from book_tracker.infrastructure.jobs import JobRepository, RateLimiter
from book_tracker.infrastructure.models import ImportBatchRow, ImportRecordRow
from book_tracker.infrastructure.quota import ProviderQuota
from book_tracker.infrastructure.repositories import ImportRepository

logger = logging.getLogger(__name__)

#: How many merged results a row keeps as proposals. The top-3 list exists so
#: the owner can pick a different result than the first when provider relevance
#: is poor — the sprint's own risk list names Spanish-title relevance as the
#: case where that matters.
TOP_N = 3

SEARCH_JOB_KIND = "search_import_rows"


class ImportSearchHandler:
    """Processes search_import_rows jobs: one provider search per row, sequential."""

    def __init__(
        self,
        engine: Engine,
        providers: Mapping[str, Any],
        *,
        rate_limiter: RateLimiter | None = None,
        quota: ProviderQuota | None = None,
    ) -> None:
        self.engine = engine
        self.providers = providers
        self.rate_limiter = rate_limiter
        self.quota = quota
        self.repo = JobRepository(engine)

    async def process(self, job_id: str, now: datetime) -> dict[str, Any]:
        job = self.repo.get_job(job_id)
        if job is None:
            return {"state": "failed", "error": "Job was not found", "error_code": "job_not_found"}
        batch_id = job.get("batch_id")
        if batch_id is None:
            return {
                "state": "failed",
                "error": "A search job belongs to a batch",
                "error_code": "batch_not_found",
            }
        user_id = job.get("user_id")
        if user_id is None:
            return {
                "state": "failed",
                "error": "A search job belongs to a user's batch",
                "error_code": "batch_not_found",
            }

        # The late-job guard, the same rule enrichment applies: undo cancels the
        # in-flight search rather than letting it write proposals for rows that
        # no longer exist. The batch belongs to whichever connector declared
        # the search job — a shared layer never names the connector it serves
        # (AC9); a batch of any other kind has no search phase to run.
        importer: Importer | None = None
        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is not None:
                importer = IMPORTERS.get(batch.kind)
            if (
                batch is None
                or batch.user_id != user_id
                or getattr(importer, "search_job", None) != SEARCH_JOB_KIND
            ):
                return {
                    "state": "failed",
                    "error": "The batch this job searches no longer exists",
                    "error_code": "batch_not_found",
                }
            if batch.state == "undone":
                self.repo.cancel(job_id)
                return {"state": "cancelled"}
            rows = list(
                session.scalars(
                    select(ImportRecordRow)
                    .where(ImportRecordRow.batch_id == batch_id)
                    .order_by(ImportRecordRow.row_number)
                )
            )

        imports = ImportRepository(self.engine, user_id)
        searched = 0
        no_results = 0
        search_failed = 0
        for row in rows:
            payload = json.loads(row.normalized_payload)
            title = str(payload.get("item", {}).get("title") or "").strip()
            creators = payload.get("item", {}).get("metadata", {}).get("creators") or []
            author = str(creators[0]).strip() if creators else ""
            if not title:
                # A row the reader refused has nothing to search for; it is not
                # a failure, it is an answer the preview already shows.
                no_results += 1
                continue
            query = " ".join(part for part in (title, author) if part)

            # The row's own domain, never a named one: the record's `item_type`
            # when the connector produces more than one library, and the
            # connector's first declared type otherwise (the same default the
            # rest of the import boundary applies to a typeless record). The
            # importer is not None here — the guard above refused a batch whose
            # connector did not declare the search job.
            assert importer is not None
            item_type = payload.get("item_type") or importer.item_types[0]
            domain = DOMAINS.get(item_type)
            if domain is None:
                # A record naming a type its connector did not declare never
                # reaches the store — preview refuses it — so this is the
                # defensive half only.
                no_results += 1
                continue
            # Only the providers that serve this row's domain are asked — the
            # interactive search's `_providers_for` rule, applied per row. A
            # provider of another domain would spend its quota to offer
            # candidates the row could never use.
            serving = [
                provider
                for provider in self.providers.values()
                if getattr(provider, "item_type", domain.item_type) == domain.item_type
            ]

            # The rate limiter gates rows, not providers: one acquire per row
            # keeps the sequential pacing the owner specified. A gate that is
            # not ready yet waits rather than skipping — the job's clock is the
            # poller's, and waiting inside the handler is what `min_interval`
            # means here.
            if self.rate_limiter is not None:
                while not self.rate_limiter.acquire(now):
                    await asyncio.sleep(0.05)
                    now = datetime.now(UTC)

            # The quota consult is per provider (DEC-045's budgeted half): a
            # capped provider is skipped for this row, and when nothing remains
            # the job defers without spending an attempt.
            allowed = [
                provider
                for provider in serving
                if self.quota is None or self.quota.allows(provider.name, now)
            ]
            if not allowed:
                until = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
                self.repo.defer(
                    job_id,
                    until,
                    reason="Every provider's daily budget is spent; the search resumes tomorrow",
                )
                return {"state": "deferred", "available_at": until.isoformat()}

            try:
                candidates = await search_providers(query, allowed, domain=domain)
            except Exception as error:  # noqa: BLE001 - containment is the design
                logger.warning(
                    "import row search failed",
                    extra={"batch": batch_id, "row": row.row_number, "error": str(error)},
                )
                search_failed += 1
                continue
            finally:
                for provider in allowed:
                    if self.quota is not None:
                        self.quota.record(provider.name, now)

            if not candidates:
                no_results += 1
                continue
            imports.add_proposals(
                batch_id=batch_id,
                record_id=row.id,
                proposals=tuple(
                    _proposal_payload(candidate, rank)
                    for rank, candidate in enumerate(candidates[:TOP_N])
                ),
            )
            searched += 1

        # The queue has drained: the batch is previewable again, and commit's
        # gate reopens. Written before the job completes so a poller reading the
        # batch the moment the job succeeds can never see `matching` with a
        # succeeded job.
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE import_batches SET state = 'previewed', updated_at = :now"
                    " WHERE id = :id AND state = 'matching'"
                ),
                {"now": _now_iso(), "id": batch_id},
            )
        return {
            "state": "succeeded",
            "progress": {
                "searched": searched,
                "no_results": no_results,
                "search_failed": search_failed,
                "total": len(rows),
            },
        }


def _proposal_payload(candidate: SearchCandidate, rank: int) -> dict[str, Any]:
    """The stored proposal: everything the confirmation will re-stage the row
    from, and nothing about how the result was found that a screen would need
    to re-derive."""
    return {
        "source": candidate.source,
        "source_id": candidate.source_id,
        "rank": rank,
        "payload": {
            "title": candidate.title,
            "subtitle": candidate.subtitle,
            "creators": list(candidate.creators),
            "year": candidate.year,
            "identifiers": dict(candidate.identifiers),
            "language": candidate.language,
            "metadata": dict(candidate.metadata),
            "cover_url": candidate.cover_url,
            "cover_fallback_urls": list(candidate.cover_fallback_urls),
        },
    }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
