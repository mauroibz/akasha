"""Recommendation infrastructure (Sprint 133, DEC-183 points 4-7).

Seed, select, store, enrich, answer, with the test-only `fake` source standing where
TMDB (134), a hosted model (135) and the library's embeddings (136) will stand. The
domain's resolve runs against recorded Cinemeta responses, never a mock of itself.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from recommendation_fake import FakeSource
from recordings import recording, replay
from sqlalchemy import text

from book_tracker.api.auth import COOKIE_NAME
from book_tracker.app.recommendations import build_source_registry
from book_tracker.application.passwords import hash_password
from book_tracker.application.recommendations import ENRICH_SUGGESTION_JOB, RECOMMEND_JOB
from book_tracker.application.sessions import SessionStore
from book_tracker.config import Settings
from book_tracker.domain.identity import normalize_identifier
from book_tracker.domain.providers import SearchCandidate
from book_tracker.domain.recommendations import (
    Candidate,
    NotConfigured,
    RecommendationSpec,
    Seed,
    SourceError,
    SourceRegistry,
    TasteProfile,
    resolve_by_identity_or_search,
    same_work,
)
from book_tracker.domain.registry import DOMAINS
from book_tracker.domains.movie.cinemeta import CinemetaMovieProvider
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.providers import create_provider_client
from book_tracker.infrastructure.repositories import DomainRepository, SourceIdentity
from book_tracker.main import create_app
from book_tracker.migrations import alembic_config, upgrade

SRC = Path(__file__).parents[1] / "src" / "book_tracker"
FILM = "movie"  # the library the tests seed; the code under test never names one


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# --- Recorded Cinemeta: the domain's providers ------------------------------------------


def _meta(imdb: str, name: str) -> tuple[str, tuple[int, Any]]:
    return f"/meta/movie/{imdb}.json", (200, recording(name))


RECORDED = dict(
    [
        _meta("tt0047478", "cinemeta_meta_movie_tt0047478_seven_samurai.json"),
        _meta("tt0076786", "cinemeta_meta_movie_tt0076786_suspiria_1977.json"),
        _meta("tt0240419", "cinemeta_meta_movie_tt0240419_la_cienaga.json"),
        _meta("tt1034415", "cinemeta_meta_movie_tt1034415_suspiria_2018.json"),
        (
            "/catalog/movie/top/search=Suspiria.json",
            (200, recording("cinemeta_search_suspiria.json")),
        ),
        # The Suspiria search lists three more films nobody recorded; the adapter skips
        # a record that answers 404, which is all these say.
        ("/meta/movie/tt33183038.json", (404, None)),
        ("/meta/movie/tt0804507.json", (404, None)),
        ("/meta/movie/tt0116284.json", (404, None)),
    ]
)


async def _no_sleep(_seconds: float) -> None:
    return None


class Cinemeta:
    """The recorded Cinemeta movie adapter, counting what it was asked."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        transport = replay(
            RECORDED, on_request=lambda request: self.requests.append(request.url.path)
        )
        self.provider = CinemetaMovieProvider(
            create_provider_client(transport), "test@example.invalid", sleep=_no_sleep
        )


def _film_spec(enrich_top: int = 3) -> RecommendationSpec:
    return RecommendationSpec(
        sources=("fake",), resolve=resolve_by_identity_or_search(("imdb",)), enrich_top=enrich_top
    )


@pytest.fixture
def films_suggested(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Films declare the fake source, as Sprint 134 will declare `tmdb`."""
    monkeypatch.setitem(DOMAINS, FILM, replace(DOMAINS[FILM], recommendation=_film_spec()))
    yield


@asynccontextmanager
async def _app(
    tmp_path: Path, **extra: Any
) -> AsyncIterator[tuple[Any, httpx.AsyncClient, Cinemeta, FakeSource]]:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", **extra)
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()  # the tests drive each job themselves
        # Covers would be fetched from the live poster host; nothing here goes out.
        app.state.job_runner.handlers[RECOMMEND_JOB].enricher.cover_client = None
        cinemeta = Cinemeta()
        app.state.providers.clear()
        app.state.providers["cinemeta"] = cinemeta.provider
        fake = FakeSource()
        app.state.recommendation_sources.register(fake)
        yield app, client, cinemeta, fake


def _seed_film(app: Any, user_id: int = 1, *, title: str = "Seven Samurai") -> int:
    result = DomainRepository(app.state.engine, user_id).create_cached_entry(
        title=title,
        subtitle=None,
        year=1954,
        metadata={"creators": ["Akira Kurosawa"]},
        identifiers=[normalize_identifier("imdb", "tt0047478")],
        sources=[SourceIdentity("cinemeta", "tt0047478", True)],
        status="watched",
        score=9,
        item_type=FILM,
    )
    return result.entry_id


async def _run_jobs(app: Any) -> list[dict[str, Any]]:
    """Process every queued recommendation job, in order, as the runner would."""
    repo = JobRepository(app.state.engine)
    handlers = app.state.job_runner.handlers
    done = []
    while (claimed := repo.claim(datetime.now(UTC))) is not None:
        result = await handlers[claimed.kind].process(claimed.id, datetime.now(UTC))
        assert result["state"] == "succeeded", result
        repo.complete(claimed.id, result.get("progress", {}), datetime.now(UTC))
        done.append({"kind": claimed.kind, **result})
    return done


def _states(round_body: dict[str, Any]) -> list[tuple[str, str]]:
    return [(row["title"], row["enrichment"]) for row in round_body["suggestions"]]


# --- Domain types -----------------------------------------------------------------------


def test_a_candidate_needs_only_a_title() -> None:
    candidate = Candidate("Stalker")
    assert candidate.year is None and candidate.creator is None
    assert dict(candidate.external_ids) == {} and dict(candidate.display) == {}
    assert candidate.reason == "" and candidate.source_score is None


def test_a_seed_without_an_entry_is_the_profile() -> None:
    assert Seed(item_type=FILM).is_profile
    assert not Seed(item_type=FILM, entry_id=3, title="Seven Samurai").is_profile
    profile = TasteProfile(item_type=FILM)
    assert profile.top_scored == profile.dismissed == profile.waiting == ()


def test_the_registry_reports_a_source_without_its_configuration() -> None:
    registry = SourceRegistry([FakeSource(), NotConfigured("tmdb", "Set TMDB_READ_TOKEN")])
    assert registry.configured("fake")
    assert not registry.configured("tmdb")
    assert isinstance(registry.get("tmdb"), NotConfigured)
    assert registry.get("nothing") is None
    assert set(registry.names()) == {"fake", "tmdb"}


def test_the_registry_is_filled_from_configuration(tmp_path: Path) -> None:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")

    def needs_a_token(settings: Settings, _client: Any) -> Any:
        return NotConfigured("keyed", "Set KEYED_TOKEN to turn it on")

    registry = build_source_registry(configured, None, (needs_a_token, lambda _s, _c: FakeSource()))
    assert registry.configured("fake") and not registry.configured("keyed")
    assert build_source_registry(configured, None).names() == ()


def _record(title: str, year: int | None, creators: tuple[str, ...]) -> SearchCandidate:
    return SearchCandidate(
        source="p", source_id="1", source_refs=(), title=title, subtitle=None,
        creators=creators, year=year, cover_url=None, identifiers={}, language=None, metadata={},
    )  # fmt: skip


@pytest.mark.parametrize(
    ("candidate", "record", "same"),
    [
        (Candidate("La Ciénaga", 2001), _record("la cienaga", 2001, ()), True),
        (Candidate("Suspiria", 2018), _record("Suspiria", 1977, ()), False),
        (Candidate("Suspiria", 1977), _record("Suspiria", 1978, ()), True),
        (
            Candidate("Suspiria", None, "Dario Argento"),
            _record("Suspiria", 2018, ("Luca Guadagnino",)),
            False,
        ),
        (Candidate("Stalker"), _record("Stalker Two", None, ()), False),
    ],
)
def test_a_record_is_the_same_work_only_when_nothing_disagrees(
    candidate: Candidate, record: SearchCandidate, same: bool
) -> None:
    assert same_work(candidate, record) is same


# --- AC1: select, store, enrich exactly the top three -----------------------------------


@pytest.mark.anyio
async def test_a_round_selects_stores_and_enriches_exactly_the_top_three(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, cinemeta, fake):
        entry_id = _seed_film(app)
        started = await client.post(f"/api/entries/{entry_id}/more-like-this")
        assert started.status_code == 202, started.text
        assert started.json()["status"] == "queued"
        round_id = started.json()["id"]
        jobs = await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{round_id}")).json()

    assert [job["kind"] for job in jobs] == [RECOMMEND_JOB]
    assert len(fake.calls) == 1, "the source is asked once per round"
    seed, profile, limit = fake.calls[0]
    assert (seed.title, seed.entry_id, seed.external_ids["imdb"]) == (
        "Seven Samurai",
        entry_id,
        "tt0047478",
    )
    assert [row.title for row in profile.top_scored] == ["Seven Samurai"]
    assert limit == 12
    assert body["status"] == "done" and body["error"] is None
    assert body["seed_entry_id"] == entry_id and body["source"] == "fake"
    # The seed itself and the second mention of Suspiria (1977) were dropped on the way in.
    assert _states(body) == [
        ("Suspiria", "enriched"),
        ("La Ciénaga", "enriched"),
        ("Suspiria", "enriched"),
        ("Rashomon", "pending"),
        ("Ikiru", "pending"),
        ("Suspiria", "pending"),
        ("Stalker", "pending"),
    ]
    first = body["suggestions"][0]
    assert first["reason"] == {"signal": "fake", "text": "Often watched together"}
    assert first["display"] == {"poster": "https://images.metahub.space/poster/small/tt0076786/img"}
    assert first["external_ids"] == {"imdb": "tt0076786"} and first["source_score"] == 0.91
    # Only the top three cost a provider request: two by IMDb id, one by title search.
    assert all("tt0042876" not in path and "tt0044741" not in path for path in cinemeta.requests)
    assert cinemeta.requests[:2] == ["/meta/movie/tt0076786.json", "/meta/movie/tt0240419.json"]
    assert "/catalog/movie/top/search=Suspiria.json" in cinemeta.requests
    with app.state.engine.connect() as connection:
        items = connection.execute(
            text(
                "SELECT i.title, i.year FROM suggestions s JOIN items i ON i.id = s.item_id"
                " ORDER BY s.id"
            )
        ).all()
        entries = connection.execute(text("SELECT count(*) FROM entries")).scalar()
    # Cached as shared items, nobody's entries: the 2018 one by its search, not the 1977.
    assert [tuple(row) for row in items] == [
        ("Suspiria", 1977),
        ("The Swamp", 2001),
        ("Suspiria", 2018),
    ]
    assert entries == 1


@pytest.mark.anyio
async def test_round_progress_reaches_the_event_stream(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, _cinemeta, _fake):
        entry_id = _seed_film(app)
        round_id = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()["id"]
        await _run_jobs(app)
        changes = JobRepository(app.state.engine).changes_for_user(1, since=None)
    recommend = [job for job in changes if job["kind"] == RECOMMEND_JOB]
    assert len(recommend) == 1
    assert recommend[0]["progress"] == {
        "round_id": round_id,
        "status": "done",
        "error": None,
        "stored": 7,
        "dropped": 2,
        "enriched": 3,
    }


@pytest.mark.anyio
async def test_pressing_it_again_shows_the_last_round_unless_refreshed(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, _cinemeta, fake):
        entry_id = _seed_film(app)
        first = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()
        await _run_jobs(app)
        again = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()
        fresh = (await client.post(f"/api/entries/{entry_id}/more-like-this?refresh=true")).json()
        await _run_jobs(app)
    assert again["id"] == first["id"] and again["status"] == "done"
    assert len(again["suggestions"]) == 7
    assert fresh["id"] != first["id"] and fresh["status"] == "queued"
    assert len(fake.calls) == 2


@pytest.mark.anyio
async def test_one_more_is_enriched_when_someone_opens_it(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, cinemeta, _fake):
        entry_id = _seed_film(app)
        round_id = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()["id"]
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{round_id}")).json()
        invented = next(
            row
            for row in body["suggestions"]
            if row["year"] == 1950 and row["creator"] == "Nobody At All"
        )
        enriched = body["suggestions"][0]
        before = len(cinemeta.requests)
        queued = await client.post(f"/api/suggestions/{invented['id']}/enrich")
        nothing = await client.post(f"/api/suggestions/{enriched['id']}/enrich")
        jobs = await _run_jobs(app)
        after = (await client.get(f"/api/suggestion-rounds/{round_id}")).json()
        shown = (await client.get(f"/api/suggestions?seed_entry_id={entry_id}")).json()
    assert queued.status_code == 202 and queued.json()["job_id"]
    assert nothing.status_code == 200 and nothing.json()["job_id"] is None
    assert [job["kind"] for job in jobs] == [ENRICH_SUGGESTION_JOB]
    assert jobs[0]["progress"]["enrichment"] == "unresolved"
    assert len(cinemeta.requests) > before
    state = {row["id"]: row["enrichment"] for row in after["suggestions"]}
    assert state[invented["id"]] == "unresolved"
    # An unresolved candidate is never shown.
    assert invented["id"] not in {row["id"] for row in shown}
    assert len(shown) == 6


# --- Store-time filtering ---------------------------------------------------------------


@pytest.mark.anyio
async def test_what_the_library_already_holds_is_dropped_on_the_way_in(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, _cinemeta, _fake):
        entry_id = _seed_film(app)
        repository = DomainRepository(app.state.engine, 1)
        # By identity (Stalker's IMDb id), and by title with a creator that agrees.
        for title, creator, ids in (
            ("Stalker", "Andrei Tarkovsky", [normalize_identifier("imdb", "tt0079944")]),
            ("Rashomon", "Akira Kurosawa", []),
        ):
            repository.create_cached_entry(
                title=title, subtitle=None, year=None, metadata={"creators": [creator]},
                identifiers=ids, sources=[], status="watchlist", score=None, item_type=FILM,
            )  # fmt: skip
        round_id = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()["id"]
        jobs = await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{round_id}")).json()
    titles = [row["title"] for row in body["suggestions"]]
    assert "Stalker" not in titles and "Rashomon" not in titles
    assert jobs[0]["progress"]["dropped"] == 4


# --- AC2: budgets -----------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_source_over_its_daily_budget_stops_and_records_why(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path, recommend_daily_limits={"fake": 1}) as (app, client, _c, fake):
        entry_id = _seed_film(app)
        await client.post(f"/api/entries/{entry_id}/more-like-this")
        await _run_jobs(app)
        second = (await client.post(f"/api/entries/{entry_id}/more-like-this?refresh=true")).json()
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{second['id']}")).json()
        # A refused round is not shown again in place of asking.
        third = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()
    assert len(fake.calls) == 1
    assert body["status"] == "over_budget"
    assert (
        body["error"] == "fake has answered its 1 rounds for today; it answers again tomorrow (UTC)"
    )
    assert body["suggestions"] == [] and body["finished_at"]
    assert third["id"] != second["id"]


@pytest.mark.anyio
async def test_no_provider_request_exceeds_its_quota(tmp_path: Path, films_suggested: None) -> None:
    async with _app(tmp_path, provider_daily_limits={"cinemeta": 1}) as (app, client, cinemeta, _f):
        entry_id = _seed_film(app)
        round_id = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()["id"]
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{round_id}")).json()
        later = (
            await client.post(f"/api/suggestions/{body['suggestions'][1]['id']}/enrich")
        ).json()
        jobs = await _run_jobs(app)
        used = app.state.provider_quota.used("cinemeta", datetime.now(UTC))
    assert cinemeta.requests == ["/meta/movie/tt0076786.json"]
    assert used == 1
    assert _states(body)[:3] == [
        ("Suspiria", "enriched"),
        ("La Ciénaga", "pending"),
        ("Suspiria", "pending"),
    ]
    assert body["status"] == "done"
    assert (
        body["error"]
        == "cinemeta is out of requests for today; the rest wait until someone opens them"
    )
    assert later["job_id"] and jobs[0]["progress"]["enrichment"] == "pending"
    assert "out of requests" in jobs[0]["progress"]["error"]


# --- Sources that fail or are missing ---------------------------------------------------


class _Refusing:
    name = "fake"

    async def select(self, seed: Seed, profile: TasteProfile, limit: int) -> list[Candidate]:
        raise SourceError("The reply was not the JSON asked for")


@pytest.mark.anyio
async def test_a_failing_source_fails_its_round_with_the_reason(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, cinemeta, _fake):
        app.state.recommendation_sources.register(_Refusing())
        entry_id = _seed_film(app)
        round_id = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()["id"]
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{round_id}")).json()
    assert body["status"] == "failed"
    assert body["error"] == "The reply was not the JSON asked for"
    assert cinemeta.requests == []


@pytest.mark.anyio
async def test_a_source_without_its_configuration_says_so_and_nothing_fails(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, _cinemeta, _fake):
        app.state.recommendation_sources.register(
            NotConfigured("fake", "Set FAKE_TOKEN to turn it on")
        )
        entry_id = _seed_film(app)
        started = await client.post(f"/api/entries/{entry_id}/more-like-this")
        jobs = await _run_jobs(app)
    assert started.status_code == 202
    assert started.json()["status"] == "not_configured"
    assert started.json()["error"] == "Set FAKE_TOKEN to turn it on"
    assert jobs == []


@pytest.mark.anyio
async def test_a_library_nothing_suggests_refuses_more_like_this(tmp_path: Path) -> None:
    async with _app(tmp_path) as (app, client, _cinemeta, _fake):
        entry_id = _seed_film(app)
        refused = await client.post(f"/api/entries/{entry_id}/more-like-this")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "no_recommendation_source"


@pytest.mark.anyio
async def test_a_source_the_library_does_not_declare_is_refused(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, _cinemeta, _fake):
        entry_id = _seed_film(app)
        refused = await client.post(f"/api/entries/{entry_id}/more-like-this?source=tmdb")
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "unknown_recommendation_source"


# --- AC3: answers -----------------------------------------------------------------------


@pytest.mark.anyio
async def test_want_adds_a_planned_entry(tmp_path: Path, films_suggested: None) -> None:
    async with _app(tmp_path) as (app, client, _cinemeta, _fake):
        entry_id = _seed_film(app)
        round_id = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()["id"]
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{round_id}")).json()
        wanted = await client.patch(
            f"/api/suggestions/{body['suggestions'][0]['id']}", json={"answer": "want"}
        )
        entry = await client.get(f"/api/entries/{wanted.json()['entry_id']}")
        twice = await client.patch(
            f"/api/suggestions/{body['suggestions'][0]['id']}", json={"answer": "want"}
        )
        pending = await client.patch(
            f"/api/suggestions/{body['suggestions'][3]['id']}", json={"answer": "want"}
        )
        shown = (await client.get("/api/suggestions")).json()
        with app.state.engine.connect() as connection:
            entries = connection.execute(text("SELECT count(*) FROM entries")).scalar()
    assert wanted.status_code == 200, wanted.text
    assert wanted.json()["answer"] == "want" and wanted.json()["answered_at"]
    assert entry.json()["status"] == "watchlist"
    assert entry.json()["item"]["title"] == "Suspiria"
    assert twice.json()["entry_id"] == wanted.json()["entry_id"]
    assert entries == 2
    assert pending.status_code == 409
    assert pending.json()["error"]["code"] == "suggestion_not_resolved"
    assert body["suggestions"][0]["id"] not in {row["id"] for row in shown}


@pytest.mark.anyio
async def test_not_for_me_hides_the_candidate_from_later_rounds(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, _cinemeta, fake):
        entry_id = _seed_film(app)
        first = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{first['id']}")).json()
        stalker = next(row for row in body["suggestions"] if row["title"] == "Stalker")
        rashomon = next(row for row in body["suggestions"] if row["title"] == "Rashomon")
        no = await client.patch(f"/api/suggestions/{stalker['id']}", json={"answer": "not_for_me"})
        seen = await client.patch(f"/api/suggestions/{rashomon['id']}", json={"answer": "seen"})
        shown = (await client.get(f"/api/suggestions?item_type={FILM}")).json()
        second = (await client.post(f"/api/entries/{entry_id}/more-like-this?refresh=true")).json()
        await _run_jobs(app)
        again = (await client.get(f"/api/suggestion-rounds/{second['id']}")).json()
        taken_back = await client.patch(f"/api/suggestions/{rashomon['id']}", json={"answer": None})
        bad = await client.patch(f"/api/suggestions/{rashomon['id']}", json={"answer": "maybe"})
    assert no.json()["answer"] == "not_for_me" and seen.json()["answer"] == "seen"
    assert {stalker["id"], rashomon["id"]}.isdisjoint({row["id"] for row in shown})
    assert "Stalker" not in [row["title"] for row in again["suggestions"]]
    assert "Rashomon" in [row["title"] for row in again["suggestions"]]
    # The next round's source is told what was turned down.
    assert [row.title for row in fake.calls[1][1].dismissed] == ["Stalker"]
    assert taken_back.json()["answer"] is None and taken_back.json()["answered_at"] is None
    assert bad.status_code == 422


# --- AC4: per user ----------------------------------------------------------------------


def _second_person(app: Any) -> str:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    credential = hash_password("second person's password")
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
                "created_at,updated_at) VALUES (2,'bruno','Bruno',:digest,:salt,0,:now,:now)"
            ),
            {"digest": credential.digest, "salt": credential.salt, "now": now},
        )
    return SessionStore(app.state.engine).create(2).token


@pytest.mark.anyio
async def test_rounds_and_suggestions_are_each_persons_own(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path, auth="on") as (app, client, _cinemeta, _fake):
        bruno = _second_person(app)
        admin = SessionStore(app.state.engine).create(1).token
        mine = _seed_film(app, 1)
        theirs = _seed_film(app, 2)
        client.cookies.set(COOKIE_NAME, admin)
        round_id = (await client.post(f"/api/entries/{mine}/more-like-this")).json()["id"]
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{round_id}")).json()
        first = body["suggestions"][0]["id"]

        client.cookies.set(COOKIE_NAME, bruno)
        refused = {
            "seed": await client.post(f"/api/entries/{mine}/more-like-this"),
            "round": await client.get(f"/api/suggestion-rounds/{round_id}"),
            "answer": await client.patch(f"/api/suggestions/{first}", json={"answer": "want"}),
            "enrich": await client.post(f"/api/suggestions/{first}/enrich"),
        }
        listed = (await client.get("/api/suggestions")).json()
        # Their own round on the same film stands on its own: nothing of mine is dropped
        # from it, and my answers do not reach it.
        own = (await client.post(f"/api/entries/{theirs}/more-like-this")).json()
        await _run_jobs(app)
        own_body = (await client.get(f"/api/suggestion-rounds/{own['id']}")).json()

        client.cookies.set(COOKIE_NAME, admin)
        still_mine = (await client.get("/api/suggestions")).json()
        client.cookies.clear()
        anonymous = await client.get("/api/suggestions")
    assert {name: response.status_code for name, response in refused.items()} == {
        "seed": 404,
        "round": 404,
        "answer": 404,
        "enrich": 404,
    }
    assert listed == []
    assert own_body["status"] == "done" and len(own_body["suggestions"]) == 7
    assert {row["id"] for row in still_mine}.isdisjoint(
        {row["id"] for row in own_body["suggestions"]}
    )
    assert anonymous.status_code == 401


# --- AC5: no branch on the item type; reading costs no provider call ---------------------


class _Exploding:
    name = "cinemeta"
    item_type = FILM

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"a read called the provider's {name}")


@pytest.mark.anyio
async def test_reading_suggestions_calls_no_provider_and_no_source(
    tmp_path: Path, films_suggested: None
) -> None:
    async with _app(tmp_path) as (app, client, _cinemeta, fake):
        entry_id = _seed_film(app)
        round_id = (await client.post(f"/api/entries/{entry_id}/more-like-this")).json()["id"]
        await _run_jobs(app)
        app.state.providers["cinemeta"] = _Exploding()
        calls = len(fake.calls)
        reads = [
            await client.get(f"/api/suggestion-rounds/{round_id}"),
            await client.get("/api/suggestions"),
            await client.get(f"/api/suggestions?seed_entry_id={entry_id}&item_type={FILM}&limit=3"),
            await client.post(f"/api/entries/{entry_id}/more-like-this"),
            await client.get("/api/home"),
        ]
        queued = JobRepository(app.state.engine).claim(datetime.now(UTC))
    assert [response.status_code for response in reads] == [200, 200, 200, 202, 200]
    assert len(reads[2].json()) == 3
    assert len(fake.calls) == calls
    assert queued is None


def test_the_shared_recommendation_layers_never_name_a_domain() -> None:
    names = "|".join(re.escape(name) for name in DOMAINS)
    literal = re.compile(rf"""["']({names})["']""")
    branch = re.compile(r"item_type\s*[!=]=\s*[\"']")
    for path in (
        SRC / "domain" / "recommendations.py",
        SRC / "application" / "recommendations.py",
        SRC / "api" / "suggestions.py",
        SRC / "app" / "recommendations.py",
    ):
        source = path.read_text(encoding="utf-8")
        assert not branch.search(source), f"{path.name} branches on an item type"
        assert not literal.search(source), f"{path.name} names a domain"


# --- Migration 0037 ---------------------------------------------------------------------


def _tables(database: Path) -> set[str]:
    connection = sqlite3.connect(database)
    try:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    finally:
        connection.close()


def test_0037_upgrades_and_downgrades_on_a_real_shaped_library(tmp_path: Path) -> None:
    from alembic import command

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    database = data_dir / "books.db"
    upgrade(configured.database_url, revision="0036_home_layouts")
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO users (id,username,is_admin,created_at,updated_at)"
        " VALUES (2,'bruno',0,'n','n')"
    )
    for item_id, title in ((1, "Seven Samurai"), (2, "Stalker")):
        connection.execute(
            "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
            " VALUES (?, 'movie', ?, '{}', '{}', 'n', 'n')",
            (item_id, title),
        )
    connection.execute(
        "INSERT INTO entries (id, user_id, item_id, status, date_added, reread_count,"
        " score_provisional, created_at, updated_at)"
        " VALUES (1, 2, 1, 'watched', 'n', 0, 0, 'n', 'n')"
    )
    connection.commit()
    connection.close()
    assert "suggestions" not in _tables(database)

    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    rounds = {row[1] for row in connection.execute("PRAGMA table_info(suggestion_rounds)")}
    assert rounds == {
        "id", "user_id", "item_type", "seed_entry_id", "source", "status", "error",
        "created_at", "finished_at",
    }  # fmt: skip
    columns = {row[1] for row in connection.execute("PRAGMA table_info(suggestions)")}
    assert columns == {
        "id", "round_id", "user_id", "item_type", "title", "year", "creator",
        "external_ids_json", "reason", "source_score", "display_json", "enrichment", "item_id",
        "answer", "answered_at", "created_at",
    }  # fmt: skip
    indexes = {row[1]: row for row in connection.execute("PRAGMA index_list(suggestions)")}
    assert "ix_suggestions_user_type_created" in indexes
    assert [
        row[2] for row in connection.execute("PRAGMA index_info(ix_suggestions_user_type_created)")
    ] == ["user_id", "item_type", "created_at"]
    connection.execute(
        "INSERT INTO suggestion_rounds (id, user_id, item_type, seed_entry_id, source, status,"
        " created_at) VALUES (1, 2, 'movie', 1, 'fake', 'done', 'n')"
    )
    connection.execute(
        "INSERT INTO suggestions (round_id, user_id, item_type, title, item_id, created_at)"
        " VALUES (1, 2, 'movie', 'Stalker', 2, 'n')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO suggestions (round_id, user_id, item_type, title, created_at)"
            " VALUES (9, 2, 'movie', 'Nowhere', 'n')"
        )
    defaults = connection.execute(
        "SELECT enrichment, external_ids_json, display_json, reason, answer FROM suggestions"
    ).fetchone()
    assert defaults == ("pending", "{}", "{}", "", None)
    # The seed's entry and the suggested item can go; the round and suggestion stay.
    connection.execute("DELETE FROM entries WHERE id = 1")
    connection.execute("DELETE FROM items WHERE id = 2")
    assert connection.execute("SELECT seed_entry_id FROM suggestion_rounds").fetchone() == (None,)
    assert connection.execute("SELECT item_id FROM suggestions").fetchone() == (None,)
    # A person deleted takes their rounds and suggestions with them.
    connection.execute("DELETE FROM users WHERE id = 2")
    assert connection.execute("SELECT count(*) FROM suggestions").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM suggestion_rounds").fetchone()[0] == 0
    connection.commit()
    connection.close()

    command.downgrade(alembic_config(configured.database_url), "0036_home_layouts")
    assert {"suggestions", "suggestion_rounds"}.isdisjoint(_tables(database))
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT count(*) FROM items").fetchone()[0] == 1
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()
