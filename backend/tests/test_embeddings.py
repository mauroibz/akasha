"""Embeddings of the library's items (Sprint 136, DEC-183 point 7, DEC-187 point 3).

The endpoint replies (`tests/fixtures/providers/embeddings_*`) are written in each
API's documented response shape and are **not recorded**: no Gemini or OpenAI key was
present in the development environment, and `embedding_fixtures.json` says so (the
owner's exception, DEC-187 point 4; `scripts/record_embedding_fixtures.py` replaces
them). Where a test needs arbitrary texts, `embedding_replay.worded_transport` answers
in the same documented shape with vectors made from the texts' words.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from embedding_library import LIBRARY
from embedding_replay import GEMINI_PATH, OPENAI_PATH, Endpoint, fixture_texts
from recordings import FIXTURES
from sqlalchemy import text

import book_tracker.app.lifespan as lifespan_module
from book_tracker.app.recommendations import build_embedder
from book_tracker.application.embeddings import (
    EMBED_JOB,
    embedding_text,
    pack,
    request_embedding,
    request_if_missing,
    request_if_needed,
    similarity,
    unpack,
)
from book_tracker.config import Settings
from book_tracker.domain.recommendations import SourceError
from book_tracker.domain.registry import DOMAINS
from book_tracker.infrastructure.embedding_clients import (
    GeminiEmbeddings,
    OpenAICompatibleEmbeddings,
    build_embedding_client,
)
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.providers import create_provider_client
from book_tracker.infrastructure.repositories import DomainRepository, SourceIdentity
from book_tracker.main import create_app
from book_tracker.migrations import alembic_config, upgrade

KEY = "sk-test-EMBEDDINGS-NEVER-LOGGED-7f3a"
BOOK = "book"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _settings(tmp_path: Path, **extra: Any) -> Settings:
    base: dict[str, Any] = {
        "data_dir": tmp_path / "data",
        "user_agent_contact": "test@example.invalid",
        "TMDB_READ_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
    }
    return Settings(**{**base, **extra})


# --- The two adapters, against their documented shapes ---------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ["gemini", "openai"])
async def test_each_provider_kind_is_asked_in_its_own_shape(provider: str) -> None:
    endpoint = Endpoint(provider)
    client = build_embedding_client(create_provider_client(endpoint.transport()), provider, KEY)
    vectors = await client.embed(fixture_texts())
    (request,) = endpoint.requests
    body = json.loads(request.content)
    assert len(vectors) == len(LIBRARY)
    assert len({len(vector) for vector in vectors}) == 1
    assert request.method == "POST"
    assert KEY not in str(request.url)
    if provider == "gemini":
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.url.path == GEMINI_PATH
        assert request.headers["x-goog-api-key"] == KEY
        first = body["requests"][0]
        assert first["model"] == "models/gemini-embedding-001"
        assert first["taskType"] == "SEMANTIC_SIMILARITY"
        assert first["outputDimensionality"] == 768
        assert len(vectors[0]) == 768
        assert client.identity == "gemini:gemini-embedding-001@768"
    else:
        assert request.url.host == "api.openai.com"
        assert request.url.path == OPENAI_PATH
        assert request.headers["authorization"] == f"Bearer {KEY}"
        # Only what every compatible server accepts.
        assert set(body) == {"model", "input"}
        assert body["model"] == "text-embedding-3-small"
        assert len(vectors[0]) == 1536


@pytest.mark.anyio
async def test_an_openai_compatible_endpoint_is_its_configured_url() -> None:
    endpoint = Endpoint("openai")
    client = build_embedding_client(
        create_provider_client(endpoint.transport()),
        "openai",
        KEY,
        "voyage-3.5",
        "https://api.voyageai.com/v1/",
    )
    await client.embed(fixture_texts())
    (request,) = endpoint.requests
    assert str(request.url) == "https://api.voyageai.com/v1/embeddings"
    assert json.loads(request.content)["model"] == "voyage-3.5"
    assert client.identity == "openai:voyage-3.5@https://api.voyageai.com/v1"


@pytest.mark.anyio
async def test_an_openai_reply_is_put_back_in_the_order_asked() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )

    client = OpenAICompatibleEmbeddings(create_provider_client(httpx.MockTransport(handle)), KEY)
    assert await client.embed(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]


@pytest.mark.anyio
async def test_a_reply_of_another_count_is_malformed() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [{"values": [0.1, 0.2]}]})

    client = GeminiEmbeddings(create_provider_client(httpx.MockTransport(handle)), KEY)
    with pytest.raises(SourceError) as raised:
        await client.embed(["one", "two"])
    assert raised.value.code == "malformed"


@pytest.mark.anyio
async def test_a_refused_key_is_a_source_error_that_never_names_the_key() -> None:
    endpoint = Endpoint("openai", status=401)
    client = build_embedding_client(create_provider_client(endpoint.transport()), "openai", KEY)
    with pytest.raises(SourceError) as raised:
        await client.embed(["Rayuela"])
    assert raised.value.code == "unauthorized"
    assert "AKASHA_RECS_EMBEDDINGS_KEY" in str(raised.value)
    assert KEY not in str(raised.value) and KEY not in repr(client)


def test_every_embedding_fixture_is_marked_unrecorded_or_recorded() -> None:
    sidecar = json.loads((FIXTURES / "embedding_fixtures.json").read_text(encoding="utf-8"))
    assert isinstance(sidecar["recorded"], bool)
    for name, row in sidecar["files"].items():
        assert (FIXTURES / name).is_file(), name
        assert isinstance(row["recorded"], bool)


# --- The text an item is embedded from ------------------------------------------------


def test_the_text_is_title_creator_first_year_and_declared_fields_in_order() -> None:
    body = embedding_text(
        DOMAINS[BOOK],
        "Rayuela",
        "Cortázar, Julio",
        2000,
        {
            "creators": ["Julio Cortázar"],
            "original_year": 1963,
            "description": "A novel  in\ntwo  orders.",
            "subjects": ["Argentine fiction", "Paris"],
            "publisher": "Cátedra",
            "page_count": 736,
        },
    )
    assert body == (
        "Rayuela\nBy Julio Cortázar\n1963\nSubjects: Argentine fiction, Paris\n"
        "Description: A novel in two orders."
    )


def test_a_domain_that_declares_no_text_fields_is_its_title_creator_and_year() -> None:
    assert DOMAINS["album"].ranking.text_fields == ()
    body = embedding_text(DOMAINS["album"], "Kind of Blue", "Miles Davis", 1959, {})
    assert body == "Kind of Blue\nBy Miles Davis\n1959"


def test_every_domain_but_albums_declares_what_describes_it() -> None:
    assert DOMAINS[BOOK].ranking.text_fields == ("subjects", "description")
    assert DOMAINS["movie"].ranking.text_fields == ("genres", "description")
    assert DOMAINS["series"].ranking.text_fields == ("genres", "synopsis")
    assert DOMAINS["anime"].ranking.text_fields == ("genres", "synopsis")


def test_a_vector_is_stored_as_unit_length_float32() -> None:
    blob = pack([3.0, 4.0])
    assert len(blob) == 8
    assert list(unpack(blob)) == pytest.approx([0.6, 0.8])
    assert similarity(unpack(blob), unpack(pack([6.0, 8.0]))) == pytest.approx(1.0)


# --- Configuration ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "kind", "model"),
    [
        ({"GEMINI_API_KEY": KEY}, GeminiEmbeddings, "gemini-embedding-001"),
        ({"recs_embeddings_key": KEY}, GeminiEmbeddings, "gemini-embedding-001"),
        ({"recs_embeddings_provider": " ", "GEMINI_API_KEY": KEY}, GeminiEmbeddings, None),
        (
            {"recs_embeddings_provider": "openai", "OPENAI_API_KEY": KEY},
            OpenAICompatibleEmbeddings,
            "text-embedding-3-small",
        ),
        (
            {
                "recs_embeddings_provider": "openai",
                "recs_embeddings_key": KEY,
                "recs_embeddings_model": "voyage-3.5",
                "recs_embeddings_url": "https://api.voyageai.com/v1",
            },
            OpenAICompatibleEmbeddings,
            "voyage-3.5",
        ),
    ],
)
def test_the_endpoint_is_chosen_by_configuration(
    tmp_path: Path, extra: dict[str, Any], kind: type, model: str | None
) -> None:
    client = build_embedder(_settings(tmp_path, **extra), create_provider_client())
    assert isinstance(client, kind)
    assert client.model == (model or "gemini-embedding-001")


@pytest.mark.parametrize(
    "extra",
    [
        {},
        # The Claude API has no embeddings: a Claude key alone leaves them off.
        {"ANTHROPIC_API_KEY": KEY, "recs_model_key": KEY},
        # A key for the other kind does not configure this one.
        {"OPENAI_API_KEY": KEY},
        {"recs_embeddings_provider": "openai", "GEMINI_API_KEY": KEY},
        {"recs_embeddings_key": "   "},
    ],
)
def test_without_a_gemini_or_openai_key_embeddings_are_off(
    tmp_path: Path, extra: dict[str, Any]
) -> None:
    assert build_embedder(_settings(tmp_path, **extra), create_provider_client()) is None


def test_anthropic_is_not_an_embeddings_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="recs_embeddings_provider"):
        _settings(tmp_path, recs_embeddings_provider="anthropic")


# --- The job, end to end ----------------------------------------------------------------


@asynccontextmanager
async def _app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: Endpoint | None,
    **extra: Any,
) -> AsyncIterator[tuple[Any, httpx.AsyncClient]]:
    if endpoint is not None:
        transport = endpoint.transport()
        monkeypatch.setattr(
            lifespan_module,
            "create_provider_client",
            lambda *_args: create_provider_client(transport),
        )
        extra = {"GEMINI_API_KEY": KEY, **extra}
    app = create_app(_settings(tmp_path, **extra))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        app.state.providers.clear()
        yield app, client


async def _run_jobs(app: Any) -> list[dict[str, Any]]:
    repo = JobRepository(app.state.engine)
    handlers = app.state.job_runner.handlers
    done = []
    while (claimed := repo.claim(datetime.now(UTC))) is not None:
        result = await handlers[claimed.kind].process(claimed.id, datetime.now(UTC))
        if result["state"] == "succeeded":
            repo.complete(claimed.id, result.get("progress", {}), datetime.now(UTC))
        else:
            repo.fail(claimed.id, result["error"], datetime.now(UTC), code=result["error_code"])
        done.append({"kind": claimed.kind, **result})
    return done


def seed_library(app: Any, user_id: int = 1) -> dict[str, int]:
    """The fixture library as this person's entries; title to entry id."""
    entries: dict[str, int] = {}
    for book in LIBRARY:
        created = DomainRepository(app.state.engine, user_id).create_cached_entry(
            title=book["title"],
            subtitle=None,
            year=book["year"],
            metadata=dict(book["metadata"]),
            identifiers=[],
            sources=[SourceIdentity("openlibrary", f"OL-{book['title']}", True)],
            status=book["status"],
            score=book.get("score"),
            item_type=BOOK,
        )
        entries[book["title"]] = created.entry_id
    return entries


def _stored(app: Any) -> list[tuple[int, str, int, str]]:
    with app.state.engine.connect() as connection:
        return [
            tuple(row)
            for row in connection.execute(
                text("SELECT item_id, model, dims, text_hash FROM item_embeddings ORDER BY 1")
            )
        ]


@pytest.mark.anyio
async def test_the_job_embeds_the_library_in_one_batch_from_the_documented_reply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = Endpoint("gemini")
    async with _app(tmp_path, monkeypatch, endpoint) as (app, _client):
        seed_library(app)
        assert request_embedding(app.state.engine) is not None
        # One waiting job is enough: asking again queues nothing.
        assert request_embedding(app.state.engine) is None
        done = await _run_jobs(app)
        stored = _stored(app)
    assert [job["kind"] for job in done] == [EMBED_JOB]
    assert done[0]["progress"]["embedded"] == len(LIBRARY)
    assert endpoint.batches == [fixture_texts()]
    assert len(stored) == len(LIBRARY)
    assert {row[1:3] for row in stored} == {("gemini:gemini-embedding-001@768", 768)}


@pytest.mark.anyio
async def test_changing_an_items_text_re_embeds_it_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = Endpoint("gemini", worded=True)
    async with _app(tmp_path, monkeypatch, endpoint) as (app, _client):
        entries = seed_library(app)
        request_embedding(app.state.engine)
        await _run_jobs(app)
        before = dict((row[0], row[3]) for row in _stored(app))
        assert len(endpoint.requests) == 1

        # Nothing changed: the maintenance pass queues nothing, and a job asks nothing.
        assert (
            request_if_needed(app.state.engine, app.state.embedding_model, datetime.now(UTC))
            is None
        )
        request_embedding(app.state.engine)
        await _run_jobs(app)
        assert len(endpoint.requests) == 1

        # The person corrects one book's subjects: only that book is embedded again.
        with app.state.engine.begin() as connection:
            item_id = connection.execute(
                text("SELECT item_id FROM entries WHERE id = :id"),
                {"id": entries["The Hobbit"]},
            ).scalar_one()
            connection.execute(
                text(
                    "UPDATE items SET metadata = json_set(metadata, '$.subjects',"
                    ' json(\'["Fantasy fiction", "Middle-earth"]\')) WHERE id = :id'
                ),
                {"id": item_id},
            )
        assert request_if_needed(app.state.engine, app.state.embedding_model, datetime.now(UTC))
        await _run_jobs(app)
        await _run_jobs(app)
        request_embedding(app.state.engine)
        await _run_jobs(app)
        after = dict((row[0], row[3]) for row in _stored(app))
    assert len(endpoint.requests) == 2
    assert endpoint.batches[1] == [
        "The Hobbit\nBy J. R. R. Tolkien\n1937\nSubjects: Fantasy fiction, Middle-earth"
    ]
    assert {key for key in before if before[key] != after[key]} == {item_id}


@pytest.mark.anyio
async def test_a_new_model_embeds_everything_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = Endpoint("gemini", worded=True)
    async with _app(tmp_path, monkeypatch, endpoint) as (app, _client):
        seed_library(app)
        request_embedding(app.state.engine)
        await _run_jobs(app)
    other = Endpoint("gemini", worded=True)
    async with _app(tmp_path, monkeypatch, other, recs_embeddings_model="gemini-embedding-002") as (
        app,
        _client,
    ):
        assert request_if_needed(app.state.engine, app.state.embedding_model, datetime.now(UTC))
        await _run_jobs(app)
        models = {row[1] for row in _stored(app)}
    assert len(other.batches) == 1 and len(other.batches[0]) == len(LIBRARY)
    assert models == {"gemini:gemini-embedding-002@768"}


@pytest.mark.anyio
async def test_a_spent_budget_asks_nothing_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = Endpoint("gemini", worded=True)
    async with _app(tmp_path, monkeypatch, endpoint, provider_daily_limits={"embeddings": 0}) as (
        app,
        _client,
    ):
        seed_library(app)
        request_embedding(app.state.engine)
        done = await _run_jobs(app)
        stored = _stored(app)
    assert endpoint.requests == []
    assert stored == []
    assert done[0]["state"] == "succeeded"
    assert done[0]["progress"]["note"] == "today's embedding budget is spent"


@pytest.mark.anyio
async def test_a_large_library_is_embedded_in_batches_across_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = Endpoint("gemini", worded=True)
    async with _app(tmp_path, monkeypatch, endpoint) as (app, _client):
        repository = DomainRepository(app.state.engine, 1)
        for number in range(300):
            repository.create_cached_entry(
                title=f"Book {number}",
                subtitle=None,
                year=2000,
                metadata={"creators": ["Someone"]},
                identifiers=[],
                sources=[SourceIdentity("openlibrary", f"OL{number}", True)],
                status="to_read",
                score=None,
                item_type=BOOK,
            )
        request_embedding(app.state.engine)
        done = await _run_jobs(app)
        stored = _stored(app)
    # 32 to a request, eight requests a job, then a follow-up takes the rest.
    assert [len(batch) for batch in endpoint.batches] == [32] * 9 + [12]
    assert [job["progress"]["embedded"] for job in done] == [256, 44]
    assert len(stored) == 300


@pytest.mark.anyio
async def test_a_refusing_endpoint_fails_the_job_without_the_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    endpoint = Endpoint("openai", status=401)
    async with _app(
        tmp_path, monkeypatch, endpoint, recs_embeddings_provider="openai", OPENAI_API_KEY=KEY
    ) as (app, _client):
        seed_library(app)
        request_embedding(app.state.engine)
        (done,) = await _run_jobs(app)
    assert done["state"] == "failed"
    assert done["error_code"] == "unauthorized"
    assert KEY not in json.dumps(done) and KEY not in caplog.text


@pytest.mark.anyio
async def test_without_configuration_nothing_is_embedded_or_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with _app(tmp_path, monkeypatch, None, ANTHROPIC_API_KEY=KEY) as (app, _client):
        seed_library(app)
        assert app.state.embedding_model is None
        request_embedding(app.state.engine)
        done = await _run_jobs(app)
        stored = _stored(app)
    assert done[0]["progress"] == {"embedded": 0, "configured": False}
    assert stored == []


@pytest.mark.anyio
async def test_an_enrichment_that_filled_something_queues_embedding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = Endpoint("gemini", worded=True)
    async with _app(tmp_path, monkeypatch, endpoint) as (app, _client):
        handler = app.state.job_runner.handlers["enrich_item"]
        assert handler.on_enriched is not None
        handler.on_enriched(1)
        handler.on_enriched(2)
        with app.state.engine.connect() as connection:
            queued = connection.execute(
                text("SELECT count(*) FROM jobs WHERE kind = :kind AND state = 'queued'"),
                {"kind": EMBED_JOB},
            ).scalar_one()
    assert queued == 1


@pytest.mark.anyio
async def test_an_entry_added_by_any_path_is_noticed_by_the_minutes_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The walkthrough's finding: an add from search enriches nothing, so no job was
    queued, and the hourly pass had already run at start; the vector waited an hour."""
    endpoint = Endpoint("gemini", worded=True)
    async with _app(tmp_path, monkeypatch, endpoint) as (app, _client):
        runner = app.state.job_runner
        ((sweep, every),) = runner.sweeps
        assert every == timedelta(minutes=1)
        model = app.state.embedding_model
        start = datetime.now(UTC)
        # Nothing held: nothing queued.
        await runner.idle(start)
        assert JobRepository(app.state.engine).claim(datetime.now(UTC)) is None
        seed_library(app)
        # Inside the minute the pass does not run again; after it, it queues one job.
        await runner.idle(start + timedelta(seconds=30))
        assert JobRepository(app.state.engine).claim(datetime.now(UTC)) is None
        await runner.idle(start + timedelta(minutes=1))
        await _run_jobs(app)
        stored = _stored(app)
        # Everything has a vector now: the cheap check finds nothing.
        assert request_if_missing(app.state.engine, model, datetime.now(UTC)) is None
    assert len(stored) == len(LIBRARY)
    assert sweep.func is request_if_missing  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_without_configuration_enrichment_queues_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with _app(tmp_path, monkeypatch, None) as (app, _client):
        assert app.state.job_runner.handlers["enrich_item"].on_enriched is None
        assert len(app.state.job_runner.housekeeping) == 1
        assert app.state.job_runner.sweeps == ()


# --- Migration 0038 ---------------------------------------------------------------------


def _tables(database: Path) -> set[str]:
    connection = sqlite3.connect(database)
    try:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    finally:
        connection.close()


def test_0038_upgrades_and_downgrades_on_a_real_shaped_library(tmp_path: Path) -> None:
    from alembic import command

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    database = data_dir / "books.db"
    upgrade(configured.database_url, revision="0037_suggestions")
    connection = sqlite3.connect(database)
    for item_id, title in ((1, "Rayuela"), (2, "Ficciones")):
        connection.execute(
            "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
            " VALUES (?, 'book', ?, '{}', '{}', 'n', 'n')",
            (item_id, title),
        )
    connection.commit()
    connection.close()
    assert "item_embeddings" not in _tables(database)

    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(item_embeddings)")}
    assert set(columns) == {"item_id", "model", "dims", "vector", "text_hash", "created_at"}
    assert columns["item_id"][5] == 1  # the primary key
    for item_id in (1, 2):
        connection.execute(
            "INSERT INTO item_embeddings VALUES (?, 'gemini:m@2', 2, ?, 'h', 'n')",
            (item_id, pack([1.0, 0.0])),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO item_embeddings VALUES (1, 'gemini:m@2', 2, x'00', 'h', 'n')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO item_embeddings VALUES (9, 'gemini:m@2', 2, x'00', 'h', 'n')"
        )
    # An item pruned from the cache takes its vector with it.
    connection.execute("DELETE FROM items WHERE id = 2")
    assert connection.execute("SELECT item_id FROM item_embeddings").fetchall() == [(1,)]
    connection.commit()
    connection.close()

    command.downgrade(alembic_config(configured.database_url), "0037_suggestions")
    assert "item_embeddings" not in _tables(database)
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT count(*) FROM items").fetchone()[0] == 1
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()
