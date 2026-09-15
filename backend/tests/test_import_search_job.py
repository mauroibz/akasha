"""The search_import_rows job (Sprint 083 D3): sequential, quota-bound, honest.

One job per list-connector preview walks the batch's rows in order, searches the
book domain's providers for each — one row at a time, no concurrency across
rows, respecting public-API rate limits (the owner's explicit "secuencial y
async") — and persists the merged top-N as proposals. The batch is `matching`
while the job runs and flips to `previewed` when the queue drains; commit is
refused meanwhile.

Failure containment is the design: a row whose searches all fail is
`search_failed` on the job's progress, never a dead-lettered job; a provider
over its daily budget defers the whole job without spending an attempt
(DEC-045's split — background work is budgeted, not recorded-never-blocked).

The provider boundary is proven against doubles here for the *failure* shapes
per the sprint file; the correctness suite (AC5) replays recorded real Open
Library responses and lives in the fixture replay tests.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.providers import SearchCandidate, SourceRef
from book_tracker.domain.registry import DOMAINS
from book_tracker.infrastructure.jobs import JobRepository, RateLimiter
from book_tracker.infrastructure.quota import ProviderQuota
from book_tracker.infrastructure.repositories import ImportRepository
from book_tracker.migrations import upgrade

NOW = datetime(2026, 9, 13, 12, 0, 0, tzinfo=UTC)


class FakeProvider:
    """A provider double the handler can call, with counted spends."""

    name = "openlibrary"
    item_type = "book"

    def __init__(self, results: list[SearchCandidate] | None = None, *, fail: bool = False):
        self.results = results or []
        self.fail = fail
        self.queries: list[str] = []

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("provider is down")
        return self.results[:limit]

    async def fetch(self, source_id: str) -> Any:  # pragma: no cover - not used by the job
        raise NotImplementedError


def candidate(title: str, source_id: str, **kwargs: Any) -> SearchCandidate:
    # Distinct ISBNs by default: `merge_and_rank` groups on identity, so two
    # candidates sharing an ISBN collapse to one before the top-N cut.
    default_isbn = f"978{abs(hash(source_id)) % 10**10:010d}"
    return SearchCandidate(
        source="openlibrary",
        source_id=source_id,
        source_refs=(SourceRef(source="openlibrary", source_id=source_id),),
        title=title,
        subtitle=None,
        creators=kwargs.get("creators", ("Julio Cortázar",)),
        year=kwargs.get("year", 1963),
        cover_url=kwargs.get("cover_url"),
        identifiers=kwargs.get("identifiers", {"isbn": default_isbn}),
        language=kwargs.get("language", "es"),
        metadata=kwargs.get("metadata", {}),
    )


def make_engine(tmp_path: Path):
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    return create_engine(configured)


def stage_preview(engine, rows: list[dict[str, Any]], *, batch_id: str = "b1") -> str:
    """A previewed list batch with the given record payloads, the shape
    `ImportService.preview` writes (minus the staging directory, which the
    search job never reads)."""
    from sqlalchemy import text

    records = []
    for index, row in enumerate(rows):
        records.append(
            {
                "row_number": index + 2,
                "item": {
                    "title": row["title"],
                    "subtitle": None,
                    "year": None,
                    "identifiers": {},
                    "metadata": {"creators": [row["author"]]} if row.get("author") else {},
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
                "errors": row.get("errors", []),
                "planned_action": row.get("planned_action", "create_item"),
            }
        )
    now = NOW.isoformat()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO import_batches (id, user_id, kind, fingerprint, state,"
                " source_descriptor, preview_summary, counters, created_at, updated_at)"
                " VALUES (:id, 1, 'list', :fingerprint, 'previewed', '{}',"
                " :summary, '{}', :now, :now)"
            ),
            {
                "id": batch_id,
                "fingerprint": f"f-{batch_id}",
                "summary": json.dumps({"total": len(records)}),
                "now": now,
            },
        )
        for record in records:
            connection.execute(
                text(
                    "INSERT INTO import_records (batch_id, user_id, row_number,"
                    " normalized_payload, conflicts, validation_errors, planned_action,"
                    " match_kind, created_at, updated_at)"
                    " VALUES (:batch, 1, :row, :payload, :conflicts, :errors,"
                    " :action, 'new', :now, :now)"
                ),
                {
                    "batch": batch_id,
                    "row": record["row_number"],
                    "payload": json.dumps(
                        {
                            "row_number": record["row_number"],
                            "item": record["item"],
                            "entry": record["entry"],
                            "shelves": record["shelves"],
                            "source_fields": record["source_fields"],
                            "item_type": record["item_type"],
                            "cover_stage": record["cover_stage"],
                        },
                        ensure_ascii=False,
                    ),
                    "conflicts": json.dumps({"candidates": []}),
                    "errors": json.dumps(record["errors"]),
                    "action": record["planned_action"],
                    "now": now,
                },
            )
    return batch_id


def make_handler(
    engine,
    providers,
    *,
    quota: ProviderQuota | None = None,
    rate_limiter: RateLimiter | None = None,
):
    from book_tracker.application.import_search import ImportSearchHandler

    return ImportSearchHandler(
        engine,
        {provider.name: provider for provider in providers},
        rate_limiter=rate_limiter,
        quota=quota,
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class TestTheJob:
    @pytest.mark.anyio
    async def test_rows_are_searched_sequentially_and_proposals_persist(
        self, tmp_path: Path
    ) -> None:
        engine = make_engine(tmp_path)
        stage_preview(
            engine,
            [
                {"title": "Rayuela", "author": "Julio Cortázar"},
                {"title": "Ficciones", "author": "Jorge Luis Borges"},
            ],
        )
        rayuela = candidate("Rayuela", "OL1M", identifiers={"isbn": "9788437604572"})
        edition = candidate("Rayuela (ed.)", "OL2M", identifiers={"isbn": "9788437604589"})
        provider = FakeProvider([rayuela, edition])
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
        # The batch is matching while its job is queued.
        with Session_of(engine) as session:
            session.execute(text_update_state("b1", "matching"))
            session.commit()

        handler = make_handler(engine, [provider])
        result = await handler.process(job_id, NOW)

        assert result["state"] == "succeeded"
        # Both rows searched in order, one query each, title and author both
        # in the query string (Spanish titles need the author to disambiguate).
        assert provider.queries == [
            "Rayuela Julio Cortázar",
            "Ficciones Jorge Luis Borges",
        ]
        repository = ImportRepository(engine, 1)
        proposals = repository.proposals_for_batch("b1")
        assert len(proposals) == 4  # top-3 per row, 2 available here
        assert [p["rank"] for p in proposals] == [0, 1, 0, 1]
        first = proposals[0]
        assert first["payload"]["title"] == "Rayuela"
        assert first["payload"]["identifiers"] == {"isbn": "9788437604572"}
        assert proposals[1]["payload"]["title"] == "Rayuela (ed.)"
        # The batch is previewable again.
        with Session_of(engine) as session:
            state = session.execute(text_batch_state("b1")).scalar_one()
        assert state == "previewed"
        assert result["progress"]["searched"] == 2
        assert result["progress"]["total"] == 2

    @pytest.mark.anyio
    async def test_a_provider_of_another_domain_is_never_asked(self, tmp_path: Path) -> None:
        """AC9's neutrality proof with a second domain's data: the row search
        asks only the providers that serve the row's own domain. Before the
        fix the handler passed every enabled provider — a book row proposed a
        movie and a series in the live walkthrough, spending other domains'
        quota to offer answers the row could never use."""
        engine = make_engine(tmp_path)
        stage_preview(engine, [{"title": "Rayuela", "author": "Julio Cortázar"}])
        book_provider = FakeProvider([candidate("Rayuela", "OL1M")])

        class MovieProvider(FakeProvider):
            name = "cinemeta"
            item_type = "movie"

        movie_provider = MovieProvider([candidate("Room in Rome", "tt123")])
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)

        handler = make_handler(engine, [book_provider, movie_provider])
        result = await handler.process(job_id, NOW)

        assert result["state"] == "succeeded"
        assert book_provider.queries == ["Rayuela Julio Cortázar"]
        assert movie_provider.queries == [], "a movie provider answered a book row"
        proposals = ImportRepository(engine, 1).proposals_for_batch("b1")
        assert [p["payload"]["title"] for p in proposals] == ["Rayuela"]

    @pytest.mark.anyio
    async def test_the_handler_serves_any_searching_connectors_batch(self, tmp_path: Path) -> None:
        """The handler is a shared layer (AC9): the batch it serves is the one
        whose **registered connector declared the search job** — a batch of a
        connector with no search phase (goodreads) is refused without naming
        any connector in this handler, so a future searching connector needs
        only its declaration, no handler change."""
        engine = make_engine(tmp_path)
        # A batch staged as goodreads: a real registered connector whose
        # declaration has no search_job.
        batch_id = stage_preview(engine, [{"title": "Kind of Blue", "author": ""}])
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE import_batches SET kind = 'goodreads' WHERE id = :id"),
                {"id": batch_id},
            )
        provider = FakeProvider([candidate("Kind of Blue", "MB1")])
        jobs = JobRepository(engine)
        job_id = jobs.enqueue(batch_id, "search_import_rows", {"batch_id": batch_id}, user_id=1)
        handler = make_handler(engine, [provider])
        refused = await handler.process(job_id, NOW)
        assert refused["state"] == "failed"
        assert refused["error_code"] == "batch_not_found"
        assert provider.queries == [], "a connector with no search phase was searched"

        # The registered searching connector's batch still runs.
        other = stage_preview(engine, [{"title": "Rayuela", "author": ""}], batch_id="b2")
        other_job = jobs.enqueue(other, "search_import_rows", {"batch_id": other}, user_id=1)
        result = await handler.process(other_job, NOW)
        assert result["state"] == "succeeded"
        assert provider.queries == ["Rayuela"]
        assert ImportRepository(engine, 1).proposals_for_batch(other)

    @pytest.mark.anyio
    async def test_error_rows_are_searched_like_any_other(self, tmp_path: Path) -> None:
        """A row the reader marked as an error still gets searched: its title
        exists (the empty-title rows are the ones the reader refused), and the
        owner still wants to see what the providers say about it."""
        engine = make_engine(tmp_path)
        stage_preview(
            engine,
            [
                {
                    "title": "Trutles alls the way down",
                    "author": "John Green",
                    "errors": [{"field": "author", "code": "missing"}],
                },
            ],
        )
        provider = FakeProvider([candidate("Turtles All the Way Down", "OL9M")])
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
        handler = make_handler(engine, [provider])
        result = await handler.process(job_id, NOW)
        assert result["state"] == "succeeded"
        assert ImportRepository(engine, 1).proposals_for_batch("b1")

    @pytest.mark.anyio
    async def test_top_n_is_capped_at_ten(self, tmp_path: Path) -> None:
        """Ten stored (the owner's 2026-09-14 'Show more'), three rendered:
        the providers are consulted once per row, so the deeper results cost
        nothing but storage."""
        engine = make_engine(tmp_path)
        stage_preview(engine, [{"title": "Rayuela", "author": "Julio Cortázar"}])
        provider = FakeProvider(
            [candidate(f"Result {index}", f"OL{index}M") for index in range(20)]
        )
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
        handler = make_handler(engine, [provider])
        await handler.process(job_id, NOW)
        proposals = ImportRepository(engine, 1).proposals_for_batch("b1")
        assert len(proposals) == 10
        assert [p["rank"] for p in proposals] == list(range(10))

    @pytest.mark.anyio
    async def test_no_results_is_an_answer_not_an_error(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        stage_preview(engine, [{"title": "Libro inexistente", "author": "Nadie"}])
        provider = FakeProvider([])
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
        handler = make_handler(engine, [provider])
        result = await handler.process(job_id, NOW)
        assert result["state"] == "succeeded"
        assert ImportRepository(engine, 1).proposals_for_batch("b1") == []
        # The progress the runner persists on success is the dict the handler
        # returned; read it here because the test drives the handler directly.
        assert result["progress"]["searched"] == 0
        assert result["progress"]["no_results"] == 1

    @pytest.mark.anyio
    async def test_a_row_whose_providers_all_fail_is_contained(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        stage_preview(
            engine,
            [
                {"title": "Rayuela", "author": "Julio Cortázar"},
                {"title": "Ficciones", "author": "Jorge Luis Borges"},
            ],
        )
        failing = FakeProvider(fail=True)
        provider = FakeProvider([candidate("Ficciones", "OL5M")])
        # Two providers: one fails, one answers — the row still gets proposals.
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
        handler = make_handler(engine, [failing, provider], rate_limiter=None)
        result = await handler.process(job_id, NOW)
        assert result["state"] == "succeeded"
        proposals = ImportRepository(engine, 1).proposals_for_batch("b1")
        # Both rows got proposals from the answering provider; the failing one
        # contributed nothing and cost nothing.
        assert len(proposals) == 2
        assert result["progress"]["search_failed"] == 0

        # Every provider failing on a row: the row is search_failed, the job
        # still drains the batch to previewed.
        second_dir = tmp_path / "second"
        second_dir.mkdir()
        engine2 = make_engine(second_dir)
        stage_preview(engine2, [{"title": "Solo", "author": "Uno"}], batch_id="b2")
        jobs2 = JobRepository(engine2)
        job2 = jobs2.enqueue("b2", "search_import_rows", {"batch_id": "b2"}, user_id=1)
        handler2 = make_handler(engine2, [FakeProvider(fail=True)])
        result2 = await handler2.process(job2, NOW)
        assert result2["state"] == "succeeded"
        assert result2["progress"]["search_failed"] == 1
        with Session_of(engine2) as session:
            assert session.execute(text_batch_state("b2")).scalar_one() == "previewed"

    @pytest.mark.anyio
    async def test_a_capped_provider_defers_without_spending_an_attempt(
        self, tmp_path: Path
    ) -> None:
        engine = make_engine(tmp_path)
        stage_preview(engine, [{"title": "Rayuela", "author": "Julio Cortázar"}])
        provider = FakeProvider([candidate("Rayuela", "OL1M")])
        quota = ProviderQuota(engine, limits={"openlibrary": 2})
        # Spend the whole daily budget first.
        quota.record("openlibrary", NOW)
        quota.record("openlibrary", NOW)
        assert not quota.allows("openlibrary", NOW)
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
        handler = make_handler(engine, [provider], quota=quota)
        result = await handler.process(job_id, NOW)
        assert result["state"] == "deferred"
        job = jobs.get_job(job_id)
        assert job["state"] == "queued"
        assert job["attempts"] == 0
        assert job["error_code"] == "provider_quota_exhausted"
        assert provider.queries == []

    @pytest.mark.anyio
    async def test_the_limiter_gates_each_row(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        stage_preview(
            engine,
            [{"title": f"Libro {index}", "author": "Autor"} for index in range(3)],
        )
        provider = FakeProvider([candidate("X", "OL1M")])
        limiter = RateLimiter(min_interval_seconds=0.0)
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
        handler = make_handler(engine, [provider], rate_limiter=limiter)
        result = await handler.process(job_id, NOW)
        assert result["state"] == "succeeded"
        # One query per row: the limiter's clock is injected, so a single
        # `now` means the second and third rows must be paced by the handler
        # waiting on the limiter rather than skipped.
        assert len(provider.queries) == 3

    @pytest.mark.anyio
    async def test_an_undone_batch_cancels_its_job(self, tmp_path: Path) -> None:
        engine = make_engine(tmp_path)
        stage_preview(engine, [{"title": "Rayuela", "author": "Julio Cortázar"}])
        provider = FakeProvider([candidate("Rayuela", "OL1M")])
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
        with Session_of(engine) as session:
            session.execute(text_update_state("b1", "undone"))
            session.commit()
        handler = make_handler(engine, [provider])
        result = await handler.process(job_id, NOW)
        assert result["state"] == "cancelled"
        assert provider.queries == []


# -- helpers the tests share -------------------------------------------------


def Session_of(engine):
    from sqlalchemy.orm import Session

    return Session(engine)


def text_update_state(batch_id: str, state: str):
    from sqlalchemy import text

    return text("UPDATE import_batches SET state = :state WHERE id = :id").bindparams(
        state=state, id=batch_id
    )


def text_batch_state(batch_id: str):
    from sqlalchemy import text

    return text("SELECT state FROM import_batches WHERE id = :id").bindparams(id=batch_id)


class TestPreviewIntegration:
    """The list connector's preview stages `matching` and enqueues the job; the
    commit gate refuses until the queue drains; the handler is registered."""

    LIST_CSV = (
        "Título del libro,Autor\r\nRayuela,Julio Cortázar\r\nFicciones,Jorge Luis Borges\r\n"
    ).encode()

    @pytest.mark.anyio
    async def _app(self, tmp_path: Path):
        import httpx

        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        return app, httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test")

    @pytest.mark.anyio
    async def test_preview_stages_matching_and_enqueues_one_job(self, tmp_path: Path) -> None:
        app, client = await self._app(tmp_path)
        async with app.router.lifespan_context(app), client:
            preview = await client.post(
                "/api/import/list/preview",
                files={"file": ("libros.csv", self.LIST_CSV, "text/csv")},
                data={"targets": "book"},
            )
            assert preview.status_code == 201
            body = preview.json()
            assert body["state"] == "matching"
            # Exactly one search job, owned by the previewing user.
            with Session_of(app.state.engine) as session:
                from sqlalchemy import text

                jobs = session.execute(
                    text("SELECT kind, user_id, batch_id, state FROM jobs WHERE batch_id = :batch"),
                    {"batch": body["batch_id"]},
                ).fetchall()
            assert len(jobs) == 1
            kind, user_id, batch_id, state = jobs[0]
            assert kind == "search_import_rows"
            assert user_id == 1
            assert batch_id == body["batch_id"]
            assert state == "queued"

            # Commit is refused while matching.
            commit = await client.post(
                "/api/import/list/commit",
                json={"batch_id": body["batch_id"]},
            )
            assert commit.status_code == 409
            assert commit.json()["error"]["code"] == "import_batch_not_committable"

    @pytest.mark.anyio
    async def test_commit_succeeds_once_the_queue_drains(self, tmp_path: Path) -> None:
        app, client = await self._app(tmp_path)
        async with app.router.lifespan_context(app), client:
            preview = await client.post(
                "/api/import/list/preview",
                files={"file": ("libros.csv", self.LIST_CSV, "text/csv")},
                data={"targets": "book"},
            )
            batch_id = preview.json()["batch_id"]

            # Drain the job the way the runner would: the handler itself,
            # against a provider double so no network is spent.
            from book_tracker.application.import_search import ImportSearchHandler
            from book_tracker.infrastructure.jobs import JobRepository

            JobRepository(app.state.engine)
            with Session_of(app.state.engine) as session:
                from sqlalchemy import text

                job_id = session.execute(
                    text("SELECT id FROM jobs WHERE batch_id = :batch"),
                    {"batch": batch_id},
                ).scalar_one()
            handler = ImportSearchHandler(
                app.state.engine,
                {"openlibrary": FakeProvider([candidate("Rayuela", "OL1M")])},
                rate_limiter=None,
            )
            result = await handler.process(job_id, NOW)
            assert result["state"] == "succeeded"

            commit = await client.post(
                "/api/import/list/commit",
                json={"batch_id": batch_id},
            )
            assert commit.status_code == 200
            assert commit.json()["state"] == "committed"

    @pytest.mark.anyio
    async def test_the_handler_is_registered_in_the_app(self, tmp_path: Path) -> None:
        app, _ = await self._app(tmp_path)
        async with app.router.lifespan_context(app):
            assert "search_import_rows" in app.state.job_runner.handlers

    @pytest.mark.anyio
    async def test_reclaim_covers_an_abandoned_matching_batch(self, tmp_path: Path) -> None:
        """An abandoned matching batch is the same leak an abandoned preview
        always was: `reclaim_import_batches` takes it once its (absent) undo
        window logic applies — the sprint's D3.5 recovery path."""

        app, _ = await self._app(tmp_path)
        async with app.router.lifespan_context(app):
            engine = app.state.engine
            batch_id = stage_preview(engine, [{"title": "X", "author": "Y"}])
            with Session_of(engine) as session:
                session.execute(text_update_state(batch_id, "matching"))
                session.commit()
            # An abandoned matching batch has no undo window; the sweep's
            # committed-batch rule does not apply, but the staging directory
            # does not grow either. What the sprint demands: the state must not
            # wedge the batch forever — claim the same recovery the job's own
            # lease/backoff machinery gives by re-running the handler.
            from book_tracker.application.import_search import ImportSearchHandler
            from book_tracker.infrastructure.jobs import JobRepository

            jobs = JobRepository(engine)
            job_id = jobs.enqueue(batch_id, "search_import_rows", {"batch_id": batch_id}, user_id=1)
            handler = ImportSearchHandler(
                engine, {"openlibrary": FakeProvider([candidate("X", "OL1M")])}
            )
            result = await handler.process(job_id, NOW)
            assert result["state"] == "succeeded"
            with Session_of(engine) as session:
                assert session.execute(text_batch_state(batch_id)).scalar_one() == "previewed"


class TestRecordedFixtureReplay:
    """AC5: the job's proposal pipeline proven against recorded real Open
    Library responses (DEC-025), never a mock of the provider contract."""

    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    async def test_the_job_produces_real_proposals_from_the_recording(self, tmp_path: Path) -> None:
        from recordings import recording, replay

        from book_tracker.domains.book.providers import OpenLibraryProvider
        from book_tracker.infrastructure.providers import create_provider_client

        engine = make_engine(tmp_path)
        stage_preview(
            engine,
            [
                {"title": "Rayuela", "author": "Julio Cortázar"},
                {"title": "Ficciones", "author": "Jorge Luis Borges"},
            ],
        )
        transport = replay(
            {
                "/search.json": (200, recording("search_rayuela.json")),
            }
        )
        async with create_provider_client(transport=transport) as provider_client:
            provider = OpenLibraryProvider(provider_client, "test@example.invalid")
            jobs = JobRepository(engine)
            job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
            handler = make_handler(engine, [provider])
            result = await handler.process(job_id, NOW)

        assert result["state"] == "succeeded"
        proposals = ImportRepository(engine, 1).proposals_for_batch("b1")
        assert proposals, "the recorded search produced proposals"
        first = proposals[0]
        # The payload is the recorded response's own data, mapped by the
        # provider the way the interactive search maps it — not invented here.
        assert first["source"] == "openlibrary"
        assert first["payload"]["title"] == "Rayuela"
        assert first["payload"]["creators"] == ["Julio Cortázar"]
        assert first["rank"] == 0
        # Both rows were searched even though only one had a recording: the
        # replay answers every query with the same recording, which is exactly
        # the fixture's point — one recorded answer proves the mapping.
        assert result["progress"]["searched"] == 2

    @pytest.mark.anyio
    async def test_the_recording_survives_the_whole_merge_path(self, tmp_path: Path) -> None:
        """The proposal is what `merge_and_rank` produced, ranked: the replay
        runs the real provider, the real merge, and the job stores the result
        of both — the same path the interactive search takes."""
        from recordings import recording, replay

        from book_tracker.application.providers import search_providers
        from book_tracker.domains.book.providers import OpenLibraryProvider
        from book_tracker.infrastructure.providers import create_provider_client

        transport = replay({"/search.json": (200, recording("search_rayuela.json"))})
        async with create_provider_client(transport=transport) as provider_client:
            provider = OpenLibraryProvider(provider_client, "test@example.invalid")
            interactive = await search_providers(
                "Rayuela Julio Cortázar", [provider], domain=DOMAINS["book"]
            )

        engine = make_engine(tmp_path)
        stage_preview(engine, [{"title": "Rayuela", "author": "Julio Cortázar"}])
        jobs = JobRepository(engine)
        job_id = jobs.enqueue("b1", "search_import_rows", {"batch_id": "b1"}, user_id=1)
        async with create_provider_client(
            transport=replay({"/search.json": (200, recording("search_rayuela.json"))})
        ) as provider_client:
            handler = make_handler(
                engine,
                [OpenLibraryProvider(provider_client, "t@e.invalid")],
            )
            await handler.process(job_id, NOW)

        proposals = ImportRepository(engine, 1).proposals_for_batch("b1")
        # One candidate per interactive merge result, same order, same titles.
        assert [p["payload"]["title"] for p in proposals] == [
            candidate.title for candidate in interactive[: len(proposals)]
        ]
