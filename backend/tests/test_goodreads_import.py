from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from book_tracker.config import Settings
from book_tracker.infrastructure.models import ImportBatchRow, ImportRecordRow
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_preview_persists_normalized_plan_without_library_writes(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    content = (FIXTURES / "goodreads_valid.csv").read_bytes()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("library.csv", content, "text/csv")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["summary"] == {"total": 2, "ready": 1, "errors": 1, "ambiguous": 0}
        assert body["records"][0]["goodreads_book_id"] == "101"
        assert body["records"][0]["isbn"] == "9788437604572"
        assert body["records"][0]["suggested_status"] == "read"
        assert body["records"][0]["score"] == 8
        assert body["records"][0]["score_provisional"] is True
        assert body["records"][0]["shelves"] == ["favoritos"]
        assert body["records"][1]["score"] is None
        assert body["records"][0]["errors"][0]["field"] == "date_read"
        with app.state.engine.connect() as connection:
            for table in ("items", "entries", "shelves", "item_identifiers"):
                assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        with Session(app.state.engine) as session:
            assert session.scalar(select(func.count()).select_from(ImportBatchRow)) == 1
            assert session.scalar(select(func.count()).select_from(ImportRecordRow)) == 2


@pytest.mark.anyio
async def test_preview_rejects_missing_columns_malformed_and_oversized_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("book_tracker.api.imports.MAX_IMPORT_BYTES", 32)
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        missing = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("bad.csv", b"Title,Author\nBook,A\n", "text/csv")},
        )
        assert missing.status_code == 422
        assert missing.json()["error"]["code"] == "missing_columns"
        malformed = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("bad.csv", b"\xff\xfe", "text/csv")},
        )
        assert malformed.status_code == 422
        assert malformed.json()["error"]["code"] == "invalid_csv"
        oversized = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("large.csv", b"x" * 33, "text/csv")},
        )
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "import_too_large"


def csv_row(
    *,
    book_id: str = "1",
    title: str = "Ficciones",
    author: str = "Jorge Luis Borges",
    isbn: str = '="9780141187761"',
) -> bytes:
    header = (FIXTURES / "goodreads_valid.csv").read_text(encoding="utf-8").splitlines()[0]
    row = (
        f'{book_id},{title},{author},,="",{isbn},5,Sur,200,1944,1944,'
        '2024/01/01,2024/01/02,"read, cuentos",read,Nota,1'
    )
    return f"{header}\n{row}\n".encode()


@pytest.mark.anyio
async def test_commit_is_atomic_idempotent_and_records_ordered_effects(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    content = csv_row() + csv_row(book_id="2").split(b"\n", 1)[1]
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post(
            "/api/import/goodreads/preview", files={"file": ("x.csv", content, "text/csv")}
        )
        assert preview.status_code == 201
        batch_id = preview.json()["batch_id"]
        committed = await client.post("/api/import/goodreads/commit", json={"batch_id": batch_id})
        assert committed.status_code == 200
        assert committed.json()["created_items"] == 1
        assert committed.json()["created_entries"] == 1
        assert committed.json()["unchanged_entries"] == 1
        retried = await client.post("/api/import/goodreads/commit", json={"batch_id": batch_id})
        assert retried.json() == committed.json()
        with app.state.engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM items")) == 1
            assert connection.scalar(text("SELECT count(*) FROM entries")) == 1
            entry = connection.execute(
                text("SELECT status,score,score_provisional,suggested_status FROM entries")
            ).one()
            assert tuple(entry) == ("unsorted", 10, 1, "read")
            effects = (
                connection.execute(text("SELECT effect_id FROM import_effects ORDER BY effect_id"))
                .scalars()
                .all()
            )
            assert effects == sorted(effects) and len(effects) >= 3


@pytest.mark.anyio
async def test_commit_requires_ambiguity_choice_and_preserves_existing_entry(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        existing = DomainRepository(app.state.engine).create_cached_entry(
            title="Ficciones",
            subtitle=None,
            year=1944,
            metadata={"authors": ["Jorge Luis Borges"], "publisher": "Manual"},
            identifiers=[],
            sources=[],
            status="read",
            score=9,
        )
        content = csv_row(isbn='=""')
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            preview = await client.post(
                "/api/import/goodreads/preview", files={"file": ("x.csv", content, "text/csv")}
            )
            record = preview.json()["records"][0]
            assert record["planned_action"] == "ambiguous"
            rejected = await client.post(
                "/api/import/goodreads/commit", json={"batch_id": preview.json()["batch_id"]}
            )
            assert rejected.status_code == 409
            committed = await client.post(
                "/api/import/goodreads/commit",
                json={
                    "batch_id": preview.json()["batch_id"],
                    "choices": [{"record_id": record["record_id"], "item_id": existing.item_id}],
                },
            )
            assert committed.status_code == 200
        with app.state.engine.connect() as connection:
            entry = connection.execute(
                text("SELECT status,score FROM entries WHERE id=:id"), {"id": existing.entry_id}
            ).one()
            assert tuple(entry) == ("read", 9)
            assert connection.scalar(text("SELECT count(*) FROM items")) == 1
