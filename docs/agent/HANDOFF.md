# Handoff — Sprint 042 planned and not started

Plan revision 21. The anime line (Sprints 038–041) is complete; **Sprint 042 is planned,
`ready`, and deliberately unexecuted.** The owner has a UX fix to do first and asked for
the plan committed ahead of it.

Work remains on the branch **`sprint-038-anime`**, unpushed and **unmerged**. Sprint 042
depends on the anime line's code, which is not on `main`, so it continues there unless the
owner merges first (DEC-053).

## What Sprint 042 is

Close the frictions the third domain actually hit, so the fourth does not hit them again.
**Nothing user-visible changes and there is no walkthrough gate** — if a deliverable turns
out to touch a screen, that is a scope error, not a reason to add one.

The retrospective behind it is **DEC-094**, and its finding is not the expected one: **the
abstraction held; the friction was mechanical.** Ranked by time the line actually lost:

1. Walkthrough selector churn — every walkthrough needed 2–4 corrections, and the
   assumption was wrong every time rather than the product.
2. The `entries` rebuild recipe — three failed attempts in Sprint 040.
3. `validate_entry_fields` is a denylist — the root cause of `progress` reaching storage
   unvalidated for a whole sprint.
4. Conformance has no wiring tier.
5. Three entry-field render sites; 6. three hand-enumerated `EntryRow` constructions.

Six deliverables follow from those, and the sprint file holds them in full. The two that
carry real work are the allowlisting validator and the conformance wiring tier; the other
four are small, and the sprint file names them as the split point if the first two run long.

## Before starting it

Read `docs/sprints/042-sharpening-the-domain-contract.md` and **DEC-094**, then the
baseline it records — every fact in that section was verified on 2026-08-27 at `0f1b86e`
rather than recalled, but re-check anything the UX fix may have moved. In particular:

- `validate_entry_fields` is called from `application/library.py:163`,
  `application/add.py:187` and `application/imports.py:157`, and its return value is
  discarded at two of the three.
- Conformance has exactly two tiers, `REGISTRY_CHECKS` and `CORE_CHECKS`, registered by
  the decorators at `tests/test_domain_conformance.py:161-170`.
- The wiring check to move lives at `tests/test_enrichment_pipeline.py:550`.
- `EntryRow` is constructed at `infrastructure/repositories.py:256,382,774`.
- `alembic/env.py` still says nothing about the `PRAGMA foreign_keys` silence that three
  migrations depend on.

**Deliverable 1 touches every entry write path in the application.** The existing tests are
the guard and must not be relaxed to fit the new signature; if one has to change, say
exactly why in the Outcome.

## Deliberately not in it

The shared frontend hook for the three entry-field render sites (a refactor with its own
risk — Sprint 040 already repaired its one real consequence), the OAuth seam IGDB will
need, a generalised cover chooser, and `goodreads.py`'s two pre-existing defects
(an unguarded `shelf_slug`, a blank title left blank — DEC-093). All named in the sprint
file so they read as deferred rather than missed.

## The caveat worth carrying

**This is a sample of one domain, and an unusual one** — anime was the first with a real
cross-provider identity, the first needing enrichment on a non-ISBN key, and the first
needing a per-entry number. Games would exercise authentication with a lifetime instead
and would very likely surface a different list. The argument for waiting was weighed and
rejected because deliverables 1–3 record mistakes already made rather than predictions;
if any of them starts to feel speculative mid-sprint, that is the signal to stop and hand
the rest to the domain that asks.

## Still open, and nobody's sprint

- `JobRepository.complete` never clears `error`/`error_code`, so a job that failed then
  succeeded shows `succeeded` beside stale failure text (DEC-091).
- `createEntry`'s body type in `frontend/src/api/add.ts` is out of sync with what
  `AddForm` sends.
- Watched-episode counts do not appear in Triage — the owner's Sprint 040 scoping, not an
  oversight.

## State at this handoff

`make check`, `make test` (698 backend / 189 frontend) and Playwright (103 passed, 2
skipped) were all green at `0f1b86e`. This commit changes documentation, state and the
validator's sprint bound only; no product gate applies to it.
