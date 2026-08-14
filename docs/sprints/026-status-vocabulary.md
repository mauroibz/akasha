# Sprint 026 — Status vocabulary (seam 5b)

**Status:** ready
**Depends on:** 025
**Roadmap revision:** 10

## Objective

A domain has **its own statuses**, not just its own names for everyone else's. The sprint succeeds
when an album's entry offers the statuses an album can actually be in, the library filters and the
triage keyboard follow, and the product question underneath — whether `reread_count` and
`date_finished` mean anything for an album — has an owner's answer recorded rather than a default.

## Required context

1. `AGENTS.md`, `docs/agent/WORKFLOW.md`
2. **`docs/domain-architecture-proposal.md` section 4 seam 5 and section 7**, which split this seam
   in two and explain why 5b waited for two domains
3. `docs/decisions.md`: **DEC-057 first** (the owner's answer: an album's status is possession),
   then **DEC-052** (the split, and the owner's three answers), **DEC-055** (where the seams
   actually landed — read this before assuming anything about the registry), DEC-051 (owner data
   versus derived), DEC-019 if the status suggestion logic moves
4. Sprint 025's Outcome, especially its walkthrough findings: "Rereads: 0" and "Your reading data" on
   an album detail page are this sprint's two visible symptoms
5. `docs/specs/product-spec.md` sections 3.2, 5, 7; `docs/specs/technical-spec.md` sections 5.1, 7.1
6. `docs/agent/HANDOFF.md` and the last worklog entry

## Current implementation baseline

Observed 2026-08-14 at Sprint 025's close. **Re-derive at activation.**

- `EntryStatus` is a global `StrEnum` in `backend/src/book_tracker/domain/types.py`, used as the
  validation type on `EntryCreateBody.status`, `EntryPatch.status`, `BulkSet.status` and the
  `status` query parameter of `GET /api/entries` (`api/library.py`).
- `Domain` in `backend/src/book_tracker/domain/domains.py` carries `status_labels`, a *partial*
  override map served at `GET /api/item-types`. Albums override `read`/`reading`/`to_read` only.
  **There is no per-domain list of which statuses exist.**
- Frontend: `statusLabels`, `chooseableStatuses` and `statusHotkeys` are one table in
  `frontend/src/features/library/labels.ts`; `statusLabelsFor(itemType, types)` applies a domain's
  overrides. `StatusSelect` takes a `labels` prop and hardcodes `orderedStatuses`. The triage bulk
  chooser and the library filter chips deliberately use the shared vocabulary, because a selection
  or a facet count can span domains.
- `facets.status_counts` is computed across the whole library and keyed by the global status values.
- `suggested_status` (Goodreads' shelf mapping) is book-only in practice but not by declaration.

## Deliverables

1. **The product decision, mostly settled — finish it.** **DEC-057 has the owner's answer**: an
   album's status records *possession* (`wishlist` / `pending` / `owned`), not consumption, and
   `reread_count`, `date_started` and `date_finished` are meaningless for it. Read DEC-057 first.
   What is still open is the one question it names: whether format tags (CD/Digital/Vinyl,
   physical/borrowed/digital) carry ownership too, and therefore overlap `owned`. Settle that with
   the owner, with the recommendation DEC-057 gives, before building either.
2. **Per-domain status vocabularies.** `Domain` gains the ordered statuses it has and which of them
   are directly choosable; `unsorted` stays universal, because imports land there and the default
   library view hides it. Validation moves from the global `EntryStatus` to a per-type lookup keyed
   on the item's own type, with a clear 422 when a status does not belong to the domain.
3. **The surfaces that follow it:** `StatusSelect`'s ordered list, the triage keyboard map, and the
   library filter chips. Decide explicitly what a chip means in a mixed library — a count for a
   status only one domain has is either hidden, or shown with its own domain's name.
4. **The Goodreads status suggestion stays book-only by declaration**, not by accident.
5. **The entry panel's copy** stops calling itself "Your reading data" for every domain.

## Acceptance criteria

1. An album's status control offers the album's statuses, and a book's offers the book's, with no
   `type === "album"` branch in a component.
2. Setting a status a domain does not have is refused with a 422 naming the domain, not stored.
3. Every existing entry keeps its status across the change: no data migration silently remaps a
   value, and if one is genuinely needed it is a migration with a test, not a default.
4. The triage keyboard sets the right status for the row it is on, whatever domain it belongs to.
5. Filter chips and `status_counts` are correct and legible in a mixed library, per the choice made
   in deliverable 3.
6. An album shows no reread count and no started/finished dates, per DEC-057, and a book still
   shows all three. The remaining ownership/format question is answered in `docs/decisions.md`
   before any code depends on it.
7. Every book behaviour the suite covers is unchanged: imports, triage, undo, bulk edit, backup.

## Required tests (TDD)

- A status outside a domain's vocabulary is refused on create, patch and bulk-set.
- Every entry's status survives the change, proven against a database seeded before it.
- The triage hotkey map is derived from the domain, and the drift assertion in `labels.test.ts`
  still holds for every domain rather than for one.
- A mixed library's facet counts are correct with statuses that do not exist in both domains.
- The Goodreads importer still suggests book statuses and suggests nothing for a domain that does
  not declare them.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && make build && make smoke-container
git diff --check
```

Plus the walkthrough gate against a real library holding both books and albums: set statuses on both
from the library grid, the detail page and triage; filter by each chip; and report what you saw.

## Explicit non-scope

- Games (027) and series (028).
- Per-domain **entry** models beyond whatever deliverable 1 decides — hierarchy is Sprint 028's
  question, and it is a much larger one.
- Re-opening seam 5a. Labels are done; this sprint is about which statuses exist.

## Commit checkpoints

1. `docs: settle what an album's statuses are` (the decision, before the code)
2. `feat: give each domain its own statuses`
3. `feat: follow the domain vocabulary in triage and the filters`
4. final `docs(sprint-026): close sprint and hand off`

## Risks and decisions to surface

- **The product question is the sprint, and DEC-057 answered most of it.** What remains — whether
  format tags carry ownership — still gates deliverable 2, because it decides whether `owned` is a
  status at all. Do not guess it: it is not a reversible implementation detail.
- **Entry fields become per-domain, not only statuses.** DEC-057 means an album hides
  `reread_count`, `date_started` and `date_finished`. That reaches the opinion dialog, the detail
  panel, the export and the Goodreads CSV mapping. Check whether hiding is enough or whether the
  fields should be refused on write for a domain that does not have them.
- **A mixed filter chip has no obviously right answer.** "Listened 3" and "Read 6" as separate chips
  is honest but doubles the row; one "Finished 9" chip is compact and lies slightly. This is a
  product judgement worth surfacing with a recommendation rather than settling silently.
- **`EntryStatus` is a validation type in four API models.** Moving off it touches the OpenAPI
  surface, so regenerate and re-check the frontend types in the same commit.
- The branch question is settled by DEC-053: this is a domain-line sprint, so cut a branch from
  `main` at activation.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
