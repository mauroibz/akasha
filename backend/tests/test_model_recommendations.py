"""A hosted model as a recommendation source, in three provider kinds (Sprint 135, DEC-187).

The model replies (`tests/fixtures/providers/model_*`) are written in each API's
documented response shape and are **not recorded**: no model key was present in the
development environment, and `model_fixtures.json` says so (DEC-187 point 4, the
owner's exception to the recorded-real rule; `scripts/record_model_fixtures.py`
replaces them). The books the model names are resolved against **recorded** Open
Library searches (`openlibrary_search_*`, captured 2026-11-23), so resolution and the
dropping of an invented title are proven against real responses.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from recordings import FIXTURES, recording, replay
from sqlalchemy import text

from book_tracker.app.recommendations import DEFAULT_RECOMMEND_LIMITS, build_source_registry
from book_tracker.application.recommendations import RECOMMEND_JOB, budget_key, want_status
from book_tracker.config import Settings
from book_tracker.domain.identity import normalize_identifier
from book_tracker.domain.providers import SearchCandidate
from book_tracker.domain.recommendations import (
    Candidate,
    NotConfigured,
    Seed,
    SourceError,
    TasteEntry,
    TasteProfile,
    resolve_by_identity_or_search,
    same_work,
)
from book_tracker.domain.registry import DOMAINS
from book_tracker.domains.book.providers import OpenLibraryProvider
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.model_clients import (
    AnthropicClient,
    GeminiClient,
    OpenAICompatibleClient,
    build_model_client,
)
from book_tracker.infrastructure.model_recommendations import (
    SENDS,
    ModelRecommendations,
    build_prompt,
    parse_reply,
)
from book_tracker.infrastructure.providers import create_provider_client
from book_tracker.infrastructure.repositories import DomainRepository, SourceIdentity
from book_tracker.main import create_app

KEY = "sk-test-NEVER-LOGGED-7f3a9c"
BOOK = "book"

#: Where each provider kind is asked, and the reply recorded for it.
PROVIDERS: dict[str, tuple[str, str]] = {
    "anthropic": ("/v1/messages", "model_anthropic_messages_rayuela.json"),
    "gemini": (
        "/v1beta/models/gemini-2.5-flash:generateContent",
        "model_gemini_generate_content_rayuela.json",
    ),
    "openai": ("/v1/chat/completions", "model_openai_chat_completions_rayuela.json"),
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Model:
    """One provider kind over its documented reply, keeping what it was sent."""

    def __init__(self, provider: str, routes: Mapping[str, tuple[int, Any]] | None = None) -> None:
        path, name = PROVIDERS[provider]
        self.requests: list[httpx.Request] = []
        transport = replay(
            routes or {path: (200, recording(name))}, on_request=self.requests.append
        )
        self.client = build_model_client(create_provider_client(transport), provider, KEY)
        self.source = ModelRecommendations(self.client)

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(request.content) for request in self.requests]


def _seed() -> Seed:
    return Seed(
        item_type=BOOK,
        entry_id=1,
        item_id=1,
        title="Rayuela",
        year=1963,
        creators=("Julio Cortázar",),
        external_ids={"isbn13": "9788437604572"},
        metadata={"description": "PRIVATE-DESCRIPTION"},
        options={"kind": "books", "creator": "author"},
    )


# --- The three adapters, against their documented shapes ----------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", sorted(PROVIDERS))
async def test_each_provider_kind_is_asked_in_its_own_shape(provider: str) -> None:
    model = Model(provider)
    reply = await model.client.complete("SYSTEM", "QUESTION")
    assert json.loads(reply)["suggestions"][0]["title"] == "Pedro Páramo"
    (request,) = model.requests
    body = model.bodies[0]
    assert request.method == "POST"
    assert request.url.path == PROVIDERS[provider][0]
    # The key travels in a header only: httpx logs URLs.
    assert KEY not in str(request.url)
    if provider == "anthropic":
        assert request.url.host == "api.anthropic.com"
        assert request.headers["x-api-key"] == KEY
        assert request.headers["anthropic-version"] == "2026-10-21"
        assert body["model"] == "claude-haiku-5-5"
        assert body["system"] == "SYSTEM"
        assert body["messages"] == [{"role": "user", "content": "QUESTION"}]
        assert body["output_config"]["format"]["type"] == "json_schema"
        assert not {"temperature", "top_p", "top_k"} & set(body)
    elif provider == "gemini":
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.headers["x-goog-api-key"] == KEY
        assert body["contents"] == [{"role": "user", "parts": [{"text": "QUESTION"}]}]
        assert body["systemInstruction"] == {"parts": [{"text": "SYSTEM"}]}
        assert body["generationConfig"]["responseMimeType"] == "application/json"
    else:
        assert request.url.host == "api.openai.com"
        assert request.headers["authorization"] == f"Bearer {KEY}"
        assert body["model"] == "gpt-5-mini"
        assert body["messages"] == [
            {"role": "system", "content": "SYSTEM"},
            {"role": "user", "content": "QUESTION"},
        ]
        assert body["response_format"] == {"type": "json_object"}


@pytest.mark.anyio
async def test_an_openai_compatible_endpoint_is_its_configured_url() -> None:
    requests: list[httpx.Request] = []
    transport = replay(
        {"/api/v1/chat/completions": (200, recording(PROVIDERS["openai"][1]))},
        on_request=requests.append,
    )
    client = build_model_client(
        create_provider_client(transport),
        "openai",
        KEY,
        "some/model",
        "https://openrouter.example/api/v1/",
    )
    assert isinstance(client, OpenAICompatibleClient)
    await client.complete("s", "q")
    assert str(requests[0].url) == "https://openrouter.example/api/v1/chat/completions"
    assert json.loads(requests[0].content)["model"] == "some/model"


@pytest.mark.anyio
async def test_a_refused_key_is_a_source_error_that_never_names_the_key() -> None:
    model = Model("anthropic", {"/v1/messages": (401, recording("model_anthropic_error_401.json"))})
    with pytest.raises(SourceError) as raised:
        await model.client.complete("s", "q")
    assert raised.value.code == "unauthorized"
    assert "AKASHA_RECS_MODEL_KEY" in str(raised.value)
    assert KEY not in str(raised.value)
    assert KEY not in repr(model.client)


@pytest.mark.anyio
async def test_a_reply_cut_off_at_the_token_limit_fails() -> None:
    body = dict(recording(PROVIDERS["anthropic"][1]), stop_reason="max_tokens")
    model = Model("anthropic", {"/v1/messages": (200, body)})
    with pytest.raises(SourceError) as raised:
        await model.client.complete("s", "q")
    assert raised.value.code == "malformed"


# --- Reading a reply -----------------------------------------------------------------------


def test_a_reply_in_prose_is_malformed() -> None:
    prose = recording("model_anthropic_messages_prose.json")["content"][0]["text"]
    with pytest.raises(SourceError) as raised:
        parse_reply(prose, 8)
    assert raised.value.code == "malformed"


def test_a_reply_is_read_forgivingly_item_by_item() -> None:
    reply = (
        "```json\n"
        + json.dumps(
            {
                "suggestions": [
                    {"title": "Ficciones", "creator": "", "year": 0, "reason": ""},
                    {"creator": "Nobody"},
                    {"title": "  Pedro   Páramo ", "creator": "Juan Rulfo", "year": "1955"},
                    {"title": "ficciones", "creator": "Borges", "year": 1944, "reason": "again"},
                    {"title": "Aura", "creator": "Carlos Fuentes", "year": True, "reason": "x"},
                ]
            }
        )
        + "\n```"
    )
    candidates = parse_reply(reply, 8)
    assert [(c.title, c.creator, c.year) for c in candidates] == [
        ("Ficciones", None, None),
        ("Pedro Páramo", "Juan Rulfo", 1955),
        ("Aura", "Carlos Fuentes", None),
    ]
    assert candidates[0].reason == "Suggested by the model"
    assert parse_reply(reply, 2)[-1].title == "Pedro Páramo"
    assert parse_reply('{"suggestions": []}', 8) == []


def test_a_list_of_unusable_items_is_malformed() -> None:
    with pytest.raises(SourceError):
        parse_reply('{"suggestions": [{"name": "x"}, 3]}', 8)
    with pytest.raises(SourceError):
        parse_reply('{"picks": []}', 8)


# --- What is sent ----------------------------------------------------------------------------

_ALLOWED_LINE = re.compile(r"- [^\n]+?( — [^\n,]+)?(, \d{4})?( \(\d{1,2}/10\))?")


def test_the_prompt_carries_titles_creators_years_and_scores_only() -> None:
    profile = TasteProfile(
        item_type=BOOK,
        top_scored=(TasteEntry("Bestiario", 1951, "Julio Cortázar", 9),),
        recent_finishes=(TasteEntry("Aura", 1962, "Carlos Fuentes", 7),),
        dismissed=(TasteEntry("Cien años de soledad", 1967, "Gabriel García Márquez"),),
        waiting=(TasteEntry("2666", 2004, "Roberto Bolaño"),),
    )
    system, prompt = build_prompt(_seed(), profile, 8)
    assert "books" in system and "author" in system and "at most 8" in system
    assert "Rayuela — Julio Cortázar, 1963" in prompt
    assert "Bestiario — Julio Cortázar, 1951 (9/10)" in prompt
    assert "Cien años de soledad — Gabriel García Márquez, 1967" in prompt
    assert "2666 — Roberto Bolaño, 2004" in prompt
    # Nothing else of the seed: not its identifiers, not its metadata.
    assert "9788437604572" not in prompt + system
    assert "PRIVATE" not in prompt + system
    for line in prompt.splitlines():
        if line.startswith("- "):
            assert _ALLOWED_LINE.fullmatch(line), line


def test_a_profile_round_says_so() -> None:
    _system, prompt = build_prompt(
        Seed(item_type=BOOK, options={"kind": "books"}),
        TasteProfile(item_type=BOOK, top_scored=(TasteEntry("Bestiario", 1951, None, 9),)),
        8,
    )
    assert prompt.startswith("Suggest books this person would like")
    assert "- Bestiario, 1951 (9/10)" in prompt


# --- Configuration -------------------------------------------------------------------------


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


@pytest.mark.parametrize(
    ("extra", "kind", "model"),
    [
        ({"ANTHROPIC_API_KEY": KEY}, AnthropicClient, "claude-haiku-5-5"),
        ({"recs_model_key": KEY}, AnthropicClient, "claude-haiku-5-5"),
        (
            {"recs_model_provider": "gemini", "GEMINI_API_KEY": KEY},
            GeminiClient,
            "gemini-2.5-flash",
        ),
        (
            {"recs_model_provider": "openai", "recs_model_key": KEY, "recs_model": "gpt-x"},
            OpenAICompatibleClient,
            "gpt-x",
        ),
    ],
)
def test_the_provider_is_chosen_by_configuration(
    tmp_path: Path, extra: dict[str, Any], kind: type, model: str
) -> None:
    registry = build_source_registry(_settings(tmp_path, **extra), create_provider_client())
    source = registry.get("model")
    assert isinstance(source, ModelRecommendations)
    assert isinstance(source.client, kind)
    assert source.client.model == model
    described = registry.describe("model")
    assert described["configured"] is True
    assert described["resolved_only"] is True
    assert described["about"]["model"] == model
    assert described["about"]["sends"] == SENDS
    assert KEY not in json.dumps(described)


def test_a_key_for_another_provider_does_not_configure_this_one(tmp_path: Path) -> None:
    registry = build_source_registry(
        _settings(tmp_path, recs_model_provider="gemini", ANTHROPIC_API_KEY=KEY),
        create_provider_client(),
    )
    found = registry.get("model")
    assert isinstance(found, NotConfigured)
    assert "AKASHA_RECS_MODEL_KEY" in found.hint
    assert found.about is not None and found.about["provider_label"] == "Gemini"


def test_every_domain_declares_the_model_after_its_own_sources() -> None:
    # The library's own embeddings follow the model (Sprint 136).
    movie, series = DOMAINS["movie"].recommendation, DOMAINS["series"].recommendation
    assert movie is not None and movie.sources == ("tmdb", "model", "library")
    assert series is not None and series.sources == ("tmdb", "model", "library")
    for item_type in ("book", "anime", "album"):
        spec = DOMAINS[item_type].recommendation
        assert spec is not None and spec.sources == ("model", "library")
        assert spec.source_options["model"]["kind"]


def test_an_albums_want_goes_on_the_wishlist() -> None:
    assert want_status(DOMAINS["album"]) == "wishlist"
    assert want_status(DOMAINS["book"]) == "to_read"
    assert want_status(DOMAINS["anime"]) == "plan_to_watch"


def test_every_model_fixture_is_marked_unrecorded_or_recorded() -> None:
    sidecar = json.loads((FIXTURES / "model_fixtures.json").read_text(encoding="utf-8"))
    for name, row in sidecar["files"].items():
        assert (FIXTURES / name).is_file(), name
        assert isinstance(row["recorded"], bool)
        assert "sk-" not in (FIXTURES / name).read_text(encoding="utf-8")


# --- A round, end to end -------------------------------------------------------------------

OL_SEARCHES = {
    "Pedro Páramo Juan Rulfo": "openlibrary_search_pedro_paramo.json",
    "Ficciones Jorge Luis Borges": "openlibrary_search_ficciones.json",
    "Los detectives salvajes Roberto Bolaño": "openlibrary_search_los_detectives_salvajes.json",
    "El jardín de los espejos quietos Aurelio Benavídez": (
        "openlibrary_search_invented_jardin.json"
    ),
}


def _open_library(asked: list[str]) -> OpenLibraryProvider:
    def key(request: httpx.Request) -> str:
        query = request.url.params.get("q", "")
        asked.append(query)
        return f"{request.url.path}?q={query}"

    routes = {f"/search.json?q={q}": (200, recording(name)) for q, name in OL_SEARCHES.items()}
    return OpenLibraryProvider(
        create_provider_client(replay(routes, key=key)), "test@example.invalid"
    )


@asynccontextmanager
async def _app(
    tmp_path: Path, model: Model | None, asked: list[str], **extra: Any
) -> AsyncIterator[tuple[Any, httpx.AsyncClient]]:
    app = create_app(_settings(tmp_path, **extra))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        app.state.job_runner.handlers[RECOMMEND_JOB].enricher.cover_client = None
        app.state.providers.clear()
        app.state.providers["openlibrary"] = _open_library(asked)
        if model is not None:
            app.state.recommendation_sources.register(model.source)
        yield app, client


async def _run_jobs(app: Any) -> None:
    repo = JobRepository(app.state.engine)
    handlers = app.state.job_runner.handlers
    while (claimed := repo.claim(datetime.now(UTC))) is not None:
        result = await handlers[claimed.kind].process(claimed.id, datetime.now(UTC))
        assert result["state"] == "succeeded", result
        repo.complete(claimed.id, result.get("progress", {}), datetime.now(UTC))


def _book(app: Any, title: str, year: int, creator: str, **entry: Any) -> int:
    result = DomainRepository(app.state.engine, 1).create_cached_entry(
        title=title,
        subtitle=None,
        year=year,
        metadata={"creators": [creator], "description": "PRIVATE-DESCRIPTION"},
        identifiers=[normalize_identifier("isbn13", "9788437604572")] if title == "Rayuela" else [],
        sources=[SourceIdentity("openlibrary", f"OL-{title}", True)],
        status=entry.pop("status", "read"),
        score=entry.pop("score", None),
        item_type=BOOK,
    )
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE entries SET notes = 'PRIVATE-NOTE', location = 'PRIVATE-SHELF',"
                " date_finished = '2026-10-01' WHERE id = :id"
            ),
            {"id": result.entry_id},
        )
    return result.entry_id


@pytest.mark.anyio
@pytest.mark.parametrize("provider", sorted(PROVIDERS))
async def test_a_book_seed_yields_resolved_picks_and_drops_an_invented_one(
    tmp_path: Path, provider: str
) -> None:
    asked: list[str] = []
    model = Model(provider)
    async with _app(tmp_path, model, asked) as (app, client):
        seed = _book(app, "Rayuela", 1963, "Julio Cortázar", score=9)
        _book(app, "Bestiario", 1951, "Julio Cortázar", score=8)
        queued = await client.post(f"/api/entries/{seed}/more-like-this?source=model")
        assert queued.status_code == 202, queued.text
        assert queued.json()["source"] == "model"
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{queued.json()['id']}")).json()
        listed = (await client.get("/api/suggestions")).json()
    assert body["status"] == "done", body
    states = {row["title"]: row["enrichment"] for row in body["suggestions"]}
    assert states == {
        "Pedro Páramo": "enriched",
        "Ficciones": "enriched",
        "Los detectives salvajes": "enriched",
        # A title no provider knows: stored, never shown.
        "El jardín de los espejos quietos": "unresolved",
    }
    # Every pick was looked up (not only the first three), by title and author.
    assert sorted(asked) == sorted(OL_SEARCHES)
    first = body["suggestions"][0]
    assert first["reason"] == {
        "signal": "model",
        "text": "Another Latin American novel that breaks time apart, as Rayuela does.",
    }
    assert first["item_id"] is not None
    assert {row["title"] for row in listed} == {
        "Pedro Páramo",
        "Ficciones",
        "Los detectives salvajes",
    }
    # What was sent: titles, creators, years and scores of this library, nothing else.
    (sent,) = model.requests
    payload = sent.content.decode()
    assert "Rayuela" in payload and "Bestiario" in payload and "(8/10)" in payload
    for private in ("PRIVATE", "9788437604572", "2026-10-01", "OL-Rayuela"):
        assert private not in payload


@pytest.mark.anyio
async def test_a_malformed_reply_fails_the_round_with_its_reason(tmp_path: Path) -> None:
    asked: list[str] = []
    model = Model(
        "anthropic", {"/v1/messages": (200, recording("model_anthropic_messages_prose.json"))}
    )
    async with _app(tmp_path, model, asked) as (app, client):
        seed = _book(app, "Rayuela", 1963, "Julio Cortázar")
        queued = await client.post(f"/api/entries/{seed}/more-like-this?source=model")
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{queued.json()['id']}")).json()
    assert body["status"] == "failed"
    assert body["error"] == "Claude answered something other than the list it was asked for"
    assert body["suggestions"] == []
    assert asked == []


@pytest.mark.anyio
async def test_without_a_key_the_source_says_how_and_nothing_fails(tmp_path: Path) -> None:
    async with _app(tmp_path, None, []) as (app, client):
        seed = _book(app, "Rayuela", 1963, "Julio Cortázar")
        types = {row["id"]: row for row in (await client.get("/api/item-types")).json()}
        queued = await client.post(f"/api/entries/{seed}/more-like-this?source=model")
        job = JobRepository(app.state.engine).claim(datetime.now(UTC))
    source, _library = types["book"]["recommendation"]["sources"]
    assert source["name"] == "model" and source["label"] == "Model"
    assert source["configured"] is False
    assert "AKASHA_RECS_MODEL_KEY" in source["hint"]
    assert source["resolved_only"] is True
    assert source["about"]["model"] == "claude-haiku-5-5"
    assert types["book"]["recommendation"]["attribution"] == {}
    assert [row["name"] for row in types["movie"]["recommendation"]["sources"]] == [
        "tmdb",
        "model",
        "library",
    ]
    assert queued.status_code == 202
    assert queued.json()["status"] == "not_configured"
    assert job is None


@pytest.mark.anyio
async def test_the_key_never_reaches_a_log_line(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.DEBUG)
    asked: list[str] = []
    ok = Model("anthropic")
    refused = Model(
        "anthropic", {"/v1/messages": (401, recording("model_anthropic_error_401.json"))}
    )
    async with _app(tmp_path, ok, asked, ANTHROPIC_API_KEY=KEY) as (app, client):
        seed = _book(app, "Rayuela", 1963, "Julio Cortázar")
        first = await client.post(f"/api/entries/{seed}/more-like-this?source=model")
        await _run_jobs(app)
        app.state.recommendation_sources.register(refused.source)
        second = await client.post(f"/api/entries/{seed}/more-like-this?source=model&refresh=true")
        await _run_jobs(app)
        rounds = [
            (await client.get(f"/api/suggestion-rounds/{row.json()['id']}")).json()
            for row in (first, second)
        ]
        types = (await client.get("/api/item-types")).text
    assert rounds[0]["status"] == "done"
    assert rounds[1]["status"] == "failed" and "refused the key" in rounds[1]["error"]
    out, err = capfd.readouterr()
    for written in (caplog.text, out, err, json.dumps(rounds), types):
        assert KEY not in written


@pytest.mark.anyio
async def test_a_spent_budget_stops_further_calls(tmp_path: Path) -> None:
    asked: list[str] = []
    model = Model("anthropic")
    async with _app(tmp_path, model, asked, recommend_daily_limits={"model": 1}) as (app, client):
        seed = _book(app, "Rayuela", 1963, "Julio Cortázar")
        first = await client.post(f"/api/entries/{seed}/more-like-this?source=model")
        await _run_jobs(app)
        second = await client.post(f"/api/entries/{seed}/more-like-this?source=model&refresh=true")
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{second.json()['id']}")).json()
    assert first.json()["id"] != second.json()["id"]
    assert body["status"] == "over_budget"
    assert "1 rounds for today" in body["error"]
    assert len(model.requests) == 1


@pytest.mark.anyio
async def test_the_model_is_held_to_fifty_rounds_a_day_unless_configured(tmp_path: Path) -> None:
    assert DEFAULT_RECOMMEND_LIMITS == {"model": 50}
    async with _app(tmp_path, None, []) as (app, _client):
        quota = app.state.job_runner.handlers[RECOMMEND_JOB].round_quota
        assert quota.limits[budget_key("model")] == 50
    async with _app(tmp_path, None, [], recommend_daily_limits={"model": 5}) as (app, _client):
        quota = app.state.job_runner.handlers[RECOMMEND_JOB].round_quota
        assert quota.limits[budget_key("model")] == 5


# --- A film's year differs between providers --------------------------------------------


def _record(title: str, year: int | None, *creators: str) -> SearchCandidate:
    return SearchCandidate(
        source="cinemeta",
        source_id="tt0",
        source_refs=(),
        title=title,
        subtitle=None,
        creators=creators,
        year=year,
        cover_url=None,
        identifiers={},
        language=None,
        metadata={},
    )


def test_an_agreeing_director_admits_a_later_release_year() -> None:
    """Observed in the walkthrough: Cinemeta dates Kurosawa's films by their US
    release (*Red Beard* 1968, *The Hidden Fortress* 1960), so the model's true
    years (1965, 1958) left both unresolved and unshown."""
    assert same_work(
        Candidate("Red Beard", 1965, "Akira Kurosawa"), _record("Red Beard", 1968, "Akira Kurosawa")
    )
    assert same_work(
        Candidate("The Hidden Fortress", 1958, "Akira Kurosawa"),
        _record("The Hidden Fortress", 1960, "Akira Kurosawa"),
    )
    # Without a creator to agree on, one year is all the slack there is.
    assert not same_work(Candidate("Red Beard", 1965), _record("Red Beard", 1968, "Akira Kurosawa"))
    assert not same_work(Candidate("Red Beard", 1965), _record("Red Beard", 1968))
    # A creator who disagrees is another work, whatever the year.
    assert not same_work(
        Candidate("Red Beard", 1968, "Akira Kurosawa"),
        _record("Red Beard", 1968, "Kazuyoshi Yoshikawa"),
    )
    # A remake decades on is not the same work, director or not.
    assert not same_work(
        Candidate("The Hidden Fortress", 1958, "Akira Kurosawa"),
        _record("The Hidden Fortress", 2001, "Akira Kurosawa"),
    )


class _Answers:
    """A provider of the library that answers a search with what it was given."""

    def __init__(self, name: str, rows: list[SearchCandidate] | Exception) -> None:
        self.name = name
        self.item_type = "movie"
        self.rows = rows

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows


@pytest.mark.anyio
async def test_a_provider_that_failed_leaves_a_pick_to_try_again_not_unresolved() -> None:
    """`unresolved` means every provider answered and none knew it; one that failed
    may have been the one that did (Cinemeta, after Wikidata's Spanish labels)."""
    resolve = resolve_by_identity_or_search()
    pick = Candidate("Red Beard", 1965, "Akira Kurosawa")
    other = _Answers("wikidata", [_record("Barbarroja", 1965, "Akira Kurosawa")])
    with pytest.raises(httpx.ReadTimeout):
        await resolve(
            pick, {"wikidata": other, "cinemeta": _Answers("cinemeta", httpx.ReadTimeout("slow"))}
        )
    # Every provider answered and none knew it: unresolved.
    assert await resolve(pick, {"wikidata": other}) is None
    # A failure before a provider that knows it does not matter.
    found = await resolve(
        pick,
        {
            "cinemeta": _Answers("cinemeta", httpx.ReadTimeout("slow")),
            "wikidata": _Answers("wikidata", [_record("Red Beard", 1968, "Akira Kurosawa")]),
        },
    )
    assert found is not None and found.year == 1968


def test_the_seed_is_named_once_with_its_works_first_year() -> None:
    """Observed in the walkthrough: Rayuela's item is a 2000 edition, and it was
    sent as "Rayuela — Julio Cortázar, 2000", twice (as the seed and as a score)."""
    seed = Seed(
        item_type=BOOK,
        entry_id=1,
        title="Rayuela",
        year=2000,
        creators=("Julio Cortázar",),
        metadata={"original_year": 1963, "description": "PRIVATE-DESCRIPTION"},
        options={"kind": "books", "creator": "author"},
    )
    profile = TasteProfile(
        item_type=BOOK,
        top_scored=(
            TasteEntry("Rayuela", 1963, "Julio Cortázar", 9),
            TasteEntry("Bestiario", 1951, "Julio Cortázar", 8),
        ),
    )
    _system, prompt = build_prompt(seed, profile, 8)
    assert prompt.count("Rayuela") == 1
    assert "- Rayuela — Julio Cortázar, 1963" in prompt
    assert "- Bestiario — Julio Cortázar, 1951 (8/10)" in prompt
    assert "2000" not in prompt and "PRIVATE" not in prompt


@pytest.mark.anyio
async def test_the_profile_carries_a_works_first_year(tmp_path: Path) -> None:
    from book_tracker.application.recommendations import taste_profile

    async with _app(tmp_path, None, []) as (app, _client):
        DomainRepository(app.state.engine, 1).create_cached_entry(
            title="Rayuela",
            subtitle=None,
            year=2000,
            metadata={"creators": ["Julio Cortázar"], "original_year": 1963},
            identifiers=[],
            sources=[SourceIdentity("openlibrary", "OL1M", True)],
            status="read",
            score=9,
            item_type=BOOK,
        )
        profile = taste_profile(app.state.engine, 1, DOMAINS[BOOK])
    assert [(row.title, row.year) for row in profile.top_scored] == [("Rayuela", 1963)]
