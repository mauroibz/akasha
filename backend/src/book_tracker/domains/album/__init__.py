"""Albums: what this domain declares about itself.

Measured against live MusicBrainz on 2026-08-14 rather than guessed (DEC-052), which is
why the fields are the ones a release actually carries and the identity rule is "never
merge" rather than a barcode.
"""

import re

from book_tracker.domain.providers import IdentityStrategy, SearchCandidate
from book_tracker.domain.spec import (
    UNSORTED,
    ColumnSpec,
    Domain,
    FieldSpec,
    FormatSpec,
    StatusSpec,
    UrlMatch,
    split_url,
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

ALBUM_FORMATS = (
    FormatSpec("vinyl", "Vinyl"),
    FormatSpec("cd", "CD"),
    FormatSpec("digital", "Digital"),
)


def no_shared_identity(_candidate: SearchCandidate) -> None:
    """Albums have no cross-provider identity, and that is a complete answer.

    DEC-052 observed barcode `888837168625` on three distinct releases. A barcode is
    therefore not an edition key, and there is no other global identifier a second
    provider would carry — so the correct behaviour is to merge nothing rather than
    to merge on a weaker key.
    """
    return None


ALBUM_IDENTITY = IdentityStrategy(no_shared_identity, ("musicbrainz",))


_MUSICBRAINZ_HOSTS = {"musicbrainz.org", "www.musicbrainz.org", "beta.musicbrainz.org"}
_MUSICBRAINZ_RELEASE_GROUP = re.compile(
    r"/release-group/([0-9a-fA-F-]{36})/?",
)


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


DOMAIN = Domain(
    item_type="album",
    label="Album",
    identity=ALBUM_IDENTITY,
    fields=ALBUM_FIELDS,
    statuses=ALBUM_STATUSES,
    default_status="owned",
    entry_fields=frozenset(),
    formats=ALBUM_FORMATS,
    entry_panel_label="Your copy",
    # One MusicBrainz release fetch already returns everything an album has, so
    # there is nothing for a background job to fill. A complete answer, not a gap.
    enrichment=None,
    recognize=lambda value: recognize_album_url(value),
    chooses_covers=False,
)
