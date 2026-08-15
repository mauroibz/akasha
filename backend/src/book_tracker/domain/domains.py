"""What a domain knows about itself, and the registry of the domains that exist.

The shared layers speak in neutral terms — an item has a type, a title, creators,
identifiers and an opaque metadata object — and a domain plugin supplies the parts
only it can know (DEC-052, `docs/domain-architecture-proposal.md` section 4). A domain
is never translated into another domain's vocabulary, and the shared layer never
branches on which one it is holding.

This record grows one seam at a time. It starts with identity because that is the seam
the earlier plan did not anticipate and the one most likely to be wrong.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import SplitResult, parse_qs, urlsplit

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.providers import ALBUM_IDENTITY, BOOK_IDENTITY, IdentityStrategy

FieldType = Literal["text", "long_text", "number", "rows"]
Multiplicity = Literal["one", "many"]


@dataclass(frozen=True)
class ColumnSpec:
    """One cell of a `rows` field — a tracklist's position, title or length.

    The first metadata shape the spec could not describe was an ordered list of
    structured rows: a tracklist is not text, not a number and not a list of strings.
    This describes the row so the renderer and the validator stay data-driven.
    """

    name: str
    label: str
    type: Literal["text", "number", "duration"] = "text"


@dataclass(frozen=True)
class FieldSpec:
    """One metadata field, described rather than modelled.

    Storage stays an opaque JSON object; this says what may be in it and how to
    render and validate it. `name` is permanent, `label` is user-facing copy.
    """

    name: str
    label: str
    type: FieldType = "text"
    multiplicity: Multiplicity = "one"
    minimum: int | None = None
    maximum: int | None = None
    #: Only for `type="rows"`: what one row holds.
    columns: tuple[ColumnSpec, ...] = ()


# The four item columns the dialog edits beside the metadata — `title`, `subtitle`,
# `year`, `creator_sort_override` — are neutral and belong to every domain, so a
# metadata field may not shadow one.
RESERVED_FIELD_NAMES = frozenset({"title", "subtitle", "year", "creator_sort_override"})

BOOK_FIELDS = (
    FieldSpec("creators", "Creators", multiplicity="many"),
    FieldSpec("publisher", "Publisher"),
    FieldSpec("language", "Language"),
    FieldSpec("page_count", "Page count", type="number", minimum=1, maximum=100_000),
    FieldSpec("description", "Description", type="long_text"),
    FieldSpec("subjects", "Subjects", multiplicity="many"),
    FieldSpec("series", "Series"),
    FieldSpec("original_year", "Original publication year", type="number", minimum=0, maximum=9999),
)

# Measured against live MusicBrainz on 2026-08-14, not guessed: the publisher analogue
# is label plus catalogue number (obs. 9), language lives on the release (obs. 8), and
# the credit is a rendered string rather than the join of the artist list (obs. 4).
ALBUM_FIELDS = (
    FieldSpec("creators", "Artists", multiplicity="many"),
    FieldSpec("credit", "Artist credit"),
    FieldSpec("label", "Label"),
    FieldSpec("catalog_number", "Catalogue number"),
    FieldSpec("country", "Country"),
    FieldSpec("language", "Language"),
    FieldSpec("format", "Format"),
    FieldSpec("track_count", "Tracks", type="number", minimum=1, maximum=10_000),
    # The first field the spec could not describe: an ordered list of structured
    # rows. It costs one `inc=…+recordings` parameter on a request the adapter
    # already makes, and it is *metadata on the album* — tracks are not entities,
    # nothing hangs off one, and entry hierarchy stays Sprint 028's question.
    FieldSpec(
        "tracklist",
        "Tracklist",
        type="rows",
        multiplicity="many",
        columns=(
            # As printed on the sleeve — `A1` on a record — not the sequential index.
            ColumnSpec("number", "#"),
            ColumnSpec("title", "Title"),
            ColumnSpec("length_ms", "Length", type="duration"),
        ),
    ),
)


@dataclass(frozen=True)
class StatusSpec:
    """One status a domain's entries can be in.

    Seam 5a gave a domain the right to *rename* a shared status; seam 5b gives it the
    right to have different ones (DEC-057). `value` is the permanent stored name,
    `label` is copy, `choosable` is false for a status nothing may be set to directly,
    and `hotkey` is the triage key — kept beside the status it sets rather than in a
    second table that can drift away from this one.
    """

    value: str
    label: str
    choosable: bool = True
    hotkey: str | None = None


@dataclass(frozen=True)
class FormatSpec:
    """How a copy is held: `Vinyl`, `Borrowed`. A property of the entry, not the item.

    The vocabulary is closed and declared here rather than stored, which is the whole
    difference between this and a shelf: a shelf is something the owner invents
    ("work", "fiction"), a format is something the domain knows (DEC-059).
    """

    value: str
    label: str


#: Where an import lands, in every domain. The default library view hides it, so it is
#: never something to choose — only something to leave.
UNSORTED = StatusSpec("unsorted", "Inbox", choosable=False, hotkey="u")

BOOK_STATUSES = (
    UNSORTED,
    StatusSpec("read", "Read", hotkey="r"),
    StatusSpec("reading", "Reading", hotkey="g"),
    StatusSpec("to_read", "To read", hotkey="t"),
    StatusSpec("wishlist", "Wishlist", hotkey="w"),
    StatusSpec("dropped", "Dropped", hotkey="d"),
)

# DEC-057, in the owner's words: an album is played hundreds of times or twice, and the
# interesting fact is whether you have it. So this is not the book vocabulary renamed —
# it is a different concept with three states, and `read`/`reading` are absent rather
# than relabelled.
ALBUM_STATUSES = (
    UNSORTED,
    StatusSpec("wishlist", "Wishlist", hotkey="w"),
    StatusSpec("pending", "On the way", hotkey="p"),
    StatusSpec("owned", "Owned", hotkey="o"),
)

BOOK_FORMATS = (
    FormatSpec("physical", "Physical"),
    FormatSpec("borrowed", "Borrowed"),
    FormatSpec("digital", "Digital"),
)
ALBUM_FORMATS = (
    FormatSpec("vinyl", "Vinyl"),
    FormatSpec("cd", "CD"),
    FormatSpec("digital", "Digital"),
)

#: The three entry columns that date a passage through a work. A domain declares which
#: of them it has; DEC-057 says an album has none of them.
PASSAGE_FIELDS = frozenset({"date_started", "date_finished", "reread_count"})


@dataclass(frozen=True)
class Domain:
    """`item_type` is the value stored in `items.type` and is permanent."""

    item_type: str
    label: str
    identity: IdentityStrategy
    fields: tuple[FieldSpec, ...]
    #: Whether background enrichment applies. One MusicBrainz release fetch already
    #: returns everything an album has, where a Goodreads row starts as little more
    #: than an ISBN — so "this domain does not enrich" is a simplification, not a gap.
    enriches: bool = True
    #: The statuses an entry on this domain can hold, in the order a control offers
    #: them, and the one a newly added entry gets when nobody chose.
    statuses: tuple[StatusSpec, ...] = BOOK_STATUSES
    default_status: str = "read"
    #: Which of `PASSAGE_FIELDS` this domain's entries have. Anything absent is refused
    #: on write, not merely hidden: a reread count on a record is not a display problem.
    entry_fields: frozenset[str] = PASSAGE_FIELDS
    #: How a copy of this is held (DEC-059).
    formats: tuple[FormatSpec, ...] = BOOK_FORMATS
    #: The heading over the personal region of the detail page. "Your reading data" is
    #: a book's phrase, and an album's entry records possession rather than reading.
    entry_panel_label: str = "Your reading data"
    #: Recognizes a URL or identifier this domain can resolve, for add-by-URL.
    recognize: Callable[[str], "UrlMatch | None"] = lambda _value: None
    #: Whether this domain can offer alternative covers to choose from (DEC-067 row 7).
    #: The shared implementation is still Open Library's work-editions path, so only a
    #: domain Open Library serves may declare it: an album has no work and no editions,
    #: and the control could only ever say no. Declaring this is what stops a screen
    #: offering a chooser that cannot work, rather than a screen knowing the type.
    chooses_covers: bool = True

    def status(self, value: str) -> StatusSpec | None:
        return next((row for row in self.statuses if row.value == value), None)


BOOK = Domain(
    item_type="book",
    label="Book",
    identity=BOOK_IDENTITY,
    fields=BOOK_FIELDS,
    recognize=lambda value: recognize_book_input(value),
)
ALBUM = Domain(
    item_type="album",
    label="Album",
    identity=ALBUM_IDENTITY,
    fields=ALBUM_FIELDS,
    enriches=False,
    statuses=ALBUM_STATUSES,
    default_status="owned",
    entry_fields=frozenset(),
    formats=ALBUM_FORMATS,
    entry_panel_label="Your copy",
    recognize=lambda value: recognize_album_url(value),
    chooses_covers=False,
)

DOMAINS: dict[str, Domain] = {domain.item_type: domain for domain in (BOOK, ALBUM)}

# Every route, importer and repository that predates the second domain works on books;
# naming that here keeps `"book"` out of those call sites as a literal.
DEFAULT_DOMAIN = BOOK


def _ordered_union(values: Sequence[Sequence[str]]) -> tuple[str, ...]:
    """Every value once, in first-declared order. Order is the API's, not a set's."""
    seen: dict[str, None] = {}
    for group in values:
        for value in group:
            seen.setdefault(value, None)
    return tuple(seen)


#: Every status any domain declares. A *filter* legitimately spans domains — a triage
#: selection or a facet count can hold both — so the query parameter validates against
#: this, while a *write* validates against the item's own domain.
ALL_STATUSES = _ordered_union(
    [[status.value for status in domain.statuses] for domain in DOMAINS.values()]
)
ALL_FORMATS = _ordered_union([[row.value for row in domain.formats] for domain in DOMAINS.values()])


class EntryStatus(StrEnum):
    """The published union, so OpenAPI enumerates what a client may send.

    Spelled out rather than built from `ALL_STATUSES`, because a dynamic enum is
    opaque to the type checker and this is a public surface. `test_domain.py` asserts
    the two agree, so adding a domain status and forgetting this fails a test instead
    of quietly dropping the value from the API contract.

    It is not the authority on what is legal for a given item: that is
    `validate_status`, keyed on the item's own type (seam 5b).
    """

    UNSORTED = "unsorted"
    READ = "read"
    READING = "reading"
    TO_READ = "to_read"
    WISHLIST = "wishlist"
    DROPPED = "dropped"
    PENDING = "pending"
    OWNED = "owned"


class EntryFormat(StrEnum):
    """The published union of every domain's formats, for filters and facets."""

    PHYSICAL = "physical"
    BORROWED = "borrowed"
    DIGITAL = "digital"
    VINYL = "vinyl"
    CD = "cd"


class ItemTypeName(StrEnum):
    """The published union of domain names, so `?type=` enumerates in OpenAPI.

    Spelled out for the same reason `EntryStatus` is, and pinned to `DOMAINS` by the
    same test. Unlike a status, a type is never validated against an item's own domain
    — it *is* the domain — so this enum is the whole check the filter needs.
    """

    BOOK = "book"
    ALBUM = "album"


class InvalidStatus(ValueError):
    """A status the item's own domain does not have."""


class InvalidFormat(ValueError):
    """A format the item's own domain does not have."""


class InvalidEntryField(ValueError):
    """An entry field the item's own domain does not have (DEC-057)."""


def validate_status(domain: Domain, value: str) -> str:
    """The one place a status is checked against the domain holding the item.

    The message names the domain, because the value is very often perfectly valid one
    row further down the library and "invalid status" would send the reader hunting.
    """
    if domain.status(value) is None:
        raise InvalidStatus(f"{domain.label} has no status named {value!r}")
    return value


def validate_formats(domain: Domain, values: Sequence[str]) -> list[str]:
    """Refuse anything outside the vocabulary, and keep the domain's own order."""
    declared = [row.value for row in domain.formats]
    for value in values:
        if value not in declared:
            raise InvalidFormat(f"{domain.label} has no format named {value!r}")
    return [value for value in declared if value in set(values)]


def validate_entry_fields(domain: Domain, changes: Mapping[str, Any]) -> dict[str, Any]:
    """Refuse the passage fields a domain does not have, and pass everything else.

    Hiding them in the UI would leave the API, the importers and the export able to
    store a reread count on a record — a value nothing can ever mean (DEC-057).
    """
    for name in PASSAGE_FIELDS - domain.entry_fields:
        if name in changes:
            raise InvalidEntryField(f"{domain.label} entries have no {name!r}")
    return dict(changes)


@dataclass(frozen=True)
class UrlMatch:
    """What a domain recognized in something typed into the add box.

    `action` is how to spend it: `fetch` a record by its id, expand a `work` into its
    editions, or run a `search` the domain's providers already understand.
    """

    provider: str
    action: Literal["fetch", "work", "search"]
    value: str


_OPENLIBRARY_HOSTS = {"openlibrary.org", "www.openlibrary.org"}
_MUSICBRAINZ_HOSTS = {"musicbrainz.org", "www.musicbrainz.org", "beta.musicbrainz.org"}
_OPENLIBRARY_EDITION = re.compile(r"/books/(OL\d+M)/?")
_OPENLIBRARY_WORK = re.compile(r"/works/(OL\d+W)/?")
_MUSICBRAINZ_RELEASE_GROUP = re.compile(
    r"/release-group/([0-9a-fA-F-]{36})/?",
)


def split_url(value: str) -> tuple[SplitResult, str] | None:
    """A parsed URL and its casefolded host, or `None` for anything unparseable.

    `urlsplit` **raises** on a malformed authority — `http://[` is `ValueError: Invalid
    IPv6 URL` — and a recognizer that raises does not fail only its own domain:
    `resolve_input` asks each registered domain in turn, so the first one to raise
    denies every domain after it its turn. Every recognizer therefore parses through
    here rather than reaching for `urlsplit` itself, and a domain that forgets is caught
    by `test_domain_conformance.py`.
    """
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").casefold()
    except ValueError:
        return None
    return parsed, host


def recognize_book_input(value: str) -> UrlMatch | None:
    """An ISBN, an Open Library edition or work, or a Google Books volume."""
    try:
        isbn = normalize_identifier("isbn", value).normalized_value
    except InvalidIdentifier:
        isbn = None
    if isbn:
        return UrlMatch("", "search", f"isbn:{isbn}")
    split = split_url(value)
    if split is None:
        return None
    parsed, host = split
    if host in _OPENLIBRARY_HOSTS:
        edition = _OPENLIBRARY_EDITION.fullmatch(parsed.path)
        if edition:
            return UrlMatch("openlibrary", "fetch", edition.group(1))
        work = _OPENLIBRARY_WORK.fullmatch(parsed.path)
        if work:
            return UrlMatch("openlibrary", "work", work.group(1))
    if host == "books.google.com" or host.endswith(".books.google.com"):
        volume = parse_qs(parsed.query).get("id", [""])[0]
        if volume:
            return UrlMatch("googlebooks", "fetch", volume)
    return None


def recognize_album_url(value: str) -> UrlMatch | None:
    """A MusicBrainz release-group URL. A release URL is deliberately not one.

    The item is the release group; pointing at one pressing would silently add a
    different record from the one the link names.
    """
    split = split_url(value)
    if split is None:
        return None
    parsed, host = split
    if host not in _MUSICBRAINZ_HOSTS:
        return None
    group = _MUSICBRAINZ_RELEASE_GROUP.fullmatch(parsed.path)
    return UrlMatch("musicbrainz", "fetch", group.group(1)) if group else None


class InvalidMetadata(ValueError):
    """A patch that the domain's own field spec refuses."""


def validate_metadata_patch(domain: Domain, patch: Mapping[str, Any]) -> dict[str, Any]:
    """Check a metadata patch against the fields this domain declares.

    Replaces `BookMetadataPatch`'s `extra="forbid"` plus per-field constraints, and
    keeps its behaviour: a key the domain does not declare is refused rather than
    stored, so a typo cannot quietly become a field.
    """
    for name, value in patch.items():
        field = next((row for row in domain.fields if row.name == name), None)
        if field is None:
            raise InvalidMetadata(f"{domain.label} metadata has no field named {name!r}")
        if value is None:
            continue
        if field.type == "rows":
            if not isinstance(value, Sequence) or isinstance(value, str | bytes):
                raise InvalidMetadata(f"{name!r} is a list of rows")
            declared = {column.name: column for column in field.columns}
            for row in value:
                if not isinstance(row, Mapping):
                    raise InvalidMetadata(f"{name!r} is a list of rows")
                for key, cell in row.items():
                    column = declared.get(key)
                    if column is None:
                        raise InvalidMetadata(f"{name!r} rows have no column {key!r}")
                    if cell is None:
                        continue
                    if column.type == "text" and not isinstance(cell, str):
                        raise InvalidMetadata(f"{key!r} is text")
                    if column.type in {"number", "duration"} and (
                        isinstance(cell, bool) or not isinstance(cell, int)
                    ):
                        raise InvalidMetadata(f"{key!r} is a whole number")
            continue
        if field.multiplicity == "many":
            if not isinstance(value, Sequence) or isinstance(value, str | bytes):
                raise InvalidMetadata(f"{name!r} is a list of values")
            if any(not isinstance(entry, str) for entry in value):
                raise InvalidMetadata(f"{name!r} is a list of text values")
            continue
        if field.type == "number":
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidMetadata(f"{name!r} is a whole number")
            if field.minimum is not None and value < field.minimum:
                raise InvalidMetadata(f"{name!r} must be {field.minimum} or more")
            if field.maximum is not None and value > field.maximum:
                raise InvalidMetadata(f"{name!r} must be {field.maximum} or less")
            continue
        if not isinstance(value, str):
            raise InvalidMetadata(f"{name!r} is text")
    return dict(patch)
