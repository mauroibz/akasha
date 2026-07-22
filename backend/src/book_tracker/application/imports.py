import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from book_tracker.application.library import LibraryError
from book_tracker.domain.calibre import CalibreAdapter
from book_tracker.domain.goodreads import parse_goodreads
from book_tracker.domain.identity import normalize_identifier
from book_tracker.domain.matching import MatchKind
from book_tracker.infrastructure.covers import CoverError, install_cover, prepare_uploaded_cover
from book_tracker.infrastructure.models import ImportBatchRow, ImportRecordRow
from book_tracker.infrastructure.repositories import DomainRepository, ImportRepository


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class GoodreadsImportService:
    def __init__(self, engine: Engine, data_dir: Path) -> None:
        self.engine = engine
        self.data_dir = data_dir
        self.domain = DomainRepository(engine)
        self.imports = ImportRepository(engine)

    def preview(self, data: bytes, filename: str) -> dict[str, Any]:
        fingerprint = hashlib.sha256(data).hexdigest()
        existing = self.imports.get_batch_by_fingerprint("goodreads", fingerprint)
        if existing is not None:
            return self.get_preview(existing)
        parsed = parse_goodreads(data)
        batch_id = str(uuid.uuid4())
        planned: list[dict[str, Any]] = []
        for payload in parsed:
            identifiers = [normalize_identifier("isbn", payload["isbn"])] if payload["isbn"] else []
            author = payload["authors"][0] if payload["authors"] else ""
            match = self.domain.match(
                identifiers=identifiers, title=payload["title"], first_author=author
            )
            if payload["errors"]:
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
                    **payload,
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
        }
        self.imports.create_preview(batch_id, fingerprint, filename, summary, planned)
        directory = self.data_dir / "imports" / batch_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "source.csv").write_bytes(data)
        return self.get_preview(batch_id)

    def get_preview(self, batch_id: str) -> dict[str, Any]:
        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None:
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
            records = []
            for row in rows:
                value = json.loads(row.normalized_payload)
                records.append(
                    {
                        "record_id": row.id,
                        **value,
                        "planned_action": row.planned_action,
                        "match_kind": row.match_kind,
                        "candidates": json.loads(row.conflicts).get("candidates", []),
                        "errors": json.loads(row.validation_errors),
                    }
                )
            return {
                "batch_id": batch.id,
                "fingerprint": batch.fingerprint,
                "state": batch.state,
                "summary": json.loads(batch.preview_summary),
                "records": records,
            }

    def commit(self, batch_id: str, choices: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
        return self.imports.commit(batch_id, choices)


class CalibreImportService:
    def __init__(self, engine: Engine, data_dir: Path, calibre_dir: Path) -> None:
        self.engine = engine
        self.data_dir = data_dir
        self.domain = DomainRepository(engine)
        self.imports = ImportRepository(engine)
        self.adapter = CalibreAdapter(calibre_dir)

    def get_preview(self, batch_id: str) -> dict[str, Any]:
        return GoodreadsImportService(self.engine, self.data_dir).get_preview(batch_id)

    def preview(self, library_path: str) -> dict[str, Any]:
        snapshot = self.adapter.read(library_path)
        existing = self.imports.get_batch_by_fingerprint("calibre", snapshot.fingerprint)
        if existing is not None:
            return self.get_preview(existing)
        batch_id = str(uuid.uuid4())
        directory = self.data_dir / "imports" / batch_id / "covers"
        directory.mkdir(parents=True, exist_ok=True)
        planned: list[dict[str, Any]] = []
        for payload in snapshot.records:
            source = payload.pop("cover_source")
            cover_staged = False
            cover_stage = None
            if source:
                try:
                    prepared = prepare_uploaded_cover(
                        Path(source).read_bytes(), "image/jpeg", self.data_dir
                    )
                    staged = directory / f"{payload['row_number']}.jpg"
                    prepared.replace(staged)
                    cover_stage = str(staged.relative_to(self.data_dir))
                    cover_staged = True
                except (CoverError, OSError):
                    pass
            identifiers = []
            if payload.get("isbn"):
                identifiers.append(normalize_identifier("isbn", payload["isbn"]))
            if payload.get("calibre_uuid"):
                identifiers.append(normalize_identifier("calibre_uuid", payload["calibre_uuid"]))
            match = self.domain.match(
                identifiers=identifiers,
                title=payload["title"],
                first_author=payload["authors"][0] if payload["authors"] else "",
            )
            if payload["errors"]:
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
                    **payload,
                    "cover_staged": cover_staged,
                    "cover_stage": cover_stage,
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
        }
        self.imports.create_preview(
            batch_id,
            snapshot.fingerprint,
            "metadata.db",
            summary,
            planned,
            kind="calibre",
            source_descriptor={"library_path": library_path},
        )
        return self.get_preview(batch_id)

    def commit(self, batch_id: str, choices: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
        result = self.imports.commit(batch_id, choices, kind="calibre")
        with Session(self.engine) as session:
            rows = list(
                session.scalars(select(ImportRecordRow).where(ImportRecordRow.batch_id == batch_id))
            )
            installs = [
                (row.matched_item_id, json.loads(row.normalized_payload).get("cover_stage"))
                for row in rows
                if row.matched_item_id
            ]
        for item_id, relative in installs:
            if not relative:
                continue
            staged = self.data_dir / relative
            if not staged.is_file():
                continue
            try:
                install_cover(staged, self.data_dir, item_id)
                self.domain.set_cover_path(item_id, f"covers/{item_id}.jpg")
            except CoverError:
                pass
        return result
