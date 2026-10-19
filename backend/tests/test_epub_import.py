"""The ebook-files connector: an EPUB describes itself (Sprint 086, DEC-164)."""

import zipfile
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.domain.importers import ImportReadContext, ImportSource
from book_tracker.domain.registry import IMPORTERS
from book_tracker.main import create_app

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="{opf}" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""

#: The owner's DDIA 2nd edition, as O'Reilly shipped it: a stamped dc:title beside a clean
#: dcterms:title, an unschemed hyphenated ISBN, both authors in one creator, a PNG cover
#: declared both ways. Reduced to its metadata; the shape is verbatim.
DDIA_OPF = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/"
 version="3.0" unique-identifier="pub-identifier"><metadata>
<dc:identifier id="pub-identifier">978-1-098-11906-5</dc:identifier>
<dc:title id="pub-title">Designing Data-Intensive Applications (for dagfhhhhh dfafaf)</dc:title>
<meta property="dcterms:title" id="meta-title">Designing Data-Intensive Applications</meta>
<dc:language id="pub-language">en</dc:language>
<dc:publisher>O'Reilly Media, Inc.</dc:publisher>
<dc:date>2024-09-03</dc:date>
<dc:description>Data is at the center of &lt;b&gt;many&lt;/b&gt; challenges.</dc:description>
<dc:creator>Martin Kleppmann and Chris Riccomini</dc:creator>
<meta name="cover" content="cover-image"/>
</metadata><manifest>
<item id="cover-image" properties="cover-image" href="assets/cover.png" media-type="image/png"/>
</manifest></package>"""

EPUB2_OPF = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:opf="http://www.idpf.org/2007/opf" version="2.0"><metadata>
<dc:title>Ficciones</dc:title>
<dc:creator opf:role="aut" opf:file-as="Borges, Jorge Luis">Jorge Luis Borges</dc:creator>
<dc:creator opf:role="trl">Anthony Kerrigan</dc:creator>
<dc:identifier opf:scheme="ISBN">urn:isbn:9780141187761</dc:identifier>
<dc:identifier opf:scheme="uuid">urn:uuid:1234</dc:identifier>
<dc:subject>Fiction</dc:subject><dc:subject>Short stories</dc:subject>
<dc:date>1944</dc:date>
<meta name="calibre:series" content="Penguin Modern Classics"/>
<meta name="cover" content="cov"/>
</metadata><manifest>
<item id="cov" href="images/front.jpg" media-type="image/jpeg"/>
</manifest></package>"""

EPUB3_ROLES_OPF = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/"
 version="3.0"><metadata>
<dc:title>Rayuela</dc:title>
<dc:creator id="c1">Julio Cortázar</dc:creator>
<meta refines="#c1" property="role" scheme="marc:relators">aut</meta>
<dc:creator id="c2">Gregory Rabassa</dc:creator>
<meta refines="#c2" property="role" scheme="marc:relators">trl</meta>
<meta property="belongs-to-collection" id="col">Biblioteca Cortázar</meta>
</metadata><manifest/></package>"""


def _image(kind: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (60, 90), "navy").save(buffer, kind)
    return buffer.getvalue()


def build_epub(
    path: Path,
    opf: str,
    *,
    opf_path: str = "OEBPS/content.opf",
    assets: dict[str, bytes] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", CONTAINER.format(opf=opf_path))
        archive.writestr(opf_path, opf)
        base = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""
        for name, data in (assets or {}).items():
            archive.writestr(base + name, data)
    return path


def ddia(path: Path) -> Path:
    return build_epub(
        path, DDIA_OPF, opf_path="content.opf", assets={"assets/cover.png": _image("PNG")}
    )


def ficciones(path: Path) -> Path:
    return build_epub(path, EPUB2_OPF, assets={"images/front.jpg": _image("JPEG")})


def _read(tmp_path: Path, *files: Path):  # noqa: ANN202 - a snapshot, typed by the reader
    parts = tmp_path / "export" / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    for file in files:
        (parts / file.name).write_bytes(file.read_bytes())
    importer = IMPORTERS["epub"]
    return importer.read(
        ImportSource(export=tmp_path / "export"), ImportReadContext(path_root=tmp_path)
    )


def test_the_owners_ddia_file_reads_as_the_book_it_is(tmp_path: Path) -> None:
    snapshot = _read(tmp_path, ddia(tmp_path / "in" / "ddia.epub"))
    [record] = snapshot.records
    assert record.errors == ()
    assert record.item.title == "Designing Data-Intensive Applications"
    assert record.item.year == 2024
    assert record.item.identifiers == {"isbn": "9781098119065"}
    metadata = record.item.metadata
    assert metadata["creators"] == ["Martin Kleppmann", "Chris Riccomini"]
    assert metadata["publisher"] == "O'Reilly Media, Inc."
    assert metadata["language"] == "en"
    assert metadata["description"] == "Data is at the center of many challenges."
    assert record.source_files == ("ddia.epub",)
    assert record.attachment_name == "ddia.epub"
    assert record.attachment_source and Path(record.attachment_source).is_file()
    assert record.cover_source and Path(record.cover_source).is_file()
    assert record.entry.suggested_status is None


def test_epub2_roles_schemes_subjects_and_series(tmp_path: Path) -> None:
    [record] = _read(tmp_path, ficciones(tmp_path / "in" / "Ficciones.epub")).records
    assert record.item.title == "Ficciones"
    assert record.item.metadata["creators"] == ["Jorge Luis Borges"]
    assert record.item.creator_sort == "Borges, Jorge Luis"
    assert record.item.identifiers == {"isbn": "9780141187761"}
    assert record.item.metadata["subjects"] == ["Fiction", "Short stories"]
    assert record.item.metadata["series"] == "Penguin Modern Classics"
    assert record.item.year == 1944
    assert record.cover_source is not None


def test_epub3_refined_roles_keep_authors_and_collection_is_the_series(tmp_path: Path) -> None:
    [record] = _read(tmp_path, build_epub(tmp_path / "in" / "r.epub", EPUB3_ROLES_OPF)).records
    assert record.item.metadata["creators"] == ["Julio Cortázar"]
    assert record.item.metadata["series"] == "Biblioteca Cortázar"
    assert record.item.identifiers == {}
    assert record.cover_source is None


def test_a_broken_file_is_one_errored_row_and_the_rest_still_read(tmp_path: Path) -> None:
    broken = tmp_path / "in" / "not-a-book.epub"
    broken.parent.mkdir(parents=True)
    broken.write_bytes(b"this is not a zip")
    good = ficciones(tmp_path / "in" / "Ficciones.epub")
    records = _read(tmp_path, broken, good).records
    assert len(records) == 2
    errored = next(record for record in records if record.errors)
    assert errored.item.title == "not-a-book"
    assert errored.errors[0]["code"] == "invalid_epub"
    assert errored.attachment_source is None
    assert any(not record.errors and record.item.title == "Ficciones" for record in records)


def test_a_document_declaring_entities_is_refused_as_that_files_error(tmp_path: Path) -> None:
    hostile = DDIA_OPF.replace(
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?xml version="1.0"?><!DOCTYPE p [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;">]>',
    )
    [record] = _read(
        tmp_path, build_epub(tmp_path / "in" / "x.epub", hostile, opf_path="content.opf")
    ).records
    assert record.errors and record.errors[0]["code"] == "invalid_epub"


def test_a_file_with_no_title_falls_back_to_its_filename(tmp_path: Path) -> None:
    untitled = EPUB3_ROLES_OPF.replace("<dc:title>Rayuela</dc:title>", "")
    [record] = _read(
        tmp_path, build_epub(tmp_path / "in" / "Some Book -- Author.epub", untitled)
    ).records
    assert record.item.title == "Some Book -- Author"
    assert record.errors == ()


def test_the_fingerprint_is_the_files_not_their_order(tmp_path: Path) -> None:
    a = ddia(tmp_path / "in" / "a.epub")
    b = ficciones(tmp_path / "in" / "b.epub")
    first = _read(tmp_path / "one", a, b).fingerprint
    second = _read(tmp_path / "two", b, a).fingerprint
    assert first == second
    assert first != _read(tmp_path / "three", a).fingerprint


# --------------------------------------------------------------------------------------
# Through the route: preview, commit, Triage, attachment, cover
# --------------------------------------------------------------------------------------


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app(tmp_path: Path) -> object:
    return create_app(
        Settings(
            data_dir=tmp_path / "data",
            calibre_dir=tmp_path / "absent",
            user_agent_contact="test@example.invalid",
        )
    )


def _files(*paths: Path) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (path.name, path.read_bytes(), "application/epub+zip")) for path in paths]


@pytest.mark.anyio
async def test_three_dropped_epubs_land_in_triage_with_their_file_and_cover(
    tmp_path: Path,
) -> None:
    files = (
        ddia(tmp_path / "in" / "Designing Data-Intensive Applications.epub"),
        ficciones(tmp_path / "in" / "Ficciones.epub"),
        build_epub(tmp_path / "in" / "Rayuela.epub", EPUB3_ROLES_OPF),
    )
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        catalog = (await client.get("/api/importers")).json()
        epub = next(row for row in catalog if row["id"] == "epub")
        assert epub["input"]["quick_add"] is True
        assert epub["input"]["kind"] == "export"
        assert all(not row["input"]["quick_add"] for row in catalog if row["id"] != "epub")

        preview = await client.post("/api/import/epub/preview", files=_files(*files))
        assert preview.status_code == 201, preview.text
        records = preview.json()["records"]
        assert sorted(record["title"] for record in records) == [
            "Designing Data-Intensive Applications",
            "Ficciones",
            "Rayuela",
        ]
        assert all(record["attachment_staged"] for record in records)
        # Nothing searched these rows, so they carry no proposal list at all: an
        # empty one reads on the screen as "searched and found nothing".
        assert all("proposals" not in record for record in records)
        assert sum(record["cover_staged"] for record in records) == 2

        committed = await client.post(
            "/api/import/epub/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        assert committed.status_code == 200, committed.text
        assert committed.json()["created_entries"] == 3
        assert committed.json()["unsorted_entries"] == 3

        with app.state.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT items.id, items.title, items.cover_path, entries.status "
                    "FROM items JOIN entries ON entries.item_id = items.id ORDER BY items.title"
                )
            ).all()
        assert [row.status for row in rows] == ["unsorted"] * 3
        assert [bool(row.cover_path) for row in rows] == [True, True, False]
        attached = await client.get(f"/api/items/{rows[0].id}/attachments")
        assert [row["filename"] for row in attached.json()["attachments"]] == [
            "Designing Data-Intensive Applications.epub"
        ]

        replay = await client.post("/api/import/epub/preview", files=_files(*files))
        assert replay.status_code in (200, 201)
        assert replay.json()["batch_id"] == preview.json()["batch_id"]


@pytest.mark.anyio
async def test_an_epub_for_a_book_already_held_matches_by_isbn(tmp_path: Path) -> None:
    app = _app(tmp_path)
    file = ficciones(tmp_path / "in" / "Ficciones.epub")
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        first = await client.post("/api/import/epub/preview", files=_files(file))
        await client.post("/api/import/epub/commit", json={"batch_id": first.json()["batch_id"]})
        renamed = tmp_path / "in2" / "ficciones-other-copy.epub"
        build_epub(
            renamed,
            EPUB2_OPF.replace("<dc:title>Ficciones</dc:title>", "<dc:title>Fictions</dc:title>"),
            assets={"images/front.jpg": _image("JPEG")},
        )
        second = await client.post("/api/import/epub/preview", files=_files(renamed))
        [record] = second.json()["records"]
        assert record["match_kind"] == "exact"
        with app.state.engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM items")) == 1


@pytest.mark.anyio
async def test_a_file_that_is_not_an_epub_is_refused_before_it_is_written(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        refused = await client.post(
            "/api/import/epub/preview",
            files=[("files", ("notes.pdf", b"%PDF-1.4", "application/pdf"))],
        )
        assert refused.status_code == 422
        assert refused.json()["error"]["details"]["member"] == "notes.pdf"
