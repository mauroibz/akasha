"""Loose EPUB files: a book that describes itself (Sprint 086, DEC-164).

An EPUB carries its own catalogue card — an OPF package document with Dublin Core
metadata and, usually, a declared cover — so a file dropped on the Add screen can become a
book without anybody typing anything. This connector reads that card and nothing else:
no chapters, no reading position, no format-aware file UI. The file itself is attached to
the book it described, through the same `attachment_source` channel a Calibre export
already uses, so commit installs it with no second upload (DEC-083).
"""

import hashlib
import html
import posixpath
import re
import zipfile
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.importers import (
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
from book_tracker.domain.sniffing import is_epub
from book_tracker.domains.book import DOMAIN
from book_tracker.infrastructure.covers import MAX_COVER_BYTES, CoverError, prepare_uploaded_cover

_DC = "{http://purl.org/dc/elements/1.1/}"
_OPF = "{http://www.idpf.org/2007/opf}"
_CONTAINER = "{urn:oasis:names:tc:opendocument:xmlns:container}"

#: A container or package document is a few kilobytes; anything near this is not one.
MAX_DOCUMENT_BYTES = 1024 * 1024

_COVER_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_SUFFIX_TYPES = {suffix: content_type for content_type, suffix in _COVER_TYPES.items()}

#: One creator string naming several people: "Martin Kleppmann and Chris Riccomini".
_CREATOR_SPLIT = re.compile(r"\s+(?:and|&)\s+|\s*;\s*", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_ISBN_PREFIX = re.compile(r"^(?:urn:)?isbn:?\s*", re.IGNORECASE)


class EpubError(ImportReadError):
    """The one way this source can fail as a whole: nothing was offered to read."""


class _Unreadable(Exception):
    """One file is not an EPUB this can read; it becomes that file's row error."""


def _document(archive: zipfile.ZipFile, name: str) -> ElementTree.Element:
    """Parse one small XML member, refusing anything that declares entities.

    The standard library parser never fetches external entities, and expat bounds
    expansion, but a package document has no business declaring entities at all — so
    one that does is refused outright rather than trusted to stay small.
    """
    try:
        info = archive.getinfo(name)
    except KeyError as error:
        raise _Unreadable(f"missing {name}") from error
    if info.file_size > MAX_DOCUMENT_BYTES:
        raise _Unreadable(f"{name} is too large")
    data = archive.read(info)
    if b"<!ENTITY" in data.upper():
        raise _Unreadable(f"{name} declares entities")
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise _Unreadable(f"{name} is not well formed") from error


def _text(element: ElementTree.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def _isbn(metadata: ElementTree.Element) -> str | None:
    """The first identifier that is an ISBN, whether or not it says so.

    O'Reilly ships `978-1-098-11906-5` with no scheme at all, so a declared scheme is a
    preference, not a requirement.
    """
    identifiers = metadata.findall(f"{_DC}identifier")
    declared = [
        element
        for element in identifiers
        if (element.get(f"{_OPF}scheme") or "").lower() == "isbn"
        or _text(element).lower().startswith(("urn:isbn", "isbn"))
    ]
    for element in [*declared, *identifiers]:
        value = _ISBN_PREFIX.sub("", _text(element))
        if not value or not re.fullmatch(r"[0-9Xx\- ]{10,17}", value):
            continue
        try:
            return normalize_identifier("isbn", value).normalized_value
        except InvalidIdentifier:
            continue
    return None


def _refinements(metadata: ElementTree.Element) -> dict[tuple[str, str], str]:
    """EPUB 3 `<meta refines="#id" property="…">` values, keyed by (id, property)."""
    refined: dict[tuple[str, str], str] = {}
    for meta in metadata.findall(f"{_OPF}meta"):
        target = (meta.get("refines") or "").lstrip("#")
        prop = meta.get("property") or ""
        if target and prop:
            refined.setdefault((target, prop), _text(meta))
    return refined


def _creators(
    metadata: ElementTree.Element, refined: dict[tuple[str, str], str]
) -> tuple[list[str], str | None]:
    """Authors, in order, and the first author's sort form when the file states one.

    A creator with an explicit role other than author (a translator, an illustrator) is
    not who the book is by; a creator with no role is assumed to be.
    """
    names: list[str] = []
    sort: str | None = None
    for element in metadata.findall(f"{_DC}creator"):
        identifier = element.get("id") or ""
        role = (element.get(f"{_OPF}role") or refined.get((identifier, "role")) or "").lower()
        if role and role != "aut":
            continue
        value = _text(element)
        if not value:
            continue
        if sort is None:
            sort = element.get(f"{_OPF}file-as") or refined.get((identifier, "file-as")) or None
        for name in _CREATOR_SPLIT.split(value):
            if name.strip() and name.strip() not in names:
                names.append(name.strip())
    return names, sort


def _meta(metadata: ElementTree.Element, *, name: str = "", prop: str = "") -> str:
    for meta in metadata.findall(f"{_OPF}meta"):
        if meta.get("refines"):
            continue
        if name and meta.get("name") == name:
            return (meta.get("content") or "").strip()
        if prop and meta.get("property") == prop:
            return _text(meta)
    return ""


def _cover(
    archive: zipfile.ZipFile, package: ElementTree.Element, base: str
) -> tuple[str, str] | None:
    """The member name and media type of the declared cover image, if any.

    EPUB 3 marks the manifest item `cover-image`; EPUB 2 points at it from a
    `<meta name="cover">`. Both are declarations — nothing here guesses from a filename.
    """
    manifest = package.find(f"{_OPF}manifest")
    if manifest is None:
        return None
    items = manifest.findall(f"{_OPF}item")
    metadata = package.find(f"{_OPF}metadata")
    pointer = _meta(metadata, name="cover") if metadata is not None else ""
    chosen = next(
        (item for item in items if "cover-image" in (item.get("properties") or "").split()),
        None,
    )
    if chosen is None:
        chosen = next((item for item in items if pointer and item.get("id") == pointer), None)
    if chosen is None:
        return None
    media_type = (chosen.get("media-type") or "").lower()
    href = unquote(chosen.get("href") or "")
    if media_type not in _COVER_TYPES or not href:
        return None
    member = posixpath.normpath(posixpath.join(base, href))
    if member.startswith("../") or member.startswith("/"):
        return None
    try:
        if archive.getinfo(member).file_size > MAX_COVER_BYTES:
            return None
    except KeyError:
        return None
    return member, media_type


def _year(metadata: ElementTree.Element) -> int | None:
    for element in metadata.findall(f"{_DC}date"):
        match = re.match(r"\s*(\d{4})", _text(element))
        if match:
            return int(match.group(1))
    return None


def read_epub(path: Path, covers: Path, row_number: int) -> NormalizedImportRecord:
    """One file, as the record it describes — or as one row naming why it could not be."""
    try:
        with zipfile.ZipFile(path) as archive:
            container = _document(archive, "META-INF/container.xml")
            rootfile = container.find(f"{_CONTAINER}rootfiles/{_CONTAINER}rootfile")
            opf_path = rootfile.get("full-path") if rootfile is not None else None
            if not opf_path:
                raise _Unreadable("container names no package document")
            package = _document(archive, opf_path)
            metadata = package.find(f"{_OPF}metadata")
            if metadata is None:
                raise _Unreadable("package has no metadata")
            cover = _cover(archive, package, posixpath.dirname(opf_path))
            cover_source = None
            if cover is not None:
                member, media_type = cover
                cover_file = covers / f"{row_number}{_COVER_TYPES[media_type]}"
                cover_file.parent.mkdir(parents=True, exist_ok=True)
                cover_file.write_bytes(archive.read(member))
                cover_source = str(cover_file)
    except (zipfile.BadZipFile, _Unreadable, OSError, RuntimeError, ValueError) as error:
        return NormalizedImportRecord(
            row_number=row_number,
            item=ImportItem(title=path.stem, subtitle=None, year=None, identifiers={}, metadata={}),
            entry=ImportEntry(score=None, notes=None, date_added=None, values={}),
            shelves=(),
            errors=({"field": "file", "code": "invalid_epub", "value": f"{path.name}: {error}"},),
            source_fields={"filename": path.name},
        )

    refined = _refinements(metadata)
    creators, creator_sort = _creators(metadata, refined)
    # A publisher's stamp can ride `dc:title` ("… (for <buyer>)") while the clean title
    # sits in a `dcterms:title` meta beside it — measured on the owner's own file.
    title = (
        _meta(metadata, prop="dcterms:title") or _text(metadata.find(f"{_DC}title")) or path.stem
    )
    description = " ".join(
        html.unescape(_TAG.sub(" ", _text(metadata.find(f"{_DC}description")))).split()
    )
    description = re.sub(r"\s+([.,;:!?])", r"\1", description)
    subjects = [value for element in metadata.findall(f"{_DC}subject") if (value := _text(element))]
    series = _meta(metadata, name="calibre:series") or _meta(metadata, prop="belongs-to-collection")
    fields: dict[str, Any] = {
        "publisher": _text(metadata.find(f"{_DC}publisher")),
        "language": _text(metadata.find(f"{_DC}language")),
        "description": description,
        "subjects": subjects,
        "series": series,
    }
    isbn = _isbn(metadata)
    return NormalizedImportRecord(
        row_number=row_number,
        item=ImportItem(
            title=title,
            subtitle=None,
            year=_year(metadata),
            identifiers={"isbn": isbn} if isbn else {},
            metadata={
                "creators": creators,
                **{key: value for key, value in fields.items() if value not in ("", [])},
            },
            creator_sort=creator_sort,
        ),
        entry=ImportEntry(score=None, notes=None, date_added=None, values={}),
        shelves=(),
        errors=(),
        source_fields={"filename": path.name},
        cover_source=cover_source,
        source_files=(path.name,),
        attachment_source=str(path),
        attachment_name=path.name,
    )


class EpubImporter:
    name = "epub"
    label = "Ebook files"
    item_types = (DOMAIN.item_type,)
    input = ImportInputSpec(
        kind="export",
        label="EPUB files",
        field="files",
        accept=".epub",
        accepts_files=True,
        help="Drop EPUB files and each one becomes a book, with its cover and the file attached.",
        guide=(
            "Drag one or more .epub files onto this box, or choose them.",
            "Each file's own title, authors, ISBN, publisher and cover are read from inside it.",
            "Every book lands in Triage, and the file is attached to it.",
        ),
        empty_state="Drop .epub files here.",
        # A flat set of files, each its own book. Upper case too, because a file
        # name's extension is whatever the shop that sold it chose.
        members=("*.epub", "*.EPUB"),
        max_bytes=2 * 1024 * 1024 * 1024,
        max_files=100,
        quick_add=True,
    )
    identity_kinds = frozenset({"isbn"})
    error_codes = frozenset({"invalid_epub"})

    def sniff(self, head: bytes, name: str) -> float:
        """An EPUB says so in its first member (Sprint 095)."""
        return 1.0 if is_epub(head) else 0.0

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        if source.export is None:
            raise EpubError("invalid_epub", "EPUB files are required")
        files = sorted(
            path
            for path in (source.export / "parts").glob("*")
            if path.is_file() and path.suffix.lower() == ".epub"
        )
        if not files:
            raise EpubError(
                "invalid_epub",
                "No EPUB files were offered",
                user_message="No EPUB files were offered to import.",
                action="Drop one or more .epub files.",
            )
        # The set of files, not their names or order: the same three books dropped
        # again replay the batch that already holds them.
        digest = hashlib.sha256()
        for file_digest in sorted(_digest(path) for path in files):
            digest.update(file_digest.encode())
        covers = source.export / "covers"
        return ImportSnapshot(
            fingerprint=digest.hexdigest(),
            filename=files[0].name if len(files) == 1 else f"{len(files)} EPUB files",
            source_descriptor={"source": "upload", "files": len(files)},
            records=tuple(
                read_epub(path, covers, row_number)
                for row_number, path in enumerate(files, start=1)
            ),
        )

    def stage(self, snapshot: ImportSnapshot, directory: Path, data_dir: Path) -> ImportSnapshot:
        records = []
        for record in snapshot.records:
            cover_relative = None
            if record.cover_source:
                source = Path(record.cover_source)
                try:
                    prepared = prepare_uploaded_cover(
                        source.read_bytes(), _SUFFIX_TYPES[source.suffix], data_dir
                    )
                    staged = directory / "covers" / f"{record.row_number}.jpg"
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    prepared.replace(staged)
                    cover_relative = str(staged.relative_to(data_dir))
                except (CoverError, OSError, KeyError):
                    pass
            attachment_relative = None
            if record.attachment_source and record.attachment_name:
                try:
                    suffix = PurePosixPath(record.attachment_name).suffix.lower()
                    staged_file = directory / "files" / f"{record.row_number}{suffix}"
                    staged_file.parent.mkdir(parents=True, exist_ok=True)
                    staged_file.write_bytes(Path(record.attachment_source).read_bytes())
                    attachment_relative = str(staged_file.relative_to(data_dir))
                except OSError:
                    pass
            records.append(
                replace(
                    record,
                    cover_source=None,
                    cover_stage=cover_relative,
                    attachment_source=None,
                    attachment_stage=attachment_relative,
                    attachment_name=record.attachment_name if attachment_relative else None,
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


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


IMPORTER = EpubImporter()
