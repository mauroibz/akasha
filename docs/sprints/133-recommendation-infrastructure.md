# Sprint 133 — Recommendation infrastructure

**Sprint:** 133
**Status:** planned
**Roadmap revision:** 54
**Depends on:** 132
**Owner:** Mauro

## Objective

A per-domain, provider-agnostic recommendation pipeline (seed → select → store → enrich →
answer) exists end to end, proven with a recorded fake source, so a real source is only an
adapter.

## Required context

- DEC-183 points 4–7; the proposal §3.
- `domain/spec.py` (how a domain declares enrichment), `domain/registry.py`,
  `domain/providers.py`, `infrastructure/jobs.py` (job kinds, handlers, leases),
  `infrastructure/quota.py` (`ProviderQuota`), `application/enrichment.py` (the resolve path and
  budgets), `application/add.py` (adding a candidate as an entry), `api/events.py` (the event
  stream), `docs/guides/adding-a-domain.md`.

## Deliverables

1. `domain/recommendations.py`: `Seed` (an entry, or a profile), `TasteProfile` (top scored,
   recent finishes, dismissed), `Candidate(title, year, creator, external_ids, reason,
   source_score, display)`, the `RecommendationSource` protocol, and `RecommendationSpec(sources,
   resolve, enrich_top=3)` as an optional field on the domain spec.
2. A source registry keyed by name, filled from configuration; a source whose configuration is
   missing reports `not_configured` instead of failing.
3. Migration `0037_suggestions`: `suggestion_rounds(id, user_id, item_type, seed_entry_id NULL,
   source, status, error, created_at, finished_at)` and `suggestions(id, round_id, user_id,
   item_type, title, year, creator, external_ids_json, reason, source_score, display_json,
   enrichment: pending|enriched|unresolved, item_id NULL, answer: NULL|want|not_for_me|seen,
   answered_at, created_at)`, with indexes on `(user_id, item_type, created_at)`; candidates
   already in the library or answered *not for me* are dropped at store time.
4. Job kind `recommend`: runs the source's `select` once, stores the round, then enriches the
   top `enrich_top` through the domain's `resolve` under `ProviderQuota`; budgets per source
   (`recommend_daily_limits` in config). A later `enrich_suggestion` job enriches one on demand.
5. Endpoints: `POST /api/entries/{id}/more-like-this` (202, round id; reuses a round under a
   day old unless `refresh=true`), `GET /api/suggestions?seed_entry_id=&item_type=&limit=`,
   `GET /api/suggestion-rounds/{id}`, `POST /api/suggestions/{id}/enrich`,
   `PATCH /api/suggestions/{id}` `{answer}`; *want* adds the resolved item as a planned entry.
   Round progress is published on the event stream.
6. A `fake` source used only by tests, backed by a recorded JSON file, and a technical spec
   section describing the contract; `docs/guides/adding-a-domain.md` gains *Recommendation
   sources*.

## Acceptance criteria

1. With the fake source, a round selects, stores, enriches exactly the top three, and leaves the
   rest `pending` (tested).
2. A source over its daily budget stops and records why; no provider call exceeds the quota
   (tested).
3. *Want* creates a planned entry; *not for me* hides the candidate from later rounds (tested).
4. Rounds and suggestions are per user (tested with auth on).
5. No `item_type ==` branch above the registry; rendering any page makes no provider call.

## Required tests (TDD)

Domain types, store-time filtering, job handler with a recorded source, quota exhaustion,
answers, API and per-user isolation, migration up/down.

## Verification

Per DEC-167. No screen changes (the UI is Sprint 134), so no walkthrough beyond an API pass with
the fake source.

## Explicit non-scope

TMDB, the sheet, the Home module (134); model (135); embeddings (136).

## Outcome

_Not started._
