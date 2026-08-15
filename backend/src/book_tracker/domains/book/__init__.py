"""Books: what this domain declares about itself.

Everything the shared layers may know about a book is here — its metadata fields, its
status and format vocabularies, its cross-provider identity rule and what it recognizes
in the add box. Nothing outside this package spells a book's vocabulary.
"""

import re
from urllib.parse import parse_qs

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.providers import IdentityStrategy, SearchCandidate
from book_tracker.domain.spec import (
    PASSAGE_FIELDS,
    UNSORTED,
    Domain,
    FieldSpec,
    FormatSpec,
    StatusSpec,
    UrlMatch,
    split_url,
)

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

BOOK_STATUSES = (
    UNSORTED,
    StatusSpec("read", "Read", hotkey="r"),
    StatusSpec("reading", "Reading", hotkey="g"),
    StatusSpec("to_read", "To read", hotkey="t"),
    StatusSpec("wishlist", "Wishlist", hotkey="w"),
    StatusSpec("dropped", "Dropped", hotkey="d"),
)

BOOK_FORMATS = (
    FormatSpec("physical", "Physical"),
    FormatSpec("borrowed", "Borrowed"),
    FormatSpec("digital", "Digital"),
)


def isbn_identity(candidate: SearchCandidate) -> str | None:
    """Books' cross-provider identity: an ISBN is globally unique, so it can group."""
    value = candidate.identifiers.get("isbn13") or candidate.identifiers.get("isbn")
    if not value:
        return None
    try:
        return normalize_identifier("isbn", value).normalized_value
    except InvalidIdentifier:
        return None


#: Product spec 4.3 prefers Open Library's record; alphabetical order does not.
SOURCE_PREFERENCE = ("openlibrary", "googlebooks")
BOOK_IDENTITY = IdentityStrategy(isbn_identity, SOURCE_PREFERENCE)


_OPENLIBRARY_HOSTS = {"openlibrary.org", "www.openlibrary.org"}
_OPENLIBRARY_EDITION = re.compile(r"/books/(OL\d+M)/?")
_OPENLIBRARY_WORK = re.compile(r"/works/(OL\d+W)/?")


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


DOMAIN = Domain(
    item_type="book",
    label="Book",
    identity=BOOK_IDENTITY,
    fields=BOOK_FIELDS,
    statuses=BOOK_STATUSES,
    default_status="read",
    entry_fields=PASSAGE_FIELDS,
    formats=BOOK_FORMATS,
    entry_panel_label="Your reading data",
    enriches=True,
    recognize=lambda value: recognize_book_input(value),
    chooses_covers=True,
)
