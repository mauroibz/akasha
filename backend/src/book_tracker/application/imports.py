import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from book_tracker.application.enrichment import enqueue_enrichment_backfill
from book_tracker.application.library import LibraryError, LibraryService, clean_attachment_filename
from book_tracker.domain.importers import (
    Importer,
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
        attachment_max_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self.engine = engine
        self.data_dir = data_dir
        self.source_root = source_root
        self.importer = importer
        #: The same per-file ceiling the manual `/batches/{id}/files` route enforces
        #: (DEC-083), applied here to a reader-staged attachment too: a source that
        #: already had the bytes on disk does not get a bigger allowance than one that
        #: needed a second upload.
        self.attachment_max_bytes = attachment_max_bytes
        #: The domains this connector declared, in declaration order. A batch has no
        #: one domain any more (DEC-106): each record resolves its own, and the first
        #: entry is what a record naming no type of its own becomes.
        self.domains = {item_type: DOMAINS[item_type] for item_type in importer.item_types}
        self.library = DomainRepository(engine)
        self.imports = ImportRepository(engine)

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
        """
        if set(targets) == set(self.domains):
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
                replace(record, entry=replace(record.entry, values=self._validate(record)))
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
        return self.get_preview(batch_id)

    def get_preview(self, batch_id: str) -> dict[str, Any]:
        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None or batch.kind != self.importer.name:
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
            return {
                "batch_id": batch.id,
                "fingerprint": batch.fingerprint,
                "state": batch.state,
                "summary": json.loads(batch.preview_summary),
                "records": [_preview_record(row) for row in rows],
            }

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
            if batch is None or batch.kind != self.importer.name:
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
        attachment = LibraryService(self.engine).record_attachment(
            item_id, filename=filename, sha256=sha256, byte_size=byte_size
        )
        with Session(self.engine) as session:
            record_id = session.scalar(
                select(ImportRecordRow.id).where(
                    ImportRecordRow.batch_id == batch_id,
                    ImportRecordRow.matched_item_id == item_id,
                )
            )
            existing = session.scalar(
                select(ImportEffectRow.effect_id).where(
                    ImportEffectRow.batch_id == batch_id,
                    ImportEffectRow.entity_type == "attachment",
                    ImportEffectRow.entity_id == str(attachment["id"]),
                )
            )
            if existing is None:
                session.add(
                    ImportEffectRow(
                        batch_id=batch_id,
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
