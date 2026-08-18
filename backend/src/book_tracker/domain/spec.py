"""What a domain is: the vocabulary every domain declares itself in.

The shared layers speak in neutral terms — an item has a type, a title, creators,
identifiers and an opaque metadata object — and a domain plugin supplies the parts
only it can know (DEC-052, `docs/domain-architecture-proposal.md` section 4). A domain
is never translated into another domain's vocabulary, and the shared layer never
branches on which one it is holding.

**This module holds the shapes and the rules; no domain lives here.** Each domain
declares itself in `book_tracker/domains/<item_type>/`, and `domain/registry.py` says
which ones exist. Splitting the three apart is what lets two domains be built in
parallel without editing each other's file (technical spec 6.6, DEC-067).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import SplitResult, urlsplit

from book_tracker.domain.providers import IdentityStrategy

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

#: The three entry columns that date a passage through a work. A domain declares which
#: of them it has; DEC-057 says an album has none of them.
PASSAGE_FIELDS = frozenset({"date_started", "date_finished", "reread_count"})


@dataclass(frozen=True)
class Domain:
    """Everything the shared layers may know about one kind of thing.

    Every field is an obligation (technical spec 6.6). The five that used to default to
    books' answers are required now that books live in a package of their own: a shared
    type whose defaults are one domain's vocabulary is the book shape hiding in the
    core, and a domain that inherits it silently is the failure this record exists to
    prevent. `item_type` is the value stored in `items.type` and is permanent.
    """

    item_type: str
    label: str
    identity: IdentityStrategy
    fields: tuple[FieldSpec, ...]
    #: The statuses an entry on this domain can hold, in the order a control offers
    #: them, and the one a newly added entry gets when nobody chose.
    statuses: tuple[StatusSpec, ...]
    default_status: str
    #: Which of `PASSAGE_FIELDS` this domain's entries have. Anything absent is refused
    #: on write, not merely hidden: a reread count on a record is not a display problem.
    entry_fields: frozenset[str]
    #: How a copy of this is held (DEC-059).
    formats: tuple[FormatSpec, ...]
    #: The heading over the personal region of the detail page. "Your reading data" is
    #: a book's phrase, and an album's entry records possession rather than reading.
    entry_panel_label: str
    #: Whether background enrichment applies. One MusicBrainz release fetch already
    #: returns everything an album has, where a Goodreads row starts as little more
    #: than an ISBN — so "this domain does not enrich" is a simplification, not a gap.
    enriches: bool = True
    #: Recognizes a URL or identifier this domain can resolve, for add-by-URL. The
    #: neutral default recognizes nothing, which is the safe answer for a domain that
    #: has not written one yet: `resolve_input` simply asks the next domain.
    recognize: Callable[[str], "UrlMatch | None"] = lambda _value: None
    #: Whether this domain can offer alternative covers to choose from (DEC-067 row 7).
    #: The shared implementation is still Open Library's work-editions path, so only a
    #: domain Open Library serves may declare it: an album has no work and no editions,
    #: and the control could only ever say no. Defaulting to `False` is deliberate —
    #: a domain that has not thought about covers offers no chooser, rather than one
    #: that cannot answer.
    chooses_covers: bool = False

    def status(self, value: str) -> StatusSpec | None:
        return next((row for row in self.statuses if row.value == value), None)


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
