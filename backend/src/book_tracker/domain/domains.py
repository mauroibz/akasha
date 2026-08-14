"""What a domain knows about itself, and the registry of the domains that exist.

The shared layers speak in neutral terms — an item has a type, a title, creators,
identifiers and an opaque metadata object — and a domain plugin supplies the parts
only it can know (DEC-052, `docs/domain-architecture-proposal.md` section 4). A domain
is never translated into another domain's vocabulary, and the shared layer never
branches on which one it is holding.

This record grows one seam at a time. It starts with identity because that is the seam
the earlier plan did not anticipate and the one most likely to be wrong.
"""

from dataclasses import dataclass

from book_tracker.domain.providers import ALBUM_IDENTITY, BOOK_IDENTITY, IdentityStrategy


@dataclass(frozen=True)
class Domain:
    """`item_type` is the value stored in `items.type` and is permanent."""

    item_type: str
    label: str
    identity: IdentityStrategy


BOOK = Domain(item_type="book", label="Book", identity=BOOK_IDENTITY)
ALBUM = Domain(item_type="album", label="Album", identity=ALBUM_IDENTITY)

DOMAINS: dict[str, Domain] = {domain.item_type: domain for domain in (BOOK, ALBUM)}

# Every route, importer and repository that predates the second domain works on books;
# naming that here keeps `"book"` out of those call sites as a literal.
DEFAULT_DOMAIN = BOOK
