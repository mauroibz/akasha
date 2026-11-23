# Sprint 134 — TMDB, and More like this

**Sprint:** 134
**Status:** completed
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

Delivered 2026-11-23 on `home-and-recommendations` (DEC-189).

**Commits:** `10e9d51` [ADD] TMDB suggests films and series for More like this (adapter,
domain declarations, recordings, availability on `/api/item-types`, cover route, pruning,
Home's `suggested` section); `688889d` [ADD] More like this: the sheet, its button, and Home's
module; `ac4b5a1` [MOD] Tighten the More like this sheet and module after the walkthrough;
the closing documentation commit.

**Delivered**

1. `tmdb` source, `infrastructure/tmdb_recommendations.py`, registered by `tmdb_source` in
   `SOURCE_FACTORIES` (`NotConfigured` with the `TMDB_READ_TOKEN` hint without a token). The
   seed's TMDB id from its identifiers, else one `/find/{imdb_id}`, kept on the item through a
   new `Selection(candidates, seed_ids)` answer; one `/{media}/{id}/recommendations`; up to
   twelve candidates. **Deviation:** TMDB's recommendations carry no IMDb id on any row, so a
   candidate names TMDB's id alone; the media comes from the domain's new
   `RecommendationSpec.source_options`.
2. Movies and series declare `RecommendationSpec(sources=("tmdb",),
   resolve=resolve_by_identity_or_search(("imdb", "tmdb")), source_options=…)`. The Wikidata
   adapters answer `fetch_by_identifier("tmdb", …)`; providers declare `identifier_kinds` so
   Cinemeta and TVmaze are not asked (or charged) for a TMDB id.
3. Rounds of a source with `retention` (TMDB: 182 days) are deleted by
   `prune_expired_suggestions`, run by the job runner's new hourly `housekeeping` hook on an idle
   pass, whether or not the token is still set. **Deviation:** there was no maintenance pass for
   this; the hook is new. The attribution line is the source's `attribution`, published on
   `/api/item-types` and shown under the sheet and Home's module.
4. *More like this* on the detail page and each On now card, drawn only where
   `/api/item-types` gives the library a `recommendation`; the side sheet (bottom sheet on a
   phone) with the source segment, *Refresh*, each pick's state, *Want* / *Not for me* /
   *Seen it* and *Undo*, *Look up* on a pending pick. Updates come from the event stream only.
   Lately's rows are one line, so the button is not on them (the sprint file allowed this).
   Art: the cover route admits an item the requester's suggestions point at; suggestions carry
   `cover_url` and `seed`.
5. Home's `suggested` module (default M; 2/4/8 picks by size), `enriched` rows only, *Want* and
   *Not for me* in place, a tap opens the round. Added to `DEFAULT_LAYOUT`, `MODULES`,
   `moduleLabels`, `fallbackLayout`, `hasContent`, `/api/home` (skipped when hidden) and the e2e
   console's layout stub.
6. Recordings: `tmdb_find_tt0047478_seven_samurai.json`, `tmdb_find_tt9999999999_no_match.json`,
   `tmdb_movie_346_recommendations_seven_samurai.json`,
   `tmdb_tv_1396_recommendations_breaking_bad.json`, `tmdb_movie_999999999_recommendations_404.json`,
   plus eighteen Wikidata captures resolving the top three of each round (README rows).
   No token in any file (a test checks).

Also: `RecommendationSpec.want_status` (default the first planned status) with the conformance
check accepting it, so albums can declare `wishlist` in 135.

**Acceptance criteria**

1. Movie and series seeds each store a round with three enriched candidates against
   recordings: `test_a_film_round_stores_twelve_and_enriches_three` (seed with only an IMDb id:
   `/find` then recommendations, TMDB id kept) and `test_a_series_round_stores_and_enriches_three`.
2. Without the token: `/api/item-types` says `configured: false` with the hint, a POST stores
   `not_configured` and queues nothing (`test_without_a_token_the_round_is_not_configured_and_says_how`);
   the sheet explains and asks nothing (Vitest, and the e2e spec).
3. The sheet updates from the event stream and answers persist across a reload:
   `e2e/more-like-this.spec.ts` against a stateful stub of the fake source's shape, whose
   `/api/events` reports the round and a looked-up pick.
4. Attribution on the sheet and Home's module: Vitest and the e2e spec.
5. Axe (wcag2a/aa, 21a/aa, no serious or critical) with the sheet open at 390 and 1440 px, no
   horizontal scroll, the sheet inside the viewport: e2e.

**Verification (DEC-167)**

- Backend: `test_tmdb_recommendations.py` 28; over the touched modules a 1,153-test run
  (`test_cover_candidates` called `/api/item-types` without the lifespan and failed; fixed);
  final focused run 391 passed (tmdb, recommendations, home API, home layout, conformance,
  IMDb import, cover candidates).
- `npx vitest related` over the changed files: 367 (two `EditHome` tests counted nine modules;
  updated for the tenth); `src/features/suggest` + `src/features/home` 55.
- Playwright: `more-like-this.spec.ts` + `home.spec.ts` 21 passed; add-detail, lent, rescore,
  accessibility, progress-marks, diary-goal 67 passed, 1 failed:
  `accessibility.spec.ts` *the add dialog over the library* (a contrast probe), which failed 2
  of 3 on the pre-sprint commit `9dfa89a` in a separate worktree too.
- `make check` green.
- Live: three rounds with the owner's token (Seven Samurai via Wikidata, Suspiria via Cinemeta
  and `/find`, Breaking Bad), each `done` in 5.5 s with 12 stored and 3 enriched; The Bear
  (Cinemeta only) through `/find` on `tv`. Walkthrough in the worklog.
