"""Enrichment handler: fills empty item metadata from providers without overwriting."""

from __future__ import annotations

import json
import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from book_tracker.domain.merge import prefer_fuller
from book_tracker.domain.providers import ItemPayload
from book_tracker.domain.registry import DOMAINS
from book_tracker.domain.spec import EnrichmentSpec
from book_tracker.infrastructure.covers import CoverError, install_cover, prepare_cover
from book_tracker.infrastructure.jobs import JobRepository, RateLimiter
from book_tracker.infrastructure.models import (
    EntryRow,
    ImportBatchRow,
    ImportEffectRow,
    ImportRecordRow,
    ItemRow,
    ItemSourceRow,
)
from book_tracker.infrastructure.providers import ProviderPayloadError
from book_tracker.infrastructure.quota import ProviderQuota

logger = logging.getLogger(__name__)

# Which providers are asked, and in what order, is now the *domain's* declaration
# (`EnrichmentSpec.provider_order`) rather than a constant here — books' "Open Library
# first, Google Books as the fallback" lives in `domains/book/` where it belongs
# (product spec 4.2, DEC-067 row 3). What remains is display copy: how to name a
# provider in a reason a person reads. A provider absent from this table is named by
# its own identifier, which is legible.
PROVIDER_LABELS = {
    "openlibrary": "Open Library",
    "googlebooks": "Google Books",
    "anilist": "AniList",
    "kitsu": "Kitsu",
    "wikidata": "Wikidata",
    "wikidata-series": "Wikidata",
    "tvmaze": "TVmaze",
}


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
        quota: ProviderQuota | None = None,
        cover_client: httpx.AsyncClient | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.engine = engine
        self.providers = providers
        self.rate_limiter = rate_limiter
        self.quota = quota
        self.cover_client = cover_client
        self.data_dir = data_dir
        self.repo = JobRepository(engine)

    async def _fetch(
        self,
        kind: str,
        value: str,
        spec: EnrichmentSpec,
        now: datetime | None = None,
        *,
        title: str | None = None,
        creators: Sequence[str] | None = None,
    ) -> tuple[ItemPayload | None, str | None, dict[str, Any] | None]:
        """Try the domain's providers in its order, returning the first usable payload.

        The order is the domain's declaration rather than a module constant, and the
        key is the domain's too: this loop said `openlibrary`, `googlebooks` and
        `fetch_by_isbn` until Sprint 039 (DEC-067 row 3).

        Failures are never swallowed: every attempt contributes a sentence to the
        reason recorded on the job row (DEC-025, technical spec 6.2).

        A provider over its daily budget is skipped rather than called, and if that
        leaves nothing to try the caller defers the job instead of failing it — a
        quota that has not reset yet is not a failure (DEC-045).

        The first usable payload wins, with one declared exception
        (`fuller_answer_fields`): after it is chosen, the remaining providers are
        asked for those fields alone, and the longest answer fills the field if
        it beats the first provider's. Every other field, and the whole payload
        when the domain declares none, behaves exactly as before.
        """
        reasons: list[str] = []
        unreachable = False
        capped = False
        available = False
        moment = now or datetime.now(UTC)
        chosen: ItemPayload | None = None
        chosen_source: str | None = None
        for name in spec.provider_order:
            provider = self.providers.get(name)
            if provider is None:
                reasons.append(f"{_label(name)} is not configured.")
                continue
            if self.quota is not None and not self.quota.allows(name, moment):
                capped = True
                reasons.append(f"{_label(name)} is out of requests for today.")
                logger.info("provider quota exhausted", extra={"provider": name})
                continue
            available = True
            if self.quota is not None:
                self.quota.record(name, moment)
            try:
                if spec.needs_item_context:
                    payload = await provider.fetch_by_identifier(
                        kind, value, title=title, creators=creators
                    )
                else:
                    payload = await provider.fetch_by_identifier(kind, value)
            except ProviderPayloadError as error:
                unreachable = unreachable or error.code in {
                    "provider_unreachable",
                    "provider_http_error",
                }
                reasons.append(f"{error}.")
                logger.warning(
                    "enrichment provider miss",
                    extra={"provider": name, "kind": kind, "value": value, "code": error.code},
                )
                continue
            except (TimeoutError, httpx.HTTPError, OSError) as error:
                unreachable = True
                reasons.append(f"{_label(name)} could not be reached ({type(error).__name__}).")
                logger.warning(
                    "enrichment provider unreachable",
                    extra={
                        "provider": name,
                        "kind": kind,
                        "value": value,
                        "error": type(error).__name__,
                    },
                )
                continue
            if not _is_usable(payload):
                reasons.append(
                    f"{_label(name)} returned no usable metadata for {kind.upper()} {value}."
                )
                continue
            if chosen is None:
                chosen = payload
                chosen_source = name
                if not spec.fuller_answer_fields:
                    # Nothing left to ask: the first usable payload is the answer,
                    # exactly as before this declaration existed.
                    return payload, name, None
                continue
            # A second usable payload, reached only when the domain declared
            # `fuller_answer_fields`: it contributes those fields alone, and only
            # when its answer is longer than what the earlier provider supplied.
            # A shorter or equally long answer changes nothing, and no other
            # field of the first payload is ever touched — the second payload's
            # other values are not merged in, so this is not "the last provider
            # wins", and it is not "both providers merged" either (DEC-115).
            fuller = prefer_fuller(chosen.metadata, payload.metadata, spec.fuller_answer_fields)
            if fuller:
                chosen = replace(chosen, metadata={**chosen.metadata, **fuller})
            return chosen, chosen_source, None

        if chosen is not None:
            # The first provider was usable and a later one was not — the loop's
            # `continue` after choosing means a miss or outage below the chosen
            # provider must not lose the payload already in hand.
            return chosen, chosen_source, None

        if capped and not available:
            # Nothing was even tried: every configured provider is out of budget.
            return None, None, {"state": "deferred", "error": " ".join(reasons)[:500]}
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

        # Which domain is this, and what does it enrich on? Read from the item rather
        # than carried in the payload, so a queued job picks up a deployment's current
        # provider order instead of the one that happened to be wired when it was made.
        with self.engine.connect() as connection:
            row = connection.execute(
                text("SELECT type, title, metadata FROM items WHERE id = :id"),
                {"id": item_id},
            ).one_or_none()
        if row is None:
            return {
                "state": "failed",
                "error": f"Item {item_id} no longer exists",
                "error_code": "item_not_found",
            }
        item_type, item_title, item_metadata_json = row
        domain = DOMAINS.get(str(item_type))
        spec = domain.enrichment if domain is not None else None
        if spec is None:
            return {
                "state": "failed",
                "error": f"{item_type} records are not enriched in the background",
                "error_code": "domain_does_not_enrich",
            }
        # Only read when a domain declares it needs this: every other domain's
        # identity value is sufficient on its own (an ISBN, an IMDb id), so paying
        # for a metadata parse on every job would be waste (Sprint 064).
        context_title: str | None = None
        context_creators: Sequence[str] | None = None
        if spec.needs_item_context:
            context_title = str(item_title) if item_title else None
            item_metadata = json.loads(item_metadata_json) if item_metadata_json else {}
            raw_creators = item_metadata.get("creators")
            context_creators = (
                tuple(str(name) for name in raw_creators if isinstance(name, str) and name.strip())
                if isinstance(raw_creators, list)
                else None
            )

        # The payload shape changed in Sprint 039 from `{item_id, isbn}` to
        # `{item_id, kind, value}`. Jobs survive restart by design, so a row queued
        # before the upgrade is still here afterwards; it is read as the domain's own
        # key rather than failing silently in a queue nobody is watching.
        kind = str(payload.get("kind") or spec.identity_kinds[0])
        value = payload.get("value") or payload.get("isbn")
        if not value:
            return {
                "state": "failed",
                "error": f"This item has no {kind} to look up",
                "error_code": "no_enrichment_key",
            }

        if not any(self.providers.get(name) for name in spec.provider_order):
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

        payload_data, source_name, failure = await self._fetch(
            kind, str(value), spec, now, title=context_title, creators=context_creators
        )
        if payload_data is None:
            assert failure is not None
            if failure["state"] == "deferred":
                # Tomorrow's budget, without spending one of this job's attempts.
                until = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
                self.repo.defer(job_id, until, reason=str(failure["error"]))
                return {"state": "deferred", "available_at": until.isoformat()}
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

                # An imported item reaches this handler with an identifier
                # (an ISBN, a Letterboxd slug) but no `item_sources` row at
                # all — the import path that creates it has no provider to
                # record one from, unlike a search-added item, which always
                # gets one (`add.py`). Left unfixed, a successful enrichment
                # fills the record's metadata and cover but leaves it
                # permanently unable to satisfy `primary_source()` — every
                # later refresh or cover-fetch fails with "no provider
                # source", on a record a provider plainly did resolve.
                # Guarded on the item having no source at all, not on this
                # one being new, so an item search-added from a *different*
                # provider (which already has a primary source) is untouched.
                if not session.scalar(
                    select(ItemSourceRow.source).where(ItemSourceRow.item_id == item_id).limit(1)
                ):
                    for ref in payload_data.source_refs:
                        session.add(
                            ItemSourceRow(
                                item_id=item_id,
                                source=ref.source,
                                source_id=ref.source_id,
                                is_primary=int(ref.source == payload_data.source),
                                created_at=now_iso,
                                updated_at=now_iso,
                            )
                        )
                    session.flush()

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

        if payload_data.match_note and self._write_match_note(item_id, payload_data.match_note):
            filled.append("notes")

        return {"state": "succeeded", "progress": {"filled": filled, "provider": source_name}}

    def _write_match_note(self, item_id: int, note: str) -> bool:
        """A note worth a person's attention when the resolved payload is weaker
        evidence than usual (Sprint 064). Never overwrites an owner's own note —
        the same rule every other fill in this handler already follows.

        Not independently undo-tracked: the entry this note lives on is itself a
        `create` effect of the import, so undoing the batch deletes the whole row,
        note included, in the common case. The one gap is an entry the owner has
        since edited (`undo.py`'s "retained" path), where a stale-but-still-true
        note would survive an undo — accepted rather than adding a second effect
        type for one edge case a fresh scan already treats as the owner's row.
        """
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            session = Session(bind=connection)
            try:
                entry = session.execute(
                    select(EntryRow).where(EntryRow.item_id == item_id, EntryRow.user_id == 1)
                ).scalar_one_or_none()
                if entry is None or entry.notes:
                    connection.rollback()
                    return False
                entry.notes = note
                entry.updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                session.flush()
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise
            finally:
                session.close()

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
    """Queue enrichment for persisted items a provider lookup could still improve.

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
    for item_id, kind, value in rows:
        repository.enqueue(
            batch_id, "enrich_item", {"item_id": item_id, "kind": kind, "value": value}
        )
    return len(rows)


def _backfillable_items(
    engine: Engine, item_ids: Collection[int] | None = None
) -> list[tuple[int, str, str]]:
    """Every item worth a lookup, asked once per enriching domain.

    One statement per domain rather than one across all of them, because all three
    halves of the question are the domain's own (DEC-067 row 3): which identifier the
    lookup is keyed on, and which missing metadata fields mean "still worth asking".
    Both were books' until Sprint 039 — the join said `kind = 'isbn'` and the
    incompleteness rule named `publisher`, `page_count` and `description`, which an
    anime has none of, so every anime would have looked incomplete for ever.

    A missing cover or year counts in every registered domain — as the
    `wants_cover`/`wants_year` declarations, which default to True rather than
    being constants, so a domain whose providers carry neither can opt out
    instead of being re-queued for ever (DEC-116).
    """
    rows: list[tuple[int, str, str]] = []
    for domain in DOMAINS.values():
        # A domain declares whether background enrichment applies at all. One
        # MusicBrainz release fetch already returns everything an album has, so there is
        # nothing for a job to fill — a simplification rather than a gap (DEC-052).
        spec = domain.enrichment
        if spec is None:
            continue
        claimed: set[int] = set()
        parameters: dict[str, Any] = {"type": domain.item_type}
        # The field names reach SQLite as *bound* `json_extract` paths rather than as
        # interpolated SQL, so a domain cannot spell its way into the statement.
        incomplete = []
        for index, field in enumerate(spec.completeness_fields):
            incomplete.append(f"json_extract(items.metadata, :path_{index}) IS NULL")
            parameters[f"path_{index}"] = f"$.{field}"
        # The cover and year conditions are the domain's declaration too, not a
        # constant: a domain whose providers carry no covers, or whose rows
        # legitimately carry no year, would otherwise be re-queued on every
        # backfill for ever (DEC-116). Both default to True, which is what every
        # registered domain means today.
        conditions = []
        if spec.wants_cover:
            conditions.append("items.cover_path IS NULL")
            conditions.append("items.cover_path = ''")
        if spec.wants_year:
            conditions.append("items.year IS NULL")
        # An item an import connector created and enrichment already filled
        # completely is still worth asking once more, for a reason none of the
        # domain's own declarations name: nothing ever recorded *which*
        # provider resolved it (DEC-130), so it can never be refreshed or have
        # a missing cover fetched again. Unconditional, and listed first, so a
        # domain declaring no cover/year interest and no completeness fields
        # never leaves this OR empty.
        conditions.insert(
            0, "NOT EXISTS (SELECT 1 FROM item_sources WHERE item_sources.item_id = items.id)"
        )
        scope = ""
        if item_ids is not None:
            # Bound and parameterised rather than interpolated.
            placeholders = ", ".join(f":item_{index}" for index, _ in enumerate(item_ids))
            scope = f"AND items.id IN ({placeholders})"
            parameters.update({f"item_{index}": value for index, value in enumerate(item_ids)})
        # One statement per declared key, in the domain's own order of preference. An
        # item reachable by several is queued once, under the first it actually has:
        # the alternative — one statement with `kind IN (…)` — cannot say which kind
        # the value it returned belongs to, and the handler needs both.
        for kind in spec.identity_kinds:
            with engine.connect() as connection:
                result = connection.execute(
                    text(
                        f"""
                    SELECT items.id AS item_id, MIN(ident.normalized_value) AS value
                    FROM items
                    JOIN item_identifiers AS ident
                      ON ident.item_id = items.id AND ident.kind = :kind
                    WHERE items.type = :type
                      AND (
                            {" OR ".join([*conditions, *incomplete])}
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
                    {**parameters, "kind": kind},
                )
                for row in result:
                    if row.item_id in claimed:
                        continue
                    claimed.add(row.item_id)
                    rows.append((row.item_id, kind, row.value))
    return sorted(rows)
