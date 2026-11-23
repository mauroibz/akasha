"""*From your library*: the nearest waiting entries by embeddings (Sprint 136).

The vectors are the documented-shape fixtures of `test_embeddings.py` (unrecorded,
DEC-187 point 4); the order they encode is `embedding_library.NEAREST_TO_RAYUELA`.
"""

from __future__ import annotations

import random
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from embedding_library import NEAREST_TO_RAYUELA
from embedding_replay import Endpoint
from sqlalchemy import text
from test_embeddings import KEY, _run_jobs, _settings, seed_library

import book_tracker.app.lifespan as lifespan_module
from book_tracker.application.embeddings import pack, request_embedding, store_vectors
from book_tracker.application.library_source import nearest_waiting
from book_tracker.application.recommendations import SuggestionStore
from book_tracker.domain.recommendations import Candidate
from book_tracker.infrastructure.providers import create_provider_client
from book_tracker.infrastructure.repositories import DomainRepository, SourceIdentity
from book_tracker.main import create_app

BOOK = "book"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@asynccontextmanager
async def _app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, endpoint: Endpoint | None, **extra: Any
) -> AsyncIterator[tuple[Any, httpx.AsyncClient]]:
    if endpoint is not None:
        transport = endpoint.transport()
        monkeypatch.setattr(
            lifespan_module,
            "create_provider_client",
            lambda *_args: create_provider_client(transport),
        )
        key = "OPENAI_API_KEY" if endpoint.provider == "openai" else "GEMINI_API_KEY"
        extra = {key: KEY, "recs_embeddings_provider": endpoint.provider, **extra}
    app = create_app(_settings(tmp_path, **extra))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        # No metadata provider may be asked: the library's picks are cached items.
        app.state.providers.clear()
        yield app, client


async def _round(client: httpx.AsyncClient, app: Any, entry_id: int, **params: Any) -> Any:
    queued = await client.post(
        f"/api/entries/{entry_id}/more-like-this", params={"source": "library", **params}
    )
    assert queued.status_code == 202, queued.text
    await _run_jobs(app)
    return (await client.get(f"/api/suggestion-rounds/{queued.json()['id']}")).json()


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ["gemini", "openai"])
async def test_from_your_library_returns_the_nearest_waiting_entries_to_the_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    endpoint = Endpoint(provider)
    async with _app(tmp_path, monkeypatch, endpoint) as (app, client):
        entries = seed_library(app)
        request_embedding(app.state.engine)
        await _run_jobs(app)
        body = await _round(client, app, entries["Rayuela"])
        listed = (await client.get("/api/suggestions")).json()
        types = {row["id"]: row for row in (await client.get("/api/item-types")).json()}
    assert body["status"] == "done", body
    assert [row["title"] for row in body["suggestions"]] == NEAREST_TO_RAYUELA
    first = body["suggestions"][0]
    assert first["enrichment"] == "enriched"
    assert first["entry_id"] == entries["62: Modelo para armar"]
    assert first["reason"]["signal"] == "library"
    assert first["reason"]["text"].startswith("Waiting since ")
    assert first["source_score"] > body["suggestions"][1]["source_score"]
    # One request embedded the library; the round asked nothing more.
    assert len(endpoint.requests) == 1
    # Home's *More like this* shows only things not yet held.
    assert listed == []
    sources = {row["name"]: row for row in types[BOOK]["recommendation"]["sources"]}
    assert list(sources) == ["model", "library"]
    assert sources["library"]["label"] == "From your library"
    assert sources["library"]["configured"] is True
    assert sources["library"]["from_library"] is True
    assert sources["library"]["about"]["model"] == (
        "gemini-embedding-001" if provider == "gemini" else "text-embedding-3-small"
    )
    assert KEY not in str(types)


@pytest.mark.anyio
async def test_only_this_persons_waiting_entries_of_that_library_are_suggested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = Endpoint("gemini", worded=True)
    async with _app(tmp_path, monkeypatch, endpoint) as (app, client):
        entries = seed_library(app)
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, username, is_admin, created_at, updated_at)"
                    " VALUES (2, 'bruno', 0, 'n', 'n')"
                )
            )
            # Finished now: no longer waiting.
            connection.execute(
                text("UPDATE entries SET status = 'read' WHERE id = :id"),
                {"id": entries["Ficciones"]},
            )
        DomainRepository(app.state.engine, 2).create_cached_entry(
            title="Final del juego",
            subtitle=None,
            year=1956,
            metadata={"creators": ["Julio Cortázar"], "subjects": ["Argentine fiction"]},
            identifiers=[],
            sources=[SourceIdentity("openlibrary", "OL-final", True)],
            status="to_read",
            score=None,
            item_type=BOOK,
        )
        request_embedding(app.state.engine)
        await _run_jobs(app)
        body = await _round(client, app, entries["Rayuela"])
    titles = [row["title"] for row in body["suggestions"]]
    assert "Ficciones" not in titles and "Final del juego" not in titles
    assert sorted(titles) == sorted(set(NEAREST_TO_RAYUELA) - {"Ficciones"})


@pytest.mark.anyio
async def test_a_seed_not_yet_embedded_is_embedded_for_its_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = Endpoint("gemini", worded=True)
    async with _app(tmp_path, monkeypatch, endpoint) as (app, client):
        entries = seed_library(app)
        request_embedding(app.state.engine)
        await _run_jobs(app)
        late = DomainRepository(app.state.engine, 1).create_cached_entry(
            title="Bestiario",
            subtitle=None,
            year=1951,
            metadata={"creators": ["Julio Cortázar"], "subjects": ["Argentine fiction"]},
            identifiers=[],
            sources=[SourceIdentity("openlibrary", "OL-bestiario", True)],
            status="read",
            score=8,
            item_type=BOOK,
        )
        # The job for it has not run: the round embeds the seed alone, once.
        with app.state.engine.begin() as connection:
            connection.execute(text("DELETE FROM jobs"))
        body = await _round(client, app, late.entry_id)
    assert body["status"] == "done"
    assert endpoint.batches[-1] == [
        "Bestiario\nBy Julio Cortázar\n1951\nSubjects: Argentine fiction"
    ]
    assert body["suggestions"][0]["title"] == "62: Modelo para armar"
    assert entries


@pytest.mark.anyio
async def test_want_adds_nothing_for_what_is_already_held_and_not_for_me_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = Endpoint("gemini")
    async with _app(tmp_path, monkeypatch, endpoint) as (app, client):
        entries = seed_library(app)
        request_embedding(app.state.engine)
        await _run_jobs(app)
        body = await _round(client, app, entries["Rayuela"])
        first = body["suggestions"][0]
        want = await client.patch(f"/api/suggestions/{first['id']}", json={"answer": "want"})
        no = await client.patch(f"/api/suggestions/{first['id']}", json={"answer": "not_for_me"})
        again = await _round(client, app, entries["Rayuela"], refresh="true")
        with app.state.engine.connect() as connection:
            held = connection.execute(text("SELECT count(*) FROM entries")).scalar_one()
    # Already held: the answer is recorded and no second entry is made.
    assert want.status_code == 200 and want.json()["entry_id"] == first["entry_id"]
    assert no.status_code == 200 and no.json()["answer"] == "not_for_me"
    assert [row["title"] for row in again["suggestions"]] == NEAREST_TO_RAYUELA[1:]
    assert held == 6


@pytest.mark.anyio
async def test_without_embeddings_the_source_says_how_and_nothing_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with _app(tmp_path, monkeypatch, None, ANTHROPIC_API_KEY=KEY) as (app, client):
        entries = seed_library(app)
        types = {row["id"]: row for row in (await client.get("/api/item-types")).json()}
        queued = await client.post(
            f"/api/entries/{entries['Rayuela']}/more-like-this?source=library"
        )
        default = await client.post(f"/api/entries/{entries['Rayuela']}/more-like-this")
    library = types[BOOK]["recommendation"]["sources"][1]
    assert library["name"] == "library" and library["configured"] is False
    assert "AKASHA_RECS_EMBEDDINGS_KEY" in library["hint"]
    assert "Claude API has no embeddings" in library["hint"]
    assert queued.json()["status"] == "not_configured"
    # The model (Claude) still answers by default.
    assert default.json()["source"] == "model"
    assert [row["name"] for row in types["movie"]["recommendation"]["sources"]] == [
        "tmdb",
        "model",
        "library",
    ]


# --- Other sources' found picks, in order of likeness ---------------------------------


def _item(app: Any, title: str, status: str | None = None) -> tuple[int, int | None]:
    repository = DomainRepository(app.state.engine, 1)
    if status is not None:
        created = repository.create_cached_entry(
            title=title,
            subtitle=None,
            year=2000,
            metadata={},
            identifiers=[],
            sources=[SourceIdentity("openlibrary", f"OL-{title}", True)],
            status=status,
            score=9,
            item_type=BOOK,
        )
        with app.state.engine.connect() as connection:
            item_id = connection.execute(
                text("SELECT item_id FROM entries WHERE id = :id"), {"id": created.entry_id}
            ).scalar_one()
        return int(item_id), created.entry_id
    item_id = repository.cache_item(
        title=title,
        subtitle=None,
        year=2000,
        metadata={},
        identifiers=[],
        sources=[SourceIdentity("openlibrary", f"OL-{title}", True)],
        creator_sort=None,
        item_type=BOOK,
    )
    return int(item_id), None


@pytest.mark.anyio
async def test_a_rounds_found_picks_are_read_in_order_of_likeness_to_the_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with _app(tmp_path, monkeypatch, None) as (app, _client):
        seed_item, seed_entry = _item(app, "Seed", "read")
        far, _ = _item(app, "Far")
        near, _ = _item(app, "Near")
        middle, _ = _item(app, "Middle")
        model = "gemini:test@3"
        store_vectors(
            app.state.engine,
            model,
            [
                (seed_item, "h", [1.0, 0.0, 0.0]),
                (far, "h", [0.0, 1.0, 0.0]),
                (near, "h", [0.9, 0.1, 0.0]),
                (middle, "h", [0.5, 0.5, 0.0]),
            ],
        )
        plain = SuggestionStore(app.state.engine, 1)
        assert seed_entry is not None
        round_id = plain.create_round(BOOK, seed_entry, "model", status="done")
        plain.store(
            round_id,
            BOOK,
            [
                Candidate("Far", item_id=far),
                Candidate("Pending one"),
                Candidate("Middle", item_id=middle),
                Candidate("Near", item_id=near),
            ],
        )
        as_chosen = [row["title"] for row in plain.round(round_id)["suggestions"]]  # type: ignore[index]
        liked = SuggestionStore(app.state.engine, 1, embedding_model=model).round(round_id)
        other_model = SuggestionStore(app.state.engine, 1, embedding_model="openai:x@y").round(
            round_id
        )
    assert as_chosen == ["Far", "Pending one", "Middle", "Near"]
    assert liked is not None and other_model is not None
    # Found picks take the found picks' places, nearest first; the pending one stays.
    assert [row["title"] for row in liked["suggestions"]] == [
        "Near",
        "Pending one",
        "Middle",
        "Far",
    ]
    assert [row["title"] for row in other_model["suggestions"]] == as_chosen


# --- The budget: 10,000 waiting items under 300 ms -----------------------------------------


@pytest.mark.anyio
async def test_a_ten_thousand_item_library_answers_under_300_ms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dims = 768
    count = 10_000
    model = f"gemini:gemini-embedding-001@{dims}"
    rng = random.Random(136)
    async with _app(tmp_path, monkeypatch, None) as (app, _client):
        with app.state.engine.begin() as connection:
            raw = connection.connection.driver_connection
            assert raw is not None
            raw.executemany(
                "INSERT INTO items (id, type, title, identifiers, metadata, created_at,"
                " updated_at) VALUES (?, 'book', ?, '{}', '{}', 'n', 'n')",
                [(number, f"Book {number}") for number in range(1, count + 1)],
            )
            raw.executemany(
                "INSERT INTO entries (id, user_id, item_id, status, date_added, reread_count,"
                " score_provisional, created_at, updated_at)"
                " VALUES (?, 1, ?, ?, '2024-03-01', 0, 0, 'n', 'n')",
                [
                    (number, number, "read" if number == 1 else "to_read")
                    for number in range(1, count + 1)
                ],
            )
            raw.executemany(
                "INSERT INTO item_embeddings VALUES (?, ?, ?, ?, 'h', 'n')",
                [
                    (number, model, dims, pack([rng.gauss(0, 1) for _ in range(dims)]))
                    for number in range(1, count + 1)
                ],
            )
        timings = []
        for _attempt in range(3):
            started = time.perf_counter()
            found = nearest_waiting(app.state.engine, model, 1, 12)
            timings.append(time.perf_counter() - started)
    assert found is not None and len(found) == 12
    assert found == sorted(found, key=lambda row: -row["similarity"])
    print(f"nearest_waiting over {count}: {[round(t * 1000) for t in timings]} ms")
    assert min(timings) < 0.3, timings
