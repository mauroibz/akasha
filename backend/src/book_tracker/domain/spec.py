"""What a domain is: the vocabulary every domain declares itself in.

The shared layers speak in neutral terms — an item has a type, a title, creators,
identifiers and an opaque metadata object — and a domain plugin supplies the parts
only it can know (DEC-052). A domain is never translated into another domain's
vocabulary, and the shared layer never branches on which one it is holding.

**This module holds the shapes and the rules; no domain lives here.** Each domain
declares itself in `book_tracker/domains/<item_type>/`, and `domain/registry.py` says
which ones exist. Splitting the three apart is what lets two domains be built in
parallel without editing each other's file (technical spec 6.6, DEC-067).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
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

# Entry values the neutral core owns rather than any one domain. Domain-specific
# values are the declared passage fields plus optional progress below. Keep this list
# beside the validator: a new write surface must either use one of these meanings or
# extend `Domain` so the owning domain can declare it.
NEUTRAL_ENTRY_VALUES = frozenset(
    {
        "status",
        "score",
        "notes",
        "shelf_ids",
        "formats",
        "add_shelves",
        "remove_shelves",
        "add_formats",
        "remove_formats",
        "clear_provisional",
    }
)


@dataclass(frozen=True)
class ProgressSpec:
    """How far through one of these you are, when that is a thing this domain has.

    DEC-077 priced entry *depth* across nine shared surfaces, rejected child entities
    with their own state on evidence, and chose this shape instead: one number on the
    flat entry, declared by the domain that means something by it. An anime records
    episodes watched; a book records nothing of the kind, because a page count is not
    something the entry holds.

    It is deliberately **not** a fourth `PASSAGE_FIELDS` name. Those are three fixed
    columns with fixed meanings. The shared `validate_entry_values` allowlist composes
    their domain declaration with this separate progress rule, which also needs a label,
    a unit and a reference to its total—none of which a passage field can express.
    """

    #: What this domain calls the count. "Episodes watched".
    label: str
    #: The singular noun for one of them, so a control can read "20 / 170 episodes".
    unit_label: str
    #: A `number` metadata field on the *item* holding the total, when one exists.
    #:
    #: **For display only, and never a bound.** Refusing a count above it was the first
    #: draft of this sprint and the owner rejected it: AniList returns `episodes: null`
    #: for an airing or unreleased show, a weekly series' cached total is stale by
    #: definition, and an explicit metadata refresh could lower the total underneath a
    #: count already stored — making a row that was valid when written invalid on its
    #: next write. That is `ck_entries_status`'s mistake wearing new clothes: a
    #: constraint over data the domain does not control (DEC-067 row 1). The reader's
    #: number wins over our cache.
    total_field: str | None = None


@dataclass(frozen=True)
class EnrichmentSpec:
    """What background enrichment means for one domain (DEC-067 row 3).

    Everything below `enriches` used to be books': the backfill joined
    `item_identifiers` on the literal `'isbn'`, judged a record incomplete by the
    absence of `publisher`, `page_count` and `description`, and tried two book
    providers from a module constant. A domain that enriches on anything else could
    declare the flag and get nothing — or worse, look permanently incomplete because
    it has none of the three book fields, and be re-queued on every backfill.

    All three parts are per-domain, because all three were book-shaped:

    - **`identity_kinds`** are the `item_identifiers.kind` values the lookup may be
      keyed on, in order of preference: `isbn` for a book, `mal` for an anime,
      `letterboxd` then `imdb` for a film. An item carrying none of them is never
      queued, because there is nothing to look it up by; an item carrying several is
      queued **once**, under the first it has.

      More than one because a domain's *sources* supply different keys and the domain
      does not get to choose which one the owner used. A Letterboxd export names a film
      by a `boxd.it` URI and carries no IMDb id; an IMDb export names it by `tt` and
      carries no Letterboxd URI. Under a single declared key, whichever source was not
      the one in mind when the domain was written gets no enrichment at all — no
      poster, no genres, no runtime — while every gate stays green (DEC-113).
    - **`provider_order`** is which adapters are asked, in order. The first usable
      payload wins; a provider that is not wired contributes a sentence to the
      recorded reason rather than being skipped silently.
    - **`completeness_fields`** are the metadata fields whose absence means this
      record is still worth a lookup. They must be fields the domain declares — a
      name it does not have is always absent, so the record would never look complete.
      A missing cover or year counts in every registered domain but is a declaration
      (`wants_cover`, `wants_year`) rather than a constant, because a domain whose
      providers carry neither must not be re-queued against them for ever (DEC-116).
    - **`fuller_answer_fields`** are the long-text fields where a longer answer is a
      better answer rather than a conflict (DEC-115). The first usable payload still
      wins every other field; for these alone, the remaining providers in
      `provider_order` are also asked, and the longest value fills the field when it
      is still empty. An owner's own value is never replaced, however short, and a
      provider's answer is never swapped for a shorter one — the rule is
      fuller-*than-what-would-otherwise-be-stored*, not "the last provider wins".
    """

    identity_kinds: tuple[str, ...]
    provider_order: tuple[str, ...]
    completeness_fields: tuple[str, ...]
    #: Whether a missing cover makes a record worth a lookup. The cover pipeline
    #: post-dates the assumption: every enriching domain's providers can carry a
    #: poster (Open Library and Google Books for films' books, Stremio for movies
    #: and series, AniList for anime), so the default is True — but it is a
    #: declaration rather than a constant because a domain whose providers carry
    #: none must not be re-queued for ever against them (DEC-116).
    wants_cover: bool = True
    #: Whether a missing year makes a record worth a lookup. Sharper than the
    #: cover condition: no provider contract guarantees a year, so a domain
    #: whose rows legitimately carry none would be re-queued on every backfill
    #: for ever unless it says otherwise (DEC-116).
    wants_year: bool = True
    #: Which long-text fields prefer the fuller of the providers' answers. Absent
    #: means every field keeps its first provider's answer, as before.
    fuller_answer_fields: tuple[str, ...] = ()


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
    #: What this domain calls its `entry_fields`, for the ones a neutral word gets wrong.
    #:
    #: `entry_panel_label` above made the heading over the personal region the domain's
    #: copy; the fields under it stayed book-shaped, so an anime read `Rereads`. Keys are
    #: `PASSAGE_FIELDS` names the domain declares — labelling a field you do not have is
    #: a label nothing renders — and anything absent falls back to the neutral word.
    #: Partial on purpose: `Started` and `Finished` are right for a book and a series
    #: alike, and a domain restating them adds drift rather than clarity.
    entry_field_labels: Mapping[str, str] = MappingProxyType({})
    #: What background enrichment is keyed on, whom it asks and what counts as
    #: incomplete — or `None` for a domain that does not enrich at all. One MusicBrainz
    #: release fetch already returns everything an album has, so `None` is a
    #: simplification rather than a gap. This replaced a bare `enriches: bool` in
    #: Sprint 039: the flag was real, and everything underneath it assumed an ISBN and
    #: two book providers (DEC-067 row 3).
    enrichment: "EnrichmentSpec | None" = None
    #: How far through one of these you are, or `None` for a domain where that means
    #: nothing. DEC-077's shape (a), built in Sprint 040 against anime's real case.
    progress: "ProgressSpec | None" = None
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

    @property
    def enriches(self) -> bool:
        """Whether background enrichment applies at all.

        Kept as a reading of the declaration so no call site has to ask two questions,
        and so the one thing most code wants to know stays a single word.
        """
        return self.enrichment is not None


class InvalidStatus(ValueError):
    """A status the item's own domain does not have."""


class InvalidFormat(ValueError):
    """A format the item's own domain does not have."""


class InvalidEntryField(ValueError):
    """An entry field the item's own domain does not have (DEC-057)."""


class InvalidProgress(ValueError):
    """A progress count on a domain that has no such concept, or a negative one."""


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


def validate_progress(domain: Domain, value: int | None) -> int | None:
    """The fourth validator, keyed on the domain holding the item (DEC-077).

    `None` is always allowed, in every domain: it means *not recorded*, and clearing a
    value nobody should have set is not something to refuse. `0` is a different fact —
    recorded as zero — and the owner's own library holds one, a film sitting at 0 of 1
    episodes under `Plan to Watch`.

    There is no upper bound. See `ProgressSpec.total_field` for why.
    """
    if value is None:
        return None
    if domain.progress is None:
        raise InvalidProgress(f"{domain.label} entries do not record progress")
    if value < 0:
        raise InvalidProgress(f"{domain.label} progress cannot be negative")
    return value


def validate_entry_values(domain: Domain, values: Mapping[str, Any]) -> dict[str, Any]:
    """Allow only neutral values and the entry values this domain declares.

    The old passage-field denylist was silent about every name it had never heard of.
    That is how `progress` reached storage before its domain guard was wired. This is
    the single entry-value boundary for PATCH, add and import: an unfamiliar name is a
    refusal, never an implicit new storage contract.
    """
    validated = validate_entry_fields(domain, values)
    allowed = NEUTRAL_ENTRY_VALUES | domain.entry_fields | {"progress"}
    unknown = set(validated) - allowed
    if unknown:
        names = ", ".join(repr(name) for name in sorted(unknown))
        raise InvalidEntryField(f"{domain.label} entries have no declared value {names}")
    if "progress" in validated:
        validated["progress"] = validate_progress(domain, validated["progress"])
    return validated


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


def declares_field(domain: Domain, name: str) -> bool:
    """Whether this domain has a field by this name.

    `SearchCandidate.language` is a transport field every provider may fill, but only
    `book` and `album` declare somewhere to put it: `movie` and `series` model the
    original languages as a `many` field called `languages`, and `anime` has neither.
    The add and refresh paths folded it in unconditionally, so a provider filling it for
    one of the other three turned every add of its results into a 422 — which is exactly
    what TVmaze did from Sprint 050 until DEC-125. Whether a candidate's language is
    stored is the domain's question, and this is how the two callers ask it.
    """
    return any(row.name == name for row in domain.fields)


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
