from sqlalchemy import Computed, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
    created_at: Mapped[str]
    updated_at: Mapped[str]


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
