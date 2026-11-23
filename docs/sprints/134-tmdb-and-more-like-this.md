# Sprint 134 — TMDB, and More like this

**Sprint:** 134
**Status:** in_progress
**Roadmap revision:** 54
**Depends on:** 133
**Owner:** Mauro

## Objective

On a movie or series, *More like this* asks TMDB once, shows the picks in a side sheet as they
arrive, enriches the top three through the domain's own providers, and lets the person answer
each. Home shows the latest suggestions.

## Required context

- DEC-183 point 6 (amends DEC-103 for recommendations), DEC-103, DEC-099; Sprint 133's Outcome
  and DEC-188 (the pipeline's choices); technical spec 6.7; `domain/recommendations.py`,
  `app/recommendations.py` (`SOURCE_FACTORIES`), `application/recommendations.py`,
  `api/suggestions.py`; `backend/tests/test_recommendations.py` (how a round is driven in tests).
- `domains/movie/` and `domains/series/` (`providers.py`, `posters.py`: the existing TMDB
  client and `TMDB_READ_TOKEN`), `config.py`, the mockup's *More like this* section.
- TMDB API: `/movie/{id}/recommendations`, `/tv/{id}/recommendations`, `/find/{imdb_id}`.

## Deliverables

1. `tmdb` recommendation source (shared adapter, provider-agnostic shape): resolves the seed's
   TMDB id from its external ids, or through `/find` from its IMDb id (one request, cached on the
   item); one recommendations request; up to twelve candidates with title, year, TMDB and (when
   given) IMDb ids, and a reason ("TMDB: often watched together").
2. Movies and series declare `RecommendationSpec(sources=("tmdb",), resolve=…)`, resolving a
   candidate through their existing providers by IMDb id or title and year.
3. TMDB-sourced suggestion rows older than six months are deleted by the existing maintenance
   pass; the attribution line "This product uses the TMDB API but is not endorsed or certified by
   TMDB." appears wherever they are shown.
4. *More like this* button on the detail page and on On now and Lately cards for domains that
   declare a source; a side sheet (TMDB / later Model segment) listing candidates with their
   enrichment state, and *Want*, *Not for me*, *Seen it*; opening a pending one enriches it.
   Pressing it again shows the last round with *Refresh*.
5. Home's *More like this* module: the newest unanswered suggestions across domains, from storage.
   A new module key (DEC-185 consequences): `DEFAULT_LAYOUT` in `application/home_layout.py`,
   `MODULES`/`moduleLabels`/`fallbackLayout` in `features/home/layout.ts`, a `hasContent` case
   in `HomePage`, a `/api/home` section skipped when hidden, and the e2e console's default
   layout stub. Lately's rows (`features/home/Lately.tsx`) are not cards: the button goes on its
   entry rows only if it fits the one-line row.
6. Recorded real TMDB responses under `backend/tests/fixtures/providers/` (token stripped).

Notes from Sprint 133 (DEC-188):

- The source is a factory in `SOURCE_FACTORIES` returning the adapter, or
  `NotConfigured("tmdb", <how to set TMDB_READ_TOKEN>)`; a round asked of it is then stored
  `not_configured` with that hint, which is what the button explains. Its rounds are budgeted by
  `AKASHA_RECOMMEND_DAILY_LIMITS` (`{"tmdb": …}`).
- `resolve_by_identity_or_search(("imdb",))` already resolves a film by IMDb id through Cinemeta
  and Wikidata, else by title; series can use the same with their own providers.
- Nothing publishes yet which domains declare a source and whether it is configured; the
  button's availability needs that from the server (a field on an existing domain or settings
  read, or a small endpoint), not a client list.
- The sheet's live updates: the `recommend` job's progress on `/api/events` carries `round_id`
  and `status`; re-read `GET /api/suggestion-rounds/{id}`.
- Art: `GET /api/items/{id}/cover` answers only for an item the person has an entry on when
  `AKASHA_AUTH=on`, so a suggestion's cached cover is not reachable before *Want*. Use the
  source's poster in `display` (an allowlisted host) or let the cover route admit items the
  person's suggestions point at; decide and record it.
- Pruning TMDB rows older than six months is new: there is no scheduled maintenance pass for
  suggestions yet.

## Acceptance criteria

1. Against recorded responses, a movie seed and a series seed each produce a stored round with
   three enriched candidates (tested).
2. Without `TMDB_READ_TOKEN` the button explains that the source is not configured; nothing
   fails (tested).
3. The sheet updates live from the event stream; answers persist across reloads (tested in e2e
   with the fake source).
4. Attribution shows on the sheet and the Home module.
5. Axe passes with the sheet open; fits at 390 px.

## Required tests (TDD)

Adapter against recordings (including a seed with only an IMDb id, and a 404), resolve per
domain, pruning, the button's availability per domain from the registry, the sheet, the module,
an e2e pass.

## Verification

Per DEC-167, plus one live round with the owner's token from the local `.env` and a walkthrough
of the sheet and Home module recorded in the worklog.

## Explicit non-scope

Books, anime and albums (no TMDB coverage; the model source in 135 covers them).

## Outcome

_Not started._
