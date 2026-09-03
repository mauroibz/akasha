"""Albums: what this domain declares about itself.

Measured against live MusicBrainz on 2026-08-14 rather than guessed (DEC-052), which is
why the fields are the ones a release actually carries and the identity rule is "never
merge" rather than a barcode.
"""

import re

from book_tracker.domain.normalization import normalize_text
from book_tracker.domain.providers import IdentityStrategy, SearchCandidate
from book_tracker.domain.spec import (
    UNSORTED,
    ColumnSpec,
    Domain,
    EnrichmentSpec,
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
    FieldSpec("creators", "Artists", multiplicity="many", groupable=True),
    FieldSpec("credit", "Artist credit"),
    FieldSpec("label", "Label", groupable=True),
    FieldSpec("catalog_number", "Catalogue number"),
    FieldSpec("country", "Country", groupable=True),
    FieldSpec("language", "Language", groupable=True),
    FieldSpec("format", "Format", groupable=True),
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

# Sprint 064 supersedes `enrichment=None` without rewriting its reasoning: that premise
# — one MusicBrainz fetch already returns everything an album has — was true for the
# only way an album could be created when it was written, a search add that reaches
# MusicBrainz directly. An importer is a second way, and its rows arrive as a title and
# an artist with everything else still to fetch, which is exactly the gap
# `EnrichmentSpec` exists to fill (DEC-067 row 3).
ALBUM_ENRICHMENT = EnrichmentSpec(
    # A Spotify export's saved-album id, and nothing else: a search-added album
    # carries no `spotify` identifier at all, so it is never queued — the original
    # decision stays exactly right for the case it was made for.
    identity_kinds=("spotify",),
    provider_order=("musicbrainz",),
    # Fields only MusicBrainz can supply and a resolved release reliably carries;
    # `creators` and `credit` are deliberately absent because the importer already
    # fills them from Spotify's own artist field, so they never look incomplete.
    completeness_fields=("label", "country", "track_count"),
    # Both passes of the Spotify resolver need the item's own title and artist, which
    # a bare identifier value cannot carry (see domains/album/providers.py).
    needs_item_context=True,
)


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
    # True for a search add, which is why this stayed `None` until Sprint 064 gave
    # an importer a second way to create an album — see `ALBUM_ENRICHMENT` above.
    enrichment=ALBUM_ENRICHMENT,
    recognize=lambda value: recognize_album_url(value),
    chooses_covers=False,
    # "Various Artists" is not an artist; ranking by creator would put it third in the
    # owner's own library (measured, docs/spotify-import-and-insights-viability.md).
    insight_suppressed_keys=frozenset({normalize_text("Various Artists")}),
)
