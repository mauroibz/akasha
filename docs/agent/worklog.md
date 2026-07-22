# Work log

Append-only, one entry per working session, newest at the bottom. This is the
agent's cross-session memory *within* a sprint: what was actually done, what was
verified and how, what diverged, and the exact next step. `HANDOFF.md` is the
current-state pointer; this file is the running history that keeps a later
session from re-deriving or silently redoing what an earlier one already learned.

Rules:

- Never edit or delete a prior entry. Correct the record by appending a new one.
- Terse and factual; this is for agents, not a narrative.
- Durable architecture decisions still go in `docs/decisions.md`; per-sprint
  delivered behavior still goes in the sprint `Outcome`. This file is the
  session-level layer between them.

Entry format:

```markdown
## YYYY-MM-DD — Sprint NNN (in progress | complete | blocked | interrupted)
- Done: steps completed; migrations/commits involved.
- Verified: each acceptance behavior touched and exactly how (command, browser
  session, migrated DB) — not "looks good".
- Deviations: anything that diverged from the docs and why; where it was recorded.
- Blocked/open: none, or what and why.
- Next: the very next concrete step for whoever picks this up.
```

---

## 2026-07-21 — Planning baseline (complete)
- Done: established canonical specs, roadmap revision 2, execution protocol, and
  machine-readable state. No application code yet.
- Verified: `python scripts/validate_project.py` passes.
- Deviations: none.
- Blocked/open: four product questions carry authorized defaults (DEC-006); the
  owner may override before the affected sprint activates.
- Next: claim Sprint 001 per `AGENTS.md` and build the reproducible foundation.

## 2026-07-21 — Sprint 001 (complete)
- Done: delivered backend migration/health/SQLite foundation (`29e2ad1`), frontend health view and unified contract/tooling (`e355640`), and CI/production container proof (`4ceebba`). Repaired the validator's generated-directory traversal and recorded the lock strategy in DEC-014.
- Verified: 7 backend tests and 2 frontend component tests pass; required bootstrap/format/check/test/build commands pass; Compose config renders; scripted Docker recreation proves ready health, SPA routing, persisted probe, non-root UID, and no Node; `git diff --check` passes.
- Deviations: no product or sprint scope deviation. The container uses a non-editable uv environment created at `/opt/venv` because copied editable/relocated environments failed the smoke proof.
- Blocked/open: none.
- Next: claim Sprint 002 and implement the complete domain migration and repositories in acceptance order.

## 2026-07-22 — Sprint 002 (complete)
- Done: delivered the complete domain migration (`d45f365`), normalization and matching contracts
  (`19ea28d`), and transactional mapped repositories (`ca21ca6`). Expanded Sprint 003 from the
  roadmap using the implemented paths.
- Verified: 25 backend and 2 frontend tests pass; real file-backed migration empty/previous-head
  round trips and a focused two-thread ISBN-equivalence race pass. `make format`, `make check`,
  `make test`, `make build`, project validation, and `git diff --check` pass.
- Deviations: none.
- Blocked/open: none.
- Next: claim Sprint 003 and add application/API contracts in acceptance order, beginning with
  failing entry and shelf mutation tests.

## 2026-07-22 — Sprint 003 (complete)
- Done: delivered typed library CRUD, normalized filter/facet/list queries, all-sort opaque keyset
  pagination, atomic bulk/suggested mutations, list indexes, and generated OpenAPI (`7c8435b`);
  fixed deterministic generated-contract formatting (`26c5c4f`); expanded Sprint 004.
- Verified: 49 backend and 2 frontend tests pass; focused ASGI tests cover CRUD/domain errors,
  static route precedence, bulk rollback, all six asc/desc sorts, duplicate/null/deleted cursor
  cases, normalized search, and query-plan index use. Required format/check/test/build/project
  validation and `git diff --check` pass.
- Deviations: deterministic connection-level SQLite normalization replaces the vague stored
  normalization/collation wording; technical spec section 7.2 and DEC-015 record the contract.
- Blocked/open: none.
- Next: claim Sprint 004 and begin with failing typed library loading/empty/error/populated component
  tests before adding the application shell and virtualization.

## 2026-07-22 — Sprint 004 (complete)
- Done: delivered typed library states (`2c38bec`), cursor-aware server controls and fixed-size
  virtual grid/table views (`01d0cdf`), optimistic edits/keyboard behavior (`fc44dff`), and isolated
  browser artifacts (`01e031e`), and guarded focus restoration (`22eb2ec`); expanded Sprint 005
  against current paths.
- Verified: 49 backend and 9 frontend tests pass; two Chromium checks prove keyboard guards,
  reduced motion, and fewer than 20 mounted entries in a deterministic 5,000-entry library.
  Required format/check/test/build/project-validation and `git diff --check` commands pass.
- Deviations: no product/scope deviation. Grid cards use fixed-height virtual rows rather than
  masonry; the `/add` route is a non-functional scope-boundary notice until Sprint 006.
- Blocked/open: none. The sandboxed isolated Python build could not resolve hatchling; the required
  approved `make build` rerun with network access passed.
- Next: claim Sprint 005 and begin with failing provider model/merge plus independent partial-failure
  search tests before implementing HTTP adapters.
