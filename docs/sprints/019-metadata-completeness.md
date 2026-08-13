# Sprint 019 — Metadata completeness: viability, then build

**Status:** ready
**Depends on:** 018
**Roadmap revision:** 7

## Objective

A measured verdict on whether cross-provider field completion and edition choice are affordable,
and then whatever that verdict — plus an explicit owner go-ahead — justifies building.

**This sprint is gated.** DEC-035 approves an *assessment*, not an implementation. An agent that
arrives here and starts building cross-provider merging because the feature is "approved" has
skipped the entire point. Phase A concluding that the feature is not worth its cost is a
legitimate, complete outcome.

## Required context

1. `AGENTS.md`
2. `docs/sprints/ROADMAP.md`, the Sprint 019 section and OQ-001 — the gate and the owner's framing
   are stated there and this file does not replace them
3. `docs/specs/product-spec.md` section 4.3 (per-field completion) and section 5 (enrichment)
4. `docs/specs/technical-spec.md` section 6 (providers), section 7 (jobs), section 1 (budgets)
5. `docs/decisions.md` DEC-008 (enrichment fills empty fields only), DEC-025 (verification requires
   using the application; provider behaviour is proven against recorded responses), DEC-035 (the
   gate itself), DEC-036 (stored normalized projection), DEC-041 (a dev-server-only suite is not
   evidence about the shipped artifact)
6. Sprint 018 Outcome and `docs/agent/HANDOFF.md`
7. `backend/src/book_tracker/infrastructure/providers.py`, `application/enrichment.py`,
   `infrastructure/covers.py`, `infrastructure/jobs.py`, and
   `backend/tests/fixtures/providers/` with its README

## Current implementation baseline

Re-derive at activation. As of Sprint 018's close: enrichment tries Open Library and consults
Google Books only when Open Library fails or returns nothing usable, so a record that comes back
usable but incomplete is accepted as-is. One cover is stored per item at `data/covers/<item_id>.jpg`
and there is no notion of candidates. `RateLimiter` enforces a minimum interval per provider and
the 429/backoff path is tested at the HTTP boundary. `scripts/benchmark_library.py` measures list
latency at 10,000 entries, idle and with the job queue draining, and is the natural place to add
provider-request counting rather than starting a harness from nothing.

## Phase A — viability and impact assessment

No product change ships in this phase. The deliverable is a written verdict in `docs/decisions.md`
with measurements behind every claim, answering:

- What each provider's published and observed rate limits actually are, and what a 500-book and a
  5,000-book import would cost against them under per-field completion.
- Measured wall-clock impact on a realistic import, against current fallback-only behaviour as the
  baseline.
- Whether a fetched candidate can be **verified to be the same edition** before its fields are
  merged. The known sharp edge: `GoogleBooksProvider.fetch_by_isbn` takes the first hit of an
  `isbn:` search, which is not guaranteed to carry the requested ISBN13, so merging its publisher
  or page count risks attaching one edition's data to another.
- What storing multiple cover candidates costs on disk, and whether they are fetched eagerly or on
  demand when a chooser is opened.
- How failure semantics change shape: one provider succeeding while another errors is a successful
  enrichment, not a failed job.
- Whether DEC-008's fill-empty-only invariant survives unchanged. It should, because merging
  happens before the write, but that must be demonstrated rather than assumed.

Phase A may conclude a narrow slice — cover choice alone, on demand, with no change to automatic
enrichment — carries most of the value at a fraction of the risk. Report that plainly.

## Phase B — build what Phase A justified

Scope is set by Phase A's verdict and an explicit owner go-ahead, not by this document. Whatever is
built inherits the existing invariants without exception: imported user data is never overwritten,
network providers are never consulted while rendering cached library pages, and enrichment still
only fills empty fields.

## Acceptance criteria

1. Phase A's verdict is recorded in `docs/decisions.md` with the measurements that support it,
   **including the ones that argue against building**.
2. Edition verification is answered concretely: either a fetched candidate can be confirmed to be
   the requested edition, or the assessment says it cannot and what that rules out.
3. If Phase B proceeds: no regression in import throughput beyond the budget Phase A set, no
   provider blocking or rate-limit errors under a full-library run, and the fill-empty-only
   invariant proven intact.
4. If a cover chooser ships: reachable from the detail page, defaults to the current cover, never
   blocks the page it lives on, and passes the axe gate like every other surface.
5. The two long-standing observations folded into this sprint are addressed or explicitly deferred
   with a reason: a provider "image not available" placeholder stored as a real cover, and edition
   choice preferring a recent reprint over the original.

## Required tests (TDD)

- Provider behaviour against the recorded fixtures in `backend/tests/fixtures/providers/`, never
  against a mock of the method under test (DEC-025). **Never silently re-record a fixture** — it is
  a pinned observation of an external contract.
- Edition verification: a candidate whose returned identifiers do not include the requested ISBN13
  is rejected before any field is merged.
- DEC-008 intact: a merged record still never overwrites a field the user or an import supplied.
- If a chooser ships: unit coverage for candidate selection, an e2e path through the detail page,
  and an axe check on the open chooser.

## Verification

```bash
python scripts/validate_project.py
make format
make check
make test
cd frontend && npm run test:e2e
cd .. && make build
make smoke-container
git diff --check
```

Plus, recorded in the Outcome: the Phase A measurements in full, and a walkthrough against the
container (not `make dev`) if anything user-visible shipped.

## Explicit non-scope

- Authentication, public exposure, multi-user support.
- Rewriting the enrichment job runner. Extend it.
- Re-recording provider fixtures to make a test pass.

## Commit checkpoints

1. `feat: count provider requests per enrichment job in the benchmark`
2. `docs: record the Phase A metadata completeness verdict`
3. Phase B checkpoints, named once the verdict and the owner's go-ahead exist
4. final `docs(sprint-019): close sprint and hand off`

## Risks and decisions to surface

- The gate itself: do not start Phase B without an explicit owner go-ahead recorded in
  `docs/decisions.md`.
- Free-tier limits are the owner's exposure, not the agent's. Doubling traffic per book must not
  get the application rate-limited or blocked.
- This is the final planned sprint. On close, follow `WORKFLOW.md`'s final-sprint rule: set the
  project complete with null active fields, and write a release-state handoff. Do not tag, publish,
  deploy or push unless the owner asks.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
