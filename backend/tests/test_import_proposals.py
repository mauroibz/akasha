"""The import proposal store (Sprint 083 D2): what the background search found.

A proposal is one provider result offered for one row — the thing the owner
confirms or discards before commit. It is durable across the job's lifetime and
user sessions, and it is user-scoped like every other import row.

The schema tests follow the migration suite's habits: the table exists with the
columns the confirm route will read, the indexes it needs to answer "this
batch's rows" exist, and the CRUD holds the invariants the confirm flow leans
on (one chosen per record at most; discard clears every proposal's choice).
"""

import json
import sqlite3
from pathlib import Path

import pytest

from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.infrastructure.repositories import (
    DomainRepository,
    ImportRepository,
)
from book_tracker.migrations import upgrade

NOW = "2026-09-13T00:00:00Z"


def make_engine(tmp_path: Path):
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    return create_engine(configured)


def seed_batch(engine, user_id: int = 1, batch_id: str = "b1", kind: str = "list") -> int:
    """A batch and one record, the way `create_preview` writes them."""
    from sqlalchemy import text

    payload = json.dumps(
        {
            "row_number": 2,
            "item": {
                "title": "Rayuela",
                "subtitle": None,
                "year": None,
                "identifiers": {},
                "metadata": {"creators": ["Julio Cortázar"]},
                "creator_sort": None,
            },
            "entry": {
                "score": None,
                "notes": None,
                "date_added": None,
                "values": {},
                "score_provisional": False,
                "suggested_status": None,
            },
            "shelves": [],
            "source_fields": {},
            "item_type": None,
            "cover_stage": None,
        }
    )
    with DomainRepository(engine, user_id)._write() as session:
        session.execute(
            text(
                "INSERT INTO import_batches (id, user_id, kind, fingerprint, state,"
                " source_descriptor, preview_summary, counters, created_at, updated_at)"
                " VALUES (:id, :user, :kind, 'f', 'previewed', '{}', '{}', '{}', :now, :now)"
            ),
            {"id": batch_id, "user": user_id, "kind": kind, "now": NOW},
        )
        session.execute(
            text(
                "INSERT INTO import_records (batch_id, user_id, row_number,"
                " normalized_payload, conflicts, validation_errors, planned_action,"
                " match_kind, created_at, updated_at)"
                " VALUES (:batch, :user, 2, :payload, '{\"candidates\": []}', '[]',"
                " 'create_item', 'new', :now, :now)"
            ),
            {"batch": batch_id, "user": user_id, "payload": payload, "now": NOW},
        )
        return int(
            session.execute(
                text("SELECT id FROM import_records WHERE batch_id = :batch"),
                {"batch": batch_id},
            ).scalar_one()
        )


class TestSchema:
    def test_the_proposals_table_exists_with_its_columns(self, tmp_path: Path) -> None:
        make_engine(tmp_path)
        with sqlite3.connect(tmp_path / "books.db") as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(import_proposals)")}
        assert {
            "id",
            "batch_id",
            "user_id",
            "record_id",
            "source",
            "source_id",
            "payload_json",
            "rank",
            "chosen",
            "created_at",
        } <= columns
        indexes = {
            row[1]
            for row in sqlite3.connect(tmp_path / "books.db").execute(
                "PRAGMA index_list(import_proposals)"
            )
        }
        assert any("batch" in name for name in indexes)

    def test_the_chain_reaches_the_new_revision(self, tmp_path: Path) -> None:
        from book_tracker.migrations import pending_revisions

        make_engine(tmp_path)
        configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
        assert pending_revisions(configured.database_url) == []


class TestCrud:
    def test_proposals_are_created_ranked_and_listed_per_record(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        record_id = seed_batch(engine)
        repository = ImportRepository(engine, 1)
        repository.add_proposals(
            batch_id="b1",
            record_id=record_id,
            proposals=(
                {
                    "source": "openlibrary",
                    "source_id": "OL1M",
                    "payload": {"title": "Rayuela"},
                    "rank": 0,
                },
                {
                    "source": "openlibrary",
                    "source_id": "OL2M",
                    "payload": {"title": "Rayuela (ed.)"},
                    "rank": 1,
                },
            ),
        )
        listed = repository.proposals_for_batch("b1")
        assert len(listed) == 2
        assert [row["rank"] for row in listed] == [0, 1]
        assert listed[0]["payload"]["title"] == "Rayuela"
        assert all(row["chosen"] is None for row in listed)

    def test_choosing_marks_one_and_clears_the_others(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        record_id = seed_batch(engine)
        repository = ImportRepository(engine, 1)
        repository.add_proposals(
            batch_id="b1",
            record_id=record_id,
            proposals=(
                {"source": "openlibrary", "source_id": "OL1M", "payload": {}, "rank": 0},
                {"source": "openlibrary", "source_id": "OL2M", "payload": {}, "rank": 1},
            ),
        )
        repository.choose_proposal(
            "b1", record_id, proposal_source="openlibrary", proposal_source_id="OL2M"
        )
        listed = repository.proposals_for_batch("b1")
        assert [row["chosen"] for row in sorted(listed, key=lambda row: row["rank"])] == [
            False,
            True,
        ]

    def test_discard_clears_every_choice_on_the_record(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        record_id = seed_batch(engine)
        repository = ImportRepository(engine, 1)
        repository.add_proposals(
            batch_id="b1",
            record_id=record_id,
            proposals=(
                {"source": "openlibrary", "source_id": "OL1M", "payload": {}, "rank": 0},
                {"source": "openlibrary", "source_id": "OL2M", "payload": {}, "rank": 1},
            ),
        )
        repository.choose_proposal(
            "b1", record_id, proposal_source="openlibrary", proposal_source_id="OL1M"
        )
        repository.discard_proposals("b1", record_id)
        assert all(row["chosen"] is False for row in repository.proposals_for_batch("b1"))

    def test_proposals_are_user_scoped(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        record_id = seed_batch(engine)
        other = ImportRepository(engine, 2)
        assert other.proposals_for_batch("b1") == []
        with pytest.raises(LookupError):
            other.choose_proposal(
                "b1", record_id, proposal_source="openlibrary", proposal_source_id="OL1M"
            )

    def test_the_chosen_proposal_is_readable_in_one_query(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        record_id = seed_batch(engine)
        repository = ImportRepository(engine, 1)
        repository.add_proposals(
            batch_id="b1",
            record_id=record_id,
            proposals=(
                {
                    "source": "openlibrary",
                    "source_id": "OL1M",
                    "payload": {"title": "Rayuela", "identifiers": {"isbn": "9788437604572"}},
                    "rank": 0,
                },
                {
                    "source": "openlibrary",
                    "source_id": "OL2M",
                    "payload": {"title": "Otra"},
                    "rank": 1,
                },
            ),
        )
        repository.choose_proposal(
            "b1", record_id, proposal_source="openlibrary", proposal_source_id="OL1M"
        )
        chosen = repository.chosen_proposal("b1", record_id)
        assert chosen is not None
        assert chosen["payload"]["identifiers"] == {"isbn": "9788437604572"}
        assert repository.chosen_proposal("b1", record_id) is not None


class TestPreviewExposure:
    """The preview GET carries proposals per record and counts in the summary."""

    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    async def test_proposals_ride_the_preview_response(self, tmp_path: Path) -> None:

        from book_tracker.main import create_app

        engine = make_engine(tmp_path)
        record_id = seed_batch(engine)
        repository = ImportRepository(engine, 1)
        repository.add_proposals(
            batch_id="b1",
            record_id=record_id,
            proposals=(
                {
                    "source": "openlibrary",
                    "source_id": "OL1M",
                    "payload": {"title": "Rayuela", "cover_url": "https://x/c.jpg"},
                    "rank": 0,
                },
                {
                    "source": "openlibrary",
                    "source_id": "OL2M",
                    "payload": {"title": "Rayuela (ed.)"},
                    "rank": 1,
                },
            ),
        )
        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with app.router.lifespan_context(app):
            # The preview GET of a staged batch the service knows: the route is
            # reached through the connector that owns the batch.
            from book_tracker.application.imports import ImportService
            from book_tracker.domain.list import IMPORTER as LIST_IMPORTER

            service = ImportService(
                engine,
                tmp_path,
                tmp_path,
                LIST_IMPORTER,
                user_id=1,
                attachment_max_bytes=1024,
            )
            preview = service.get_preview("b1")
        assert preview["summary"]["rows_with_proposals"] == 1
        assert preview["summary"]["proposals_total"] == 2
        assert preview["records"][0]["proposals"][0]["payload"]["title"] == "Rayuela"
