import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

from book_tracker.domain.identity import normalize_identifier
from book_tracker.domain.importers import (
    ImportBrowseResult,
    ImportCandidate,
    ImportEntry,
    ImportInputSpec,
    ImportInventory,
    ImportItem,
    ImportMatcher,
    ImportPlan,
    ImportReadContext,
    ImportReadError,
    ImportSnapshot,
    ImportSource,
    NormalizedImportRecord,
)
from book_tracker.domain.matching import MatchDecision
from book_tracker.domain.normalization import shelf_slug
from book_tracker.domains.book import DOMAIN
from book_tracker.infrastructure.covers import CoverError, prepare_uploaded_cover

#: The ebook formats a Calibre library may hand over, in the order one file per book
#: is picked when a book has several. Epub leads because it is the open one and,
#: measured on the owner's library, the cheaper one: 95.4 MB against 163 MB for every
#: format of the same 18 books (DEC-083).
EBOOK_FORMATS = ("epub", "azw3", "mobi", "pdf", "cbz", "cbr", "txt")


class CalibreError(ImportReadError):
    """Every way a Calibre mount can refuse, with what the reader can do about it.

    The vocabulary is closed and declared on `CalibreImporter.error_codes`. Each code
    carries the sentence a person can act on, because "Calibre database could not be
    read" is true and useless on its own (DEC-080).
    """

    ACTIONS = {
        "invalid_calibre_path": (
            "That folder is not inside the Calibre library Akasha can see.",
            "Pick a folder from the list rather than typing a path.",
        ),
        "calibre_library_not_found": (
            "No Calibre library sits at that folder.",
            "Choose the folder that contains metadata.db — usually the one Calibre "
            "calls your Calibre Library.",
        ),
        "invalid_calibre_database": (
            "Akasha could not read this library's metadata.db.",
            "Close Calibre and try again; it locks the database while it is writing.",
        ),
        "invalid_calibre_export": (
            "Akasha could not read this export.",
            "Make sure every part-*.calibre-data file the export produced is dropped "
            "in together, from the same export.",
        ),
    }

    def __init__(self, code: str, message: str) -> None:
        user_message, action = self.ACTIONS.get(code, (None, None))
        super().__init__(code, message, user_message=user_message, action=action)


@dataclass(frozen=True)
class CalibreSnapshot:
    fingerprint: str
    library: Path
    records: list[dict[str, Any]]


class CalibreAdapter:
    REQUIRED_TABLES = {"books", "authors", "books_authors_link", "identifiers"}

    def __init__(self, root: Path) -> None:
        self.root = root

    def confine(self, library_path: str, *, allow_root: bool = False) -> Path:
        """The absolute folder a relative request names, or a refusal.

        The one place confinement is decided, so browsing and reading cannot drift
        apart: a path that `browse` would walk into is exactly a path `read` would
        open. Rejected before touching the filesystem when it is absolute or contains
        `..`, and again after resolution, which is what catches a symlink inside the
        mount pointing out of it.
        """
        relative = Path(library_path)
        if (
            (not library_path.strip() and not allow_root)
            or relative.is_absolute()
            or ".." in relative.parts
        ):
            raise CalibreError("invalid_calibre_path", "Calibre library path must be relative")
        try:
            root = self.root.resolve(strict=True)
            library = (root / relative).resolve(strict=True)
        except OSError as error:
            raise CalibreError(
                "calibre_library_not_found", "Calibre library was not found"
            ) from error
        if not library.is_relative_to(root) or not library.is_dir():
            raise CalibreError("invalid_calibre_path", "Calibre library path is not allowed")
        return library

    def browse(self, library_path: str) -> ImportBrowseResult:
        """What one folder under the mount holds — subfolder names, and nothing else.

        No file names, no absolute paths, no sizes: the reader is choosing a library,
        and everything past that would publish the deployment's filesystem layout to
        anyone who can reach the LAN. An unreadable folder lists as empty rather than
        failing the whole request; one directory the server cannot stat is not a reason
        to refuse the ones it can.
        """
        library = self.confine(library_path, allow_root=True)
        relative = str(Path(library_path)) if library_path.strip() else ""
        try:
            names = sorted(
                child.name
                for child in library.iterdir()
                if child.is_dir() and not child.is_symlink()
            )
        except OSError:
            names = []
        # Only the mount root has no parent. A first-level folder's parent is the
        # root, which is "" — the same empty string the client sends to list it.
        above = str(Path(relative).parent) if relative else None
        return ImportBrowseResult(
            path=relative,
            parent=None if above is None else ("" if above == "." else above),
            directories=tuple(names),
            importable=(library / "metadata.db").is_file() and bool(relative),
        )

    def read(self, library_path: str) -> CalibreSnapshot:
        library = self.confine(library_path)
        try:
            database = (library / "metadata.db").resolve(strict=True)
        except OSError as error:
            raise CalibreError(
                "calibre_library_not_found", "Calibre library was not found"
            ) from error
        if not database.is_relative_to(library) or not database.is_file():
            raise CalibreError("invalid_calibre_path", "Calibre library path is not allowed")
        data = database.read_bytes()
        try:
            connection = sqlite3.connect(f"file:{quote(str(database))}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            query_only = bool(connection.execute("PRAGMA query_only").fetchone()[0])
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if not self.REQUIRED_TABLES.issubset(tables):
                raise CalibreError(
                    "invalid_calibre_database", "Calibre database schema is unsupported"
                )
            records = self._records(connection, tables, library, query_only)
        except (sqlite3.DatabaseError, OSError) as error:
            raise CalibreError(
                "invalid_calibre_database", "Calibre database could not be read"
            ) from error
        finally:
            if "connection" in locals():
                connection.close()
        return CalibreSnapshot(hashlib.sha256(data).hexdigest(), library, records)

    def _records(
        self, connection: sqlite3.Connection, tables: set[str], library: Path, query_only: bool
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        # Calibre keeps a hand-curated sort name beside each author's display
        # name, which is better than anything a heuristic can infer from
        # "Gabriel García Márquez". It is read where it exists and treated as
        # owner data on commit. `REQUIRED_TABLES` only guarantees the table, not
        # its columns, so an older or hand-built database simply has no sort here.
        author_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(authors)")}
        sort_column = "a.sort" if "sort" in author_columns else "NULL"
        for row_number, book in enumerate(connection.execute("SELECT * FROM books ORDER BY id"), 2):
            book_id = int(book["id"])
            columns = set(book.keys())
            author_rows = [
                row
                for row in connection.execute(
                    f"SELECT a.name, {sort_column} FROM authors a "
                    "JOIN books_authors_link l ON l.author=a.id "
                    "WHERE l.book=? ORDER BY l.rowid",
                    (book_id,),
                )
                if row[0]
            ]
            authors = [row[0] for row in author_rows]
            author_sorts = [str(row[1] or "").strip() for row in author_rows]
            identifiers = {
                str(row[0]).lower(): str(row[1]).strip()
                for row in connection.execute(
                    "SELECT type,val FROM identifiers WHERE book=?", (book_id,)
                )
                if row[0] and row[1]
            }
            errors: list[dict[str, Any]] = []
            isbn = None
            if identifiers.get("isbn"):
                try:
                    isbn = normalize_identifier("isbn", identifiers["isbn"]).normalized_value
                except ValueError:
                    errors.append({"field": "isbn", "code": "invalid_isbn"})
            shelves: list[str] = []
            if {"tags", "books_tags_link"}.issubset(tables):
                shelves = [
                    shelf_slug(value)
                    for (value,) in connection.execute(
                        "SELECT t.name FROM tags t JOIN books_tags_link l ON l.tag=t.id "
                        "WHERE l.book=? ORDER BY t.name",
                        (book_id,),
                    )
                    if value and shelf_slug(value)
                ]
            description = None
            if "comments" in tables:
                result = connection.execute(
                    "SELECT text FROM comments WHERE book=? LIMIT 1", (book_id,)
                ).fetchone()
                description = result[0] if result and result[0] else None
            series = None
            if {"series", "books_series_link"}.issubset(tables):
                result = connection.execute(
                    "SELECT s.name FROM series s JOIN books_series_link l ON l.series=s.id "
                    "WHERE l.book=? LIMIT 1",
                    (book_id,),
                ).fetchone()
                series = result[0] if result and result[0] else None
            score = None
            if {"ratings", "books_ratings_link"}.issubset(tables):
                result = connection.execute(
                    "SELECT r.rating FROM ratings r JOIN books_ratings_link l ON l.rating=r.id "
                    "WHERE l.book=? LIMIT 1",
                    (book_id,),
                ).fetchone()
                if result and result[0]:
                    score = int(result[0])
                    if not 1 <= score <= 10:
                        errors.append({"field": "rating", "code": "invalid_rating"})
                        score = None
            pubdate = book["pubdate"] if "pubdate" in columns else None
            year = int(str(pubdate)[:4]) if pubdate and str(pubdate)[:4].isdigit() else None
            book_path = str(book["path"] or "") if "path" in columns else ""
            cover_source = self._cover(library, book_path)
            formats = self._formats(connection, tables, book_id, book_path)
            records.append(
                {
                    "row_number": row_number,
                    "calibre_book_id": str(book_id),
                    "calibre_uuid": str(book["uuid"] or "") if "uuid" in columns else "",
                    "title": str(book["title"] or "").strip(),
                    "creators": authors,
                    "author_sorts": author_sorts,
                    "isbn": isbn,
                    "publisher": None,
                    "page_count": None,
                    "year": year,
                    "original_year": None,
                    "description": description,
                    "series": series,
                    "score": score,
                    "score_provisional": False,
                    "suggested_status": None,
                    "shelves": shelves,
                    "review": None,
                    "reread_count": 0,
                    "date_finished": None,
                    "date_added": None,
                    "errors": errors,
                    "connection_mode": "ro",
                    "query_only": query_only,
                    "cover_source": str(cover_source) if cover_source else None,
                    # Kept for the planner: where this book's cover lives relative to
                    # the library root, which is what a client offers by path.
                    "book_path": book_path,
                    # Every file Calibre says this book has, by the relative path a
                    # client would offer it under. Read from `data` rather than from
                    # the disk, so it is known from `metadata.db` alone — which is all
                    # the plan route ever receives.
                    "formats": formats,
                }
            )
        return records

    @staticmethod
    def _formats(
        connection: sqlite3.Connection, tables: set[str], book_id: int, book_path: str
    ) -> list[dict[str, Any]]:
        """This book's files, in the order one of them would be picked.

        Calibre's `data` table holds the format, the stem and the uncompressed size of
        every file it manages, so the whole file list — and what it would cost to send
        — is derivable from `metadata.db` without touching a single one of them.
        `REQUIRED_TABLES` does not guarantee `data`, so a hand-built database simply
        has no formats and no files to offer.
        """
        if not book_path or "data" not in tables:
            return []
        rows = [
            {
                "path": f"{book_path}/{name}.{str(row['format']).lower()}",
                "size": int(row["uncompressed_size"] or 0),
                "format": str(row["format"]).lower(),
            }
            for row in connection.execute(
                "SELECT format, name, uncompressed_size FROM data WHERE book=? ORDER BY format",
                (book_id,),
            )
            if (name := str(row["name"] or "").strip()) and row["format"]
        ]
        order = {extension: index for index, extension in enumerate(EBOOK_FORMATS)}
        rows.sort(key=lambda row: (order.get(str(row["format"]), len(order)), row["path"]))
        return rows

    @staticmethod
    def _cover(library: Path, book_path: str) -> Path | None:
        if not book_path:
            return None
        try:
            cover = (library / book_path / "cover.jpg").resolve(strict=True)
        except OSError:
            return None
        return cover if cover.is_relative_to(library) and cover.is_file() else None

    @staticmethod
    def _attachment(library: Path, formats: list[dict[str, Any]]) -> Path | None:
        """The preferred ebook file's absolute path, only if it is actually on disk.

        A mounted or plain-uploaded library never has one — `formats` is derived from
        `metadata.db` alone and the file itself is never sent (DEC-083). A reconstructed
        export bundle may, since its bytes are already local; when they are, this is
        what makes automatic post-commit attachment possible with no second upload.
        """
        if not formats:
            return None
        try:
            resolved = (library / str(formats[0]["path"])).resolve(strict=True)
        except OSError:
            return None
        return resolved if resolved.is_relative_to(library) and resolved.is_file() else None


def _holding_reason(covers: int, files: int) -> str | None:
    """What the screen says it is skipping, naming the two kinds separately.

    A reader who sees "19 already in your library" while watching an ebook upload
    start should be able to tell which 19.
    """
    parts = []
    if covers:
        parts.append(f"{covers} already in your library with a cover")
    if files:
        parts.append(f"{files} whose file you already have")
    return " and ".join(parts) or None


#: How much of a candidate part file is read while looking for the export manifest.
#: Comfortably larger than any manifest measured in practice (15 KB for 18 books) while
#: bounding the cost of probing a multi-gigabyte data part that is not it.
_EXPORT_MANIFEST_PROBE_BYTES = 64 * 1024 * 1024


def _decode_export_manifest(part: Path) -> dict[str, Any] | None:
    """This part's manifest, if it has one at its start.

    Calibre's "Export/import all calibre data" feature keeps the manifest whole inside
    one part, followed by trailing bytes `json.loads` alone cannot handle, and which are
    not guaranteed to themselves be valid UTF-8 — `errors="replace"` never raises, and
    `raw_decode` reads exactly the JSON object and ignores whatever comes after it, so
    garbage in a trailer that decoding corrupted is never actually looked at. Which part
    holds the manifest is not guaranteed by naming or position (verified against a real
    two-part export, where it was the smaller, second part), so every part is tried.
    """
    with part.open("rb") as handle:
        prefix = handle.read(_EXPORT_MANIFEST_PROBE_BYTES)
    text = prefix.decode("utf-8", errors="replace")
    try:
        manifest, _consumed = json.JSONDecoder().raw_decode(text)
    except ValueError:
        return None
    if isinstance(manifest, dict) and isinstance(manifest.get("file_metadata"), dict):
        return manifest
    return None


def _export_library_key(manifest: Mapping[str, Any]) -> str:
    """The one top-level key naming the exported library's own path.

    Every other top-level key is a fixed name (`file_metadata`, `libraries`,
    `config_dir`); whichever key is none of those is the library, by construction
    (verified against a real export).
    """
    candidates = [
        key for key in manifest if key not in ("file_metadata", "libraries", "config_dir")
    ]
    if len(candidates) != 1:
        raise CalibreError("invalid_calibre_export", "Export does not name exactly one library")
    return candidates[0]


def _export_slice(parts_by_number: Mapping[int, Path], entry: Any) -> bytes:
    """One file's bytes, sliced out of the part the manifest says holds them.

    The offset is relative to the start of *that* part, never a concatenation across
    parts — verified against a real two-part export, where a book cover at part 1
    offset 15186659 length 1216439 matched its manifest SHA-1 exactly. Bounds- and
    hash-checked before a caller ever sees the bytes, because this is the one place an
    untrusted upload's own numbers are trusted enough to seek and read with.
    """
    try:
        part_number, offset, length, sha1_hex, _mtime = entry
        part_number, offset, length = int(part_number), int(offset), int(length)
    except (TypeError, ValueError) as error:
        raise CalibreError(
            "invalid_calibre_export", "Export manifest entry is malformed"
        ) from error
    part = parts_by_number.get(part_number)
    if part is None:
        raise CalibreError("invalid_calibre_export", f"Export is missing part {part_number}")
    size = part.stat().st_size
    if offset < 0 or length < 0 or offset + length > size:
        raise CalibreError("invalid_calibre_export", "Export manifest entry is out of range")
    with part.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(length)
    if not isinstance(sha1_hex, str) or hashlib.sha1(data).hexdigest() != sha1_hex.lower():
        raise CalibreError("invalid_calibre_export", "Export data does not match its checksum")
    return data


class CalibreImporter:
    name = "calibre"
    label = "Calibre"
    item_types: tuple[str, ...] = (DOMAIN.item_type,)
    input = ImportInputSpec(
        # The folder on your own machine, chosen in the browser. No mount, no
        # CALIBRE_DIR, no restart, and nothing holds your library open while
        # Calibre or calibre-web is using it (DEC-081).
        kind="directory",
        label="Calibre folder",
        field="files",
        accepts_files=True,
        placeholder=None,
        help="Select your local Calibre folder.",
        guide=(
            "Choose your Calibre library folder — the one that holds metadata.db. "
            "Your browser reads it directly; nothing needs to be mounted or configured.",
            "Only metadata.db and the covers are sent by default. You can opt in to "
            "attach one preferred ebook file per book after reviewing the size.",
            "Nothing is written back to Calibre, and nothing holds the library open, so "
            "it is safe to do while Calibre or calibre-web is running.",
            "Only empty fields are filled. Anything you have edited in Akasha wins, and "
            "a re-import of the same library changes nothing you have touched.",
            "Everything lands in Triage rather than in the library, so nothing appears "
            "until you have looked at it.",
        ),
        empty_state="Choose your Calibre library folder.",
        help_url="https://manual.calibre-ebook.com/gui.html#the-calibre-library",
        # What a Calibre library may send. `metadata.db` is that file at the root and
        # nothing else; everything else lives one directory per book, at whatever depth
        # the author/title layout puts it. The ebook formats are declared here because
        # the shared route must be able to refuse an undeclared one before writing a
        # byte — whether any of them are *offered* is the reader's toggle, not this
        # list (DEC-083).
        members=(
            "metadata.db",
            "**/cover.jpg",
            *(f"**/*.{extension}" for extension in EBOOK_FORMATS),
        ),
        # A shelf of covers is legitimately far bigger than a CSV. Measured: 21 books
        # is 8.2 MB, so this is roughly a 600-book library at those cover sizes and
        # several thousand at ordinary ones. Past it the refusal names the alternate
        # below, which has no such ceiling.
        max_bytes=256 * 1024 * 1024,
        max_files=10_000,
        # A Calibre book carries a uuid that survives edits and re-exports, which is
        # what makes planning by identity honest here (DEC-082).
        incremental=True,
        # Two more ways in, kept beneath the folder chooser (DEC-081, generalized):
        # the mount, for automation with no browser and a library too large to upload;
        # and Calibre's own "Export/import all calibre data" bundle, for a library you
        # already exported or one the browser cannot reach as a folder at all.
        alternates=(
            ImportInputSpec(
                kind="path",
                label="Calibre library path",
                field="library_path",
                placeholder="Library",
                browsable=True,
                help="Or import from a mounted Calibre library.",
                guide=(
                    "Set CALIBRE_DIR in your .env to the folder that holds your "
                    "Calibre library, then restart the container.",
                    "Browse to the right folder below, or type its path relative to that mount.",
                    "The library is opened read-only, with PRAGMA query_only set — "
                    "nothing is ever written back to Calibre.",
                    "Covers are copied during preview; nothing references the mount "
                    "afterward, so it is safe to unmount once you have committed.",
                ),
            ),
            ImportInputSpec(
                kind="export",
                label="Calibre export",
                field="parts",
                accepts_files=True,
                help="Or drop the files from Calibre's own export.",
                guide=(
                    "In Calibre: Preferences → Import/export → "
                    "“Export/import all calibre data” → Export all calibre data.",
                    "Calibre writes one or more part-0001.calibre-data, "
                    "part-0002.calibre-data, … files.",
                    "Drag every one of those files onto this screen together — the "
                    "export is incomplete without all of them.",
                    "This sends your whole library, ebook files included, because "
                    "Calibre packs them together. A preferred ebook file per book is "
                    "attached automatically; nothing needs uploading twice.",
                ),
                empty_state="Drop the part-*.calibre-data files your export produced.",
                # A flat set of opaque part files, not a folder tree: no relative paths,
                # just this one shape (DEC-083).
                members=("*.calibre-data",),
                # Calibre's export packs every ebook file in too, so this has no
                # comparable ceiling to the folder's — measured at 181 MB for an
                # 18-book library of mostly-text epubs alone. Generous by design: the
                # whole point of this input is accepting what the folder option cannot.
                max_bytes=8 * 1024 * 1024 * 1024,
                max_files=500,
            ),
        ),
    )
    identity_kinds = frozenset({"isbn", "calibre_uuid"})
    error_codes = frozenset(
        {
            "invalid_calibre_path",
            "calibre_library_not_found",
            "invalid_calibre_database",
            "invalid_calibre_export",
        }
    )

    def browse(self, path: str, context: ImportReadContext) -> ImportBrowseResult:
        return CalibreAdapter(context.path_root).browse(path)

    def plan(
        self,
        source: ImportSource,
        candidates: Sequence[ImportCandidate],
        inventory: ImportInventory,
        _context: ImportReadContext,
    ) -> ImportPlan:
        """Which offered files are worth sending, decided from `metadata.db` alone.

        The database is always wanted — it is small, it is what everything else is
        derived from, and Calibre rewrites it constantly. A cover is wanted unless the
        library already holds that book **with a picture**: an item that arrived
        without one has to be offered it again, or a failed first attempt would be
        skipped forever.
        """
        if source.directory is None:
            return ImportPlan(wanted=tuple(c.path for c in candidates))
        offered = {candidate.path for candidate in candidates}
        snapshot = CalibreAdapter(source.directory).read("library")

        covers: dict[str, str] = {}
        files: dict[str, tuple[str, str]] = {}
        for payload in snapshot.records:
            uuid = str(payload.get("calibre_uuid") or "")
            book_path = str(payload.get("book_path") or "")
            if not uuid or not book_path:
                continue
            relative = f"{book_path}/cover.jpg"
            if relative in offered:
                covers[relative] = uuid
            for entry in payload.get("formats") or ():
                path = str(entry["path"])
                if path in offered:
                    files[path] = (uuid, PurePosixPath(path).name)

        held = inventory.with_cover("calibre_uuid", sorted(set(covers.values())))
        attached = inventory.attached("calibre_uuid", sorted({uuid for uuid, _ in files.values()}))

        def wanted_file(uuid: str, filename: str) -> bool:
            return filename not in attached.get(uuid, frozenset())

        wanted = [path for path in offered if path not in covers and path not in files]
        wanted += [path for path, uuid in covers.items() if uuid not in held]
        wanted += [path for path, (uuid, name) in files.items() if wanted_file(uuid, name)]
        skipped_covers = sum(1 for uuid in covers.values() if uuid in held)
        skipped_files = sum(1 for uuid, name in files.values() if not wanted_file(uuid, name))
        return ImportPlan(
            wanted=tuple(sorted(wanted)),
            holding=skipped_covers + skipped_files,
            reason=_holding_reason(skipped_covers, skipped_files),
        )

    def read(self, source: ImportSource, context: ImportReadContext) -> ImportSnapshot:
        # Three ways in, one reader. An uploaded bundle has already been materialized
        # by the route at `<directory>/library`, so it is a Calibre library on disk
        # like any other and `CalibreAdapter` cannot tell the difference (DEC-081).
        # An export bundle is reconstructed into that same shape by `_materialize_export`
        # before this ever calls `CalibreAdapter` — the adapter never learns a third way
        # to read either.
        if source.directory is not None:
            root, library_path = source.directory, "library"
        elif source.export is not None:
            root, library_path = self._materialize_export(source.export), "library"
        elif source.path is not None:
            root, library_path = context.path_root, source.path
        else:
            raise CalibreError("invalid_calibre_path", "A Calibre library path is required")
        snapshot = CalibreAdapter(root).read(library_path)
        # Only an export bundle ever has ebook bytes sitting on disk already (DEC-083):
        # a mount or a plain folder upload never sends them, so `formats` stays a
        # declaration for the manual attach route rather than something to read here.
        # This is the one place that distinction is made — `CalibreAdapter` stays
        # source-agnostic.
        attach_files = source.export is not None
        records = []
        for payload in snapshot.records:
            formats: list[dict[str, Any]] = payload.get("formats") or []
            attachment_source = (
                CalibreAdapter._attachment(snapshot.library, list(formats))
                if attach_files
                else None
            )
            metadata = {
                "creators": payload["creators"],
                **{
                    key: payload[key]
                    for key in (
                        "publisher",
                        "page_count",
                        "original_year",
                        "description",
                        "series",
                    )
                    if payload.get(key) not in (None, "", [], {})
                },
            }
            identifiers = {
                key: str(payload[key]) for key in self.identity_kinds if payload.get(key)
            }
            records.append(
                NormalizedImportRecord(
                    row_number=payload["row_number"],
                    item=ImportItem(
                        title=payload["title"],
                        subtitle=None,
                        year=payload.get("year"),
                        identifiers=identifiers,
                        metadata=metadata,
                        creator_sort=next(
                            (
                                value.strip()
                                for value in payload.get("author_sorts", ())
                                if isinstance(value, str) and value.strip()
                            ),
                            None,
                        ),
                    ),
                    entry=ImportEntry(
                        score=payload.get("score"),
                        notes=payload.get("review"),
                        date_added=payload.get("date_added"),
                        values={
                            "date_finished": payload.get("date_finished"),
                            "reread_count": payload.get("reread_count", 0),
                        },
                        score_provisional=bool(payload.get("score_provisional")),
                        suggested_status=payload.get("suggested_status"),
                    ),
                    shelves=tuple(payload.get("shelves", ())),
                    errors=tuple(payload.get("errors", ())),
                    source_fields={
                        key: payload.get(key)
                        for key in (
                            "calibre_book_id",
                            "calibre_uuid",
                            "connection_mode",
                            "query_only",
                        )
                    },
                    cover_source=payload.get("cover_source"),
                    source_files=tuple(str(entry["path"]) for entry in formats),
                    attachment_source=str(attachment_source) if attachment_source else None,
                    attachment_name=str(formats[0]["path"]) if attachment_source else None,
                )
            )
        source_descriptor: dict[str, Any]
        if source.directory is not None:
            source_descriptor = {"source": "upload"}
        elif source.export is not None:
            source_descriptor = {"source": "export"}
        else:
            source_descriptor = {"library_path": source.path}
        return ImportSnapshot(
            fingerprint=snapshot.fingerprint,
            filename="metadata.db",
            # Never the bundle's temporary location: a host path is not the reader's
            # business and outlives nothing useful.
            source_descriptor=source_descriptor,
            records=tuple(records),
        )

    def _materialize_export(self, export: Path) -> Path:
        """Reconstruct a library on disk from an uploaded export bundle.

        The route has already streamed the raw `part-*.calibre-data` files to
        `<export>/parts/`, unread (DEC-081, generalized). This locates the manifest,
        rebuilds `metadata.db`, and rebuilds each book's cover and preferred ebook
        file at exactly the relative paths `CalibreAdapter`/`_formats` already expect
        under `<export>/library/`, so the ordinary adapter reads it exactly as it would
        a mounted or folder-uploaded library — a source that arrived as opaque bytes
        never invents a fourth thing `CalibreAdapter` has to know about.
        """
        parts = sorted((export / "parts").glob("*"))
        if not parts:
            raise CalibreError("invalid_calibre_export", "No exported parts were provided")
        parts_by_number = dict(enumerate(parts, start=1))
        manifest = next(
            (found for part in parts if (found := _decode_export_manifest(part)) is not None),
            None,
        )
        if manifest is None:
            raise CalibreError(
                "invalid_calibre_export", "No manifest was found among the exported parts"
            )
        file_metadata = manifest["file_metadata"]
        library_manifest = manifest[_export_library_key(manifest)]
        if not isinstance(library_manifest, dict):
            raise CalibreError("invalid_calibre_export", "Export manifest is malformed")

        def slice_of(key: object) -> bytes:
            entry = file_metadata.get(key) if isinstance(key, str) else None
            if entry is None:
                raise CalibreError(
                    "invalid_calibre_export", "Export manifest is missing a required file"
                )
            return _export_slice(parts_by_number, entry)

        library = export / "library"
        library.mkdir(parents=True, exist_ok=True)
        (library / "metadata.db").write_bytes(slice_of(library_manifest.get("metadata.db")))

        connection = sqlite3.connect(
            f"file:{quote(str((library / 'metadata.db').resolve()))}?mode=ro", uri=True
        )
        try:
            connection.execute("PRAGMA query_only=ON")
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            book_paths = {
                int(book_id): str(book_path or "")
                for book_id, book_path in connection.execute("SELECT id, path FROM books")
            }
            # Optional, same as `CalibreAdapter._formats` already tolerates: a hand-built
            # or older database simply has no formats and no files to reconstruct.
            data_rows: dict[int, list[tuple[str, str]]] = {}
            if "data" in tables:
                for book_id, book_format, name in connection.execute(
                    "SELECT book, format, name FROM data"
                ):
                    data_rows.setdefault(int(book_id), []).append((str(book_format), str(name)))
        except sqlite3.DatabaseError as error:
            raise CalibreError(
                "invalid_calibre_export", "Export's metadata.db could not be read"
            ) from error
        finally:
            connection.close()

        format_data = library_manifest.get("format_data")
        preference = {extension.upper(): index for index, extension in enumerate(EBOOK_FORMATS)}
        for book_id_text, formats in (format_data or {}).items():
            try:
                book_id = int(book_id_text)
            except ValueError:
                continue
            book_path = book_paths.get(book_id)
            if not book_path or not isinstance(formats, dict):
                continue
            relative = PurePosixPath(book_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise CalibreError(
                    "invalid_calibre_export", "Export names a book path outside the library"
                )
            book_dir = (library / book_path).resolve()
            if not book_dir.is_relative_to(library.resolve()):
                raise CalibreError(
                    "invalid_calibre_export", "Export names a book path outside the library"
                )
            cover_key = formats.get(".cover")
            if isinstance(cover_key, str):
                book_dir.mkdir(parents=True, exist_ok=True)
                (book_dir / "cover.jpg").write_bytes(slice_of(cover_key))
            candidates = sorted(
                (
                    (book_format, name)
                    for book_format, name in data_rows.get(book_id, ())
                    if book_format.upper() in formats
                ),
                key=lambda row: preference.get(row[0].upper(), len(preference)),
            )
            if candidates:
                book_format, name = candidates[0]
                book_dir.mkdir(parents=True, exist_ok=True)
                (book_dir / f"{name}.{book_format.lower()}").write_bytes(
                    slice_of(formats[book_format.upper()])
                )
        return export

    def stage(self, snapshot: ImportSnapshot, directory: Path, data_dir: Path) -> ImportSnapshot:
        records = []
        for record in snapshot.records:
            relative = None
            if record.cover_source:
                try:
                    prepared = prepare_uploaded_cover(
                        Path(record.cover_source).read_bytes(), "image/jpeg", data_dir
                    )
                    staged = directory / "covers" / f"{record.row_number}.jpg"
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    prepared.replace(staged)
                    relative = str(staged.relative_to(data_dir))
                except (CoverError, OSError):
                    pass
            attachment_relative = None
            if record.attachment_source and record.attachment_name:
                try:
                    suffix = PurePosixPath(record.attachment_name).suffix
                    attachment_staged = directory / "files" / f"{record.row_number}{suffix}"
                    attachment_staged.parent.mkdir(parents=True, exist_ok=True)
                    attachment_staged.write_bytes(Path(record.attachment_source).read_bytes())
                    attachment_relative = str(attachment_staged.relative_to(data_dir))
                except OSError:
                    pass
            records.append(
                replace(
                    record,
                    cover_source=None,
                    cover_stage=relative,
                    attachment_source=None,
                    attachment_stage=attachment_relative,
                    attachment_name=record.attachment_name if attachment_relative else None,
                    source_fields={**record.source_fields, "cover_staged": relative is not None},
                )
            )
        return replace(snapshot, records=tuple(records))

    def match(self, record: NormalizedImportRecord, matcher: ImportMatcher) -> MatchDecision:
        identifiers = [
            normalize_identifier(kind, value)
            for kind, value in record.item.identifiers.items()
            if kind in self.identity_kinds
        ]
        creators = record.item.metadata.get("creators", ())
        first_creator = str(creators[0]) if isinstance(creators, list) and creators else ""
        return matcher.match(
            identifiers=identifiers,
            title=record.item.title,
            first_author=first_creator,
        )


IMPORTER = CalibreImporter()
