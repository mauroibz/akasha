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
from book_tracker.domain.matching import MatchDecision, MatchKind
from book_tracker.domains.book.list import (
    ListCSVError,
    ListImporter,
    detect_delimiter,
    sniff_mapping,
)

CONTEXT = ImportReadContext(path_root=Path("/tmp"))


def csv_source(data: str, filename: str = "libros.csv") -> ImportSource:
    return ImportSource(data=data.encode("utf-8"), filename=filename)


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


def read_all(data: str, mapping: dict[str, int] | None = None):
    importer = ListImporter()
    return importer.read(csv_source(data), CONTEXT)


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
        source = ImportSource(data=b"\xff\xfe\x00bad", filename="x.csv")
        with pytest.raises(ListCSVError) as refused:
            ListImporter().read(source, CONTEXT)
        assert refused.value.code == "invalid_csv"

    def test_no_data_is_refused(self) -> None:
        source = ImportSource(data=None, filename="x.csv")
        with pytest.raises(ListCSVError) as refused:
            ListImporter().read(source, CONTEXT)
        assert refused.value.code == "invalid_csv"

    def test_the_error_codes_are_declared(self) -> None:
        assert ListImporter.error_codes == frozenset(
            {"invalid_csv", "missing_columns", "column_not_mapped"}
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
        assert snapshot.fingerprint == expected

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
            options={"title_column": 1, "author_column": 0},
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
                options={"title_column": 1, "author_column": 0},
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
                    options={"title_column": 99},
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
                    options={"author_column": -1},
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
                    options={"title_column": "Autor"},
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
                files={"file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv")},
                data={"title_column": "1", "author_column": "0"},
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
                files={"file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv")},
            )
            assert preview.status_code == 201
            body = preview.json()
            rayuela = [record for record in body["records"] if record["title"] == "Rayuela"]
            assert rayuela[0]["creators"] == ["Julio Cortázar"]
            # A same-bytes re-preview is idempotent, not a second batch.
            again = await client.post(
                "/api/import/list/preview",
                files={"file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv")},
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
                files={"file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv")},
                data={"title_column": "99"},
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
                        identifiers={"isbn": "9788437604572"},
                        language="es",
                        metadata={"publisher": "Sudamericana"},
                    )
                ]

        handler = ImportSearchHandler(
            app.state.engine, {"openlibrary": Double()}, rate_limiter=None
        )
        result = await handler.process(job_id, None)
        assert result["state"] == "succeeded"

    async def _preview(self, client):
        response = await client.post(
            "/api/import/list/preview",
            files={"file": ("libros.csv", SYNTHETIC_CSV.encode("utf-8"), "text/csv")},
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
            from book_tracker.domains.book.list import IMPORTER as LIST_IMPORTER

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
