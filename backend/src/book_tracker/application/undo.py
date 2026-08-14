"""Safe import-effect undo with 24-hour window and field-matching semantics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.models import (
    AttachmentRow,
    EntryRow,
    ImportBatchRow,
    ImportEffectRow,
    ItemRow,
)


class UndoExpiredError(Exception):
    """Raised when undo is attempted after the 24-hour window has passed."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


class UndoService:
    """Reverses import effects safely.

    Rules (DEC-009, technical spec 6.5):
    - Reverse effects in effect_id descending order (last effect first).
    - Delete only batch-created entities that remain unmodified and unreferenced.
    - Revert a filled field only if the current value still matches the recorded after-value.
    - Cancel all queued/running jobs for the batch atomically.
    - Repeated undo is harmless (second call is a no-op).
    - Undo is available only within the 24-hour window.
    """

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.repo = JobRepository(engine)

    def undo(self, batch_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        if now is None:
            now = datetime.now(UTC)
        now_iso = now.isoformat().replace("+00:00", "Z")

        with Session(self.engine) as session:
            batch = session.get(ImportBatchRow, batch_id)
            if batch is None:
                raise LookupError(batch_id)
            if batch.state == "undone":
                return {
                    "batch_id": batch_id,
                    "state": "undone",
                    "reverted": 0,
                    "retained": 0,
                    "skipped": 1,
                    "reverted_entries": 0,
                    "reverted_items": 0,
                    "retained_items": 0,
                }
            if batch.state != "committed":
                raise ValueError(f"batch_not_committable:{batch.state}")
            # Check undo window
            expires = batch.undo_expires_at
            if expires is not None and now_iso > expires:
                raise UndoExpiredError(batch_id)

        # Cancel all batch jobs atomically with undo
        self.repo.cancel_batch_jobs(batch_id)

        reverted = 0
        retained = 0
        skipped = 0
        reverted_entries = 0
        reverted_items = 0
        retained_items = 0

        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            session = Session(bind=connection)
            try:
                # Get all effects for this batch in reverse order
                effects = list(
                    session.scalars(
                        select(ImportEffectRow)
                        .where(ImportEffectRow.batch_id == batch_id)
                        .order_by(ImportEffectRow.effect_id.desc())
                    )
                )

                # Track which entities we've already processed (each entity
                # may have multiple effects — create + fill_empty)
                seen_entries: set[int] = set()
                seen_items: set[int] = set()
                # Items that had a fill_empty effect where the current value
                # didn't match the after_value — user edited after import.
                # These items must not be deleted by their create effect.
                modified_items: set[int] = set()

                for effect in effects:
                    if effect.effect_type == "create":
                        if effect.entity_type == "entry":
                            entry_id = int(effect.entity_id)
                            if entry_id in seen_entries:
                                continue
                            seen_entries.add(entry_id)
                            entry = session.get(EntryRow, entry_id)
                            if entry is None:
                                skipped += 1
                                continue
                            after = json.loads(effect.after_values)
                            if after.get("created"):
                                # Entry was created by this batch — delete it
                                # (entry_shelves cascade on delete)
                                session.delete(entry)
                                reverted += 1
                                reverted_entries += 1
                        elif effect.entity_type == "item":
                            item_id = int(effect.entity_id)
                            if item_id in seen_items:
                                continue
                            seen_items.add(item_id)
                            # Don't delete if user modified any fill_empty field
                            if item_id in modified_items:
                                retained += 1
                                retained_items += 1
                                continue
                            item = session.get(ItemRow, item_id)
                            if item is None:
                                skipped += 1
                                continue
                            # An attached file is a deliberate act by the owner, not
                            # something the import put there, so it keeps its item
                            # alive exactly the way a hand-edited field does
                            # (DEC-047). Without this, undoing an import silently
                            # destroys an uploaded epub.
                            attachments = session.scalar(
                                select(func.count())
                                .select_from(AttachmentRow)
                                .where(AttachmentRow.item_id == item_id)
                            )
                            if attachments:
                                retained += 1
                                retained_items += 1
                                continue
                            # Check if item is referenced by other entries
                            other_entries = session.scalar(
                                select(func.count())
                                .select_from(EntryRow)
                                .where(EntryRow.item_id == item_id)
                            )
                            if other_entries is not None and other_entries == 0:
                                session.delete(item)
                                reverted += 1
                                reverted_items += 1
                            else:
                                retained += 1
                                retained_items += 1
                        elif effect.entity_type == "shelf":
                            # Shelves: delete if no other entries reference them
                            shelf_id = int(effect.entity_id)
                            shelf_result = session.execute(
                                text("SELECT count(*) FROM entry_shelves WHERE shelf_id=:sid"),
                                {"sid": shelf_id},
                            ).scalar()
                            if shelf_result is not None and shelf_result == 0:
                                session.execute(
                                    text("DELETE FROM shelves WHERE id=:sid"),
                                    {"sid": shelf_id},
                                )
                                reverted += 1

                    elif effect.effect_type == "fill_empty":
                        entity_id_str = effect.entity_id
                        after = json.loads(effect.after_values)
                        before = json.loads(effect.before_values)

                        if effect.entity_type == "item":
                            item_id = int(entity_id_str)
                            if item_id in seen_items:
                                # Already processed as create — skip fill revert
                                continue
                            item = session.get(ItemRow, item_id)
                            if item is None:
                                skipped += 1
                                continue
                            for field, imported_value in after.items():
                                current_value = _get_item_field(item, field)
                                if _values_equal(current_value, imported_value):
                                    # Current value still matches — revert to before
                                    _set_item_field(item, field, before.get(field))
                                    reverted += 1
                                else:
                                    # User edited after import — retain
                                    retained += 1
                                    modified_items.add(item_id)

                        elif effect.entity_type == "item_identifier":
                            # item_identifier entity_id format: "item_id:kind:value"
                            parts = entity_id_str.split(":")
                            if len(parts) >= 3:
                                item_id = int(parts[0])
                                kind = parts[1]
                                value = ":".join(parts[2:])
                                # Check if this identifier still exists
                                exists = session.execute(
                                    text(
                                        "SELECT count(*) FROM item_identifiers "
                                        "WHERE item_id=:iid AND kind=:kind "
                                        "AND normalized_value=:val"
                                    ),
                                    {"iid": item_id, "kind": kind, "val": value},
                                ).scalar()
                                if exists is not None and exists > 0:
                                    session.execute(
                                        text(
                                            "DELETE FROM item_identifiers "
                                            "WHERE item_id=:iid AND kind=:kind "
                                            "AND normalized_value=:val"
                                        ),
                                        {"iid": item_id, "kind": kind, "val": value},
                                    )
                                    reverted += 1
                                else:
                                    skipped += 1

                        elif effect.entity_type == "entry_shelf":
                            # entity_id format: "entry_id:shelf_id"
                            parts = entity_id_str.split(":")
                            if len(parts) == 2:
                                entry_id = int(parts[0])
                                shelf_id = int(parts[1])
                                exists = session.execute(
                                    text(
                                        "SELECT count(*) FROM entry_shelves "
                                        "WHERE entry_id=:eid AND shelf_id=:sid"
                                    ),
                                    {"eid": entry_id, "sid": shelf_id},
                                ).scalar()
                                if exists is not None and exists > 0:
                                    session.execute(
                                        text(
                                            "DELETE FROM entry_shelves "
                                            "WHERE entry_id=:eid AND shelf_id=:sid"
                                        ),
                                        {"eid": entry_id, "sid": shelf_id},
                                    )
                                    reverted += 1
                                else:
                                    skipped += 1

                # Mark batch as undone
                batch = session.get(ImportBatchRow, batch_id)
                if batch is not None:
                    batch.state = "undone"
                    batch.updated_at = now_iso

                session.flush()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                session.close()

        return {
            "batch_id": batch_id,
            "state": "undone",
            "reverted": reverted,
            "retained": retained,
            "skipped": skipped,
            "reverted_entries": reverted_entries,
            "reverted_items": reverted_items,
            "retained_items": retained_items,
        }


def _get_item_field(item: ItemRow, field: str) -> Any:
    if field == "year":
        return item.year
    if field == "creator_sort_override":
        # A Calibre import seeds this from that database's curated `authors.sort`,
        # so undo has to be able to unseed it.
        return item.creator_sort_override
    if field.startswith("metadata."):
        metadata = json.loads(item.metadata_json)
        return metadata.get(field.removeprefix("metadata."))
    return None


def _set_item_field(item: ItemRow, field: str, value: Any) -> None:
    if field == "year":
        item.year = value
    elif field == "creator_sort_override":
        item.creator_sort_override = value
    elif field.startswith("metadata."):
        key = field.removeprefix("metadata.")
        metadata = json.loads(item.metadata_json)
        if value is None or _is_empty(value):
            metadata.pop(key, None)
        else:
            metadata[key] = value
        item.metadata_json = json.dumps(metadata, ensure_ascii=False)
    item.updated_at = _now_iso()


def _values_equal(current: Any, imported: Any) -> bool:
    """Compare current and imported values for undo field-matching."""
    if current is None and imported is None:
        return True
    if current == imported:
        return True
    # Handle JSON string vs native comparison
    if isinstance(current, str) and isinstance(imported, str):
        return current == imported
    return False
