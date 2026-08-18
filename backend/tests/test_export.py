"""Export: the library leaves the application in a format its owner can read.

The acceptance criterion that shapes every test here is that nothing the owner
*typed* may be missing, and nothing the application *derived* may be present.
A derived column in the dump would read as authority to whoever imports it
later, when in truth it rebuilds itself on write (DEC-036, DEC-051).
"""

import csv
import io
import json
import tracemalloc
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from book_tracker.application.export import export_csv, export_json
from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app

DERIVED_COLUMNS = (
    "creator",
    "creator_sort",
    "title_normalized",
    "creator_primary_normalized",
    "creator_sort_normalized",
)


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_export_carries_owner_data_and_omits_derived_columns(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET creator_sort_override=:sort WHERE id=:id"),
                {"sort": "Cortázar, Julio", "id": created.item_id},
            )
            connection.execute(
                text(
                    "UPDATE entries SET score=8, notes='Read it twice', reread_count=2,"
                    " date_finished='2026-01-05' WHERE id=:id"
                ),
                {"id": created.entry_id},
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "akasha-export"
    assert payload["version"] == 1

    item = payload["items"][0]
    # The override is the one creator field no algorithm can reconstruct (DEC-051).
    assert item["creator_sort_override"] == "Cortázar, Julio"
    assert item["type"] == "book"
    assert item["metadata"]["creators"] == ["Julio Cortázar"]
    for column in DERIVED_COLUMNS:
        assert column not in item, f"{column} is derived and must not be exported"

    entry = payload["entries"][0]
    assert entry["score"] == 8
    assert entry["notes"] == "Read it twice"
    assert entry["reread_count"] == 2
    assert entry["date_finished"] == "2026-01-05"


@pytest.mark.anyio
async def test_export_of_an_empty_library_is_valid_and_empty(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["entries"] == []
    assert payload["kind"] == "akasha-export"


@pytest.mark.anyio
async def test_export_does_not_special_case_the_item_type(tmp_path: Path) -> None:
    """A type the application has never seen exports through the same path.

    This is the criterion that keeps the format honest ahead of DEC-052's domain
    work: nothing here may assume the type is `book`.
    """
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        book = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        album = repository.create_or_get_entry(
            title="Kind of Blue", creators=("Miles Davis",), item_type="album"
        )
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET metadata=:meta WHERE id=:id"),
                {
                    "meta": '{"creators": ["Miles Davis"], "label": "Columbia"}',
                    "id": album.item_id,
                },
            )
            connection.execute(
                text("UPDATE items SET metadata=:meta WHERE id=:id"),
                {
                    "meta": '{"creators": ["Julio Cortázar"], "page_count": 736}',
                    "id": book.item_id,
                },
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export")

    exported = {row["title"]: row for row in response.json()["items"]}
    assert {row["type"] for row in exported.values()} == {"book", "album"}
    # Opaque both ways: each domain's own vocabulary survives untranslated, and the
    # album needs no branch of its own to get there.
    assert exported["Kind of Blue"]["metadata"] == {
        "creators": ["Miles Davis"],
        "label": "Columbia",
    }
    assert exported["Rayuela"]["metadata"] == {
        "creators": ["Julio Cortázar"],
        "page_count": 736,
    }


@pytest.mark.anyio
async def test_export_carries_attachment_references_with_their_digest(tmp_path: Path) -> None:
    """References, not bytes (DEC-054).

    The filename is owner data (DEC-050), so a dump that rebuilt names from digests
    would lose a correction. The digest is what makes the reference resolvable
    against a backup, because the blob's path *is* its digest.
    """
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            upload = await client.post(
                f"/api/items/{created.item_id}/attachments",
                files={"file": ("Rayuela.epub", b"epub bytes here", "application/epub+zip")},
            )
            assert upload.status_code == 201
            attachment_id = upload.json()["id"]
            renamed = await client.patch(
                f"/api/items/{created.item_id}/attachments/{attachment_id}",
                json={"filename": "Rayuela (1963, Sudamericana).epub"},
            )
            assert renamed.status_code == 200
            response = await client.get("/api/export")

    attachments = response.json()["items"][0]["attachments"]
    assert len(attachments) == 1
    reference = attachments[0]
    # The name the owner typed, not the one the file arrived under.
    assert reference["filename"] == "Rayuela (1963, Sudamericana).epub"
    assert reference["byte_size"] == len(b"epub bytes here")
    assert len(reference["sha256"]) == 64
    assert reference["path"].endswith(f"/attachments/{attachment_id}")
    # References, not bytes.
    assert "content" not in reference and "data" not in reference


GOODREADS_COLUMNS = [
    "Book Id",
    "Title",
    "Author",
    "Additional Authors",
    "ISBN",
    "ISBN13",
    "My Rating",
    "Publisher",
    "Number of Pages",
    "Year Published",
    "Original Publication Year",
    "Date Read",
    "Date Added",
    "Bookshelves",
    "Exclusive Shelf",
    "My Review",
    "Read Count",
]


@pytest.mark.anyio
async def test_csv_export_has_the_goodreads_columns_and_survives_hostile_text(
    tmp_path: Path,
) -> None:
    """Product spec 5.1's column list, and text that breaks naive CSV writers."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(
            title="Rayuela, o el libro de los libros",
            creators=("Julio Cortázar", "Jorge Luis Borges"),
        )
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE entries SET status='read', score=7, reread_count=2,"
                    " notes=:notes, date_finished='2026-01-05' WHERE id=:id"
                ),
                {
                    "notes": 'He said "read it".\nTwice, on a Tuesday.',
                    "id": created.entry_id,
                },
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export", params={"format": "csv"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert list(rows[0]) == GOODREADS_COLUMNS
    row = rows[0]
    # The comma in the title and the quote+newline in the note round-trip through
    # a real CSV reader rather than splitting the row.
    assert row["Title"] == "Rayuela, o el libro de los libros"
    assert row["My Review"] == 'He said "read it".\nTwice, on a Tuesday.'
    assert row["Author"] == "Julio Cortázar"
    assert row["Additional Authors"] == "Jorge Luis Borges"
    # Goodreads rates 1-5 and the importer doubled it, so the export halves it back.
    assert row["My Rating"] == "4"
    # Goodreads counts total reads; we store rereads (import did Read Count - 1).
    assert row["Read Count"] == "3"
    assert row["Exclusive Shelf"] == "read"
    assert row["Date Read"] == "2026/01/05"


@pytest.mark.anyio
async def test_csv_export_neutralizes_spreadsheet_formulas(tmp_path: Path) -> None:
    """A note beginning `=` is a formula to Excel, not text.

    The CSV is the convenience view and is made safe to open; the JSON export is
    the lossless one and carries the value exactly as typed.
    """
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(title="Ledger", creators=("A. Nobody",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET notes=:notes WHERE id=:id"),
                {"notes": "=1+1", "id": created.entry_id},
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            csv_response = await client.get("/api/export", params={"format": "csv"})
            json_response = await client.get("/api/export")

    row = next(iter(csv.DictReader(io.StringIO(csv_response.text))))
    assert not row["My Review"].startswith("=")
    assert "1+1" in row["My Review"]
    # Lossless in the JSON.
    assert json_response.json()["entries"][0]["notes"] == "=1+1"


def _seed(engine, count: int) -> int:
    """A library big enough that buffering and streaming are distinguishable."""
    padding = "x" * 400
    with engine.begin() as connection:
        for index in range(count):
            connection.execute(
                text(
                    "INSERT INTO items (type, title, subtitle, year, identifiers, metadata,"
                    " created_at, updated_at) VALUES ('book', :title, NULL, 1963, '{}',"
                    " :metadata, '2026-01-01', '2026-01-01')"
                ),
                {
                    "title": f"Title {index}",
                    "metadata": json.dumps(
                        {"creators": [f"Author {index}"], "description": padding}
                    ),
                },
            )
        connection.execute(
            text(
                "INSERT INTO entries (item_id, user_id, status, score, notes, date_added,"
                " reread_count, score_provisional, created_at, updated_at)"
                " SELECT id, 1, 'read', 8, :notes, '2026-01-01', 0, 0,"
                " '2026-01-01', '2026-01-01' FROM items"
            ),
            {"notes": padding},
        )
        return connection.execute(text("SELECT count(*) FROM items")).scalar_one()


def _peak_bytes(engine, generate) -> tuple[int, int]:
    tracemalloc.start()
    try:
        before = tracemalloc.get_traced_memory()[0]
        total = sum(len(chunk.encode()) for chunk in generate(engine))
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return peak - before, total


@pytest.mark.parametrize("exporter", ["json", "csv"])
def test_export_memory_is_flat_against_library_size(tmp_path: Path, exporter: str) -> None:
    """The property streaming exists for, measured rather than asserted.

    Flatness is the claim, so the measurement is a comparison: a library ten times
    larger must not cost ten times the peak. A buffered implementation necessarily
    peaks at or above its own output and so tracks the corpus; a streaming one
    holds a batch and a compiled statement, and peaks at roughly the same figure
    either way.

    An absolute bound was tried first and was the wrong instrument: peak is
    dominated by a fixed ~1 MB of SQLAlchemy statement compilation that does not
    grow with the corpus, so a small library failed a bound the large one passed.
    """
    generate = export_json if exporter == "json" else export_csv

    small_app = create_app(settings(tmp_path / "small"))
    with TestClient(small_app):
        _seed(small_app.state.engine, 200)
        small_peak, small_total = _peak_bytes(small_app.state.engine, generate)

    large_app = create_app(settings(tmp_path / "large"))
    with TestClient(large_app):
        _seed(large_app.state.engine, 2000)
        large_peak, large_total = _peak_bytes(large_app.state.engine, generate)

    # The artifact really did grow, so the peak comparison means something.
    assert large_total > small_total * 8
    assert large_total > 800_000
    # Ten times the library, and not ten times the memory. Measured at x1.07 (JSON)
    # and x1.66 (CSV) against x10.0 output; the bound is loose because it exists to
    # catch a return to buffering, which would track the corpus, not to pin an
    # allocator against transient garbage.
    assert large_peak < small_peak * 3, (
        f"peak grew with library size: {small_peak} -> {large_peak} bytes "
        f"while output grew {small_total} -> {large_total}"
    )


@pytest.mark.anyio
async def test_the_goodreads_csv_carries_books_and_leaves_the_other_domains_to_the_json(
    tmp_path: Path,
) -> None:
    """Found on the Sprint 025 walkthrough: the CSV was emitting albums as books.

    The CSV is one domain's export view — a Goodreads import would read an album as a
    book with no author and no ISBN. The JSON beside it is the lossless artifact and
    carries every type, so nothing is lost by leaving the CSV book-shaped.
    """
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        repository.create_or_get_entry(
            title="Kind of Blue", creators=("Miles Davis",), item_type="album"
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            csv_body = (await client.get("/api/export", params={"format": "csv"})).text
            everything = (await client.get("/api/export")).json()

    titles = [row.split(",")[1] for row in csv_body.strip().splitlines()[1:]]
    assert titles == ["Rayuela"]
    assert {row["title"] for row in everything["items"]} == {"Rayuela", "Kind of Blue"}


@pytest.mark.anyio
async def test_export_carries_the_format_of_a_copy(tmp_path: Path) -> None:
    """DEC-059 formats are owner data in DEC-054's sense: nothing derives them.

    The item says a release was pressed on vinyl in 1959. The entry says *you* have
    it on vinyl and digital — a different fact, unreconstructable from the item, so an
    export that dropped it would lose something only the owner knew.
    """
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        repository = DomainRepository(app.state.engine)
        album = repository.create_or_get_entry(title="Discovery", creators=("Daft Punk",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET type='album' WHERE id=:id"), {"id": album.item_id}
            )
        await client.patch(
            f"/api/entries/{album.entry_id}",
            json={"status": "wishlist", "formats": ["vinyl", "digital"]},
        )
        document = json.loads("".join(export_json(app.state.engine)))

    entry = document["entries"][0]
    assert entry["formats"] == ["digital", "vinyl"]
    # Independent axes: the export carries both without one implying the other.
    assert entry["status"] == "wishlist"
