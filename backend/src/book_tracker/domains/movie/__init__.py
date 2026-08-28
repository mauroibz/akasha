"""Movies: what this domain declares about itself.

Measured against live Wikidata on 2026-08-27 rather than guessed (DEC-098), which is why
the fields are the claims a film entity actually carries, why there is no cover in the
launch contract, and why the enrichment key is a Letterboxd film rather than a title.

Two absences here are decisions, not omissions:

- **No cover.** Four of the five films Sprint 045 fetched had no `P18` at all, and the
  one that did was a set photograph rather than poster art. An arbitrary image promoted
  to a poster is worse than a blank tile, so the provider returns no cover URL and manual
  upload remains the way a film gets one.
- **No start date and no progress.** Nobody records the day they began a 94-minute film,
  and `20 / 170` means nothing about one. DEC-077's `None` is a complete answer.

The vocabulary is deliberately not the book vocabulary renamed. A film is on the list or
it has been seen; there is no `reading`, and a half-watched film is not a state worth
storing (DEC-057).
"""

import re

from book_tracker.domain.providers import IdentityStrategy, SearchCandidate
from book_tracker.domain.spec import (
    UNSORTED,
    Domain,
    EnrichmentSpec,
    FieldSpec,
    FormatSpec,
    StatusSpec,
    UrlMatch,
    split_url,
)

# Measured against live Wikidata on 2026-08-27. Each of these is one claim on the film
# entity: `P57` director, `P1476` title in its original language, `P495` country of
# origin, `P364` original language, `P136` genre, `P2047` duration, `P161` cast member
# and the entity's own localized description.
#
# `creators` holds the directors, because that is the name a person files a film under.
# A director is a person and inverts, so the adapter leaves `creator_sort` unset and the
# DEC-051 heuristic runs — unlike anime, where a studio never inverts (DEC-068).
#
# `description` is Wikidata's short identification sentence — "1977 film by Dario
# Argento" — and not a synopsis. Wikidata does not publish one, and calling this field
# `synopsis` would promise something no measured record contained.
MOVIE_FIELDS = (
    FieldSpec("creators", "Directors", multiplicity="many"),
    FieldSpec("original_title", "Original title"),
    FieldSpec("countries", "Countries", multiplicity="many"),
    FieldSpec("languages", "Original languages", multiplicity="many"),
    FieldSpec("genres", "Genres", multiplicity="many"),
    FieldSpec("runtime", "Runtime (minutes)", type="number", minimum=1, maximum=10_000),
    FieldSpec("cast", "Cast", multiplicity="many"),
    FieldSpec("description", "Description", type="long_text"),
)

# `w` is spent on Watched rather than on Watchlist because an import arrives mostly
# watched and Triage is where that decision is made eighty times in a row. `l` is the
# list. The hotkey lives on the status it sets, not in a second table.
MOVIE_STATUSES = (
    UNSORTED,
    StatusSpec("watchlist", "Watchlist", hotkey="l"),
    StatusSpec("watched", "Watched", hotkey="w"),
)

# How a copy is held, which is not how it was watched: a subtitled viewing is a property
# of the viewing, and the closed-vocabulary rule (DEC-059) is about possession. Three of
# these four values already existed for anime; `dvd` is the one new published format.
MOVIE_FORMATS = (
    FormatSpec("streaming", "Streaming"),
    FormatSpec("digital", "Digital"),
    FormatSpec("bluray", "Blu-ray"),
    FormatSpec("dvd", "DVD"),
)

_Q_ID = re.compile(r"Q[1-9][0-9]*")


def wikidata_identity(candidate: SearchCandidate) -> str | None:
    """A film's identity is its Wikidata `Q` id, and nothing weaker.

    One provider means no cross-provider merge is possible today, so this key exists for
    a different reason than anime's: it is what stops the *same* provider's two rows for
    `Suspiria` — Dario Argento's in 1977 and Luca Guadagnino's in 2018 — from being
    treated as one record. Title and year are not identity even between two films that
    share both, which is exactly the pair Sprint 045 measured.

    `None` for an unusable row, which merges with nothing rather than on a weaker key.
    """
    value = str(candidate.source_id or "").strip()
    return f"wikidata:{value}" if _Q_ID.fullmatch(value) else None


MOVIE_IDENTITY = IdentityStrategy(wikidata_identity, ("wikidata",))

# A film added through search arrives complete from one fetch, as an album does. This
# declaration is for the row Sprint 047's Letterboxd export creates: a short URI, a title
# and a year, with every field a person wants to look at still empty. The key is a
# Letterboxd film because that is the only identity the export carries (DEC-067 row 3).
MOVIE_ENRICHMENT = EnrichmentSpec(
    identity_kind="letterboxd",
    provider_order=("wikidata",),
    # All five films Sprint 045 fetched carried director, genre and duration claims.
    # `cast` and `description` are deliberately absent from this rule: a legitimately
    # empty field named here re-queues its row on every backfill for ever.
    completeness_fields=("creators", "genres", "runtime"),
)


_WIKIDATA_HOSTS = {"wikidata.org", "www.wikidata.org"}
_IMDB_HOSTS = {"imdb.com", "www.imdb.com", "m.imdb.com"}
_TMDB_HOSTS = {"themoviedb.org", "www.themoviedb.org"}
_LETTERBOXD_HOSTS = {"letterboxd.com", "www.letterboxd.com"}
_BOXD_HOSTS = {"boxd.it"}

# `/wiki/Q546900` and `/entity/Q546900` both name the entity; `/wiki/Property:P31` does
# not, and the anchored `Q` pattern is what declines it.
_WIKIDATA_ENTITY = re.compile(r"/(?:wiki|entity)/(Q[1-9][0-9]*)/?")
_IMDB_TITLE = re.compile(r"/title/(tt[0-9]{7,10})(?:/[^/]*)*/?")
# TMDB renders `/movie/11906-suspiria`; only the leading number is the id. `/tv/1396` is
# a series and is deliberately not a movie URL.
_TMDB_MOVIE = re.compile(r"/movie/([0-9]+)(?:-[^/]*)?(?:/[^/]*)*/?")
_LETTERBOXD_FILM = re.compile(r"/film/([a-z0-9][a-z0-9-]*)/?")
_BOXD_SHORT = re.compile(r"/([A-Za-z0-9]{2,12})/?")

#: How the adapter is told which of the four ids it was handed.
IMDB_PREFIX = "imdb:"
TMDB_PREFIX = "tmdb:"
LETTERBOXD_PREFIX = "letterboxd:"


def recognize_movie_url(value: str) -> UrlMatch | None:
    """A Wikidata, IMDb, TMDB, Letterboxd or `boxd.it` film URL, spent on one adapter.

    Only Wikidata is a registered provider. An IMDb, TMDB or Letterboxd link resolves
    through the exact `P345`, `P4947` or `P6127` claim instead, which is identity
    resolution against a source we do have rather than a scrape of one we do not.

    A short `boxd.it` URI keeps its whole address, because resolving it costs a HEAD
    request and a recognizer must answer without touching the network.

    Parsed through `split_url` rather than `urlsplit`, which raises on a malformed
    authority: `resolve_input` asks every registered domain in turn, so a recognizer
    that raises denies every domain after it its turn.
    """
    split = split_url(value)
    if split is None:
        return None
    parsed, host = split
    if host in _WIKIDATA_HOSTS:
        match = _WIKIDATA_ENTITY.fullmatch(parsed.path)
        return UrlMatch("wikidata", "fetch", match.group(1)) if match else None
    if host in _IMDB_HOSTS:
        match = _IMDB_TITLE.fullmatch(parsed.path)
        return UrlMatch("wikidata", "fetch", f"{IMDB_PREFIX}{match.group(1)}") if match else None
    if host in _TMDB_HOSTS:
        match = _TMDB_MOVIE.fullmatch(parsed.path)
        return UrlMatch("wikidata", "fetch", f"{TMDB_PREFIX}{match.group(1)}") if match else None
    # Both Letterboxd shapes are only followed over HTTPS. A plaintext hop is where a
    # redirect can be rewritten, and the adapter that resolves it refuses one anyway.
    if parsed.scheme != "https":
        return None
    if host in _LETTERBOXD_HOSTS:
        match = _LETTERBOXD_FILM.fullmatch(parsed.path)
        if match is None:
            return None
        return UrlMatch("wikidata", "fetch", f"{LETTERBOXD_PREFIX}{match.group(1)}")
    if host in _BOXD_HOSTS and _BOXD_SHORT.fullmatch(parsed.path):
        return UrlMatch("wikidata", "fetch", f"{LETTERBOXD_PREFIX}{value.strip()}")
    return None


DOMAIN = Domain(
    item_type="movie",
    label="Movie",
    identity=MOVIE_IDENTITY,
    fields=MOVIE_FIELDS,
    statuses=MOVIE_STATUSES,
    default_status="watchlist",
    # You finish a film and you rewatch it; you do not record starting one.
    entry_fields=frozenset({"date_finished", "reread_count"}),
    formats=MOVIE_FORMATS,
    entry_panel_label="Your viewing data",
    # `Finished` reads correctly for a book and a series alike; for a film the word is
    # `Watched`, and `Rereads` is wrong for the same reason it was wrong for anime.
    entry_field_labels={"date_finished": "Watched", "reread_count": "Rewatches"},
    enrichment=MOVIE_ENRICHMENT,
    progress=None,
    recognize=lambda value: recognize_movie_url(value),
    chooses_covers=False,
)
