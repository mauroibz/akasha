"""One source, many libraries: the shared import pipeline holding N domains.

Everything here is built against a **test** connector rather than against IMDb or
Trakt, on purpose. A seam proved only by the connector it was built for is not proved
— that is what DEC-093 cost the first time somebody who had not written the boundary
tried to use it — so the two readers this seam exists for (Sprints 053 and 054) meet a
contract that was already exercised by somebody else.

The fixture connector deliberately looks like the sources that are coming: one file
carrying films and shows, rows that name their own domain, and rows whose source kind
maps to no registered domain at all.
"""

import json
from collections.abc import AsyncIterator, Iterator, Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from book_tracker.application.imports import ImportService
from book_tracker.application.library import LibraryError
from book_tracker.config import Settings
from book_tracker.domain.importers import (
    ImportEntry,
    ImportInputSpec,
    ImportItem,
    ImportMatcher,
    ImportReadContext,
    ImportSkip,
    ImportSnapshot,
    ImportSource,
    NormalizedImportRecord,
)
from book_tracker.domain.matching import MatchDecision, MatchKind
from book_tracker.domain.registry import IMPORTERS, IMPORTERS_BY_DOMAIN
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


#: One row of the fixture source, in the shape a two-domain export actually has:
#: a source-vocabulary kind, a title, and an identity whose kind depends on the kind.
Row = tuple[str, str, str]

FIXTURE_ROWS: tuple[Row, ...] = (
    ("Movie", "Arrival", "arrival-2016"),
    ("TV Series", "Breaking Bad", "tt0903747"),
    ("Movie", "Sicario", "sicario-2015"),
    ("TV Series", "The Wire", "tt0306414"),
)

#: What the source calls a thing, and which library it belongs in. The default is
#: skip-and-count, never a guess — the rule Sprint 053's `Title Type` table follows.
TARGETS: dict[str, str] = {"Movie": "movie", "TV Series": "series"}


class TwoDomainImporter:
    """A connector whose one source lands rows in two libraries.

    Its rows carry their own `item_type`, its films and shows use different identity
    kinds (which is what makes per-domain enrichment observable), and it reports the
    rows it could not target as a tally rather than as errors.
    """

    name = "two_domains"
    label = "Two domains"
    item_types: tuple[str, ...] = ("movie", "series")
    input = ImportInputSpec(
        kind="upload",
        label="Export",
        field="file",
        guide=("Open the export page.", "Download the file."),
        empty_state="Drop the export here.",
        help_url="https://example.invalid/export",
    )
    identity_kinds = frozenset({"letterboxd", "imdb"})
    error_codes = frozenset({"invalid_source"})

    def __init__(
        self,
        *,
        rows: Sequence[Row] = FIXTURE_ROWS,
        statuses: dict[str, str] | None = None,
        undeclared: str | None = None,
        skipped: tuple[ImportSkip, ...] = (ImportSkip(reason="TV Episode", count=3),),
    ) -> None:
        self.rows = tuple(rows)
        self.statuses = statuses or {"movie": "watchlist", "series": "plan_to_watch"}
        self.undeclared = undeclared
        self.skipped = skipped

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        records = []
        for number, (kind, title, identity) in enumerate(self.rows, start=1):
            item_type = self.undeclared or TARGETS[kind]
            records.append(
                NormalizedImportRecord(
                    row_number=number,
                    item=ImportItem(
                        title=title,
                        subtitle=None,
                        year=None,
                        identifiers={"letterboxd" if item_type == "movie" else "imdb": identity},
                        metadata={"creators": []},
                    ),
                    entry=ImportEntry(
                        score=None,
                        notes=None,
                        date_added=None,
                        values={},
                        suggested_status=self.statuses.get(item_type),
                    ),
                    shelves=(),
                    errors=(),
                    source_fields={"kind": kind},
                    item_type=item_type,
                )
            )
        return ImportSnapshot(
            fingerprint=f"two-domains:{(source.data or b'').decode() or 'default'}",
            filename="export.csv",
            source_descriptor={},
            records=tuple(records),
            skipped=self.skipped,
        )

    def stage(self, snapshot: ImportSnapshot, _directory: Path, _data_dir: Path) -> ImportSnapshot:
        return snapshot

    def match(self, record: NormalizedImportRecord, matcher: ImportMatcher) -> MatchDecision:
        del matcher
        del record
        return MatchDecision(kind=MatchKind.NEW, item_id=None, candidates=())


@pytest.fixture
def two_domains() -> Iterator[TwoDomainImporter]:
    """Register the fixture connector for the life of one test.

    Registration is a mutation of the two registry indexes rather than a monkeypatched
    module attribute, because the routes hold the dictionaries themselves — and because
    a connector that is not in both indexes is exactly the defect conformance refuses.
    """
    importer = TwoDomainImporter()
    IMPORTERS[importer.name] = importer  # type: ignore[assignment]
    for item_type in importer.item_types:
        IMPORTERS_BY_DOMAIN[item_type] = (*IMPORTERS_BY_DOMAIN[item_type], importer)  # type: ignore[arg-type]
    try:
        yield importer
    finally:
        del IMPORTERS[importer.name]
        for item_type in importer.item_types:
            IMPORTERS_BY_DOMAIN[item_type] = tuple(
                row for row in IMPORTERS_BY_DOMAIN[item_type] if row is not importer
            )


def _app(tmp_path: Path) -> Any:
    return create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid")
    )


async def _client(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        yield client


def _service(app: Any, importer: object) -> ImportService:
    return ImportService(
        app.state.engine,
        app.state.data_dir,
        app.state.calibre_dir,
        importer,  # type: ignore[arg-type]
    )


def _types(engine: Any) -> dict[str, int]:
    with Session(engine) as session:
        return {
            str(row[0]): int(row[1])
            for row in session.execute(text("SELECT type, count(*) FROM items GROUP BY type"))
        }


@pytest.mark.anyio
async def test_one_source_previews_and_commits_rows_of_both_types(tmp_path: Path) -> None:
    """AC1. One batch, two libraries, and nothing above the registry branching."""
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        service = _service(app, TwoDomainImporter())
        preview = service.preview(ImportSource(data=b"one", filename="export.csv"))
        assert preview["summary"]["total"] == 4
        assert [row["item_type"] for row in preview["records"]] == [
            "movie",
            "series",
            "movie",
            "series",
        ]

        committed = service.commit(preview["batch_id"], {})

    assert committed["created_items"] == 4
    assert committed["created_entries"] == 4
    assert _types(app.state.engine) == {"movie": 2, "series": 2}


@pytest.mark.anyio
async def test_each_row_is_validated_against_its_own_domain(tmp_path: Path) -> None:
    """AC3. `watching` is a series word; a film is never watching.

    The failure this prevents is subtle and would not have looked like a bug: under a
    single batch domain, every row of a mixed source is checked against whichever
    domain happened to be declared first, so half the batch is validated against a
    vocabulary that is not its own.
    """
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        # Legal for series, illegal for movies. The series rows must survive it.
        service = _service(
            app,
            TwoDomainImporter(statuses={"movie": "watching", "series": "watching"}),
        )
        with pytest.raises(LibraryError) as refused:
            service.preview(ImportSource(data=b"one", filename="export.csv"))
        assert refused.value.code == "invalid_import_record"
        assert refused.value.status_code == 422
        # Row 1 is the film; the series row that follows it is not what was refused.
        assert refused.value.details["row_number"] == 1

        # The same status, on the rows whose domain declares it, is accepted.
        allowed = _service(
            app,
            TwoDomainImporter(
                rows=(("TV Series", "Breaking Bad", "tt0903747"),),
                statuses={"series": "watching"},
            ),
        )
        preview = allowed.preview(ImportSource(data=b"two", filename="export.csv"))

    assert preview["records"][0]["suggested_status"] == "watching"


@pytest.mark.anyio
async def test_a_record_naming_an_undeclared_domain_is_refused(tmp_path: Path) -> None:
    """A reader may not target a library its connector never declared.

    Refused with the same code and at the same boundary as an undeclared identity
    kind: one rule shape for "the connector produced something it did not declare",
    not two.
    """
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        service = _service(app, TwoDomainImporter(undeclared="album"))
        with pytest.raises(LibraryError) as refused:
            service.preview(ImportSource(data=b"one", filename="export.csv"))

    assert refused.value.code == "invalid_import_record"
    assert refused.value.status_code == 422
    assert "album" in refused.value.message


@pytest.mark.anyio
async def test_undo_of_a_mixed_batch_leaves_nothing_behind(
    tmp_path: Path, two_domains: TwoDomainImporter
) -> None:
    """AC5. Undo never learned which domain it was reversing, and must not have to."""
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        async for client in _client(app):
            preview = await client.post(
                "/api/import/two_domains/preview",
                files={"file": ("export.csv", b"one", "text/csv")},
            )
            assert preview.status_code == 201, preview.text
            batch_id = preview.json()["batch_id"]
            commit = await client.post(
                "/api/import/two_domains/commit", json={"batch_id": batch_id}
            )
            assert commit.status_code == 200, commit.text
            assert _types(app.state.engine) == {"movie": 2, "series": 2}

            undone = await client.delete(f"/api/import/batches/{batch_id}")

    assert undone.status_code == 200, undone.text
    assert undone.json()["reverted_items"] == 4
    with Session(app.state.engine) as session:
        assert session.execute(text("SELECT count(*) FROM items")).scalar_one() == 0
        assert session.execute(text("SELECT count(*) FROM entries")).scalar_one() == 0
        assert session.execute(text("SELECT count(*) FROM item_identifiers")).scalar_one() == 0


@pytest.mark.anyio
async def test_enrichment_is_queued_for_every_domain_the_batch_touched(tmp_path: Path) -> None:
    """AC6. Both target domains enrich, on different identity kinds.

    The guard this replaces asked one domain whether it enriched. A mixed batch has no
    one domain, and asking the wrong one would silently skip half the library's
    backfill — which is the failure that took Sprints 011 to 014 to notice once.
    """
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        service = _service(app, TwoDomainImporter())
        preview = service.preview(ImportSource(data=b"one", filename="export.csv"))
        service.commit(preview["batch_id"], {})

        with Session(app.state.engine) as session:
            queued = [
                json.loads(str(row[0]))
                for row in session.execute(
                    text("SELECT payload FROM jobs WHERE kind = 'enrich_item'")
                )
            ]

    assert {row["kind"] for row in queued} == {"letterboxd", "imdb"}
    assert len(queued) == 4


@pytest.mark.anyio
async def test_a_batch_previewed_before_this_contract_still_commits(tmp_path: Path) -> None:
    """A staged batch older than per-record types is not orphaned by them.

    Preview is durable: a batch may sit in `previewed` for as long as the owner takes
    to look at it, so an upgrade lands on payloads written under the old rule. They
    name no type, and the answer is the connector's first declared one — which for
    every connector that existed before this sprint was the only one it had. Named in
    a test rather than discovered on the owner's library.
    """
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        service = _service(app, TwoDomainImporter(rows=(("Movie", "Arrival", "arrival-2016"),)))
        preview = service.preview(ImportSource(data=b"one", filename="export.csv"))

        # Rewrite the staged payloads as the previous contract wrote them.
        with Session(app.state.engine) as session:
            for row in session.execute(
                text("SELECT id, normalized_payload FROM import_records")
            ).all():
                payload = json.loads(str(row[1]))
                del payload["item_type"]
                session.execute(
                    text("UPDATE import_records SET normalized_payload = :payload WHERE id = :id"),
                    {"payload": json.dumps(payload), "id": row[0]},
                )
            session.commit()

        committed = service.commit(preview["batch_id"], {})

    assert committed["created_items"] == 1
    assert _types(app.state.engine) == {"movie": 1}


@pytest.mark.anyio
async def test_unticking_a_target_excludes_its_rows_and_says_how_many(tmp_path: Path) -> None:
    """AC7. The service applies the selection, so no connector can get it wrong."""
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        service = _service(app, TwoDomainImporter())
        preview = service.preview(
            ImportSource(data=b"one", filename="export.csv"), targets=("movie",)
        )
        assert preview["summary"]["total"] == 2
        assert {row["item_type"] for row in preview["records"]} == {"movie"}
        assert preview["summary"]["skipped_not_requested"] == 2

        committed = service.commit(preview["batch_id"], {})

    assert committed["created_items"] == 2
    assert _types(app.state.engine) == {"movie": 2}


@pytest.mark.anyio
async def test_the_same_source_with_different_targets_is_a_different_import(
    tmp_path: Path,
) -> None:
    """AC8. The trap DEC-106 names: idempotency is on `(connector, fingerprint)`.

    Without the target set folded in, importing an export as films and then as shows
    returns the *first* preview — a wrong answer that looks like a working feature.
    """
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        service = _service(app, TwoDomainImporter())
        films = service.preview(ImportSource(data=b"same", filename="export.csv"), ("movie",))
        shows = service.preview(ImportSource(data=b"same", filename="export.csv"), ("series",))
        both = service.preview(ImportSource(data=b"same", filename="export.csv"), None)
        again = service.preview(ImportSource(data=b"same", filename="export.csv"), ("movie",))

    assert films["batch_id"] != shows["batch_id"] != both["batch_id"]
    assert {row["item_type"] for row in films["records"]} == {"movie"}
    assert {row["item_type"] for row in shows["records"]} == {"series"}
    assert both["summary"]["total"] == 4
    # Still idempotent within one target set: the same request returns its own batch.
    assert again["batch_id"] == films["batch_id"]


@pytest.mark.anyio
async def test_selecting_every_target_keeps_the_fingerprint_a_source_already_has(
    tmp_path: Path,
) -> None:
    """A batch previewed before targets existed must keep resolving.

    Every connector that shipped before this sprint declares one domain, so it always
    selects all of them — and the fingerprint it computes is unchanged. That is why
    this needs no migration: the composition only applies to a strict subset.
    """
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        service = _service(app, TwoDomainImporter())
        preview = service.preview(ImportSource(data=b"same", filename="export.csv"))

    assert preview["fingerprint"] == "two-domains:same"


@pytest.mark.anyio
async def test_rows_the_reader_could_not_target_are_counted_not_failed(tmp_path: Path) -> None:
    """AC9. Somebody who exports a whole account meets a number, not red rows.

    A count with the source's own word for the thing, so a title type IMDb has not
    published yet reads as "40 Podcast Episode" rather than as forty failed imports.
    """
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        service = _service(
            app,
            TwoDomainImporter(
                skipped=(
                    ImportSkip(reason="TV Episode", count=40),
                    ImportSkip(reason="Podcast Episode", count=4),
                )
            ),
        )
        preview = service.preview(ImportSource(data=b"one", filename="export.csv"))

    summary = preview["summary"]
    assert summary["skipped_unsupported"] == 44
    assert summary["errors"] == 0
    assert summary["skipped_reasons"] == [
        {"reason": "TV Episode", "count": 40},
        {"reason": "Podcast Episode", "count": 4},
    ]
    assert all(not row["errors"] for row in preview["records"])


@pytest.mark.anyio
async def test_the_registry_publishes_every_domain_a_connector_targets(
    tmp_path: Path, two_domains: TwoDomainImporter
) -> None:
    """AC10. The published field is a list now, and the screen renders from it."""
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        async for client in _client(app):
            response = await client.get("/api/importers")

    published = {row["id"]: row["item_types"] for row in response.json()}
    assert published["two_domains"] == ["movie", "series"]
    assert published["goodreads"] == ["book"]
    assert published["letterboxd"] == ["movie"]


@pytest.mark.anyio
async def test_the_chosen_targets_travel_with_the_preview_request(
    tmp_path: Path, two_domains: TwoDomainImporter
) -> None:
    """The selection is part of the request, not state the screen holds."""
    app = _app(tmp_path)
    async with app.router.lifespan_context(app):
        async for client in _client(app):
            response = await client.post(
                "/api/import/two_domains/preview",
                files={"file": ("export.csv", b"one", "text/csv")},
                data={"targets": "series"},
            )
            assert response.status_code == 201, response.text
            assert response.json()["summary"]["total"] == 2
            assert response.json()["summary"]["skipped_not_requested"] == 2

            refused = await client.post(
                "/api/import/two_domains/preview",
                files={"file": ("export.csv", b"two", "text/csv")},
                data={"targets": "album"},
            )

    assert refused.status_code == 422, refused.text
    assert refused.json()["error"]["code"] == "invalid_import_targets"
