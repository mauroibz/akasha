# Sprint 135 — The model source

**Sprint:** 135
**Status:** ready
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

_Not started._
