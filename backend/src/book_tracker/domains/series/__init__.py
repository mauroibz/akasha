"""Series: what this domain declares about itself.

Measured against live Wikidata on 2026-08-31 rather than guessed (DEC-104), which is
why the fields are the claims a series entity actually carries, why the identity is an
IMDb id rather than a Wikidata `Q` id, and why the search filter is five instance-of
classes rather than the movie adapter's one (`docs/series-domain-viability.md`).

Two names here are decisions, not omissions:

- **`creators` holds the creator**, because that is the name a series is filed under
  and `P57` (director) was present on a minority of measured entities. A creator is a
  person and inverts, so `creator_sort` is left unset and the DEC-051 heuristic runs,
  exactly as for movies.
- **`synopsis` is named for its purpose.** The Wikidata adapter fills it with the
  one-line identification sentence — what movies call `description` — and the TVmaze
  adapter (Sprint 050) fills it with a real synopsis through the shared merge, which
  never overwrites the one already there. It is called `synopsis` rather than
  `description` because the real one is the point, and renaming a published field
  later is worse than naming it for its purpose from the start.
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

# Measured against live Wikidata on 2026-08-31 (docs/series-domain-viability.md).
# Each of these is one claim on the series entity: `P170` creator (falling back to
# `P58` screenwriter), `P1476` original title, `P495` country of origin, `P364`
# original language, `P136` genre, `P1113` number of episodes, `P2437` number of
# seasons, `P2047` episode duration, `P449` original broadcaster, `P161` cast member,
# and the entity's own localized description.
SERIES_FIELDS = (
    FieldSpec("creators", "Creators", multiplicity="many"),
    FieldSpec("original_title", "Original title"),
    FieldSpec("countries", "Countries", multiplicity="many"),
    FieldSpec("languages", "Original languages", multiplicity="many"),
    FieldSpec("genres", "Genres", multiplicity="many"),
    FieldSpec("episodes", "Episodes", type="number", minimum=1, maximum=100_000),
    FieldSpec("seasons", "Seasons", type="number", minimum=1, maximum=1_000),
    FieldSpec("episode_minutes", "Episode length", type="number", minimum=1, maximum=1_000),
    FieldSpec("network", "Network"),
    FieldSpec("airing_status", "Airing"),
    FieldSpec("cast", "Cast", multiplicity="many"),
    FieldSpec("synopsis", "Synopsis", type="long_text"),
)

# Anime's five, because a series is watched the same way, plus the inbox every domain
# has. The hotkeys are the same letters; the vocabulary adds nothing to `EntryStatus`.
SERIES_STATUSES = (
    UNSORTED,
    StatusSpec("watching", "Watching", hotkey="w"),
    StatusSpec("completed", "Completed", hotkey="c"),
    StatusSpec("on_hold", "On hold", hotkey="h"),
    StatusSpec("dropped", "Dropped", hotkey="d"),
    StatusSpec("plan_to_watch", "Plan to watch", hotkey="p"),
)

# The movie four: how a copy is held, not how it was watched (DEC-059).
SERIES_FORMATS = (
    FormatSpec("streaming", "Streaming"),
    FormatSpec("digital", "Digital"),
    FormatSpec("bluray", "Blu-ray"),
    FormatSpec("dvd", "DVD"),
)

_IMDB_ID = re.compile(r"tt[0-9]{7,10}")


def imdb_identity(candidate: SearchCandidate) -> str | None:
    """A series' identity is its IMDb id, and nothing weaker.

    The strongest identity position of any domain so far: Wikidata publishes it as
    `P345`, TVmaze as `externals.imdb`, and both planned importers carry it as their
    primary key — so two candidates genuinely merge and an import matches an existing
    item exactly. `None` for a candidate with none, which merges with nothing rather
    than on a weaker key.
    """
    value = str(candidate.identifiers.get("imdb") or "").strip()
    return f"imdb:{value}" if _IMDB_ID.fullmatch(value) else None


# The provider order is declared now — `("wikidata-series", "tvmaze")` — so Sprint 050
# adds an adapter and not a declaration. The Wikidata adapter's registered name is
# `wikidata-series` rather than `wikidata`: the provider catalog is keyed by name, and
# a second adapter answering to `wikidata` would silently replace the movie domain's.
SERIES_IDENTITY = IdentityStrategy(imdb_identity, ("wikidata-series", "tvmaze"))

# A series added by hand arrives complete from one fetch. This declaration is for the
# rows Sprints 051–053's importers create: an IMDb id, a title and a year, with every
# field a person wants to look at still empty. The key is an IMDb id because that is
# the only identity both exports carry (docs/series-domain-viability.md).
SERIES_ENRICHMENT = EnrichmentSpec(
    identity_kind="imdb",
    provider_order=("wikidata-series", "tvmaze"),
    # `creators`, `genres` and the description were present on 13/13 measured entities.
    # `seasons` (absent 2/13) and `cast` (absent 4/13, every animated series) are
    # deliberately absent: naming a legitimately empty field re-queues its row on
    # every backfill for ever.
    completeness_fields=("creators", "genres", "synopsis"),
)


_WIKIDATA_HOSTS = {"wikidata.org", "www.wikidata.org"}
_IMDB_HOSTS = {"imdb.com", "www.imdb.com", "m.imdb.com"}
_TMDB_HOSTS = {"themoviedb.org", "www.themoviedb.org"}
_TVDB_HOSTS = {"thetvdb.com", "www.thetvdb.com"}
_TVMAZE_HOSTS = {"tvmaze.com", "www.tvmaze.com"}

_WIKIDATA_ENTITY = re.compile(r"/(?:wiki|entity)/(Q[1-9][0-9]*)/?")
_IMDB_TITLE = re.compile(r"/title/(tt[0-9]{7,10})(?:/[^/]*)*/?")
# TMDB renders `/tv/1399-game-of-thrones`; only the leading number is the id.
# `/movie/…` is a film and is deliberately not matched — it stays the movie domain's.
_TMDB_SERIES = re.compile(r"/tv/([0-9]+)(?:-[^/]*)?(?:/[^/]*)*/?")
_TVDB_SERIES = re.compile(r"/series/([a-z0-9][a-z0-9-]*)/?")
_TVMAZE_SHOW = re.compile(r"/shows/([0-9]+)(?:/[^/]*)*/?")

#: How the adapter is told which of the four external ids it was handed.
IMDB_PREFIX = "imdb:"
TMDB_PREFIX = "tmdb:"
TVDB_PREFIX = "tvdb:"
TVMAZE_PREFIX = "tvmaze:"


def recognize_series_url(value: str) -> UrlMatch | None:
    """A Wikidata, IMDb, TMDB, TVDB or TVmaze series URL, spent on the right adapter.

    Only Wikidata is registered in Sprint 049; Sprint 050 adds TVmaze. An IMDb, TMDB
    or TVDB link resolves through the exact `P345`, `P4983` or `P4835` claim instead,
    which is identity resolution against a source we do have rather than a scrape of
    one we do not. A TVmaze link resolves through the TVmaze adapter. TMDB's `/movie/`
    path is a film and stays the movie domain's.

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
        return UrlMatch("wikidata-series", "fetch", match.group(1)) if match else None
    if host in _IMDB_HOSTS:
        match = _IMDB_TITLE.fullmatch(parsed.path)
        if match:
            return UrlMatch("wikidata-series", "fetch", f"{IMDB_PREFIX}{match.group(1)}")
        return None
    if host in _TMDB_HOSTS:
        match = _TMDB_SERIES.fullmatch(parsed.path)
        if match:
            return UrlMatch("wikidata-series", "fetch", f"{TMDB_PREFIX}{match.group(1)}")
        return None
    if host in _TVDB_HOSTS:
        match = _TVDB_SERIES.fullmatch(parsed.path)
        if match:
            return UrlMatch("wikidata-series", "fetch", f"{TVDB_PREFIX}{match.group(1)}")
        return None
    if host in _TVMAZE_HOSTS:
        match = _TVMAZE_SHOW.fullmatch(parsed.path)
        if match:
            # A TVmaze id resolves through the TVmaze adapter, registered in Sprint 050.
            return UrlMatch("tvmaze", "fetch", match.group(1))
        return None
    return None


DOMAIN = Domain(
    item_type="series",
    label="Series",
    identity=SERIES_IDENTITY,
    fields=SERIES_FIELDS,
    statuses=SERIES_STATUSES,
    default_status="plan_to_watch",
    entry_fields=PASSAGE_FIELDS,
    formats=SERIES_FORMATS,
    entry_panel_label="Your watch data",
    # `Started` and `Finished` read correctly for a series; `Rereads` does not.
    entry_field_labels={"reread_count": "Rewatches"},
    enrichment=SERIES_ENRICHMENT,
    # Every row of a Trakt export carries a watched-episode count, and Wikidata
    # carries the total as `P1113` on 13/13 measured entities — the case DEC-077's
    # shape (a) was designed for. The total is display only and never a bound
    # (DEC-092): an airing series' cached total is stale by definition.
    progress=ProgressSpec("Episodes watched", "episode", total_field="episodes"),
    recognize=lambda value: recognize_series_url(value),
    chooses_covers=False,
)
