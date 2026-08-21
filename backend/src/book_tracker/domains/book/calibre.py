import hashlib
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import quote

from book_tracker.domain.identity import normalize_identifier
from book_tracker.domain.importers import (
    ImportBrowseResult,
    ImportEntry,
    ImportInputSpec,
    ImportItem,
    ImportMatcher,
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
                }
            )
        return records

    @staticmethod
    def _cover(library: Path, book_path: str) -> Path | None:
        if not book_path:
            return None
        try:
            cover = (library / book_path / "cover.jpg").resolve(strict=True)
        except OSError:
            return None
        return cover if cover.is_relative_to(library) and cover.is_file() else None


class CalibreImporter:
    name = "calibre"
    label = "Calibre"
    item_type = DOMAIN.item_type
    input = ImportInputSpec(
        kind="path",
        label="Calibre library path",
        field="library_path",
        placeholder="Library",
        help=(
            "Akasha opens this library read-only inside the configured Calibre mount. "
            "Enter a relative folder only; covers are copied during preview."
        ),
        # What the import does to your library, in the order a reader worries about
        # it: is my Calibre safe, will it overwrite my notes, what arrives.
        guide=(
            "Pick the folder that holds metadata.db. Browsing starts at the Calibre "
            "library mounted into Akasha, so there is no path to guess.",
            "Calibre is opened read-only and is never written to. Close Calibre first "
            "anyway — it locks the database while it saves.",
            "Only empty fields are filled. Anything you have edited in Akasha wins, "
            "and a re-sync of the same library changes nothing you have touched.",
            "Covers already in Calibre are copied during preview, so the import needs "
            "no network for them.",
            "Everything lands in Triage rather than in the library, so nothing appears "
            "until you have looked at it.",
        ),
        empty_state="No folders here. Mount your Calibre library and reload.",
        help_url="https://manual.calibre-ebook.com/gui.html#the-calibre-library",
        browsable=True,
    )
    identity_kinds = frozenset({"isbn", "calibre_uuid"})
    error_codes = frozenset(
        {"invalid_calibre_path", "calibre_library_not_found", "invalid_calibre_database"}
    )

    def browse(self, path: str, context: ImportReadContext) -> ImportBrowseResult:
        return CalibreAdapter(context.path_root).browse(path)

    def read(self, source: ImportSource, context: ImportReadContext) -> ImportSnapshot:
        if source.path is None:
            raise CalibreError("invalid_calibre_path", "A Calibre library path is required")
        snapshot = CalibreAdapter(context.path_root).read(source.path)
        records = []
        for payload in snapshot.records:
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
                )
            )
        return ImportSnapshot(
            fingerprint=snapshot.fingerprint,
            filename="metadata.db",
            source_descriptor={"library_path": source.path},
            records=tuple(records),
        )

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
            records.append(
                replace(
                    record,
                    cover_source=None,
                    cover_stage=relative,
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
