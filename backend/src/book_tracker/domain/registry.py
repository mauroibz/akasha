"""Which domains exist, and the unions the API publishes across them.

The registry is **code, not a plugin runtime** (product spec section 2): a domain is a
Python object registered here at import time. Adding one is an import and a tuple entry.
Provider wiring and migrations are the other required shared registration points; an
optional importer adds one more tuple here (technical spec 6.6).

Nothing in this module knows what a book or an album *is*. That lives in
`book_tracker/domains/<item_type>/`, and what a domain may declare lives in
`domain/spec.py`.
"""

from collections.abc import Sequence
from enum import StrEnum

from book_tracker.domain.importers import Importer
from book_tracker.domain.spec import Domain
from book_tracker.domains.album import DOMAIN as ALBUM
from book_tracker.domains.anime import DOMAIN as ANIME
from book_tracker.domains.anime.myanimelist import IMPORTER as MYANIMELIST_IMPORTER
from book_tracker.domains.book import DOMAIN as BOOK
from book_tracker.domains.book.calibre import IMPORTER as CALIBRE_IMPORTER
from book_tracker.domains.book.goodreads import IMPORTER as GOODREADS_IMPORTER
from book_tracker.domains.movie import DOMAIN as MOVIE
from book_tracker.domains.movie.imdb import IMPORTER as IMDB_IMPORTER
from book_tracker.domains.movie.letterboxd import IMPORTER as LETTERBOXD_IMPORTER
from book_tracker.domains.series import DOMAIN as SERIES

DOMAINS: dict[str, Domain] = {
    domain.item_type: domain for domain in (BOOK, ALBUM, ANIME, MOVIE, SERIES)
}

# The same code-owned registration model as domains and providers: no discovery or
# plugin runtime.  Connectors live in the package of the domain they lead with; the
# shared registry only builds the two indexes it needs to publish and dispatch them.
#
# One connector may target several domains (DEC-106), so the by-domain index is a
# relation rather than a function: it is *derived* from what each connector declares
# rather than written out, because a hand-maintained index and a declaration
# disagreeing is a connector reachable from a library it cannot fill.
REGISTERED_IMPORTERS: tuple[Importer, ...] = (
    GOODREADS_IMPORTER,
    CALIBRE_IMPORTER,
    MYANIMELIST_IMPORTER,
    LETTERBOXD_IMPORTER,
    IMDB_IMPORTER,
)
IMPORTERS_BY_DOMAIN: dict[str, tuple[Importer, ...]] = {
    item_type: tuple(
        importer for importer in REGISTERED_IMPORTERS if item_type in importer.item_types
    )
    for item_type in DOMAINS
}
#: Keyed by name, so a connector indexed under two domains is still published once.
IMPORTERS: dict[str, Importer] = {importer.name: importer for importer in REGISTERED_IMPORTERS}

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
    WATCHING = "watching"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    PLAN_TO_WATCH = "plan_to_watch"
    WATCHLIST = "watchlist"
    WATCHED = "watched"


class EntryFormat(StrEnum):
    """The published union of every domain's formats, for filters and facets."""

    PHYSICAL = "physical"
    BORROWED = "borrowed"
    DIGITAL = "digital"
    VINYL = "vinyl"
    CD = "cd"
    STREAMING = "streaming"
    BLURAY = "bluray"
    DVD = "dvd"


class ItemTypeName(StrEnum):
    """The published union of domain names, so `?type=` enumerates in OpenAPI.

    Spelled out for the same reason `EntryStatus` is, and pinned to `DOMAINS` by the
    same test. Unlike a status, a type is never validated against an item's own domain
    — it *is* the domain — so this enum is the whole check the filter needs.
    """

    BOOK = "book"
    ALBUM = "album"
    ANIME = "anime"
    MOVIE = "movie"
    SERIES = "series"
