import json

from sqlalchemy import Computed, ForeignKey, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from book_tracker.domain.normalization import creator_sort_name, normalize_text


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str]
    title: Mapped[str]
    subtitle: Mapped[str | None]
    year: Mapped[int | None]
    cover_path: Mapped[str | None]
    identifiers: Mapped[str]
    metadata_json: Mapped[str] = mapped_column("metadata")
    sort_author: Mapped[str | None] = mapped_column(
        Computed("json_extract(metadata, '$.authors[0]')")
    )
    # Sorting and filtering by text used to call the connection-level
    # `normalize_text` UDF once per candidate row, which Sprint 017 measured at
    # 8x the cost of an indexed column and over budget while the job queue
    # drained. These columns hold the same values, maintained by the mapper
    # event below rather than by a generated column: SQLite generated columns
    # may only call built-in functions.
    title_normalized: Mapped[str | None]
    sort_author_normalized: Mapped[str | None]
    # `sort_author` is the creator's name as written, which is what the detail
    # page shows and what the `q` filter matches. These three are what the library
    # *sorts* by, which is not the same string: "Gabriel García Márquez" displays
    # as written and sorts under García Márquez. The override is the owner's
    # correction and the only one of the three that is not derived.
    creator_sort_override: Mapped[str | None] = mapped_column(default=None)
    creator_sort: Mapped[str | None] = mapped_column(default=None)
    creator_sort_normalized: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[str]
    updated_at: Mapped[str]


def _first_author(metadata_json: str | None) -> str | None:
    """Mirror `json_extract(metadata, '$.authors[0]')`, which defines `sort_author`."""
    decoded = json.loads(metadata_json or "{}")
    authors = decoded.get("authors") if isinstance(decoded, dict) else None
    first = authors[0] if isinstance(authors, list) and authors else None
    return first if isinstance(first, str) else None


def _project_normalized_text(_mapper: object, _connection: object, item: "ItemRow") -> None:
    """Keep the normalized projection in step with every write to an item.

    Attached to the mapper rather than to each call site so a future write path
    cannot forget it and leave a row unsortable. `sort_author` is a generated
    column with no value on the Python object before flush, so the author is read
    from the same JSON path the generated column uses.

    The creator sort name is derived here for the same reason, and only the
    override is owner data: clearing it restores the heuristic, and every path
    that edits an item — refresh, import fill, undo, manual edit — goes through an
    ORM object, so none of them can leave the sort key stale.
    """
    item.title_normalized = normalize_text(item.title or "")
    author = _first_author(item.metadata_json)
    item.sort_author_normalized = normalize_text(author) if author else None
    override = (item.creator_sort_override or "").strip()
    sort_name = override or (creator_sort_name(author) if author else "")
    item.creator_sort = sort_name or None
    item.creator_sort_normalized = normalize_text(sort_name) if sort_name else None


event.listen(ItemRow, "before_insert", _project_normalized_text)
event.listen(ItemRow, "before_update", _project_normalized_text)


class ItemIdentifierRow(Base):
    __tablename__ = "item_identifiers"
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(primary_key=True)
    normalized_value: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
    created_at: Mapped[str]
    updated_at: Mapped[str]


class ItemSourceRow(Base):
    __tablename__ = "item_sources"
    source: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    is_primary: Mapped[int]
    created_at: Mapped[str]
    updated_at: Mapped[str]


class EntryRow(Base):
    __tablename__ = "entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    status: Mapped[str]
    score: Mapped[int | None]
    notes: Mapped[str | None]
    date_added: Mapped[str]
    date_started: Mapped[str | None]
    date_finished: Mapped[str | None]
    reread_count: Mapped[int]
    score_provisional: Mapped[int]
    suggested_status: Mapped[str | None]
    created_at: Mapped[str]
    updated_at: Mapped[str]


class ShelfRow(Base):
    __tablename__ = "shelves"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    name: Mapped[str]
    slug: Mapped[str]
    created_at: Mapped[str]
    updated_at: Mapped[str]


class EntryShelfRow(Base):
    __tablename__ = "entry_shelves"
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id"), primary_key=True)
    shelf_id: Mapped[int] = mapped_column(ForeignKey("shelves.id"), primary_key=True)


class ImportBatchRow(Base):
    __tablename__ = "import_batches"
    id: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[str]
    fingerprint: Mapped[str]
    state: Mapped[str]
    source_descriptor: Mapped[str]
    preview_summary: Mapped[str]
    counters: Mapped[str]
    error: Mapped[str | None]
    committed_at: Mapped[str | None]
    undo_expires_at: Mapped[str | None]
    created_at: Mapped[str]
    updated_at: Mapped[str]


class ImportRecordRow(Base):
    __tablename__ = "import_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"))
    row_number: Mapped[int]
    normalized_payload: Mapped[str]
    matched_item_id: Mapped[int | None]
    matched_entry_id: Mapped[int | None]
    match_kind: Mapped[str | None]
    planned_action: Mapped[str | None]
    conflicts: Mapped[str]
    validation_errors: Mapped[str]
    ambiguity_resolution: Mapped[str | None]
    created_at: Mapped[str]
    updated_at: Mapped[str]


class ImportEffectRow(Base):
    __tablename__ = "import_effects"
    effect_id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str]
    record_id: Mapped[int]
    effect_type: Mapped[str]
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    before_values: Mapped[str]
    after_values: Mapped[str]


class JobRow(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(primary_key=True)
    batch_id: Mapped[str | None]
    kind: Mapped[str]
    state: Mapped[str]
    payload: Mapped[str]
    progress: Mapped[str]
    error: Mapped[str | None]
    error_code: Mapped[str | None]
    attempts: Mapped[int]
    available_at: Mapped[str]
    heartbeat_at: Mapped[str | None]
    lease_expires_at: Mapped[str | None]
    finished_at: Mapped[str | None]
    created_at: Mapped[str]
    updated_at: Mapped[str]


class AttachmentRow(Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    filename: Mapped[str]
    byte_size: Mapped[int]
    sha256: Mapped[str]
    created_at: Mapped[str]
    updated_at: Mapped[str]
