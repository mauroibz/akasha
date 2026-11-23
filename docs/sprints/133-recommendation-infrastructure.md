# Sprint 133 — Recommendation infrastructure

**Sprint:** 133
**Status:** completed
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
- Sprint 132 (DEC-186): `application/ranking.py` and `Domain.ranking: RankingSpec` already
  exist; `RecommendationSpec` sits beside it, and a candidate's `reason` can follow the pile's
  `{signal, text}` shape. Nothing stores a dismissal of a *pile* entry yet (DEC-186 point 5);
  `TasteProfile.dismissed` starts from suggestions answered *not for me*.

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

Completed 2026-11-23 (DEC-188).

Delivered:

- `domain/recommendations.py`: `Seed` (an entry, or no entry for the taste profile),
  `TasteEntry`, `TasteProfile` (top scored, recent finishes, dismissed, and the pile as
  `waiting`), `Candidate(title, year, creator, external_ids, reason, source_score, display)`,
  the async `RecommendationSource` protocol, `RecommendationSpec(sources, resolve,
  enrich_top=3)` as `Domain.recommendation` (default `None`), `SourceRegistry`,
  `NotConfigured`, `SourceError`, `ProviderBudgetSpent`, `same_work` and the shared
  `resolve_by_identity_or_search(kinds)`.
- `app/recommendations.py`: the registry built at start from `SOURCE_FACTORIES` (empty until
  134); a factory returns the source or `NotConfigured(name, hint)`.
- Migration `0037_suggestions`: `suggestion_rounds` and `suggestions` as planned, with
  `(user_id, item_type, created_at)`, round and item indexes; seed entry and item links
  `SET NULL` on delete, user and round links cascade.
- `application/recommendations.py`: the `recommend` job (round budget per source, one
  `select`, store-time filtering, the top `enrich_top` resolved through the domain's resolve
  with every provider request held to its budget) and `enrich_suggestion`; a resolved
  suggestion is a cached shared item with its cover; *Want* makes a planned entry on it.
- `api/suggestions.py`: `POST /api/entries/{id}/more-like-this` (202; a round under a day old
  again unless `refresh=true`), `GET /api/suggestions`, `GET /api/suggestion-rounds/{id}`,
  `POST /api/suggestions/{id}/enrich`, `PATCH /api/suggestions/{id}`. Progress is the job's
  progress on `/api/events`.
- `AKASHA_RECOMMEND_DAILY_LIMITS` (config, `.env.example`, `compose.yaml`).
- The test-only `fake` source (`backend/tests/recommendation_fake.py`) over
  `tests/fixtures/recommendations/fake_source.json`; technical spec 6.7 and the guide's
  *Recommendation sources*; a conformance check for the new field.

Acceptance criteria:

1. A round selects, stores, enriches exactly the top three and leaves the rest `pending`:
   `test_a_round_selects_stores_and_enriches_exactly_the_top_three` (fake source, the domain's
   resolve against recorded Cinemeta; the pending ones cost no request).
2. Over budget: `test_a_source_over_its_daily_budget_stops_and_records_why` (round
   `over_budget` with its reason, the source asked once) and
   `test_no_provider_request_exceeds_its_quota` (a Cinemeta limit of 1: exactly one request,
   the rest `pending`, the round's `error` says why).
3. *Want* makes a `watchlist` entry and *Not for me* keeps Stalker out of the next round and
   reaches the source's profile: `test_want_adds_a_planned_entry`,
   `test_not_for_me_hides_the_candidate_from_later_rounds`.
4. Per user with `auth=on`: `test_rounds_and_suggestions_are_each_persons_own` (another
   person's seed, round, answer and enrich are 404; lists are separate; anonymous is 401); the
   isolation suite's route policy covers the five routes.
5. No branch: `test_the_shared_recommendation_layers_never_name_a_domain` scans the four new
   modules; reading costs nothing: `test_reading_suggestions_calls_no_provider_and_no_source`
   (a provider that raises on any call, rounds, lists, a repeated *More like this* and
   `/api/home` all 200, no job queued, the source not asked).

Verification (DEC-167): `tests/test_recommendations.py` 28 passed (domain types, registry,
store-time filtering, the job with the recorded source, both budgets, failing and unconfigured
sources, answers, covers, per-user isolation, no provider on read, migration 0037 up and down
on a real temporary database with foreign keys on). Regression over the touched modules
(conformance, repositories, cached add, refile, library API, app shape, migrations, security
migrations, settings, home, layout, isolation, events, jobs, enrichment, enrichment pipeline,
domain, prune, quota, ranking, ownership, robustness): 634 passed. `make check` passed. No
screen changed; the walkthrough is an API pass: a real uvicorn server with the live job
runner, the fake source and recorded Cinemeta (scratchpad `api_pass_133.py`, recorded in the
worklog).

Deviations:

- `select` is async; `resolve` receives the domain's providers already budgeted (DEC-188 points
  1-2). No production domain declares a source (point 3).
- Added after the API pass: a work an earlier round resolved is stored resolved without a
  request, and the list shows each work once (`afc9f42`, point 7).
- Prerequisite repair: the documented-route check had missed Home's and the pile's routes since
  Sprint 130 (`9734b03`).

Commits: `9734b03`, `ffb263d`, `273b88c`, `37c48b2`, `afc9f42`, `0fe6311`, and the closing
commit.
