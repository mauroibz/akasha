# Sprint 134 — TMDB, and More like this

**Sprint:** 134
**Status:** planned
**Roadmap revision:** 54
**Depends on:** 133
**Owner:** Mauro

## Objective

On a movie or series, *More like this* asks TMDB once, shows the picks in a side sheet as they
arrive, enriches the top three through the domain's own providers, and lets the person answer
each. Home shows the latest suggestions.

## Required context

- DEC-183 point 6 (amends DEC-103 for recommendations), DEC-103, DEC-099; Sprint 133's Outcome.
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
6. Recorded real TMDB responses under `backend/tests/fixtures/providers/` (token stripped).

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
