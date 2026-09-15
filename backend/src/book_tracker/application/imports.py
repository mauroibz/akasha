import json
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from book_tracker.application.enrichment import enqueue_enrichment_backfill
from book_tracker.application.library import LibraryError, LibraryService, clean_attachment_filename
from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.importers import (
    ImportEntry,
    Importer,
    ImportItem,
    ImportReadContext,
    ImportSnapshot,
    ImportSource,
    NormalizedImportRecord,
)
from book_tracker.domain.matching import MatchKind
from book_tracker.domain.registry import DOMAINS
from book_tracker.domain.spec import (
    Domain,
    InvalidEntryField,
    InvalidMetadata,
    InvalidProgress,
    InvalidStatus,
    validate_entry_values,
    validate_metadata_patch,
    validate_status,
)
from book_tracker.infrastructure.attachments import AttachmentError, store_blob
from book_tracker.infrastructure.covers import CoverError, install_cover
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.models import (
    ImportBatchRow,
    ImportEffectRow,
    ImportRecordRow,
)
from book_tracker.infrastructure.repositories import DomainRepository, ImportRepository


def batch_item_ids(engine: Engine, batch_id: str) -> list[int]:
    """The items this batch created or matched, and only those."""
    with Session(engine) as session:
        return [
            item_id
            for item_id in session.scalars(
                select(ImportRecordRow.matched_item_id)
                .where(
                    ImportRecordRow.batch_id == batch_id,
                    ImportRecordRow.matched_item_id.is_not(None),
                )
                .distinct()
            )
            if item_id is not None
        ]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _stored_record(record: NormalizedImportRecord) -> dict[str, Any]:
    return {
        "row_number": record.row_number,
        "item": {
            "title": record.item.title,
            "subtitle": record.item.subtitle,
            "year": record.item.year,
            "identifiers": dict(record.item.identifiers),
            "metadata": dict(record.item.metadata),
            "creator_sort": record.item.creator_sort,
        },
        "entry": {
            "score": record.entry.score,
            "notes": record.entry.notes,
            "date_added": record.entry.date_added,
            "values": dict(record.entry.values),
            "score_provisional": record.entry.score_provisional,
            "suggested_status": record.entry.suggested_status,
        },
        "shelves": list(record.shelves),
        "source_fields": dict(record.source_fields),
        # Which library this row lands in. Written at preview time because commit
        # never re-reads the source: the snapshot is the stable result (DEC-106).
        "item_type": record.item_type,
        "cover_stage": record.cover_stage,
        # Kept so a file arriving after the commit can be resolved back to the record
        # it belongs to, without the route knowing what any source looks like on disk.
        "source_files": list(record.source_files),
        # A reader that already had the bytes for one of `source_files` on disk (an
        # export bundle, never a folder upload) stages it here so commit can attach it
        # itself — no second upload the way `/batches/{id}/files` needs one.
        "attachment_stage": record.attachment_stage,
        "attachment_name": record.attachment_name,
    }


def _preview_record(row: ImportRecordRow) -> dict[str, Any]:
    payload = json.loads(row.normalized_payload)
    item = payload["item"]
    entry = payload["entry"]
    metadata = item["metadata"]
    identifiers = item["identifiers"]
    values = entry["values"]
    source_fields = payload.get("source_fields", {})
    return {
        "record_id": row.id,
        "row_number": payload["row_number"],
        "title": item["title"],
        "creators": metadata.get("creators", []),
        "suggested_status": entry.get("suggested_status"),
        "score": entry.get("score"),
        "score_provisional": bool(entry.get("score_provisional")),
        "shelves": payload.get("shelves", []),
        "errors": json.loads(row.validation_errors),
        "planned_action": row.planned_action,
        "match_kind": row.match_kind,
        "candidates": json.loads(row.conflicts).get("candidates", []),
        "item": item,
        "entry": entry,
        "source_fields": source_fields,
        "cover_staged": payload.get("cover_stage") is not None,
        "attachment_staged": payload.get("attachment_stage") is not None,
        "item_type": payload.get("item_type"),
        # Compatibility for the two readers that predate the neutral nested shape:
        # flatten what they actually supplied without naming any domain's fields here.
        **metadata,
        **identifiers,
        **values,
        **({"review": entry["notes"]} if entry.get("notes") is not None else {}),
        **source_fields,
    }


class ImportService:
    """The one preview/commit pipeline used by every registered importer."""

    def __init__(
        self,
        engine: Engine,
        data_dir: Path,
        source_root: Path,
        importer: Importer,
        *,
        user_id: int,
        attachment_max_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self.engine = engine
        self.data_dir = data_dir
        self.source_root = source_root
        self.importer = importer
        self.user_id = user_id
        #: The same per-file ceiling the manual `/batches/{id}/files` route enforces
        #: (DEC-083), applied here to a reader-staged attachment too: a source that
        #: already had the bytes on disk does not get a bigger allowance than one that
        #: needed a second upload.
        self.attachment_max_bytes = attachment_max_bytes
        #: The domains this connector declared, in declaration order. A batch has no
        #: one domain any more (DEC-106): each record resolves its own, and the first
        #: entry is what a record naming no type of its own becomes.
        self.domains = {item_type: DOMAINS[item_type] for item_type in importer.item_types}
        self.library = DomainRepository(engine, user_id)
        self.imports = ImportRepository(engine, user_id)

    def _domain_for(self, record: NormalizedImportRecord) -> Domain:
        """The domain this row targets, refusing one the connector never declared.

        A record naming an undeclared type is a defect in the connector, so it is
        refused at the same boundary and under the same code as an undeclared identity
        kind — rather than reaching the registry as a `KeyError` with a batch already
        staged behind it.
        """
        if record.item_type is None:
            return next(iter(self.domains.values()))
        domain = self.domains.get(record.item_type)
        if domain is None:
            raise LibraryError(
                "invalid_import_record",
                f"{self.importer.label} produced a record targeting {record.item_type!r}, "
                f"which it does not declare",
                status_code=422,
                details={"row_number": record.row_number},
            )
        return domain

    def _target_of(self, record: NormalizedImportRecord) -> str:
        """Which library this row is for, before it has been validated."""
        return record.item_type or next(iter(self.domains))

    def _validate(self, record: NormalizedImportRecord) -> dict[str, Any]:
        domain = self._domain_for(record)
        unknown_identities = set(record.item.identifiers) - self.importer.identity_kinds
        if unknown_identities:
            raise LibraryError(
                "invalid_import_record",
                f"{self.importer.label} produced undeclared identities "
                f"{sorted(unknown_identities)}",
                status_code=422,
                details={"row_number": record.row_number},
            )
        if not record.item.title.strip():
            raise LibraryError(
                "invalid_import_record",
                "An imported item requires a title",
                status_code=422,
                details={"row_number": record.row_number},
            )
        try:
            validate_metadata_patch(domain, record.item.metadata)
            entry_values = validate_entry_values(domain, record.entry.values)
            if record.entry.suggested_status is not None:
                validate_status(domain, record.entry.suggested_status)
        except (InvalidMetadata, InvalidEntryField, InvalidProgress, InvalidStatus) as error:
            raise LibraryError(
                "invalid_import_record",
                str(error),
                status_code=422,
                details={"row_number": record.row_number},
            ) from error
        return entry_values

    def chosen_targets(self, targets: Sequence[str] | None) -> tuple[str, ...]:
        """Which of this connector's domains this import is for.

        `None` is every one it declares, which is what the screen ticks by default and
        what a single-domain connector can only ever mean. An unknown or empty choice
        is refused here rather than silently narrowed, because an import that quietly
        brings in nothing is worse than one that says it cannot.
        """
        if targets is None:
            return tuple(self.domains)
        chosen = tuple(item_type for item_type in self.domains if item_type in set(targets))
        unknown = sorted(set(targets) - set(self.domains))
        if unknown or not chosen:
            raise LibraryError(
                "invalid_import_targets",
                f"{self.importer.label} does not import {unknown or 'nothing'}",
                status_code=422,
                details={"declared": list(self.domains)},
            )
        return chosen

    def _capped_attachment(self, record: NormalizedImportRecord) -> NormalizedImportRecord:
        """Drop a staged attachment over the cap, falling back to declare-only.

        The record still names the file in `source_files`, so an oversize embedded
        ebook is exactly as attachable afterwards, by hand, as one a folder upload
        never had bytes for in the first place.
        """
        assert record.attachment_stage is not None
        staged = self.data_dir / record.attachment_stage
        if staged.is_file() and staged.stat().st_size <= self.attachment_max_bytes:
            return record
        if staged.is_file():
            staged.unlink(missing_ok=True)
        return replace(record, attachment_stage=None, attachment_name=None)

    def _fingerprint(self, snapshot: ImportSnapshot, targets: Sequence[str]) -> str:
        """The identity of this import, which is the source *and* what was asked of it.

        Preview is idempotent on `(connector, fingerprint)`, so an export previewed as
        films and then as shows would otherwise return the first preview — a wrong
        answer that looks like a working feature (DEC-106).

        Composed only when a strict subset was chosen, which is what keeps every
        fingerprint already in the database resolving: a connector declaring one domain
        always selects all of it, so its sources fingerprint exactly as they always did
        and no batch staged before this contract is orphaned.

        A reader that consumed the target choice to interpret its source (Sprint
        084's list reader reads the chosen domain's column vocabulary, and its
        fingerprint already carries the choice) states so in its source
        descriptor: the reader's composition is the identity, and appending the
        subset again would only double it.
        """
        if set(targets) == set(self.domains):
            return snapshot.fingerprint
        descriptor = snapshot.source_descriptor or {}
        if descriptor.get("item_type") in targets:
            return snapshot.fingerprint
        return f"{snapshot.fingerprint}#{'+'.join(targets)}"

    def preview(self, source: ImportSource, targets: Sequence[str] | None = None) -> dict[str, Any]:
        chosen = self.chosen_targets(targets)
        snapshot = self.importer.read(source, ImportReadContext(path_root=self.source_root))
        fingerprint = self._fingerprint(snapshot, chosen)
        existing = self.imports.get_batch_by_fingerprint(self.importer.name, fingerprint)
        if existing is not None:
            return self.get_preview(existing)
        snapshot = replace(
            snapshot,
            records=tuple(
                replace(
                    record,
                    entry=replace(
                        record.entry,
                        values=self._validate(record) if not record.errors else record.entry.values,
                    ),
                )
                for record in snapshot.records
            ),
        )
        # The reader always emits every row it can parse and the service applies the
        # selection, so a connector cannot get the filter wrong and one rule covers
        # every connector present and future (DEC-106). Dropped before staging: an
        # unwanted row should cost no copied bytes.
        wanted = set(chosen)
        not_requested = [
            record for record in snapshot.records if self._target_of(record) not in wanted
        ]
        snapshot = replace(
            snapshot,
            records=tuple(
                record for record in snapshot.records if self._target_of(record) in wanted
            ),
        )

        batch_id = str(uuid.uuid4())
        directory = self.data_dir / "imports" / batch_id
        snapshot = self.importer.stage(snapshot, directory, self.data_dir)
        # A reader stages an attachment without knowing the cap that governs one
        # (`stage` owns no policy, only bytes it happens to have). Enforced once, here,
        # for every connector — the same cap the manual attach route applies, so a
        # source that already had the file on disk gets no larger an allowance.
        snapshot = replace(
            snapshot,
            records=tuple(
                self._capped_attachment(record) if record.attachment_stage else record
                for record in snapshot.records
            ),
        )
        planned: list[dict[str, Any]] = []
        for record in snapshot.records:
            match = self.importer.match(record, self.library)
            if record.errors:
                action = "error"
            elif match.kind is MatchKind.AMBIGUOUS:
                action = "ambiguous"
            elif match.kind is MatchKind.IDENTITY_CONFLICT:
                action = "identity_conflict"
            elif match.item_id is None:
                action = "create_item"
            else:
                action = "reuse_item"
            planned.append(
                {
                    **_stored_record(record),
                    "errors": list(record.errors),
                    "match_kind": match.kind.value,
                    "matched_item_id": match.item_id,
                    "candidates": list(match.candidates),
                    "planned_action": action,
                }
            )
        summary = {
            "total": len(planned),
            "ready": sum(row["planned_action"] in {"create_item", "reuse_item"} for row in planned),
            "errors": sum(
                row["planned_action"] in {"error", "identity_conflict"} for row in planned
            ),
            "ambiguous": sum(row["planned_action"] == "ambiguous" for row in planned),
            # Two different things get skipped and they are never conflated: a row for
            # a library the reader did not tick, and a row of a kind no library holds.
            # Neither is an error — somebody who exports their whole account should not
            # meet forty red rows for podcasts they once rated.
            "skipped_not_requested": len(not_requested),
            "skipped_unsupported": sum(skip.count for skip in snapshot.skipped),
            "skipped_reasons": [
                {"reason": skip.reason, "count": skip.count} for skip in snapshot.skipped
            ],
        }
        self.imports.create_preview(
            batch_id,
            fingerprint,
            snapshot.filename,
            summary,
            planned,
            kind=self.importer.name,
            source_descriptor=snapshot.source_descriptor,
        )
        # A connector whose rows need provider search before they can be decided
        # (Sprint 083 D3) stages its batch in `matching` and enqueues one search
        # job; commit refuses until the job flips the batch back to `previewed`.
        # Reached by the connector's declaration, the same opt-in shape as
        # `browsable`/`incremental` — the shared pipeline never branches on
        # which connector it is holding.
        searching = getattr(self.importer, "search_job", None)
        if searching == "search_import_rows":
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE import_batches SET state = 'matching', updated_at = :now"
                        " WHERE id = :id"
                    ),
                    {"now": _now_iso(), "id": batch_id},
                )
            JobRepository(self.engine).enqueue(
                batch_id,
                "search_import_rows",
                {"batch_id": batch_id},
                user_id=self.user_id,
            )
        return self.get_preview(batch_id)

    def get_preview(self, batch_id: str) -> dict[str, Any]:
        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None or batch.user_id != self.user_id or batch.kind != self.importer.name:
                raise LibraryError(
                    "import_batch_not_found", "Import preview was not found", status_code=404
                )
            rows = list(
                session.scalars(
                    select(ImportRecordRow)
                    .where(ImportRecordRow.batch_id == batch_id)
                    .order_by(ImportRecordRow.row_number)
                )
            )
        # Proposals ride along when the connector's search job has produced
        # them; a connector with no proposal store reads exactly as it always
        # did, because the per-record list is empty and the summary counts
        # default to zero (Sprint 083 D2.3).
        proposals = self.imports.proposals_for_batch(batch_id)
        proposals_by_record: dict[int, list[dict[str, Any]]] = {}
        for proposal in proposals:
            proposals_by_record.setdefault(proposal["record_id"], []).append(
                {
                    "source": proposal["source"],
                    "source_id": proposal["source_id"],
                    "payload": proposal["payload"],
                    "rank": proposal["rank"],
                    "chosen": proposal["chosen"],
                }
            )
        records = []
        for row in rows:
            record = _preview_record(row)
            record["proposals"] = proposals_by_record.get(record["record_id"], [])
            records.append(record)
        summary = json.loads(batch.preview_summary)
        if proposals:
            summary.setdefault("rows_with_proposals", len(proposals_by_record))
            summary.setdefault("proposals_total", len(proposals))
        else:
            summary.setdefault("rows_with_proposals", 0)
            summary.setdefault("proposals_total", 0)
        # A batch still in its matching phase carries its search job's live
        # progress, so the screen polls one endpoint — the idempotent preview
        # GET — and reads the same counts the job route would give (Sprint
        # 083 D3.2). Absent for every connector without a search phase.
        search_progress: dict[str, Any] | None = None
        if batch.state == "matching":
            jobs = JobRepository(self.engine).list_batch_jobs(batch_id)
            for job in jobs:
                if job["kind"] == "search_import_rows" and job["state"] in (
                    "queued",
                    "running",
                ):
                    progress = dict(job["progress"])
                    progress["job_state"] = job["state"]
                    if job.get("error_code"):
                        progress["wait_reason"] = job["error_code"]
                    search_progress = progress
                    break
        return {
            "batch_id": batch.id,
            "fingerprint": batch.fingerprint,
            "state": batch.state,
            "summary": summary,
            "records": records,
            **({"search_progress": search_progress} if search_progress else {}),
        }

    async def answer_proposal(
        self,
        batch_id: str,
        record_id: int,
        *,
        source: str | None = None,
        source_id: str | None = None,
        discard: bool = False,
        fetch_cover: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> dict[str, Any]:
        """Record the owner's answer to a row's proposals (Sprint 083 D4).

        Confirming re-stages the record's item half from the proposal's payload —
        title, creators, identifiers, year and metadata from the provider — and
        recomputes `planned_action` against the library, so **commit needs no new
        path**: exact identity may now resolve `reuse_item`, and the per-row
        domain validation applies exactly as it did at preview. The entry half is
        the owner's own and never touched: score, notes and the triage suggestion
        stay what the spreadsheet said.

        Discarding marks every proposal of the record not-chosen: none of these
        is the book, and the row stays importable exactly as typed.

        Both require the batch to have drained (`previewed`): answering a row
        while its searches are still running would race the job rewriting the
        same record's proposals.
        """
        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None or batch.user_id != self.user_id or batch.kind != self.importer.name:
                raise LibraryError(
                    "import_batch_not_found", "Import preview was not found", status_code=404
                )
            if batch.state == "matching":
                raise LibraryError(
                    "import_batch_not_committable",
                    "This import is still searching; answer its rows once the search finishes",
                    status_code=409,
                )
            if batch.state != "previewed":
                raise LibraryError(
                    "import_batch_not_committable",
                    f"Import batch is {batch.state}, so it takes no answers",
                    status_code=409,
                )
            record = session.get(ImportRecordRow, record_id)
            if record is None or record.batch_id != batch_id or record.user_id != self.user_id:
                raise LibraryError(
                    "import_record_not_found", "Import row was not found", status_code=404
                )

        if discard:
            self.imports.discard_proposals(batch_id, record_id)
            # The final answer governs: an owner who confirmed and then
            # reconsidered gets the typed row back, exactly as the spreadsheet
            # wrote it — no provider identity, metadata or year riding along on
            # a "none of these is the book" row. Rows that were never answered
            # keep the item half the reader gave them.
            with Session(self.engine) as session:
                record = session.get(ImportRecordRow, record_id)
                assert record is not None
                stored = json.loads(record.normalized_payload)
                typed = stored.pop("typed_item", None)
                if typed is not None:
                    stored["item"] = typed
                    # The staged cover belonged to the confirmation this
                    # discard reverses — it drops with the rest of the
                    # provider data, so no orphan cover rides a typed row.
                    stored["cover_stage"] = None
                    record.normalized_payload = json.dumps(stored, ensure_ascii=False)
                    session.commit()
            if typed is not None:
                # The restored row re-plans through the connector's own match,
                # the same rule preview applied — never a hard-coded action, so
                # a future search-then-confirm connector with its own matching
                # keeps working without this service knowing it.
                with Session(self.engine) as session:
                    record = session.get(ImportRecordRow, record_id)
                    assert record is not None
                    stored = json.loads(record.normalized_payload)
                    normalized = NormalizedImportRecord(
                        row_number=stored["row_number"],
                        item=ImportItem(
                            title=stored["item"]["title"],
                            subtitle=stored["item"].get("subtitle"),
                            year=stored["item"].get("year"),
                            identifiers=stored["item"].get("identifiers") or {},
                            metadata=stored["item"].get("metadata") or {},
                            creator_sort=stored["item"].get("creator_sort"),
                        ),
                        entry=ImportEntry(
                            score=stored["entry"].get("score"),
                            notes=stored["entry"].get("notes"),
                            date_added=stored["entry"].get("date_added"),
                            values=stored["entry"].get("values") or {},
                            score_provisional=bool(stored["entry"].get("score_provisional")),
                            suggested_status=stored["entry"].get("suggested_status"),
                        ),
                        shelves=tuple(stored.get("shelves", ())),
                        errors=json.loads(record.validation_errors or "[]")
                        if isinstance(record.validation_errors, str)
                        else (),
                        source_fields=stored.get("source_fields") or {},
                        item_type=stored.get("item_type"),
                    )
                    match = self.importer.match(normalized, self.library)
                    if match.kind is MatchKind.AMBIGUOUS:
                        record.planned_action = "ambiguous"
                        record.conflicts = json.dumps({"candidates": list(match.candidates)})
                    elif match.kind is MatchKind.IDENTITY_CONFLICT:
                        record.planned_action = "identity_conflict"
                    else:
                        record.planned_action = (
                            "reuse_item" if match.item_id is not None else "create_item"
                        )
                    record.match_kind = match.kind.value
                    record.matched_item_id = match.item_id
                    session.commit()
        else:
            assert source is not None and source_id is not None
            self.imports.choose_proposal(
                batch_id, record_id, proposal_source=source, proposal_source_id=source_id
            )
            chosen = self.imports.chosen_proposal(batch_id, record_id)
            assert chosen is not None
            payload = chosen["payload"]
            # The cover the owner saw on the card: fetched here, after the
            # answer is recorded, so a refused batch never spends the fetch.
            # A failed fetch means no stage, never a refused confirmation —
            # the same never-fatal rule the add path applies.
            staged_cover: str | None = None
            cover_url = str(payload.get("cover_url") or "")
            if fetch_cover is not None and cover_url:
                staged_cover = await fetch_cover(cover_url)
            with Session(self.engine) as session:
                record = session.get(ImportRecordRow, record_id)
                assert record is not None
                stored = json.loads(record.normalized_payload)
                # What the spreadsheet said, stashed so the discard that
                # reverses this confirmation can put it back — the entry half
                # is the owner's own and never staged from a proposal.
                stored["typed_item"] = stored["item"]
                stored["item"] = {
                    "title": payload.get("title") or stored["item"]["title"],
                    "subtitle": payload.get("subtitle"),
                    "year": payload.get("year"),
                    "identifiers": dict(payload.get("identifiers") or {}),
                    "metadata": dict(payload.get("metadata") or {}),
                    "creator_sort": None,
                }
                # The identity the owner confirmed is storage, not matching
                # evidence: commit takes it onto the item through the confirmed
                # channel, bypassing the connector's empty identity declaration
                # (which governs what the *reader* trusts, D1.6). Normalized
                # through the same identity rule the add path applies, so the
                # stored kind is the canonical one (`isbn`, never a raw provider
                # key like `isbn13`) — the enrichment join and the library's
                # exact-identity match key on the canonical kind, and a raw key
                # would leave the confirmed row coverless and unmatchable
                # forever.
                confirmed: dict[str, str] = {}
                for kind, value in (payload.get("identifiers") or {}).items():
                    try:
                        identifier = normalize_identifier(kind, str(value))
                    except InvalidIdentifier:
                        continue
                    confirmed[identifier.kind] = identifier.normalized_value
                stored["item"]["identifiers"] = dict(confirmed)
                stored["item"]["confirmed_identifiers"] = dict(confirmed)
                if payload.get("creators"):
                    stored["item"]["metadata"]["creators"] = list(payload["creators"])
                if payload.get("language"):
                    stored["item"]["metadata"]["language"] = payload["language"]
                # The cover the owner saw on the confirmed card rides the same
                # staged-cover channel every other connector uses (Sprint 084:
                # books only got covers because the isbn-keyd backfill caught
                # them; a MusicBrainz album carries no identifiers at all, so
                # enrichment can never be the only cover channel). The route
                # fetched it before this call — a failed fetch is a missing
                # stage, never a refused confirmation.
                if staged_cover is not None:
                    stored["cover_stage"] = staged_cover
                    # Undo's attachment sweep keys on the stage dir; the cover
                    # stage lives beside the reader's staged bytes.
                record.normalized_payload = json.dumps(stored, ensure_ascii=False)
                session.commit()

            # planned_action recomputes against the library, the same way preview
            # computed it: an exact identity may now match an existing item.
            with Session(self.engine) as session:
                record = session.get(ImportRecordRow, record_id)
                assert record is not None
                stored = json.loads(record.normalized_payload)
                identifiers = [
                    normalize_identifier(kind, value)
                    for kind, value in stored["item"]["identifiers"].items()
                    if kind in self.importer.identity_kinds
                ]
                creators = stored["item"]["metadata"].get("creators", [])
                first_creator = str(creators[0]) if isinstance(creators, list) and creators else ""
                match = self.library.match(
                    identifiers=identifiers,
                    title=stored["item"]["title"],
                    first_author=first_creator,
                )
                if record.planned_action not in {"error", "identity_conflict"}:
                    if match.kind is MatchKind.AMBIGUOUS:
                        record.planned_action = "ambiguous"
                        record.conflicts = json.dumps({"candidates": list(match.candidates)})
                    elif match.kind is MatchKind.IDENTITY_CONFLICT:
                        record.planned_action = "identity_conflict"
                    else:
                        record.planned_action = (
                            "reuse_item" if match.item_id is not None else "create_item"
                        )
                    record.match_kind = match.kind.value
                    record.matched_item_id = match.item_id
                    session.commit()

        return self.get_preview(batch_id)

    def _recompute_summary(self, batch_id: str) -> None:
        """Recount the batch's summary from the live rows.

        Every owner answer that changes a row's fate (an exclusion, a restore)
        changes what the summary must say; the preview read serves the stored
        JSON, so the counts drift unless they are rewritten here.
        """
        with Session(self.engine) as session:
            rows = list(
                session.scalars(select(ImportRecordRow).where(ImportRecordRow.batch_id == batch_id))
            )
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None:
                return
            summary = json.loads(batch.preview_summary)
            summary["ready"] = sum(
                row.planned_action in {"create_item", "reuse_item"} for row in rows
            )
            summary["errors"] = sum(
                row.planned_action in {"error", "identity_conflict"} for row in rows
            )
            summary["ambiguous"] = sum(row.planned_action == "ambiguous" for row in rows)
            batch.preview_summary = json.dumps(summary, ensure_ascii=False)
            session.commit()

    def exclude_row(self, batch_id: str, record_id: int) -> dict[str, Any]:
        """Keep this row out of the commit entirely (the owner's 2026-09-14
        decision: 'none of these is the book' must not force a keep).

        The row's `planned_action` becomes `excluded` — the same skip set
        commit already applies to reader-error rows, so commit needs no new
        path — and the summary recounts so the commit gate tells the truth.
        """
        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None or batch.user_id != self.user_id or batch.kind != self.importer.name:
                raise LibraryError(
                    "import_batch_not_found", "Import preview was not found", status_code=404
                )
            if batch.state != "previewed":
                raise LibraryError(
                    "import_batch_not_committable",
                    "This import is still searching; answer its rows once the search finishes",
                    status_code=409,
                )
            record = session.get(ImportRecordRow, record_id)
            if record is None or record.batch_id != batch_id or record.user_id != self.user_id:
                raise LibraryError(
                    "import_record_not_found", "Import row was not found", status_code=404
                )
            if record.planned_action in {"error", "identity_conflict"}:
                # Nothing to exclude: the row already lands nowhere.
                pass
            else:
                record.planned_action = "excluded"
                session.commit()
        self._recompute_summary(batch_id)
        return self.get_preview(batch_id)

    def include_row(self, batch_id: str, record_id: int) -> dict[str, Any]:
        """Undo an exclusion: the row returns to whatever preview planned for
        it, recomputed through the connector's own match exactly as preview
        did (never a hard-coded action)."""
        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None or batch.user_id != self.user_id or batch.kind != self.importer.name:
                raise LibraryError(
                    "import_batch_not_found", "Import preview was not found", status_code=404
                )
            if batch.state != "previewed":
                raise LibraryError(
                    "import_batch_not_committable",
                    "This import is still searching; answer its rows once the search finishes",
                    status_code=409,
                )
            record = session.get(ImportRecordRow, record_id)
            if record is None or record.batch_id != batch_id or record.user_id != self.user_id:
                raise LibraryError(
                    "import_record_not_found", "Import row was not found", status_code=404
                )
            if record.planned_action != "excluded":
                pass  # already included; idempotent
            else:
                stored = json.loads(record.normalized_payload)
                typed = stored.pop("typed_item", None)
                if typed is not None:
                    stored["item"] = typed
                    record.normalized_payload = json.dumps(stored, ensure_ascii=False)
                    session.commit()
                self._replan_record(record_id)
        self._recompute_summary(batch_id)
        return self.get_preview(batch_id)

    def _replan_record(self, record_id: int) -> None:
        """Recompute one record's planned action through the connector's own
        match — the same rule preview and the discard path apply. Takes the
        row's id rather than an instance: callers hold records detached from
        closed sessions."""
        with Session(self.engine) as session:
            record = session.get(ImportRecordRow, record_id)
            assert record is not None
            stored = json.loads(record.normalized_payload)
            normalized = NormalizedImportRecord(
                row_number=stored["row_number"],
                item=ImportItem(
                    title=stored["item"]["title"],
                    subtitle=stored["item"].get("subtitle"),
                    year=stored["item"].get("year"),
                    identifiers=stored["item"].get("identifiers") or {},
                    metadata=stored["item"].get("metadata") or {},
                    creator_sort=stored["item"].get("creator_sort"),
                ),
                entry=ImportEntry(
                    score=stored["entry"].get("score"),
                    notes=stored["entry"].get("notes"),
                    date_added=stored["entry"].get("date_added"),
                    values=stored["entry"].get("values") or {},
                    score_provisional=bool(stored["entry"].get("score_provisional")),
                    suggested_status=stored["entry"].get("suggested_status"),
                ),
                shelves=tuple(stored.get("shelves", ())),
                errors=json.loads(record.validation_errors or "[]")
                if isinstance(record.validation_errors, str)
                else (),
                source_fields=stored.get("source_fields") or {},
                item_type=stored.get("item_type"),
            )
            match = self.importer.match(normalized, self.library)
            if match.kind is MatchKind.AMBIGUOUS:
                record.planned_action = "ambiguous"
                record.conflicts = json.dumps({"candidates": list(match.candidates)})
            elif match.kind is MatchKind.IDENTITY_CONFLICT:
                record.planned_action = "identity_conflict"
            else:
                record.planned_action = "reuse_item" if match.item_id is not None else "create_item"
            record.match_kind = match.kind.value
            record.matched_item_id = match.item_id
            session.commit()

    async def research_row(
        self,
        batch_id: str,
        record_id: int,
        *,
        title: str | None = None,
        author: str | None = None,
        providers: Mapping[str, Any],
        quota: Any = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Edit a row's title/author and search it again (the owner's
        2026-09-14 decision: available on any row, not only empty ones — a
        bad query can also produce wrong proposals).

        The typed row is re-staged with the edited text (the spreadsheet's
        own cells stay untouched in `source_fields`), its proposals are
        replaced with fresh results, and any earlier answer is cleared: a
        re-search asks a different question, so an old confirmation must not
        survive it. Interactive-shaped (DEC-045): the spend is recorded but
        never blocks, because a person is waiting on the answer.
        """
        from book_tracker.application.import_search import TOP_N, search_row
        from book_tracker.domain.registry import DOMAINS as _DOMAINS

        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None or batch.user_id != self.user_id or batch.kind != self.importer.name:
                raise LibraryError(
                    "import_batch_not_found", "Import preview was not found", status_code=404
                )
            if batch.state == "matching":
                raise LibraryError(
                    "import_batch_not_committable",
                    "This import is still searching; wait for it to finish"
                    " before re-searching a row",
                    status_code=409,
                )
            if batch.state != "previewed":
                raise LibraryError(
                    "import_batch_not_committable",
                    f"Import batch is {batch.state}, so it takes no re-search",
                    status_code=409,
                )
            record = session.get(ImportRecordRow, record_id)
            if record is None or record.batch_id != batch_id or record.user_id != self.user_id:
                raise LibraryError(
                    "import_record_not_found", "Import row was not found", status_code=404
                )
            stored = json.loads(record.normalized_payload)
            new_title = (title if title is not None else stored["item"]["title"]).strip()
            new_author = (author if author is not None else "").strip() or str(
                (stored["item"].get("metadata") or {}).get("creators") or [""]
            )[0]
            if not new_title:
                raise LibraryError(
                    "invalid_import_record",
                    "A row needs a title to search for",
                    status_code=422,
                )
            # The edited text is the row's own now; the spreadsheet's cell
            # stays in source_fields, which the preview already shows.
            stored["item"]["title"] = new_title
            stored["item"]["metadata"] = {
                **(stored["item"].get("metadata") or {}),
                "creators": [new_author] if new_author else [],
            }
            stored.pop("typed_item", None)
            stored["item"].pop("confirmed_identifiers", None)
            record.normalized_payload = json.dumps(stored, ensure_ascii=False)
            session.commit()

        # Re-read the persisted row outside the write session (the record
        # object above is detached once the session closes).
        with Session(self.engine) as session:
            current = session.get(ImportRecordRow, record_id)
            assert current is not None
            stored = json.loads(current.normalized_payload)
            query_title = stored["item"]["title"]
            query_author = (stored["item"].get("metadata") or {}).get("creators") or [""]
        item_type = stored.get("item_type") or self.importer.item_types[0]
        domain = _DOMAINS.get(item_type)
        if domain is None:
            raise LibraryError(
                "invalid_import_record",
                f"A row naming {item_type!r} cannot be searched",
                status_code=422,
            )
        query = " ".join(part for part in (query_title, str(query_author[0])) if part)
        candidates = await search_row(
            query,
            providers=list(providers.values()),
            domain=domain,
            quota=quota,
            now=now or datetime.now(UTC),
            budgeted=False,
        )
        from book_tracker.application.import_search import _proposal_payload

        self.imports.add_proposals(
            batch_id=batch_id,
            record_id=record_id,
            proposals=tuple(
                _proposal_payload(candidate, rank)
                for rank, candidate in enumerate(candidates[:TOP_N])
            ),
        )
        # A re-search asks a different question: any earlier answer is gone.
        self._replan_record(record_id)
        self._recompute_summary(batch_id)
        return self.get_preview(batch_id)

    def resolve_file(self, batch_id: str, path: str, *, now: datetime | None = None) -> int:
        """Which committed item a file offered under `path` belongs to.

        Asked **before** a byte is read, so an upload nothing wants costs a round trip
        rather than a whole ebook. The batch has to be committed and still inside its
        undo window: a file attached to a batch that can no longer be reversed would be
        a row the ledger cannot claim.
        """
        moment = (now or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None or batch.user_id != self.user_id or batch.kind != self.importer.name:
                raise LibraryError(
                    "import_batch_not_found", "Import batch was not found", status_code=404
                )
            if batch.state != "committed":
                raise LibraryError(
                    "import_batch_not_committed",
                    f"Import batch is {batch.state}, so it takes no files",
                    status_code=409,
                )
            if batch.undo_expires_at is not None and moment > batch.undo_expires_at:
                raise LibraryError(
                    "import_batch_not_committed",
                    "Import batch is closed, so it takes no files",
                    status_code=409,
                )
            for row in session.scalars(
                select(ImportRecordRow).where(
                    ImportRecordRow.batch_id == batch_id,
                    ImportRecordRow.matched_item_id.is_not(None),
                )
            ):
                if path in json.loads(row.normalized_payload).get("source_files", []):
                    assert row.matched_item_id is not None
                    return row.matched_item_id
        raise LibraryError(
            "import_file_not_wanted",
            "No record in this import claims that file",
            status_code=404,
        )

    def record_file(
        self, batch_id: str, item_id: int, *, filename: str, sha256: str, byte_size: int
    ) -> dict[str, Any]:
        """Attach a stored blob to an item and tell the ledger the import did it.

        The row is written before the effect on purpose. A crash between the two leaves
        an attachment the ledger does not claim, which undo then treats as the owner's
        and **retains** — the safe direction. The other order would let undo delete a
        file it never put there.
        """
        attachment = LibraryService(self.engine, self.user_id).record_attachment(
            item_id, filename=filename, sha256=sha256, byte_size=byte_size
        )
        with Session(self.engine) as session:
            record_id = session.scalar(
                select(ImportRecordRow.id).where(
                    ImportRecordRow.batch_id == batch_id,
                    ImportRecordRow.user_id == self.user_id,
                    ImportRecordRow.matched_item_id == item_id,
                )
            )
            existing = session.scalar(
                select(ImportEffectRow.effect_id).where(
                    ImportEffectRow.batch_id == batch_id,
                    ImportEffectRow.user_id == self.user_id,
                    ImportEffectRow.entity_type == "attachment",
                    ImportEffectRow.entity_id == str(attachment["id"]),
                )
            )
            if existing is None:
                session.add(
                    ImportEffectRow(
                        batch_id=batch_id,
                        user_id=self.user_id,
                        record_id=record_id,
                        effect_type="create",
                        entity_type="attachment",
                        entity_id=str(attachment["id"]),
                        before_values="{}",
                        after_values=json.dumps(
                            {
                                "created": True,
                                "item_id": item_id,
                                "filename": filename,
                                "sha256": sha256,
                            }
                        ),
                    )
                )
                session.commit()
        return attachment

    def commit(self, batch_id: str, choices: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
        result = self.imports.commit(
            batch_id,
            choices,
            kind=self.importer.name,
            domains=self.domains,
            identity_kinds=self.importer.identity_kinds,
        )
        with Session(self.engine) as session:
            rows = list(
                session.scalars(select(ImportRecordRow).where(ImportRecordRow.batch_id == batch_id))
            )
            installs = [
                (
                    row.matched_item_id,
                    json.loads(row.normalized_payload).get("cover_stage"),
                    json.loads(row.normalized_payload).get("attachment_stage"),
                    json.loads(row.normalized_payload).get("attachment_name"),
                )
                for row in rows
                if row.matched_item_id
            ]
        for item_id, cover_relative, attachment_relative, attachment_name in installs:
            if cover_relative:
                staged = self.data_dir / cover_relative
                if staged.is_file():
                    try:
                        install_cover(staged, self.data_dir, item_id)
                        self.library.set_cover_path(item_id, f"covers/{item_id}.jpg")
                    except CoverError:
                        pass
            if attachment_relative and attachment_name:
                staged = self.data_dir / attachment_relative
                if staged.is_file():
                    # Already capped in `preview` (`_capped_attachment`), so this is
                    # bounded by the same small ceiling every manual attachment is —
                    # never the size of the export the bytes came from.
                    try:
                        stored = store_blob(staged.read_bytes(), self.data_dir)
                    except AttachmentError:
                        stored = None
                    if stored is not None:
                        self.record_file(
                            batch_id,
                            item_id,
                            filename=clean_attachment_filename(PurePosixPath(attachment_name).name)
                            or "attachment",
                            sha256=stored.sha256,
                            byte_size=stored.byte_size,
                        )
                    staged.unlink(missing_ok=True)
        # Any domain this connector can produce, rather than the one it happened to
        # declare first: a mixed batch has no single domain to ask, and asking the
        # wrong one would silently skip half the library's backfill.
        if any(domain.enriches for domain in self.domains.values()):
            enqueue_enrichment_backfill(
                self.engine,
                batch_id=batch_id,
                item_ids=batch_item_ids(self.engine, batch_id),
            )
        return result
