"""The list connector: a spreadsheet a person wrote themselves (Sprint 083 D1).

No platform produced this file, so nothing in it can be trusted as identity —
the connector's whole contract is honest rows: title and author from the chosen
columns, the original cells preserved in `source_fields`, every row visible
(including the malformed ones, as `error` rows), and a `match` that never
resolves anything itself (`MatchKind.NEW`, always — the search-then-confirm
flow in D3 is the only matcher).

The fixture shapes here are derived from the owner's real CSV (Spanish/English
titles, a trailing-space header, a transposed row, a collection volume, a typo,
`et al`, a quoted comma) but the rows are synthetic — the real file never leaves
the git-ignored `exports/`.
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from book_tracker.domain.importers import (
    ImportEntry,
    ImportItem,
    ImportMatcher,
    ImportReadContext,
    ImportSource,
    NormalizedImportRecord,
)
from book_tracker.domain.list import (
    ListCSVError,
    ListImporter,
    detect_delimiter,
    sniff_mapping,
)
from book_tracker.domain.matching import MatchDecision, MatchKind

CONTEXT = ImportReadContext(path_root=Path("/tmp"))


def csv_source(data: str, filename: str = "libros.csv", domain: str = "book") -> ImportSource:
    # The domain choice rides the same options channel the screen's targets
    # field uses (Sprint 084): every reader test states its library.
    return ImportSource(data=data.encode("utf-8"), filename=filename, options={"targets": domain})


#: The owner's header set, including the trailing space that must be trimmed
#: before matching and the columns this sprint deliberately does not map.
OWNER_HEADERS = (
    "Título del libro,Autor,Editorial ,Idioma,Estado,Formato,Precio,Comentarios adicionales"
)

SYNTHETIC_CSV = (
    "﻿" + OWNER_HEADERS + "\r\n"
    "Rayuela,Julio Cortázar, Sudamericana, Castellano, Leído, Tapa blanda, , obra cumbre\r\n"
    '"Will Grayson, Will Grayson",John Green, Dutton, Inglés, Leído, Tapa dura, , \r\n'
    "Maze runner #2: Prueba de fuego,James Dashner, Smyth, Castellano, Leído,"
    " Tapa blanda, , la serie\r\n"
    "Trutles alls the way down,John Green, N/A, Inglés, , , , un typo\r\n"
    "La cúpula 1,Stephen King, , Castellano, , , , \r\n"
    "Homero,Iliada, Gredos, Castellano, , , , autor y título al revés\r\n"
    "Duma key 2,Stephen King, , Castellano, , , , volumen de colección\r\n"
    'Diccionario de la RAE,"Analia Aucia, et al", Lal, Castellano, , , ,'
    ' "no es una novela, pero está"\r\n'
    ", Autor Sin Título, , , , , , fila sin título\r\n"
    "Solo un título\r\n"
)

#: The moment the owner-batch tests run their jobs at — the same pinned-now
#: shape the other job suites use, so no test reads a wall clock.
NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=UTC)


def read_all(
    data: str,
    mapping: dict[str, int] | None = None,
    domain: str | None = "book",
):
    options: dict[str, str] | None = None
    if mapping is not None:
        options = {
            "title_column": str(mapping["title"] + 1),
            "author_column": str(mapping["author"] + 1),
        }
    if domain is not None:
        options = {**(options or {}), "targets": domain}
    importer = ListImporter()
    return importer.read(
        ImportSource(data=data.encode("utf-8"), filename="libros.csv", options=options),
        CONTEXT,
    )


def records_by_title(snapshot):
    return {record.item.title: record for record in snapshot.records}


class TestDelimiterSniffing:
    def test_comma_semicolon_and_tab_are_sniffed_from_the_first_data_line(self) -> None:
        assert detect_delimiter("a,b,c\n1,2,3") == ","
        assert detect_delimiter("a;b;c\n1;2;3") == ";"
        assert detect_delimiter("a\tb\tc\n1\t2\t3") == "\t"

    def test_the_count_not_the_presence_decides(self) -> None:
        # A comma inside a quoted title must not make a semicolon file a comma file.
        assert detect_delimiter('"a,b";c;d\n1;2;3') == ";"


class TestAutoDetection:
    def test_the_owners_headers_map_by_name_including_the_trailing_space(self) -> None:
        header, mapping = sniff_mapping(["Título del libro", "Autor", "Editorial ", "Idioma"])
        assert mapping == {"title": 0, "author": 1}

    def test_english_headers_map_too(self) -> None:
        _, mapping = sniff_mapping(["Book name", "Author", "Publisher"])
        assert mapping == {"title": 0, "author": 1}

    def test_unknown_headers_fall_back_to_the_first_two_columns(self) -> None:
        _, mapping = sniff_mapping(["Cosa", "Otra cosa", "Tercera"])
        assert mapping == {"title": 0, "author": 1}

    def test_author_only_is_not_a_title(self) -> None:
        # A header that matches author but nothing matching title: title falls
        # back to the first column, author takes the matched one.
        _, mapping = sniff_mapping(["Nombre", "Autor"])
        assert mapping == {"title": 0, "author": 1}


class TestReading:
    def test_every_non_empty_row_is_present_with_its_original_cells(self) -> None:
        snapshot = read_all(SYNTHETIC_CSV)
        titles = records_by_title(snapshot)
        assert "Rayuela" in titles
        record = titles["Rayuela"]
        assert record.item.metadata["creators"] == ["Julio Cortázar"]
        # The columns this sprint does not map ride uninterpreted.
        assert record.source_fields["Editorial"] == "Sudamericana"
        assert record.source_fields["Idioma"] == "Castellano"
        assert record.source_fields["Comentarios adicionales"] == "obra cumbre"
        assert record.item.identifiers == {}
        assert record.entry.score is None
        assert record.entry.suggested_status is None

    def test_a_quoted_comma_title_is_one_cell(self) -> None:
        titles = records_by_title(read_all(SYNTHETIC_CSV))
        assert "Will Grayson, Will Grayson" in titles
        assert titles["Will Grayson, Will Grayson"].item.metadata["creators"] == ["John Green"]

    def test_the_header_row_is_never_a_record(self) -> None:
        snapshot = read_all(SYNTHETIC_CSV)
        assert all(record.item.title != "Título del libro" for record in snapshot.records)

    def test_an_empty_title_row_is_an_error_row_not_a_skip(self) -> None:
        snapshot = read_all(SYNTHETIC_CSV)
        empty = [record for record in snapshot.records if not record.item.title]
        assert empty, "the empty-title row must still be a record"
        assert empty[0].errors == ({"field": "title", "code": "required", "value": ""},)
        # The mapped author cell is the item's creator (what was read), and the
        # unmapped cells ride in source_fields (what the spreadsheet said).
        assert empty[0].item.metadata.get("creators") == ["Autor Sin Título"]
        assert empty[0].source_fields.get("Comentarios adicionales") == "fila sin título"

    def test_a_row_shorter_than_the_mapping_is_an_error_row(self) -> None:
        snapshot = read_all(SYNTHETIC_CSV)
        short = [record for record in snapshot.records if record.item.title == "Solo un título"]
        assert short, "the short row must still be a record"
        assert {"field": "author", "code": "missing"} in [
            {"field": error["field"], "code": error["code"]} for error in short[0].errors
        ]

    def test_the_transposed_row_is_read_literally(self) -> None:
        # `Homero,Iliada` is title-in-the-author-column; the connector does not
        # guess — the confirm step is the safety net (sprint risk list).
        titles = records_by_title(read_all(SYNTHETIC_CSV))
        assert "Homero" in titles
        assert titles["Homero"].item.metadata["creators"] == ["Iliada"]

    def test_row_numbers_count_the_source_rows_not_the_records(self) -> None:
        snapshot = read_all(SYNTHETIC_CSV)
        # Header is row 1, first data row is row 2 — and stays 2 even though it
        # is the first record.
        assert snapshot.records[0].row_number == 2

    def test_bom_and_crlf_parse_cleanly(self) -> None:
        snapshot = read_all(SYNTHETIC_CSV)
        assert snapshot.records, "BOM + CRLF must parse"
        assert snapshot.records[0].item.title == "Rayuela"

    def test_a_semicolon_file_reads_the_same(self) -> None:
        data = "Título del libro;Autor\r\nRayuela;Julio Cortázar\r\n"
        titles = records_by_title(read_all(data))
        assert titles["Rayuela"].item.metadata["creators"] == ["Julio Cortázar"]


class TestErrors:
    def test_fewer_than_two_columns_is_refused_missing_columns(self) -> None:
        with pytest.raises(ListCSVError) as refused:
            read_all("Título\r\nRayuela\r\nFicciones\r\n")
        assert refused.value.code == "missing_columns"
        assert refused.value.action

    def test_invalid_utf8_is_refused_invalid_csv(self) -> None:
        source = ImportSource(
            data=b"\xff\xfe\x00bad", filename="x.csv", options={"targets": "book"}
        )
        with pytest.raises(ListCSVError) as refused:
            ListImporter().read(source, CONTEXT)
        assert refused.value.code == "invalid_csv"

    def test_no_data_is_refused(self) -> None:
        source = ImportSource(data=None, filename="x.csv", options={"targets": "book"})
        with pytest.raises(ListCSVError) as refused:
            ListImporter().read(source, CONTEXT)
        assert refused.value.code == "invalid_csv"

    def test_the_error_codes_are_declared(self) -> None:
        assert ListImporter.error_codes == frozenset(
            {"invalid_csv", "missing_columns", "column_not_mapped", "invalid_import_target"}
        )


class TestIdentityAndMatch:
    def test_identity_kinds_is_empty(self) -> None:
        assert ListImporter.identity_kinds == frozenset()

    def test_match_is_always_new(self) -> None:
        class AnyMatcher(ImportMatcher):
            def match(self, **_kwargs) -> MatchDecision:
                raise AssertionError("the connector must not consult the library")

        importer = ListImporter()
        record = NormalizedImportRecord(
            row_number=2,
            item=ImportItem(title="Rayuela", subtitle=None, year=None, identifiers={}, metadata={}),
            entry=ImportEntry(score=None, notes=None, date_added=None, values={}),
            shelves=(),
            errors=(),
            source_fields={},
        )
        decision = importer.match(record, AnyMatcher())  # type: ignore[arg-type]
        assert decision.kind is MatchKind.NEW
        assert decision.item_id is None

    def test_a_record_with_identifier_kinds_is_not_what_this_connector_makes(
        self,
    ) -> None:
        # The reader emits {} always; a non-empty identifiers mapping would be
        # refused by ImportService._validate against the empty declaration.
        snapshot = read_all(SYNTHETIC_CSV)
        assert all(record.item.identifiers == {} for record in snapshot.records)


class TestFingerprintAndStage:
    def test_the_fingerprint_is_the_bytes(self) -> None:
        snapshot = read_all(SYNTHETIC_CSV)
        expected = hashlib.sha256(SYNTHETIC_CSV.encode("utf-8")).hexdigest()
        # The chosen domain composes the fingerprint (Sprint 084): one list,
        # one library per batch — the same rule the mapping already followed.
        assert snapshot.fingerprint == f"{expected}#book"

    def test_stage_writes_the_source_bytes_and_drops_them_from_memory(self) -> None:
        import tempfile
        from dataclasses import replace

        importer = ListImporter()
        snapshot = read_all(SYNTHETIC_CSV)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            staged = importer.stage(snapshot, directory, Path(tmp))
            assert (directory / "source.csv").read_bytes() == SYNTHETIC_CSV.encode("utf-8")
            assert staged.archive_data is None
            assert replace(staged, archive_data=None).fingerprint == snapshot.fingerprint


class TestExplicitMapping:
    def test_an_explicit_mapping_reads_other_columns(self) -> None:
        # The transposed row (`Homero,Iliada`) read with title=column 2,
        # author=column 1: the mapping is the owner's answer to a spreadsheet
        # whose columns are not where the auto-detect looks.
        importer = ListImporter()
        source = ImportSource(
            data=SYNTHETIC_CSV.encode("utf-8"),
            filename="libros.csv",
            options={"targets": "book", "title_column": 1, "author_column": 0},
        )
        snapshot = importer.read(source, CONTEXT)
        titles = records_by_title(snapshot)
        assert "Iliada" in titles
        assert titles["Iliada"].item.metadata["creators"] == ["Homero"]
        # And the normal rows swap the same way.
        assert titles["Julio Cortázar"].item.title == "Julio Cortázar"
        assert titles["Julio Cortázar"].item.metadata["creators"] == ["Rayuela"]

    def test_the_mapping_composes_the_fingerprint(self) -> None:
        # The same file with a different mapping is a different import, never a
        # stale replay of the first preview (DEC-106's rule, D1.7).
        importer = ListImporter()
        plain = importer.read(csv_source(SYNTHETIC_CSV), CONTEXT)
        remapped = importer.read(
            ImportSource(
                data=SYNTHETIC_CSV.encode("utf-8"),
                filename="libros.csv",
                options={"targets": "book", "title_column": 1, "author_column": 0},
            ),
            CONTEXT,
        )
        assert plain.fingerprint != remapped.fingerprint
        assert remapped.fingerprint.endswith("#t1a0")

    def test_an_out_of_range_column_is_column_not_mapped(self) -> None:
        importer = ListImporter()
        with pytest.raises(ListCSVError) as refused:
            importer.read(
                ImportSource(
                    data=SYNTHETIC_CSV.encode("utf-8"),
                    filename="libros.csv",
                    options={"targets": "book", "title_column": 99},
                ),
                CONTEXT,
            )
        assert refused.value.code == "column_not_mapped"
        assert refused.value.action

    def test_a_negative_column_is_column_not_mapped(self) -> None:
        importer = ListImporter()
        with pytest.raises(ListCSVError) as refused:
            importer.read(
                ImportSource(
                    data=SYNTHETIC_CSV.encode("utf-8"),
                    filename="libros.csv",
                    options={"targets": "book", "author_column": -1},
                ),
                CONTEXT,
            )
        assert refused.value.code == "column_not_mapped"

    def test_a_non_integer_column_is_column_not_mapped(self) -> None:
        importer = ListImporter()
        with pytest.raises(ListCSVError) as refused:
            importer.read(
                ImportSource(
                    data=SYNTHETIC_CSV.encode("utf-8"),
                    filename="libros.csv",
                    options={"targets": "book", "title_column": "Autor"},
                ),
                CONTEXT,
            )
        assert refused.value.code == "column_not_mapped"


class TestRoutes:
    """The connector through the real API: form fields, catalog, errors."""

    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    async def test_preview_maps_columns_from_form_fields(self, tmp_path: Path) -> None:
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            preview = await client.post(
                "/api/import/list/preview",
                files={
                    "file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv"),
                },
                data={
                    "targets": "book",
                    "title_column": "1",
                    "author_column": "0",
                },
            )
        assert preview.status_code == 201
        body = preview.json()
        # This connector previews in `matching` (Sprint 083 D3): the background
        # search job owns the batch until its queue drains.
        assert body["state"] == "matching"
        transposed = [record for record in body["records"] if record["title"] == "Iliada"]
        assert transposed[0]["creators"] == ["Homero"]
        # The mapping composes the fingerprint, so this is not the auto-detected
        # batch: a different preview of the same bytes.
        assert body["fingerprint"].endswith("#t1a0")

    @pytest.mark.anyio
    async def test_preview_auto_maps_without_fields(self, tmp_path: Path) -> None:
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            preview = await client.post(
                "/api/import/list/preview",
                files={
                    "file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv"),
                },
                data={"targets": "book"},
            )
            assert preview.status_code == 201
            body = preview.json()
            rayuela = [record for record in body["records"] if record["title"] == "Rayuela"]
            assert rayuela[0]["creators"] == ["Julio Cortázar"]
            # A same-bytes re-preview is idempotent, not a second batch.
            again = await client.post(
                "/api/import/list/preview",
                files={
                    "file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv"),
                },
                data={"targets": "book"},
            )
            assert again.json()["batch_id"] == body["batch_id"]

    @pytest.mark.anyio
    async def test_a_bad_mapping_is_the_declared_error(self, tmp_path: Path) -> None:
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            preview = await client.post(
                "/api/import/list/preview",
                files={
                    "file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv"),
                },
                data={"targets": "book", "title_column": "99"},
            )
        assert preview.status_code == 422
        error = preview.json()["error"]
        # The connector's own declared vocabulary publishes as itself (DEC-080);
        # only an undeclared code would be republished as `import_read_error`.
        assert error["code"] == "column_not_mapped"
        assert error["user_message"]
        assert error["action"]

    @pytest.mark.anyio
    async def test_the_catalog_publishes_the_declared_fields(self, tmp_path: Path) -> None:
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            catalog = await client.get("/api/importers")
        listed = {row["id"]: row for row in catalog.json()}
        assert listed["list"]["input"]["fields"] == ["title_column", "author_column"]
        # Every other connector declares none, and the absent key stays absent
        # in behaviour rather than arriving as an empty patch to the screen.
        assert listed["goodreads"]["input"]["fields"] == []


class TestConfirmDiscard:
    """D4: choosing a proposal re-stages the row from the provider's payload;
    discard keeps the row as typed. Commit needs no new path."""

    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    async def _drain(self, app, batch_id: str) -> None:
        """Run the batch's search job the way the runner would, against a
        provider double, so no network is spent and the proposals exist."""
        from sqlalchemy import text as sql_text
        from sqlalchemy.orm import Session

        from book_tracker.application.import_search import ImportSearchHandler
        from book_tracker.domain.providers import SearchCandidate, SourceRef

        with Session(app.state.engine) as session:
            job_id = session.execute(
                sql_text("SELECT id FROM jobs WHERE batch_id = :b"), {"b": batch_id}
            ).scalar_one()

        class Double:
            name = "openlibrary"
            item_type = "book"

            async def search(self, query: str, limit: int = 20):
                return [
                    SearchCandidate(
                        source="openlibrary",
                        source_id="OL1M",
                        source_refs=(SourceRef(source="openlibrary", source_id="OL1M"),),
                        title="Rayuela",
                        subtitle=None,
                        creators=("Julio Cortázar",),
                        year=1963,
                        cover_url=None,
                        # The real provider shape: OpenLibraryProvider's
                        # candidates key their ISBN as `isbn13` (the `_isbn`
                        # helper), so the confirm path must normalize to the
                        # canonical `isbn` kind exactly as the add path does.
                        identifiers={"isbn13": "9788437604572"},
                        language="es",
                        metadata={"publisher": "Sudamericana"},
                    )
                ]

        handler = ImportSearchHandler(
            app.state.engine, {"openlibrary": Double()}, rate_limiter=None
        )
        result = await handler.process(job_id, NOW)
        assert result["state"] == "succeeded"

    async def _preview(self, client):
        response = await client.post(
            "/api/import/list/preview",
            files={
                "file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv"),
            },
            data={"targets": "book"},
        )
        assert response.status_code == 201
        return response.json()

    @pytest.mark.anyio
    async def test_confirming_re_stages_the_row_from_the_payload(self, tmp_path: Path) -> None:
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            body = await self._preview(client)
            batch_id = body["batch_id"]
            await self._drain(app, batch_id)
            records = (await self._preview(client))["records"]
            rayuela = next(record for record in records if record["title"] == "Rayuela")
            assert rayuela["proposals"], "the drained search wrote proposals"
            proposal = rayuela["proposals"][0]

            confirm = await client.post(
                f"/api/import/list/batches/{batch_id}/records/{rayuela['record_id']}/proposal",
                json={"source": proposal["source"], "source_id": proposal["source_id"]},
            )
            assert confirm.status_code == 200

            refreshed = next(
                record
                for record in (await self._preview(client))["records"]
                if record["record_id"] == rayuela["record_id"]
            )
            # The row is re-staged from the provider's payload: identifiers and
            # metadata the spreadsheet never had.
            assert refreshed["item"]["identifiers"] == {"isbn": "9788437604572"}
            assert refreshed["item"]["year"] == 1963
            assert refreshed["item"]["metadata"]["publisher"] == "Sudamericana"
            assert refreshed["proposals"][0]["chosen"] is True

    @pytest.mark.anyio
    async def test_discard_keeps_the_row_as_typed(self, tmp_path: Path) -> None:
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            body = await self._preview(client)
            batch_id = body["batch_id"]
            await self._drain(app, batch_id)
            records = (await self._preview(client))["records"]
            rayuela = next(record for record in records if record["title"] == "Rayuela")

            discard = await client.post(
                f"/api/import/list/batches/{batch_id}/records/{rayuela['record_id']}/proposal",
                json={"discard": True},
            )
            assert discard.status_code == 200

            refreshed = next(
                record
                for record in (await self._preview(client))["records"]
                if record["record_id"] == rayuela["record_id"]
            )
            assert refreshed["item"]["identifiers"] == {}
            assert refreshed["item"]["metadata"]["creators"] == ["Julio Cortázar"]
            assert all(proposal["chosen"] is False for proposal in refreshed["proposals"])

    @pytest.mark.anyio
    async def test_discard_after_confirm_restores_the_typed_row(self, tmp_path: Path) -> None:
        """The undo half of D4: an owner who confirms and then reconsiders
        discards, and the row returns to exactly what the spreadsheet said —
        no provider identifiers, metadata or year survive the final answer."""
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            body = await self._preview(client)
            batch_id = body["batch_id"]
            await self._drain(app, batch_id)
            records = (await self._preview(client))["records"]
            rayuela = next(record for record in records if record["title"] == "Rayuela")
            proposal = rayuela["proposals"][0]

            confirm = await client.post(
                f"/api/import/list/batches/{batch_id}/records/{rayuela['record_id']}/proposal",
                json={"source": proposal["source"], "source_id": proposal["source_id"]},
            )
            assert confirm.status_code == 200
            staged = next(
                record
                for record in (await self._preview(client))["records"]
                if record["record_id"] == rayuela["record_id"]
            )
            assert staged["item"]["identifiers"] == {"isbn": "9788437604572"}
            assert staged["item"]["year"] == 1963

            discard = await client.post(
                f"/api/import/list/batches/{batch_id}/records/{rayuela['record_id']}/proposal",
                json={"discard": True},
            )
            assert discard.status_code == 200

            refreshed = next(
                record
                for record in (await self._preview(client))["records"]
                if record["record_id"] == rayuela["record_id"]
            )
            # The final answer governs: the typed row is back, exactly as the
            # spreadsheet wrote it, with no provider data riding along.
            assert refreshed["item"]["identifiers"] == {}
            assert refreshed["item"]["year"] is None
            assert refreshed["item"]["subtitle"] is None
            assert refreshed["item"]["metadata"] == {"creators": ["Julio Cortázar"]}
            assert refreshed["planned_action"] == "create_item"
            assert refreshed["match_kind"] == "new"
            assert all(proposal["chosen"] is False for proposal in refreshed["proposals"])

    @pytest.mark.anyio
    async def test_commit_after_confirm_carries_the_provider_identity(self, tmp_path: Path) -> None:
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            body = await self._preview(client)
            batch_id = body["batch_id"]
            await self._drain(app, batch_id)
            records = (await self._preview(client))["records"]
            rayuela = next(record for record in records if record["title"] == "Rayuela")
            proposal = rayuela["proposals"][0]
            await client.post(
                f"/api/import/list/batches/{batch_id}/records/{rayuela['record_id']}/proposal",
                json={"source": proposal["source"], "source_id": proposal["source_id"]},
            )
            commit = await client.post("/api/import/list/commit", json={"batch_id": batch_id})
            assert commit.status_code == 200

            import sqlite3

            with sqlite3.connect(tmp_path / "books.db") as connection:
                found = connection.execute(
                    "SELECT identifiers FROM items WHERE title = 'Rayuela'"
                ).fetchone()
                assert found and "9788437604572" in found[0]
                homer = connection.execute(
                    "SELECT identifiers FROM items WHERE title = 'Homero'"
                ).fetchone()
                assert homer and homer[0] == "{}"
                # The confirmed identity lands under its canonical kind, the
                # same kind the add path writes: a raw provider key (`isbn13`)
                # is invisible to the enrichment join and the library's
                # exact-identity match, so the confirmed row would never get
                # its cover fetched nor match a future import.
                kinds = connection.execute(
                    "SELECT kind, normalized_value FROM item_identifiers"
                    " JOIN items ON items.id = item_identifiers.item_id"
                    " WHERE items.title = 'Rayuela'"
                ).fetchall()
                assert kinds == [("isbn", "9788437604572")]
                # And the row is backfillable: enrichment keys on the isbn.
                backfillable = connection.execute(
                    "SELECT count(*) FROM item_identifiers"
                    " JOIN items ON items.id = item_identifiers.item_id"
                    " WHERE items.title = 'Rayuela' AND item_identifiers.kind = 'isbn'"
                ).fetchone()
                assert backfillable and backfillable[0] == 1

    @pytest.mark.anyio
    async def test_another_users_batch_is_not_found(self, tmp_path: Path) -> None:
        """The proposal surface is inside the import boundary: another user's
        batch is the same not-found it always was (the 079 isolation pattern,
        driven through the service the routes wrap)."""
        import httpx

        from book_tracker.application.library import LibraryError
        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            body = await self._preview(client)
            batch_id = body["batch_id"]

            from sqlalchemy import text as sql_text

            with app.state.engine.begin() as connection:
                connection.execute(
                    sql_text(
                        "INSERT INTO users (id, username, display_name, password_hash,"
                        " password_salt, is_admin, created_at, updated_at)"
                        " VALUES (2, 'second', 'Second', 'x', 'y', 0,"
                        " '2026-09-13T00:00:00Z', '2026-09-13T00:00:00Z')"
                    )
                )

            from book_tracker.application.imports import ImportService
            from book_tracker.domain.list import IMPORTER as LIST_IMPORTER

            service = ImportService(
                app.state.engine,
                tmp_path,
                tmp_path,
                LIST_IMPORTER,
                user_id=2,
                attachment_max_bytes=1024,
            )
            with pytest.raises(LibraryError) as refused:
                service.get_preview(batch_id)
            assert refused.value.status_code == 404


class TestOwnerBatch20260914:
    """The owner's post-sprint feedback (2026-09-14), built hotfix-style:
    the connector is "Custom list"; a row can be excluded from the commit
    entirely; any row's title/author can be edited and re-searched; up to
    ten proposals are stored per row."""

    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    async def _drained(self, app, client, batch_id):
        """Run the batch's search job the way the runner would, against the
        provider double, and return the drained preview's records. The double
        also replaces the app's provider registry so the re-search route —
        interactive, not job-driven — answers from it too, never the live
        boundary (DEC-025's rule)."""
        from sqlalchemy import text as sql_text
        from sqlalchemy.orm import Session

        from book_tracker.application.import_search import ImportSearchHandler
        from book_tracker.domain.providers import SearchCandidate, SourceRef

        with Session(app.state.engine) as session:
            job_id = session.execute(
                sql_text("SELECT id FROM jobs WHERE batch_id = :b"), {"b": batch_id}
            ).scalar_one()

        class Double:
            name = "openlibrary"
            item_type = "book"

            def __init__(self) -> None:
                self.queries: list[str] = []

            async def search(self, query: str, limit: int = 20):
                self.queries.append(query)
                # The typed row ("Homero,Iliada" — transposed) gets nothing;
                # the corrected query gets its answer, so a re-search is
                # visibly a different question.
                if query.startswith("Homero"):
                    return []
                return [
                    SearchCandidate(
                        source="openlibrary",
                        source_id=f"OL{abs(hash(query)) % 10**6}M",
                        source_refs=(
                            SourceRef(
                                source="openlibrary", source_id=f"OL{abs(hash(query)) % 10**6}M"
                            ),
                        ),
                        title="Rayuela",
                        subtitle=None,
                        creators=("Julio Cortázar",),
                        year=1963,
                        cover_url=None,
                        identifiers={"isbn13": "9788437604572"},
                        language="es",
                        metadata={"publisher": "Sudamericana"},
                    )
                ]

        double = Double()
        handler = ImportSearchHandler(app.state.engine, {"openlibrary": double}, rate_limiter=None)
        result = await handler.process(job_id, NOW)
        assert result["state"] == "succeeded"
        app.state.providers = {"openlibrary": double}
        records = (await self._get(client, batch_id))["records"]
        return records, double

    async def _get(self, client, batch_id):
        response = await client.get(f"/api/import/list/batches/{batch_id}")
        assert response.status_code == 200
        return response.json()

    async def _preview(self, client):
        response = await client.post(
            "/api/import/list/preview",
            files={
                "file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv"),
            },
            data={"targets": "book"},
        )
        assert response.status_code == 201
        return response.json()

    @pytest.mark.anyio
    async def test_the_catalog_publishes_the_custom_list_label(self, tmp_path: Path) -> None:
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            catalog = (await client.get("/api/importers")).json()
            entry = next(importer for importer in catalog if importer["id"] == "list")
            assert entry["label"] == "Custom list"
            assert entry["input"]["label"] == "Your list (CSV or text)"

    @pytest.mark.anyio
    async def test_ten_proposals_are_stored_per_row(self, tmp_path: Path) -> None:
        """Ten merged results ride the preview, not three: the screen shows
        three and expands to the rest (the owner's 'Show more')."""
        import httpx

        from book_tracker.application.import_search import ImportSearchHandler
        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            body = await self._preview(client)
            batch_id = body["batch_id"]

            from sqlalchemy import text as sql_text
            from sqlalchemy.orm import Session

            from book_tracker.domain.providers import SearchCandidate, SourceRef

            with Session(app.state.engine) as session:
                job_id = session.execute(
                    sql_text("SELECT id FROM jobs WHERE batch_id = :b"), {"b": batch_id}
                ).scalar_one()

            class Ten:
                name = "openlibrary"
                item_type = "book"

                async def search(self, query: str, limit: int = 20):
                    return [
                        SearchCandidate(
                            source="openlibrary",
                            source_id=f"OL{index}M",
                            source_refs=(SourceRef(source="openlibrary", source_id=f"OL{index}M"),),
                            title=f"Rayuela edition {index}",
                            subtitle=None,
                            creators=("Julio Cortázar",),
                            year=1963,
                            cover_url=None,
                            identifiers={"isbn13": f"97800000000{index:02d}"},
                            language="es",
                            metadata={},
                        )
                        for index in range(20)
                    ]

            handler = ImportSearchHandler(
                app.state.engine, {"openlibrary": Ten()}, rate_limiter=None
            )
            await handler.process(job_id, NOW)

            records = (await self._get(client, batch_id))["records"]
            rayuela = next(record for record in records if record["title"] == "Rayuela")
            assert len(rayuela["proposals"]) == 10

    @pytest.mark.anyio
    async def test_a_row_can_be_excluded_and_the_commit_skips_it(self, tmp_path: Path) -> None:
        """The owner's decision: 'discard' on a no-results row was the only
        outcome and forced a keep. A row can now be excluded from the commit
        entirely — the summary recomputes, nothing lands for it."""
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            body = await self._preview(client)
            batch_id = body["batch_id"]
            records, _double = await self._drained(app, client, batch_id)
            before = next(record for record in records if record["title"] == "Rayuela")
            ready_before = (await self._get(client, batch_id))["summary"]["ready"]

            excluded = await client.post(
                f"/api/import/list/batches/{batch_id}/records/{before['record_id']}/exclude"
            )
            assert excluded.status_code == 200

            refreshed = await self._get(client, batch_id)
            row = next(
                record
                for record in refreshed["records"]
                if record["record_id"] == before["record_id"]
            )
            assert row["planned_action"] == "excluded"
            assert refreshed["summary"]["ready"] == ready_before - 1
            # The undo half: restoring returns the row to ready.
            restored = await client.post(
                f"/api/import/list/batches/{batch_id}/records/{before['record_id']}/include"
            )
            assert restored.status_code == 200
            row = next(
                record
                for record in (await self._get(client, batch_id))["records"]
                if record["record_id"] == before["record_id"]
            )
            assert row["planned_action"] == "create_item"

            # Exclude again, then commit: the row must not land.
            await client.post(
                f"/api/import/list/batches/{batch_id}/records/{before['record_id']}/exclude"
            )
            commit = await client.post("/api/import/list/commit", json={"batch_id": batch_id})
            assert commit.status_code == 200
            # The inline fixture carries 8 healthy rows (10 lines, 2 errors):
            # excluding one leaves 7 to land.
            assert commit.json()["created_entries"] == 7

            import sqlite3

            with sqlite3.connect(tmp_path / "books.db") as connection:
                landed = connection.execute(
                    "SELECT count(*) FROM items WHERE title = 'Rayuela'"
                ).fetchone()[0]
                assert landed == 0, "an excluded row landed in the library"

    @pytest.mark.anyio
    async def test_any_row_can_be_re_searched_with_edited_text(self, tmp_path: Path) -> None:
        """The owner's decision: editing is not gated on empty rows — a bad
        query can also produce wrong proposals. The route re-stages the row's
        title/author and replaces its proposals with fresh results."""
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            body = await self._preview(client)
            batch_id = body["batch_id"]
            records, double = await self._drained(app, client, batch_id)
            homer = next(record for record in records if record["title"] == "Homero")
            assert homer["proposals"] == [], "the double returns nothing for Homero"

            searched = await client.post(
                f"/api/import/list/batches/{batch_id}/records/{homer['record_id']}/search",
                json={"title": "La Ilíada", "author": "Homero"},
            )
            assert searched.status_code == 200

            row = next(
                record
                for record in (await self._get(client, batch_id))["records"]
                if record["record_id"] == homer["record_id"]
            )
            # The typed row is re-staged with the edited text...
            assert row["title"] == "La Ilíada"
            assert row["item"]["title"] == "La Ilíada"
            assert row["item"]["metadata"]["creators"] == ["Homero"]
            # ...and the double answered the edited query with its proposal.
            assert row["proposals"], "the re-search wrote proposals"
            assert "La Ilíada Homero" in double_queries(double)

            # A search on a matching batch is refused the way answers are.
            matching = await client.post(
                f"/api/import/list/batches/{batch_id}/records/{row['record_id']}/search",
                json={"title": "again"},
            )
            assert matching.status_code == 200  # the batch is drained; still allowed


class TestAnyDomain20260914:
    """Sprint 084: the list reader is domain-declared — any registered domain
    that declares list columns is importable, the header words and the
    creator column's meaning come from the domain, and one list is one
    domain per batch (the choice composes the fingerprint)."""

    def test_the_reader_declares_every_listable_domain(self) -> None:
        from book_tracker.domain.registry import DOMAINS

        importer = ListImporter()
        expected = tuple(
            item_type for item_type, domain in DOMAINS.items() if domain.list_columns is not None
        )
        assert "book" in expected
        assert "album" in expected
        assert "movie" in expected
        assert importer.item_types == expected

    def test_every_declared_domain_has_title_words(self) -> None:
        from book_tracker.domain.registry import DOMAINS

        for item_type, domain in DOMAINS.items():
            if domain.list_columns is None:
                continue
            assert domain.list_columns.title_headers, f"{item_type} has no title words"
            # Creator words may be empty (a film list is often one column),
            # but the spec must be explicit about it.
            assert isinstance(domain.list_columns.creator_headers, tuple)

    def test_an_album_list_autodetects_album_and_artist_headers(self) -> None:
        csv = "Álbum,Artista\r\nKind of Blue,Miles Davis\r\nDiscovery,Daft Punk\r\n"
        snapshot = read_all(csv, domain="album")
        by_title = records_by_title(snapshot)
        assert by_title["Kind of Blue"].item.metadata["creators"] == ["Miles Davis"]
        assert by_title["Kind of Blue"].item_type == "album"

    def test_a_film_list_with_one_column_imports_with_empty_creators(self) -> None:
        """A film list is often just titles: the movie domain declares no
        creator words, so a one-column list is valid and the creator is
        empty — not an error."""
        csv = "Película\r\nBlade Runner\r\nSuspiria\r\n"
        snapshot = read_all(csv, domain="movie")
        by_title = records_by_title(snapshot)
        assert by_title["Blade Runner"].item.metadata == {}
        assert by_title["Blade Runner"].item_type == "movie"
        assert not by_title["Blade Runner"].errors

    def test_a_single_column_book_list_is_still_missing_columns(self) -> None:
        """Books declare creator words, so a one-column book list still
        needs its second column — the declaration governs, not the reader."""
        csv = "Título\r\nRayuela\r\n"
        importer = ListImporter()
        with pytest.raises(ListCSVError) as refused:
            importer.read(
                ImportSource(
                    data=csv.encode("utf-8"),
                    filename="libros.csv",
                    options={"targets": "book"},
                ),
                CONTEXT,
            )
        assert refused.value.code == "missing_columns"

    def test_the_domain_choice_composes_the_fingerprint(self) -> None:
        """One list, one domain per batch: the same file for two domains is
        two imports, and re-previewing returns the stored batch."""
        csv = "Title,Creator\r\nRayuela,Julio Cortázar\r\n"
        book_snapshot = read_all(csv, domain="book")
        album_snapshot = read_all(csv, domain="album")
        assert book_snapshot.fingerprint != album_snapshot.fingerprint
        assert "book" in book_snapshot.fingerprint or book_snapshot.fingerprint
        # And the same domain twice is the same import (byte-identical replay).
        again = read_all(csv, domain="book")
        assert again.fingerprint == book_snapshot.fingerprint

    def test_rows_carry_the_chosen_domains_type(self) -> None:
        csv = "Album,Artist\r\nKind of Blue,Miles Davis\r\n"
        snapshot = read_all(csv, domain="album")
        assert all(record.item_type == "album" for record in snapshot.records)

    def test_no_domain_choice_refuses_for_a_multi_domain_connector(self) -> None:
        """The choice is required: a connector that serves five domains
        cannot guess which library the rows belong in."""
        csv = "Title\r\nRayuela\r\n"
        importer = ListImporter()
        with pytest.raises(ListCSVError) as refused:
            importer.read(
                ImportSource(data=csv.encode("utf-8"), filename="libros.csv"),
                CONTEXT,
            )
        # The refusal names the thing to fix (the library), not a column
        # complaint — the reader cannot even interpret the file's shape
        # without knowing whose vocabulary to read it with.
        assert refused.value.code == "invalid_import_target"

    def test_book_autodetection_is_unchanged(self) -> None:
        """The v2.1.0 regression contract: books keep their word lists and
        behaviour byte-for-byte."""
        csv = "﻿Título del libro,Autor,Editorial \r\nRayuela,Julio Cortázar, Sudamericana\r\n"
        snapshot = read_all(csv, domain="book")
        by_title = records_by_title(snapshot)
        assert by_title["Rayuela"].item.metadata["creators"] == ["Julio Cortázar"]
        assert by_title["Rayuela"].source_fields["Editorial"] == "Sudamericana"
        assert by_title["Rayuela"].item_type == "book"


def double_queries(double) -> list[str]:
    """The queries a provider double saw, for assertions inside tests."""
    return getattr(double, "queries", [])


class TestSyntheticFixture:
    @pytest.fixture
    def anyio_backend(self) -> str:
        return "asyncio"

    """The sanitized 12-row fixture, shaped like the owner's real CSV (BOM,
    CRLF, the trailing-space header, a transposed row, a collection volume, a
    typo, an `et al` author, a quoted comma, a no-title row, a short row) but
    with rows written for this suite — the real file never leaves the
    git-ignored `exports/`."""

    FIXTURE = Path(__file__).parent / "fixtures" / "imports" / "list_synthetic.csv"

    def test_the_fixture_auto_maps_and_reads_honestly(self) -> None:
        data = self.FIXTURE.read_bytes()
        importer = ListImporter()
        snapshot = importer.read(
            ImportSource(data=data, filename="list_synthetic.csv", options={"targets": "book"}),
            CONTEXT,
        )
        # 12 data rows (the fixture the sprint names), one header, every
        # non-empty row present — including the error rows the reader refuses
        # to invent data for.
        assert len(snapshot.records) == 12
        titles = {record.item.title for record in snapshot.records}
        assert "Rayuela" in titles
        assert '"Will Grayson, Will Grayson"'.strip('"') in titles or (
            "Will Grayson, Will Grayson" in titles
        )
        # The transposed row reads literally; confirm is the safety net.
        assert "Homero" in titles
        # Error rows are present with their reasons.
        empty_title = [record for record in snapshot.records if not record.item.title]
        assert empty_title and empty_title[0].errors[0]["field"] == "title"
        short = [record for record in snapshot.records if record.item.title == "Solo un título"]
        assert short and {"field": "author", "code": "missing"} in [
            {"field": error["field"], "code": error["code"]} for error in short[0].errors
        ]
        # The unmapped columns ride verbatim, trailing-space header and all.
        rayuela = next(record for record in snapshot.records if record.item.title == "Rayuela")
        assert rayuela.source_fields["Editorial"] == "Sudamericana"
        assert rayuela.source_fields["Idioma"] == "Castellano"

    @pytest.mark.anyio
    async def test_the_fixture_round_trips_the_service(self, tmp_path: Path) -> None:
        """The whole preview path on the fixture: staging, summary counts that
        agree with the record list, and the matching state this connector
        previews in (AC4's shape, through the service)."""
        import httpx

        from book_tracker.config import Settings
        from book_tracker.main import create_app

        app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            preview = await client.post(
                "/api/import/list/preview",
                files={
                    "file": (
                        "list_synthetic.csv",
                        self.FIXTURE.read_bytes(),
                        "text/csv",
                    )
                },
                data={"targets": "book"},
            )
            assert preview.status_code == 201
            body = preview.json()
            assert body["state"] == "matching"
            summary = body["summary"]
            records = body["records"]
            assert summary["total"] == len(records)
            # The summary's own definition: rows the commit will refuse.
            assert summary["errors"] == sum(
                1
                for record in records
                if record["planned_action"] in ("error", "identity_conflict")
            )
            assert summary["total"] == 12
