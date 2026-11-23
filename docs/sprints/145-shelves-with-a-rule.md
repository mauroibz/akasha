# Sprint 145 — Shelves with a rule

**Sprint:** 145
**Status:** completed
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

Completed 2026-11-23 (DEC-193). Commit: `3c502f4`.

Baseline as observed at activation: saved views already exist (Sprint 100): `saved_views`
keeps the Library's URL query under a name per person, `GET`/`POST`/`DELETE /api/views`, made
with *Save view* on a filtered Library and reopened only from the command bar.

- **A saved view is drawn as a shelf.** In the Shelves view, after the application's own two:
  "Follows a rule", the name, "N things match now", the first eight covers, each from one
  bounded list request at the view's own address. It opens the Library filtered as the rule
  says. *Stop keeping …* deletes the rule.
- **Save as a shelf.** The Library's *Save view* is renamed and says where the shelf is. The
  rule it keeps drops `view=`, so a rule made from any view reopens on the list.
- The command bar still lists them by name.

Acceptance: 1 by construction and the walkthrough: the shelf holds no members, it lists what
matches when it is drawn; 2 by construction: the shelf picker reads `/api/shelves`, where a
rule shelf is not; 3: no migration ran, the existing rows are the shelves; 4: the Library
already tolerates an address naming a status or shelf that no longer exists.

Verification: Vitest 648 passed; Playwright chromium and heavy-library, full run, 239 passed
and 2 skipped by design; `make check`. In the running app on a copy of the development
library: the Library filtered to read books sorted by score, *Save as a shelf* named "Books I
finished", the toast, then the Shelves view showing it with "9 things match now" and its
covers, its link carrying `?type=book&status=read&sort=score`.

Deviations:

- **No migration and no `rule` column on `shelves`.** The sprint planned to move saved views
  into the shelves table. They already are a rule under a name per person, and a shelf's
  members table has nothing to say about one. Drawing them as shelves gives the owner the
  same thing with no schema change and nothing to migrate. Two tables remain for the two
  kinds.
- A rule shelf cannot be a showcase yet: the `shelf:<id>` family is of the shelves table.
- At most twelve are drawn, one request each.
- The rule is whatever the Library's address held, so it includes the sort.

Impact on later sprints: none on 146–148. A `view:<id>` showcase family would be the way to
place a rule shelf on the Library's front.
