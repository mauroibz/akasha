"""TMDB as a recommendation source, and *More like this* on films and series (Sprint 134).

Every TMDB answer here is a recorded real response (`tests/fixtures/providers/tmdb_*`,
captured 2026-11-23 with the owner's read token, which appears in none of them). The
domains' resolve runs against recorded Wikidata responses for the same candidates:
nothing here is a mock of the unit under test (DEC-025).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import httpx
import pytest
from recordings import FIXTURES, recording, replay
from sqlalchemy import text

from book_tracker.app.recommendations import build_source_registry
from book_tracker.application.recommendations import (
    RECOMMEND_JOB,
    prune_expired_suggestions,
    want_status,
)
from book_tracker.config import Settings
from book_tracker.domain.identity import normalize_identifier
from book_tracker.domain.recommendations import (
    Candidate,
    NotConfigured,
    Seed,
    Selection,
    SourceError,
    TasteProfile,
)
from book_tracker.domain.registry import DOMAINS
from book_tracker.domains.movie.providers import WikidataMovieProvider, wikidata_route_key
from book_tracker.domains.series.providers import WikidataSeriesProvider
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.providers import create_provider_client
from book_tracker.infrastructure.repositories import DomainRepository, SourceIdentity
from book_tracker.infrastructure.tmdb_recommendations import (
    TMDB_ATTRIBUTION,
    TmdbRecommendations,
)
from book_tracker.main import create_app

FILM = "movie"
SERIES = "series"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _no_sleep(_seconds: float) -> None:
    return None


# --- Recorded TMDB ------------------------------------------------------------------------

TMDB_ROUTES: dict[str, tuple[int, Any]] = {
    "/3/find/tt0047478": (200, recording("tmdb_find_tt0047478_seven_samurai.json")),
    "/3/find/tt9999999999": (200, recording("tmdb_find_tt9999999999_no_match.json")),
    "/3/movie/346/recommendations": (
        200,
        recording("tmdb_movie_346_recommendations_seven_samurai.json"),
    ),
    "/3/tv/1396/recommendations": (
        200,
        recording("tmdb_tv_1396_recommendations_breaking_bad.json"),
    ),
    "/3/movie/999999999/recommendations": (
        404,
        recording("tmdb_movie_999999999_recommendations_404.json"),
    ),
}


class RecordedTmdb:
    """The TMDB source over recorded answers, keeping what it was asked."""

    def __init__(self, routes: Mapping[str, tuple[int, Any]] = TMDB_ROUTES) -> None:
        self.requests: list[httpx.Request] = []
        transport = replay(routes, on_request=self.requests.append)
        self.source = TmdbRecommendations(create_provider_client(transport), "recorded-token")

    @property
    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


def _seed(item_type: str = FILM, **ids: str) -> Seed:
    titles = {FILM: "Seven Samurai", SERIES: "Breaking Bad"}
    return Seed(
        item_type=item_type,
        entry_id=1,
        item_id=1,
        title=titles[item_type],
        external_ids=ids,
        options={"media": "movie" if item_type == FILM else "tv"},
    )


@pytest.mark.anyio
async def test_a_film_with_a_tmdb_id_costs_one_request() -> None:
    tmdb = RecordedTmdb()
    selection = await tmdb.source.select(_seed(tmdb="346"), TasteProfile(item_type=FILM), 12)
    assert tmdb.paths == ["/3/movie/346/recommendations"]
    assert isinstance(selection, Selection)
    assert dict(selection.seed_ids) == {}
    candidates = list(selection.candidates)
    assert len(candidates) == 12
    first = candidates[0]
    assert (first.title, first.year) == ("47 Ronin", 2013)
    assert dict(first.external_ids) == {"tmdb": "64686"}
    assert first.reason == "TMDB: often watched together"
    assert first.source_score == pytest.approx(6.216)
    assert first.display["overview"].startswith("Kai")
    assert first.display["url"] == "https://www.themoviedb.org/movie/64686"
    # No poster is kept: Akasha shows the cover the domain's own providers found.
    assert "poster_path" not in first.display
    assert [row.title for row in candidates[1:3]] == ["Yojimbo", "After the Rain"]


@pytest.mark.anyio
async def test_the_request_carries_the_token_as_a_bearer_and_nothing_in_the_url() -> None:
    tmdb = RecordedTmdb()
    await tmdb.source.select(_seed(tmdb="346"), TasteProfile(item_type=FILM), 12)
    (request,) = tmdb.requests
    assert request.headers["Authorization"] == "Bearer recorded-token"
    assert "recorded-token" not in str(request.url)


@pytest.mark.anyio
async def test_a_film_with_only_an_imdb_id_is_found_first_and_the_id_is_kept() -> None:
    tmdb = RecordedTmdb()
    selection = await tmdb.source.select(
        _seed(imdb="tt0047478", cinemeta="tt0047478"), TasteProfile(item_type=FILM), 12
    )
    assert tmdb.paths == ["/3/find/tt0047478", "/3/movie/346/recommendations"]
    find = tmdb.requests[0]
    assert dict(parse_qsl(find.url.query.decode())) == {"external_source": "imdb_id"}
    assert dict(selection.seed_ids) == {"tmdb": "346"}
    assert len(selection.candidates) == 12


@pytest.mark.anyio
async def test_a_series_reads_the_tv_recommendations() -> None:
    tmdb = RecordedTmdb()
    selection = await tmdb.source.select(
        _seed(SERIES, tmdb="1396"), TasteProfile(item_type=SERIES), 12
    )
    assert tmdb.paths == ["/3/tv/1396/recommendations"]
    titles = [(row.title, row.year) for row in selection.candidates[:3]]
    assert titles == [("Better Call Saul", 2015), ("Narcos: Mexico", 2018), ("Snowfall", 2017)]
    assert selection.candidates[0].display["url"] == "https://www.themoviedb.org/tv/60059"


@pytest.mark.anyio
async def test_a_limit_below_twelve_is_kept() -> None:
    tmdb = RecordedTmdb()
    selection = await tmdb.source.select(_seed(tmdb="346"), TasteProfile(item_type=FILM), 3)
    assert len(selection.candidates) == 3


@pytest.mark.anyio
async def test_a_seed_tmdb_does_not_know_is_a_source_error() -> None:
    tmdb = RecordedTmdb()
    with pytest.raises(SourceError) as raised:
        await tmdb.source.select(_seed(tmdb="999999999"), TasteProfile(item_type=FILM), 12)
    assert raised.value.code == "not_found"
    assert "Seven Samurai" in str(raised.value)


@pytest.mark.anyio
async def test_an_imdb_id_tmdb_cannot_find_is_a_source_error_after_one_request() -> None:
    tmdb = RecordedTmdb()
    with pytest.raises(SourceError) as raised:
        await tmdb.source.select(_seed(imdb="tt9999999999"), TasteProfile(item_type=FILM), 12)
    assert tmdb.paths == ["/3/find/tt9999999999"]
    assert raised.value.code == "not_found"


@pytest.mark.anyio
async def test_a_seed_without_an_imdb_or_tmdb_id_asks_nothing() -> None:
    tmdb = RecordedTmdb()
    with pytest.raises(SourceError) as raised:
        await tmdb.source.select(_seed(wikidata="Q189540"), TasteProfile(item_type=FILM), 12)
    assert tmdb.paths == []
    assert raised.value.code == "no_identity"


@pytest.mark.anyio
async def test_a_library_that_names_no_tmdb_media_asks_nothing() -> None:
    tmdb = RecordedTmdb()
    seed = Seed(item_type="book", entry_id=1, title="Rayuela", external_ids={"tmdb": "1"})
    with pytest.raises(SourceError) as raised:
        await tmdb.source.select(seed, TasteProfile(item_type="book"), 12)
    assert tmdb.paths == []
    assert raised.value.code == "unsupported"


@pytest.mark.anyio
async def test_a_refused_token_says_so() -> None:
    tmdb = RecordedTmdb(
        {
            "/3/movie/346/recommendations": (
                401,
                {"success": False, "status_code": 7, "status_message": "Invalid API key"},
            )
        }
    )
    with pytest.raises(SourceError) as raised:
        await tmdb.source.select(_seed(tmdb="346"), TasteProfile(item_type=FILM), 12)
    assert raised.value.code == "unauthorized"
    assert "TMDB_READ_TOKEN" in str(raised.value)


def test_the_factory_answers_not_configured_without_a_token(tmp_path: Path) -> None:
    registry = build_source_registry(
        Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid", TMDB_READ_TOKEN=""),
        create_provider_client(),
    )
    found = registry.get("tmdb")
    assert isinstance(found, NotConfigured)
    assert "TMDB_READ_TOKEN" in found.hint
    assert found.retention == timedelta(days=182)


def test_the_factory_builds_the_source_with_a_token(tmp_path: Path) -> None:
    registry = build_source_registry(
        Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid", TMDB_READ_TOKEN="x"),
        create_provider_client(),
    )
    assert registry.configured("tmdb")
    assert isinstance(registry.get("tmdb"), TmdbRecommendations)


def test_the_attribution_is_tmdbs_own_wording() -> None:
    assert TMDB_ATTRIBUTION == (
        "This product uses the TMDB API but is not endorsed or certified by TMDB."
    )


# --- Recorded Wikidata: the domains' own providers ------------------------------------


def _labels_routes(names: list[str]) -> dict[frozenset[str], Any]:
    """A label read is keyed by the ids it asks for, which the recording holds."""
    routes: dict[frozenset[str], Any] = {}
    for name in names:
        body = recording(name)
        routes[frozenset(body["entities"])] = body
    return routes


def _wikidata_transport(
    searches: Mapping[str, str],
    entities: Mapping[str, str],
    labels: list[str],
    requests: list[str],
) -> httpx.MockTransport:
    by_labels = _labels_routes(labels)

    def handler(request: httpx.Request) -> httpx.Response:
        key = wikidata_route_key(request)
        requests.append(key)
        params = dict(parse_qsl(request.url.query.decode()))
        if key.startswith("search:"):
            name = searches.get(params["srsearch"])
        elif key.startswith("entities:"):
            name = entities.get(params["ids"])
        elif key.startswith("labels:"):
            body = by_labels.get(frozenset(params["ids"].split("|")))
            if body is None:
                raise AssertionError(f"no recording for {key}")
            return httpx.Response(200, json=body)
        else:
            name = None
        if name is None:
            raise AssertionError(f"no recording for {key}")
        return httpx.Response(200, json=recording(name))

    return httpx.MockTransport(handler)


FILM_SEARCHES = {
    "haswbstatement:P4947=64686": "wikidata_search_p4947_64686.json",
    "haswbstatement:P4947=11878": "wikidata_search_p4947_11878.json",
    "haswbstatement:P4947=15319": "wikidata_search_p4947_15319.json",
}
FILM_ENTITIES = {
    "Q2816898": "wikidata_entity_Q2816898_47_ronin.json",
    "Q20475": "wikidata_entity_Q20475_yojimbo.json",
    "Q2859045": "wikidata_entity_Q2859045_after_the_rain.json",
}
FILM_LABELS = [
    "wikidata_labels_Q2816898_47_ronin.json",
    "wikidata_labels_Q20475_yojimbo.json",
    "wikidata_labels_Q2859045_after_the_rain.json",
]
SERIES_SEARCHES = {
    "haswbstatement:P4983=60059": "wikidata_series_search_p4983_60059.json",
    "haswbstatement:P4983=80968": "wikidata_series_search_p4983_80968.json",
    "haswbstatement:P4983=71694": "wikidata_series_search_p4983_71694.json",
}
SERIES_ENTITIES = {
    "Q14925221": "wikidata_series_entity_Q14925221_better_call_saul.json",
    "Q55657276": "wikidata_series_entity_Q55657276_narcos_mexico.json",
    "Q28429799": "wikidata_series_entity_Q28429799_snowfall.json",
}
SERIES_LABELS = [
    "wikidata_series_labels_Q14925221_better_call_saul.json",
    "wikidata_series_labels_Q55657276_narcos_mexico.json",
    "wikidata_series_labels_Q28429799_snowfall.json",
]


def test_every_tmdb_recording_is_free_of_the_token() -> None:
    for path in FIXTURES.glob("tmdb_*.json"):
        body = path.read_text(encoding="utf-8")
        assert "Bearer" not in body and "eyJ" not in body, path.name
        json.loads(body)


def _films(requests: list[str]) -> WikidataMovieProvider:
    return WikidataMovieProvider(
        create_provider_client(
            _wikidata_transport(FILM_SEARCHES, FILM_ENTITIES, FILM_LABELS, requests)
        ),
        "test@example.invalid",
        sleep=_no_sleep,
    )


def _series(requests: list[str]) -> WikidataSeriesProvider:
    return WikidataSeriesProvider(
        create_provider_client(
            _wikidata_transport(SERIES_SEARCHES, SERIES_ENTITIES, SERIES_LABELS, requests)
        ),
        "test@example.invalid",
        sleep=_no_sleep,
    )


class _Refusing:
    """A provider of the same library that answers no lookup by TMDB id."""

    def __init__(self, name: str, item_type: str) -> None:
        self.name = name
        self.item_type = item_type
        self.identifier_kinds = frozenset({"imdb"})
        self.calls: list[str] = []

    async def fetch_by_identifier(self, kind: str, value: str) -> Any:
        self.calls.append(f"{kind}:{value}")
        raise AssertionError("asked by a kind it does not answer")

    async def search(self, query: str, limit: int = 20) -> list[Any]:
        self.calls.append(f"search:{query}")
        return []


@pytest.mark.anyio
async def test_a_film_resolves_by_its_tmdb_id_through_wikidata() -> None:
    requests: list[str] = []
    spec = DOMAINS[FILM].recommendation
    assert spec is not None
    refusing = _Refusing("cinemeta", FILM)
    record = await spec.resolve(
        Candidate("47 Ronin", 2013, external_ids={"tmdb": "64686"}),
        {"wikidata": _films(requests), "cinemeta": refusing},
    )
    assert record is not None
    assert (record.title, record.year) == ("47 Ronin", 2013)
    assert record.identifiers["imdb"] == "tt1335975"
    assert requests[0] == "search:haswbstatement:P4947=64686"
    assert refusing.calls == []


@pytest.mark.anyio
async def test_a_series_resolves_by_its_tmdb_id_through_wikidata() -> None:
    requests: list[str] = []
    spec = DOMAINS[SERIES].recommendation
    assert spec is not None
    refusing = _Refusing("tvmaze", SERIES)
    record = await spec.resolve(
        Candidate("Better Call Saul", 2015, external_ids={"tmdb": "60059"}),
        {"wikidata-series": _series(requests), "tvmaze": refusing},
    )
    assert record is not None
    assert record.title == "Better Call Saul"
    assert record.identifiers["imdb"] == "tt3032476"
    assert refusing.calls == []


def test_films_and_series_declare_tmdb_and_want_on_their_list() -> None:
    for item_type, media, want in (
        (FILM, "movie", "watchlist"),
        (SERIES, "tv", "plan_to_watch"),
    ):
        domain = DOMAINS[item_type]
        spec = domain.recommendation
        assert spec is not None
        # TMDB first; the hosted model second (Sprint 135).
        assert spec.sources == ("tmdb", "model")
        assert dict(spec.source_options["tmdb"]) == {"media": media}
        assert want_status(domain) == want


def test_books_anime_and_albums_are_not_suggested_by_tmdb() -> None:
    # They take the hosted model alone since Sprint 135.
    for item_type in ("book", "anime", "album"):
        spec = DOMAINS[item_type].recommendation
        assert spec is not None and "tmdb" not in spec.sources


# --- A round, end to end, against recordings ------------------------------------------------


@asynccontextmanager
async def _app(
    tmp_path: Path, providers: Mapping[str, Any], tmdb: RecordedTmdb, **extra: Any
) -> AsyncIterator[tuple[Any, httpx.AsyncClient]]:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", **extra)
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        app.state.job_runner.handlers[RECOMMEND_JOB].enricher.cover_client = None
        app.state.providers.clear()
        app.state.providers.update(providers)
        app.state.recommendation_sources.register(tmdb.source)
        yield app, client


async def _run_jobs(app: Any) -> list[dict[str, Any]]:
    repo = JobRepository(app.state.engine)
    handlers = app.state.job_runner.handlers
    done = []
    while (claimed := repo.claim(datetime.now(UTC))) is not None:
        result = await handlers[claimed.kind].process(claimed.id, datetime.now(UTC))
        assert result["state"] == "succeeded", result
        repo.complete(claimed.id, result.get("progress", {}), datetime.now(UTC))
        done.append({"kind": claimed.kind, **result})
    return done


def _seed_entry(
    app: Any,
    item_type: str,
    title: str,
    year: int,
    identifiers: Mapping[str, str],
    source: tuple[str, str],
) -> int:
    result = DomainRepository(app.state.engine, 1).create_cached_entry(
        title=title,
        subtitle=None,
        year=year,
        metadata={},
        identifiers=[normalize_identifier(kind, value) for kind, value in identifiers.items()],
        sources=[SourceIdentity(source[0], source[1], True)],
        status=DOMAINS[item_type].default_status,
        score=None,
        item_type=item_type,
    )
    return result.entry_id


@pytest.mark.anyio
async def test_a_film_round_stores_twelve_and_enriches_three(tmp_path: Path) -> None:
    requests: list[str] = []
    tmdb = RecordedTmdb()
    async with _app(tmp_path, {"wikidata": _films(requests)}, tmdb) as (app, client):
        # A film only Cinemeta knows: TMDB is asked by its IMDb id first.
        entry = _seed_entry(
            app, FILM, "Seven Samurai", 1954, {"imdb": "tt0047478"}, ("cinemeta", "tt0047478")
        )
        queued = await client.post(f"/api/entries/{entry}/more-like-this")
        assert queued.status_code == 202, queued.text
        assert queued.json()["source"] == "tmdb"
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{queued.json()['id']}")).json()
        with app.state.engine.connect() as connection:
            kept = connection.execute(
                text(
                    "SELECT kind, value FROM item_identifiers WHERE kind = 'tmdb'"
                    " AND item_id = (SELECT item_id FROM entries WHERE id = :entry)"
                ),
                {"entry": entry},
            ).all()
    assert body["status"] == "done", body
    assert body["error"] is None
    assert len(body["suggestions"]) == 12
    top = body["suggestions"][:3]
    assert [(row["title"], row["enrichment"]) for row in top] == [
        ("47 Ronin", "enriched"),
        ("Yojimbo", "enriched"),
        ("After the Rain", "enriched"),
    ]
    assert all(row["item_id"] is not None for row in top)
    assert {row["enrichment"] for row in body["suggestions"][3:]} == {"pending"}
    assert top[0]["reason"] == {"signal": "tmdb", "text": "TMDB: often watched together"}
    assert tmdb.paths == ["/3/find/tt0047478", "/3/movie/346/recommendations"]
    # The TMDB id is kept on the seed's item: the next round asks once.
    assert kept == [("tmdb", "346")]


@pytest.mark.anyio
async def test_a_series_round_stores_and_enriches_three(tmp_path: Path) -> None:
    requests: list[str] = []
    tmdb = RecordedTmdb()
    async with _app(tmp_path, {"wikidata-series": _series(requests)}, tmdb) as (app, client):
        entry = _seed_entry(
            app,
            SERIES,
            "Breaking Bad",
            2008,
            {"imdb": "tt0903747", "tmdb": "1396"},
            ("wikidata-series", "Q1079"),
        )
        queued = await client.post(f"/api/entries/{entry}/more-like-this")
        assert queued.status_code == 202, queued.text
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{queued.json()['id']}")).json()
    assert body["status"] == "done", body
    assert [(row["title"], row["enrichment"]) for row in body["suggestions"][:3]] == [
        ("Better Call Saul", "enriched"),
        ("Narcos: Mexico", "enriched"),
        ("Snowfall", "enriched"),
    ]
    assert tmdb.paths == ["/3/tv/1396/recommendations"]


@pytest.mark.anyio
async def test_a_round_for_a_seed_tmdb_does_not_know_fails_with_the_reason(
    tmp_path: Path,
) -> None:
    tmdb = RecordedTmdb()
    async with _app(tmp_path, {}, tmdb) as (app, client):
        entry = _seed_entry(
            app, FILM, "Nobody's Film", 2001, {"tmdb": "999999999"}, ("wikidata", "Q1")
        )
        queued = await client.post(f"/api/entries/{entry}/more-like-this")
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{queued.json()['id']}")).json()
    assert body["status"] == "failed"
    assert "TMDB has no record" in body["error"]


@pytest.mark.anyio
async def test_without_a_token_the_round_is_not_configured_and_says_how(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            user_agent_contact="test@example.invalid",
            TMDB_READ_TOKEN="",
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        entry = _seed_entry(
            app, FILM, "Seven Samurai", 1954, {"imdb": "tt0047478"}, ("cinemeta", "tt0047478")
        )
        types = (await client.get("/api/item-types")).json()
        queued = await client.post(f"/api/entries/{entry}/more-like-this")
        jobs = JobRepository(app.state.engine).claim(datetime.now(UTC))
    by_id = {row["id"]: row for row in types}
    film = by_id[FILM]["recommendation"]
    assert film["sources"][0] == {
        "name": "tmdb",
        "label": "TMDB",
        "configured": False,
        "hint": film["sources"][0]["hint"],
        "resolved_only": False,
        "about": None,
    }
    assert [row["name"] for row in film["sources"]] == ["tmdb", "model"]
    assert "TMDB_READ_TOKEN" in film["sources"][0]["hint"]
    assert film["attribution"] == {"tmdb": TMDB_ATTRIBUTION}
    assert [row["name"] for row in by_id["book"]["recommendation"]["sources"]] == ["model"]
    assert queued.status_code == 202
    assert queued.json()["status"] == "not_configured"
    assert "TMDB_READ_TOKEN" in queued.json()["error"]
    assert jobs is None


@pytest.mark.anyio
async def test_with_a_token_the_library_says_its_source_is_configured(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            user_agent_contact="test@example.invalid",
            TMDB_READ_TOKEN="x",
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        types = (await client.get("/api/item-types")).json()
    by_id = {row["id"]: row for row in types}
    for item_type in (FILM, SERIES):
        source = by_id[item_type]["recommendation"]["sources"][0]
        assert source["name"] == "tmdb"
        assert source["configured"] is True and source["hint"] is None


# --- Pruning: TMDB's six-month window --------------------------------------------------------


def _round_at(app: Any, created: datetime, source: str, entry_id: int) -> int:
    stamp = created.isoformat().replace("+00:00", "Z")
    with app.state.engine.begin() as connection:
        round_id = connection.execute(
            text(
                "INSERT INTO suggestion_rounds (user_id, item_type, seed_entry_id, source,"
                " status, created_at, finished_at) VALUES (1, :type, :entry, :source, 'done',"
                " :at, :at)"
            ),
            {"type": FILM, "entry": entry_id, "source": source, "at": stamp},
        ).lastrowid
        connection.execute(
            text(
                "INSERT INTO suggestions (round_id, user_id, item_type, title, external_ids_json,"
                " reason, display_json, enrichment, created_at) VALUES (:round, 1, :type,"
                " 'Yojimbo', '{}', 'r', '{}', 'pending', :at)"
            ),
            {"round": round_id, "type": FILM, "at": stamp},
        )
    return int(round_id or 0)


@pytest.mark.anyio
async def test_tmdb_rounds_older_than_six_months_are_pruned(tmp_path: Path) -> None:
    tmdb = RecordedTmdb()
    async with _app(tmp_path, {}, tmdb) as (app, _client):
        entry = _seed_entry(
            app, FILM, "Seven Samurai", 1954, {"tmdb": "346"}, ("wikidata", "Q189540")
        )
        now = datetime(2026, 11, 23, tzinfo=UTC)
        old = _round_at(app, now - timedelta(days=183), "tmdb", entry)
        recent = _round_at(app, now - timedelta(days=181), "tmdb", entry)
        # A source with no retention keeps its rows however old.
        kept = _round_at(app, now - timedelta(days=400), "fake", entry)
        removed = prune_expired_suggestions(app.state.engine, app.state.recommendation_sources, now)
        with app.state.engine.connect() as connection:
            rounds = {
                row[0] for row in connection.execute(text("SELECT id FROM suggestion_rounds"))
            }
            suggestions = connection.execute(text("SELECT count(*) FROM suggestions")).scalar()
    assert removed == 1
    assert rounds == {recent, kept}
    assert suggestions == 2
    assert old not in rounds


@pytest.mark.anyio
async def test_pruning_runs_without_a_token_too(tmp_path: Path) -> None:
    """A token removed later must not leave TMDB's rows past the window."""
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            user_agent_contact="test@example.invalid",
            TMDB_READ_TOKEN="",
        )
    )
    async with app.router.lifespan_context(app):
        app.state.job_runner.stop()
        entry = _seed_entry(
            app, FILM, "Seven Samurai", 1954, {"tmdb": "346"}, ("wikidata", "Q189540")
        )
        now = datetime(2026, 11, 23, tzinfo=UTC)
        _round_at(app, now - timedelta(days=200), "tmdb", entry)
        assert (
            prune_expired_suggestions(app.state.engine, app.state.recommendation_sources, now) == 1
        )


@pytest.mark.anyio
async def test_the_job_runner_prunes_on_its_idle_pass(tmp_path: Path) -> None:
    tmdb = RecordedTmdb()
    async with _app(tmp_path, {}, tmdb) as (app, _client):
        entry = _seed_entry(
            app, FILM, "Seven Samurai", 1954, {"tmdb": "346"}, ("wikidata", "Q189540")
        )
        _round_at(app, datetime.now(UTC) - timedelta(days=200), "tmdb", entry)
        runner = app.state.job_runner
        await runner.idle(datetime.now(UTC))
        with app.state.engine.connect() as connection:
            left = connection.execute(text("SELECT count(*) FROM suggestion_rounds")).scalar()
    assert left == 0


# --- Art: a suggestion's cover is reachable before Want -----------------------------------


def _png() -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 6), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.mark.anyio
async def test_a_suggested_items_cover_is_served_to_whom_it_was_suggested(
    tmp_path: Path,
) -> None:
    from book_tracker.api.auth import COOKIE_NAME
    from book_tracker.application.passwords import hash_password
    from book_tracker.application.sessions import SessionStore

    requests: list[str] = []
    tmdb = RecordedTmdb()
    async with _app(tmp_path, {"wikidata": _films(requests)}, tmdb, auth="on") as (app, client):
        engine = app.state.engine
        stamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        credential = hash_password("second person's password")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id,username,display_name,password_hash,password_salt,"
                    "is_admin,created_at,updated_at) VALUES (2,'bruno','Bruno',:digest,:salt,0,"
                    ":now,:now)"
                ),
                {"digest": credential.digest, "salt": credential.salt, "now": stamp},
            )
        entry = _seed_entry(
            app, FILM, "Seven Samurai", 1954, {"tmdb": "346"}, ("wikidata", "Q189540")
        )
        owner = SessionStore(engine).create(1).token
        guest = SessionStore(engine).create(2).token
        client.cookies.set(COOKIE_NAME, owner)
        queued = await client.post(f"/api/entries/{entry}/more-like-this")
        await _run_jobs(app)
        body = (await client.get(f"/api/suggestion-rounds/{queued.json()['id']}")).json()
        item_id = body["suggestions"][0]["item_id"]
        (app.state.data_dir / "covers" / f"{item_id}.jpg").write_bytes(_png())
        DomainRepository(engine, 1).set_cover_path(item_id, f"covers/{item_id}.jpg")
        mine = await client.get(f"/api/items/{item_id}/cover")
        client.cookies.set(COOKIE_NAME, guest)
        theirs = await client.get(f"/api/items/{item_id}/cover")
        client.cookies.set(COOKIE_NAME, owner)
        listed = (await client.get("/api/suggestions")).json()
    assert mine.status_code == 200
    assert theirs.status_code == 404
    first = next(row for row in listed if row["item_id"] == item_id)
    assert first["cover_url"] is not None and first["cover_url"].startswith(
        f"/api/items/{item_id}/cover"
    )


# --- Home's More like this: stored rows only ------------------------------------------------


@pytest.mark.anyio
async def test_home_shows_the_newest_found_suggestions_without_asking_anyone(
    tmp_path: Path,
) -> None:
    requests: list[str] = []
    tmdb = RecordedTmdb()
    async with _app(tmp_path, {"wikidata": _films(requests)}, tmdb) as (app, client):
        entry = _seed_entry(
            app, FILM, "Seven Samurai", 1954, {"tmdb": "346"}, ("wikidata", "Q189540")
        )
        queued = await client.post(f"/api/entries/{entry}/more-like-this")
        await _run_jobs(app)
        round_body = (await client.get(f"/api/suggestion-rounds/{queued.json()['id']}")).json()
        yojimbo = round_body["suggestions"][1]["id"]
        await client.patch(f"/api/suggestions/{yojimbo}", json={"answer": "not_for_me"})
        asked = (len(requests), len(tmdb.requests))
        body = (await client.get("/api/home")).json()
        after = (len(requests), len(tmdb.requests))
    assert asked == after
    suggested = body["suggested"]
    # Only what was found (it has its cover and can be wanted); answered ones leave.
    assert [row["title"] for row in suggested] == ["47 Ronin", "After the Rain"]
    assert all(row["enrichment"] == "enriched" for row in suggested)
    assert suggested[0]["seed"] == {"entry_id": entry, "title": "Seven Samurai"}
    assert suggested[0]["source"] == "tmdb"
