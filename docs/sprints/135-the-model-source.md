# Sprint 135 — The model source

**Sprint:** 135
**Status:** completed
**Roadmap revision:** 54
**Depends on:** 134
**Owner:** Mauro

## Objective

A hosted language model, chosen by configuration and an API key, can be a recommendation source
for every domain, with its candidates shown only after the domain resolves them. Three provider
kinds are supported: the Claude API, Gemini, and any OpenAI-compatible endpoint (DEC-187).

## Required context

- DEC-183 point 7; Sprints 133–134 Outcomes; `domain/recommendations.py`; `config.py`;
  `.env.example`; the runbook's configuration section.

## Deliverables

1. Configuration: `AKASHA_RECS_MODEL_PROVIDER` (`anthropic` | `gemini` | `openai`),
   `AKASHA_RECS_MODEL` (model id), `AKASHA_RECS_MODEL_KEY` (falling back to the provider's
   conventional variable: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`), optional
   `AKASHA_RECS_MODEL_URL` for OpenAI-compatible endpoints, and a daily call budget. No key means
   `not_configured`. Defaults per provider are a current, inexpensive model; for Claude read the
   `claude-api` skill for model ids and request shape rather than relying on memory.
2. A `ModelClient` port with three adapters (Claude Messages API, Gemini `generateContent`,
   OpenAI-compatible chat completions), each a thin HTTP adapter over the app's shared client:
   same prompt in, text out, errors mapped to the provider-error types the app already has.
   Keys never appear in logs or responses.
3. `model` source: builds a compact prompt from the seed (or profile: top scores, recent
   finishes, dismissed, the pile's titles so it does not repeat them) for one domain, asks for
   strict JSON (`title`, `creator`, `year`, `reason`) with up to eight items, validates it, and
   returns candidates. A malformed reply fails the round with a recorded reason.
4. Every domain declares `"model"` after its existing sources; a model candidate that the
   domain's resolve cannot find is stored `unresolved` and never shown.
5. The sheet's *Model* segment; Settings shows whether the source is configured, which provider
   and model, and what it sends (titles, creators, years and scores, nothing else).
6. Recordings: no model runs locally (owner, 2026-11-23). Claude is the reference provider.
   `scripts/record_model_fixtures.py` records real replies for each provider whose key is present;
   if no key is available in the environment, fixtures are written in each API's documented
   response shape, marked `"recorded": false` in a sidecar, and the HANDOFF and Outcome say
   that a live run with the owner's key is pending (owner-directed exception to the recorded-real
   rule, DEC-187).

Notes from Sprint 133 (DEC-188):

- `TasteProfile` already carries `top_scored`, `recent_finishes`, `dismissed` and `waiting` (the
  pile) as titles, creators, years and scores; build the prompt from it and the `Seed`. A
  malformed reply raises `SourceError`, which fails the round with its message.
- The daily call budget is the existing round budget: `AKASHA_RECOMMEND_DAILY_LIMITS`
  (`{"model": …}`), counted under `recommend:model`.
- A model candidate the domain cannot find is stored `unresolved`, and `GET /api/suggestions`
  already leaves those out; the round endpoint lists every state, so the sheet must hide them.
- Albums have no `planned` status. Sprint 134 added `RecommendationSpec.want_status` (DEC-189
  point 8) and the conformance check accepts it in place of a planned status: albums declare
  `want_status="wishlist"` (the coordinator's decision, recorded in DEC-189).
Notes from Sprint 134 (DEC-189):

- `GET /api/item-types` publishes each library's `recommendation.sources` (`name`, `label`,
  `configured`, `hint`) and `attribution`; the `model` source needs a `label` ("Model" or the
  provider's name) and no attribution unless the provider's terms ask for one. `NotConfigured`
  takes `label`, `retention` and `attribution` too.
- The sheet (`features/suggest/MoreLikeThisSheet.tsx`) draws the declared sources as a segment
  but always asks the first configured one; make the segment a choice that passes `?source=`
  to `POST /api/entries/{id}/more-like-this` and keeps one round per source.
- Domains that add `"model"` after `"tmdb"` keep TMDB first for films and series. Give the
  model source no `retention` unless its terms ask for one.
- A model candidate carries no ids, so resolve goes to the title search; `identifier_kinds`
  keeps the identity step from spending requests.
- Only *More like this* (an entry seed) has an endpoint. The job already runs a seedless
  (profile) round; a route for one is new work if the sheet or Home needs it.

## Acceptance criteria

1. Against a Claude-shaped reply, a book seed yields resolved candidates and drops an invented
   title (tested with a reply that contains one); the same for Gemini and OpenAI shapes.
2. Provider selection by configuration; no key: the segment says how to configure it; nothing
   fails (tested).
3. The prompt contains no data beyond titles, creators, years and scores (tested), and the key
   never reaches a log line (tested).
4. Budget exhaustion stops further calls (tested).

## Verification

Per DEC-167; a live round against Claude if a key is present, otherwise recorded as pending; a
walkthrough of the *Model* segment with a replayed transport.

## Explicit non-scope

Embeddings (136); running a model locally.

## Outcome

Closed 2026-11-23 (DEC-190). **No model key was present in the environment, so no real model
reply was recorded and no live round was run: the live check against Claude is pending, the
owner's** (export `ANTHROPIC_API_KEY`, run `scripts/record_model_fixtures.py` from `backend/`,
then one *Model* round in the app).

Delivered:

- Configuration: `AKASHA_RECS_MODEL_PROVIDER` (`anthropic` default, `gemini`, `openai`),
  `AKASHA_RECS_MODEL` (defaults `claude-haiku-5-5` from the `claude-api` skill,
  `gemini-2.5-flash`, `gpt-5-mini`), `AKASHA_RECS_MODEL_KEY` falling back to
  `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY`, `AKASHA_RECS_MODEL_URL`; passed
  through `compose.yaml` and documented in `.env.example`, README and the runbook. The daily
  budget is the round budget, `{"model": 50}` unless `AKASHA_RECOMMEND_DAILY_LIMITS` names it.
- `infrastructure/model_clients.py`: the `ModelClient` port and three plain-HTTP adapters over
  the shared client (Claude Messages API, Gemini `generateContent`, OpenAI-compatible
  `chat/completions`), errors mapped to `SourceError`, the key a header only.
- `infrastructure/model_recommendations.py`: the `model` source — prompt from the seed and the
  taste profile (titles, creators, years, scores), strict JSON reply of up to eight, a
  malformed reply fails the round. `resolved_only`: every pick is resolved and only found ones
  are shown.
- Every domain declares `"model"` (after `"tmdb"` for films and series) with
  `source_options["model"]`; books and albums resolve by title and creator; albums
  `want_status="wishlist"`.
- The sheet's segment is a choice (`?source=`, one round per source per seed, every round kept
  current from the event stream), a model's found picks only with *Try again* for pending
  ones, its provider and model named; Settings → Suggestions lists each source, on or off,
  provider, model and what is sent. Home opens a pick in its own source's round.
- `scripts/record_model_fixtures.py`; fixtures `model_*` (documented shapes, `"recorded":
  false` in `model_fixtures.json`) and four real Open Library searches.

Acceptance criteria:

1. Claude-, Gemini- and OpenAI-shaped replies for a *Rayuela* seed: three books resolved
   against recorded Open Library searches, the invented one stored `unresolved` and left out of
   `/api/suggestions` (`test_a_book_seed_yields_resolved_picks_and_drops_an_invented_one`,
   parametrized over the three providers; each adapter's request shape in
   `test_each_provider_kind_is_asked_in_its_own_shape`).
2. Provider chosen by configuration (`test_the_provider_is_chosen_by_configuration`, four
   cases; a key for another provider does not configure it); without a key `/api/item-types`
   says `configured: false` with the hint, a round is `not_configured` and no job is queued
   (`test_without_a_key_the_source_says_how_and_nothing_fails`); the sheet explains and asks
   nothing (Vitest and Playwright).
3. The prompt carries titles, creators, years and scores only
   (`test_the_prompt_carries_titles_creators_years_and_scores_only`, and the end-to-end test
   checks the request body for notes, location, dates, ISBN, provider ids and metadata); the
   key reaches no log line, stdout/stderr, round error or `/api/item-types` across a good and
   a refused call (`test_the_key_never_reaches_a_log_line`).
4. A spent budget stops further calls: a second round is `over_budget` and the transport saw
   one request (`test_a_spent_budget_stops_further_calls`); the default of fifty is tested.

Verification (DEC-167): `tests/test_model_recommendations.py` 31; a focused regression over the
touched modules, 593 passed (conformance, domain, app shape, film, series, album, anime,
library API, home, ranking, cached add, TMDB, recommendations, settings, multi-domain
imports); Vitest related 346, then 73 after the last sheet fix; Playwright
`more-like-this.spec.ts` + `home.spec.ts` 24 passed, and the export axe check; `make check`.

Walkthrough: `scripts/walkthrough.py --keep --replay` with a scratchpad replay module that
answers `api.anthropic.com` with Claude-shaped replies (books, films or albums by the prompt)
and passes everything else live, `TMDB_READ_TOKEN` exported, a dummy Claude key that never
leaves the process; vite on 5180. Rayuela, Seven Samurai and Kind of Blue added live. Book
round done in about 10 s: Pedro Páramo, Ficciones, Los detectives salvajes found with covers,
the invented title not shown. Film: TMDB first, Model second; three Kurosawa films found,
the invented one hidden; switching back to TMDB made no request. Album: A Love Supreme, Mingus
Ah Um found (Time Out once left pending by a MusicBrainz 503, offered *Try again*); *Want* on A
Love Supreme made a `wishlist` entry. Settings lists Model (Claude · claude-haiku-5-5, what it
is sent) and TMDB. 390 px: no overflow, sheet 390 wide. The prompts sent carried only the
seed line; the dummy key appears nowhere in the backend log. Console: only the auth-off
`/api/auth/me` 404s.

Observed and fixed: `--replay` broken since Sprint 101 (`880c657`); real films unresolved
(Cinemeta's US-release years, Wikidata's Spanish labels) and a failed provider making a pick
unresolved for good (`1ebae80`); the seed sent with its edition year (Rayuela 2000) and
twice (`1ebae80`); a TMDB round switched away from mid-enrichment frozen (`f3d3229`).

Observed, left: every found row still says "Found in your providers", which is redundant on a
model round; Settings lists Model before TMDB because books come first in the registry; the
film seed's title is Wikidata's Spanish one ("Los siete samuráis") and goes to the model as
such.

Commits: `1f6e015` [ADD] the model source; `c0d8a1c` [MOD] the segment as a choice and
Settings; `880c657` [FIX] the replay launcher; `1ebae80` [FIX] film resolution, pending on a
provider failure, the work's first year; `f3d3229` [FIX] rounds kept current across sources.

Deviations: the sprint planned the sheet's *Model* segment; it is the declared sources as a
radio group, *Model* among them. `resolved_only` and `about` are new source attributes.
`same_work` and `resolve_by_identity_or_search` changed for every source (DEC-190 point 6).
