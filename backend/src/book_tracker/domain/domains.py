"""What a domain knows about itself, and the registry of the domains that exist.

The shared layers speak in neutral terms — an item has a type, a title, creators,
identifiers and an opaque metadata object — and a domain plugin supplies the parts
only it can know (DEC-052, `docs/domain-architecture-proposal.md` section 4). A domain
is never translated into another domain's vocabulary, and the shared layer never
branches on which one it is holding.

This record grows one seam at a time. It starts with identity because that is the seam
the earlier plan did not anticipate and the one most likely to be wrong.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from book_tracker.domain.providers import ALBUM_IDENTITY, BOOK_IDENTITY, IdentityStrategy

FieldType = Literal["text", "long_text", "number"]
Multiplicity = Literal["one", "many"]


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
)


@dataclass(frozen=True)
class Domain:
    """`item_type` is the value stored in `items.type` and is permanent."""

    item_type: str
    label: str
    identity: IdentityStrategy
    fields: tuple[FieldSpec, ...]


BOOK = Domain(item_type="book", label="Book", identity=BOOK_IDENTITY, fields=BOOK_FIELDS)
ALBUM = Domain(item_type="album", label="Album", identity=ALBUM_IDENTITY, fields=ALBUM_FIELDS)

DOMAINS: dict[str, Domain] = {domain.item_type: domain for domain in (BOOK, ALBUM)}

# Every route, importer and repository that predates the second domain works on books;
# naming that here keeps `"book"` out of those call sites as a literal.
DEFAULT_DOMAIN = BOOK


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
