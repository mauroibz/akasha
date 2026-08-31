"""Anime: what this domain declares about itself.

Measured against live AniList and Kitsu on 2026-08-27 rather than guessed (DEC-088),
which is why the fields are the ones a series actually carries, the identity rule is a
MyAnimeList id rather than "never merge", and MyAnimeList's own scraper mirror is not
one of the two providers.

Two names here were chosen against the obvious ones on purpose. A release is a `kind`
and not a `format`, because `format` is the entry-level axis for how a copy is held
(DEC-059) and a metadata field wearing that word reads as that concept on every screen.
An `airing_status` is not a `status`, for the same reason against the entry vocabulary.
"""

import re

from book_tracker.domain.providers import IdentityStrategy, SearchCandidate
from book_tracker.domain.spec import (
    PASSAGE_FIELDS,
    UNSORTED,
    Domain,
    EnrichmentSpec,
    FieldSpec,
    FormatSpec,
    ProgressSpec,
    StatusSpec,
    UrlMatch,
    split_url,
)

# Measured against live AniList and Kitsu on 2026-08-27. `creators` holds the animation
# studio, because that is the name a person files a series under and the one both
# sources curate; a studio never inverts, so the adapters supply `creator_sort`
# unchanged and the DEC-051 heuristic never runs on `MAPPA` (DEC-068 predicted exactly
# this for IGDB's companies).
ANIME_FIELDS = (
    FieldSpec("creators", "Studios", multiplicity="many"),
    FieldSpec("english_title", "English title"),
    FieldSpec("japanese_title", "Japanese title"),
    FieldSpec("kind", "Type"),
    FieldSpec("episodes", "Episodes", type="number", minimum=1, maximum=10_000),
    FieldSpec("episode_minutes", "Episode length", type="number", minimum=1, maximum=1_000),
    FieldSpec("season", "Season"),
    FieldSpec("source", "Adapted from"),
    FieldSpec("genres", "Genres", multiplicity="many"),
    FieldSpec("airing_status", "Airing"),
    FieldSpec("synopsis", "Synopsis", type="long_text"),
)

# MyAnimeList's own five states, because the owner's library is already written in them
# and an import that had to translate would be translating into a vocabulary nobody
# uses. `dropped` is a coincidence of spelling with the book vocabulary, not shared
# state (technical spec 6.6).
ANIME_STATUSES = (
    UNSORTED,
    StatusSpec("watching", "Watching", hotkey="w"),
    StatusSpec("completed", "Completed", hotkey="c"),
    StatusSpec("on_hold", "On hold", hotkey="h"),
    StatusSpec("dropped", "Dropped", hotkey="d"),
    StatusSpec("plan_to_watch", "Plan to watch", hotkey="p"),
)

# How a copy is held, which is not how it was watched: subbed and dubbed are properties
# of a viewing, and the closed-vocabulary rule (DEC-059) is about possession.
ANIME_FORMATS = (
    FormatSpec("streaming", "Streaming"),
    FormatSpec("digital", "Digital"),
    FormatSpec("bluray", "Blu-ray"),
)


def mal_identity(candidate: SearchCandidate) -> str | None:
    """Anime's cross-provider identity: the MyAnimeList id, which both sources publish.

    The first real identity since books (DEC-088). AniList carries it as `idMal` on the
    record and Kitsu carries it as a `myanimelist/anime` mapping returned in the same
    search request, so two rows for one series genuinely merge — where an album could
    only ever answer `None`, because a barcode is not an edition key.

    `None` is still the answer for a candidate that carries no mapping, and that is not
    a degraded one: AniList returns `idMal: null` for legitimate entries, and a row with
    no shared identifier must merge with nothing rather than on a weaker key.
    """
    value = str(candidate.identifiers.get("mal") or "").strip()
    return f"mal:{value}" if value.isdigit() else None


ANIME_IDENTITY = IdentityStrategy(mal_identity, ("anilist", "kitsu"))

# An anime added by hand arrives complete from one fetch; an *imported* MyAnimeList
# row is an id, a title, a type and an episode count, and everything a person wants
# to look at — the cover, the studio, the year, the synopsis — has to be fetched.
# This is the case DEC-067 row 3 reserved the seam for: the key is a MyAnimeList id
# and not an ISBN, and both providers resolve it (DEC-088).
ANIME_ENRICHMENT = EnrichmentSpec(
    identity_kinds=("mal",),
    provider_order=("anilist", "kitsu"),
    # What an imported row is missing. Deliberately not every field: `season` and
    # `episode_minutes` are legitimately absent on plenty of records, and a rule
    # that names them would re-queue those rows for ever.
    completeness_fields=("creators", "genres", "synopsis"),
)


_ANILIST_HOSTS = {"anilist.co", "www.anilist.co"}
# Kitsu serves its API from `kitsu.io` and its site from `kitsu.app`; a reader may paste
# either, and both name the same record by slug or by id.
_KITSU_HOSTS = {"kitsu.io", "www.kitsu.io", "kitsu.app", "www.kitsu.app"}
_MYANIMELIST_HOSTS = {"myanimelist.net", "www.myanimelist.net"}

_ANILIST_ANIME = re.compile(r"/anime/(\d+)(?:/[^/]*)*/?")
_KITSU_ANIME = re.compile(r"/anime/([A-Za-z0-9][A-Za-z0-9-]*)/?")
_MYANIMELIST_ANIME = re.compile(r"/anime/(\d+)(?:/[^/]*)*/?")


def recognize_anime_url(value: str) -> UrlMatch | None:
    """An AniList, Kitsu or MyAnimeList series URL. A manga URL is deliberately not one.

    A MyAnimeList link is spent on **AniList**, because Jikan is not registered
    (DEC-088) and AniList resolves a MyAnimeList id directly through `Media(idMal:)`.
    The `mal:` prefix is how the adapter is told which of the two ids it was handed.

    Parsed through `split_url` rather than `urlsplit`, which raises on a malformed
    authority: `resolve_input` asks every registered domain in turn, so a recognizer
    that raises denies every domain after it its turn.
    """
    split = split_url(value)
    if split is None:
        return None
    parsed, host = split
    if host in _ANILIST_HOSTS:
        match = _ANILIST_ANIME.fullmatch(parsed.path)
        return UrlMatch("anilist", "fetch", match.group(1)) if match else None
    if host in _KITSU_HOSTS:
        match = _KITSU_ANIME.fullmatch(parsed.path)
        return UrlMatch("kitsu", "fetch", match.group(1)) if match else None
    if host in _MYANIMELIST_HOSTS:
        match = _MYANIMELIST_ANIME.fullmatch(parsed.path)
        return UrlMatch("anilist", "fetch", f"mal:{match.group(1)}") if match else None
    return None


DOMAIN = Domain(
    item_type="anime",
    label="Anime",
    identity=ANIME_IDENTITY,
    fields=ANIME_FIELDS,
    statuses=ANIME_STATUSES,
    default_status="completed",
    entry_fields=PASSAGE_FIELDS,
    formats=ANIME_FORMATS,
    entry_panel_label="Your watch data",
    # `Started` and `Finished` read correctly for a series; `Rereads` does not.
    entry_field_labels={"reread_count": "Rewatches"},
    enrichment=ANIME_ENRICHMENT,
    # Every row of a MyAnimeList export carries a watched-episode count, and 7 of
    # the owner's 81 are partial — `Black Clover`, dropped at 20 of 170. Without
    # this the library can say only "dropped" (DEC-077 shape (a)).
    progress=ProgressSpec("Episodes watched", "episode", total_field="episodes"),
    recognize=lambda value: recognize_anime_url(value),
    chooses_covers=False,
)
