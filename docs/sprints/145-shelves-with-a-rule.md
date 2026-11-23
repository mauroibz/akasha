# Sprint 145 — Shelves with a rule

**Sprint:** 145
**Status:** planned
**Roadmap revision:** 56
**Depends on:** 144
**Owner:** Mauro

## Objective

A saved view becomes a shelf whose contents follow a rule, beside hand-picked shelves.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 3.5 and the mockup.
- The roadmap's *Not scheduled* entry "Saved views (smart shelves)" and DEC-139's acceptance in principle.
- Frontend: `features/library/SaveView.tsx`, `features/library/library.ts` (URL filters). Backend: the shelves model and API, `alembic/versions/`.

## Current implementation baseline

To be observed at activation: what `SaveView` stores today and where.

## Deliverables

1. **Storage.** One migration: a shelf may carry a `rule` (the Library's filter set as JSON: medium, statuses, formats, score range, query). A shelf with a rule has no hand-picked members.
2. **Making one.** *Save as a shelf* on a filtered Library creates it; existing saved views are migrated.
3. **Everywhere a shelf is.** It appears in the Shelves view, opens as the library with that filter, and can be a showcase; it is marked as following a rule, and entries cannot be added to it by hand.

## Acceptance criteria

1. A shelf "anime rated 9 or more" gains an entry when its score becomes 9, with no other action.
2. The shelf picker on an entry does not offer a shelf with a rule.
3. Existing saved views survive the migration as shelves (pytest on a migrated database).
4. A rule naming a status or medium that no longer exists is refused on write and tolerated on read.

## Required tests (TDD)

`test_shelves.py` (rules, migration), `SaveView` (Vitest), `e2e/shelves.spec.ts`.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*. Migrate a copy of a real library.

## Explicit non-scope

A rule builder beyond the Library's existing filters.

## Commit checkpoints

`[ADD]` shelf rules; `[MOD]` save as a shelf; `[DOCS]` close.

## Risks and decisions to surface

- Counting a rule shelf's members on every Shelves view render: one query per shelf, bounded.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
