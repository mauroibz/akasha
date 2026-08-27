# Sprint 040 — Entry progress

**Status:** completed
**Depends on:** 038
**Roadmap revision:** 20

## Objective

DEC-077 shape (a), built: a domain declares that its entries carry a progress count, and the entry
holds one. `20 / 170` on a dropped anime becomes expressible without a child entity.

## Required context

- `docs/decisions.md`: **DEC-077** — the verdict this sprint implements. It chose the shape and built
  nothing; read what it rejected as carefully as what it chose. Also **DEC-089**, DEC-071 (the
  two-phase entry), DEC-057 and DEC-060 (what a domain declares about its entries), DEC-059
  (format is not status is not shelf).
- `docs/specs/product-spec.md` §10 item 4 (one score, one status, one `reread_count` per item) and
  §11 item 4 (the deliberate choice not to model sets).
- `docs/specs/technical-spec.md` §5.1 `entries`, and §6.6's `entry_fields` rule.
- Code: `domain/spec.py` (`PASSAGE_FIELDS`, `validate_entry_fields`), `application/library.py`
  around `_validated`, `api/library.py`, `infrastructure/models.py`, `application/export.py`,
  `backend/alembic/versions/0014_status_is_the_domains.py` (the head),
  `frontend/src/pages/DetailPage.tsx`, `frontend/src/features/detail/OpinionDialog.tsx`,
  `frontend/src/features/library/labels.ts`.
- `backend/tests/test_flat_entry_contract.py` — the suite that pins the flat entry. This sprint adds
  to the flat entry without adding depth; that file is where the distinction is asserted.

## Current implementation baseline

Observed on 2026-08-27 at `bcb11ca`:

- `PASSAGE_FIELDS = frozenset({"date_started", "date_finished", "reread_count"})`. A domain declares
  a subset; `validate_entry_fields` refuses what is *absent*, and the conformance suite refuses a
  domain that invents a fourth name.
- `entries` carries `date_started`, `date_finished`, `reread_count` and no count of partial progress.
- `frontend/src/features/library/labels.ts` exposes `hasEntryField`, typed to a closed union of the
  three names; `DetailPage` and `OpinionDialog` both branch on it to render or omit a control.
- Migration head is `0014_status_is_the_domains`.
- **DEC-077 built nothing.** There is no `progress` anywhere in `backend/src` outside job progress
  and import batch counters, which are unrelated concepts wearing the same word.

## Deliverables

### 1. The declaration — `domain/spec.py`

```python
@dataclass(frozen=True)
class ProgressSpec:
    """How far through one of these you are, when that is a thing this domain has."""
    label: str                  # "Episodes watched"
    unit_label: str             # "episode"
    #: The metadata field on the item that holds the total, when one exists — so a
    #: control can render "20 / 170" and bound its input. `None` means unbounded.
    total_field: str | None = None
```

`Domain.progress: ProgressSpec | None`. `None` is the complete answer books and albums both give.
Conformance: `total_field`, when present, must name a `number` field this domain declares — a
declaration pointing at a field that does not exist is a domain that believes in a total nothing
holds.

`validate_progress(domain, value)` is the fourth validator beside `validate_status`,
`validate_formats` and `validate_metadata_patch`: it refuses a progress write on a domain that
declares none, and refuses a negative value. The message names the domain, as the others do.

**It does not bound the value by the item's total, and `total_field` is display only.** The owner
settled this at planning time on 2026-08-27, against this file's first draft. Measured: AniList
returns `episodes: null` for airing and unreleased shows, a weekly series' cached total is stale by
definition, and an explicit metadata refresh could lower `episodes` under an already-stored
progress — making a row that was valid when written violate a rule on its next write. That is
`ck_entries_status`'s mistake in a new costume: a constraint over data the domain does not control
(DEC-067 row 1). The reader's number wins over our cache, which is the technical spec's first
priority.

### 2. The schema — `backend/alembic/versions/0015_entry_progress.py`

One nullable integer column `entries.progress` with a non-negative CHECK. **No CHECK on an upper
bound** — the total lives in a domain's opaque metadata and a constraint cannot reach it, which is
exactly the mistake `ck_entries_status` made and migration `0014` undid (DEC-067 row 1). Nullable
because "no progress recorded" and "zero episodes watched" are different facts.

This is the **only shared-table change in the whole anime line**, and it is the reason this sprint is
separate from every other one.

### 3. The API

- `progress` on the entry response, and on the entry patch, validated through the domain.
- A patch carrying `progress` for a domain that declares none is refused with 422 naming the domain,
  the same shape as a bad status.
- `make openapi`.

### 4. The screens

- `DetailPage`: a progress fact rendered only when the domain declares one, showing
  `20 / 170 episodes` when a total exists and `20 episodes` when it does not.
- `OpinionDialog`: a number input under the same condition, labelled from the declaration.
- `labels.ts`: a `progressFor(itemType, types)` beside `hasEntryField`, with the same defensive
  behaviour — an unreachable registry must never be the reason a control is missing or a value is
  hidden.
- **No screen branches on item type.** The control renders a declaration.

### 5. Export

`application/export.py` carries `progress` on the entry. It is owner data; an export that drops it is
an export that loses it.

### 6. Anime declares it

`ProgressSpec(label="Episodes watched", unit_label="episode", total_field="episodes")`.

## Acceptance criteria

1. Anime entries accept, store, return and export a progress count; books and albums refuse one with
   422 naming the domain.
2. A negative progress is refused. **A progress above the item's total is accepted** — the total
   is display only, and an item with no total at all is equally fine.
3. `null` progress round-trips as "not recorded" and is distinguishable from `0`.
4. The detail page shows `20 / 170 episodes` for an anime with a 170-episode total, and shows no
   progress control at all on a book or an album.
5. Migration `0015` applies forward on a populated database and its down-revision is tested.
6. Existing entries are unaffected: every book and album entry reads back exactly as before.
7. Export and re-import of an anime entry preserves progress.
8. `test_flat_entry_contract.py` still passes. **This sprint adds a field to the flat entry; it must
   not add depth.** No child entity, no per-episode row, no second status.

## Required tests (TDD)

- `tests/test_domain_conformance.py` — malformed fixtures: a `ProgressSpec` whose `total_field` names
  no declared field, and one naming a non-number field.
- `tests/test_library_api.py` — the 422 on a domain that declares no progress; the bounds; the
  null/zero distinction.
- `tests/test_migrations.py` — `0015` up and down against a populated database.
- `tests/test_export.py` — progress present for anime, absent for book.
- `tests/test_flat_entry_contract.py` — asserts the entry is still flat.
- Frontend: the control renders from the declaration and is absent for a domain without one.

## Verification

```bash
cd backend && uv run pytest tests/test_migrations.py tests/test_library_api.py \
  tests/test_export.py tests/test_flat_entry_contract.py tests/test_domain_conformance.py -q
make check && make test
cd frontend && npm run test:e2e
```

Walkthrough: add an anime with a known episode count, set it to `watching` with a partial count, see
`n / total` on the detail page and in the library row if it appears there, set it to `dropped` and
confirm the count survives. Open a book and confirm no progress control exists. Take a backup, apply
the migration on a copy of real data, and confirm nothing else moved.

## Explicit non-scope

- **Child entities.** DEC-077 rejected shape (c) on evidence over nine shared surfaces. This sprint
  does not reopen it and finding it convenient is not evidence.
- **Progress as a sort key or a filter.** Additive later if wanted; not needed to hold the value.
- **Progress on the library card or in Triage.** The owner scoped this to the detail page and the
  opinion dialog on 2026-08-27. Neither surface shows any entry field beyond status and score today,
  and widening the row controls Sprints 036/037 just settled is not this sprint's business.
- **Auto-advancing progress**, watch dates per episode, or anything that turns a count into a log.
- **A shared typed progress concept.** DEC-077's reopen condition 3 is *two* domains shipping shape
  (a) and their vocabularies drifting. One domain is not that.
- **Ordered shelves / sets.** Named by DEC-077 as a different feature. Still deferred.

## Commit checkpoints

1. `feat(sprint-040): declare progress on the domain contract`
2. `feat(sprint-040): add entries.progress`
3. `feat(sprint-040): validate and serve progress per domain`
4. `feat(sprint-040): show progress where a domain declares it`
5. `feat(sprint-040): carry progress in the export`
6. `docs(sprint-040): close sprint and hand off`

## Risks and decisions to surface

- **This is the sprint that can break existing data.** It is the only migration in the line. Back up
  before the walkthrough, test the down-revision, and do not fold any other change into its commit.
- **`total_field` is a soft coupling** between the entry layer and a domain's opaque metadata. It is
  declared rather than assumed, and the conformance check is what keeps it honest. If it proves
  awkward, `total_field=None` with an unbounded input is the fallback and is a decision to record.
- **Watch for the second domain.** If games later want `progress` for a completion percentage, the
  vocabularies will start to drift and DEC-077's reopen condition 3 fires. Note it in the Outcome so
  the next reader sees it coming.

## Outcome

**Completed 2026-08-27** on branch `sprint-038-anime`. Commits `b17060b` (contract and
migration), `e396d46` (validation and API), `e16a4b3` (screens and the add-form repair),
and the closure commit. Recorded as **DEC-092**.

### The decision that changed during planning

This file's first draft refused a count above the item's episode total. **The owner
overruled it and was right.** AniList returns `episodes: null` for airing and unreleased
shows, a weekly series' cached total is stale by definition, and a metadata refresh can
lower `episodes` under a count already stored — making a row that was valid when written
violate a rule on its next write. That is `ck_entries_status`'s mistake in new clothes.
The value is bounded below and never above, everywhere in the stack, and `total_field` is
for display only. See DEC-092.

### Acceptance criteria, one line each

1. **Per domain.** Anime stores, returns and exports a count; a book and an album refuse
   one with 422 naming the domain (`Book entries do not record progress`), verified live.
2. **Negative refused, large accepted.** `-1` is refused by Pydantic before the service;
   `200` against a 170-episode item is stored, which is the criterion this file inverted.
3. **Three states.** `null` round-trips as not-recorded and is distinguishable from `0`;
   a patch that never mentions progress leaves it alone. `exclude_unset` is what keeps
   them apart, and clearing is allowed on every domain — including one declaring no
   progress, so a value a retyped item stranded can still be removed.
4. **The detail page** reads `20 / 170 episodes` with a total and `20 episodes` without,
   `—` when null, and shows no control at all on a book or an album.
5. **Migration `0015`** applies forward and back against a populated database; both
   directions are tested.
6. **Existing entries unaffected** — proved against a copy of the owner's real library
   (16 entries, 19 items, 7 shelf memberships, 6 formats): every count preserved,
   `integrity_check ok`, all four CHECKs, six indexes, and all 16 rows `NULL` rather
   than `0`.
7. **Export.** Rewritten from the original wording: there is no JSON *importer*, so
   "export and re-import" was untestable. The JSON export carries `progress`, including
   an explicit `null` for a book so a consumer can tell "not recorded" from "an older
   export"; the Goodreads CSV does not and should not.
8. **`test_flat_entry_contract.py` passes unchanged.** A scalar column is exactly what it
   was written to permit.

### Verification

- `make check` green; `make openapi` regenerated for three response models.
- `make test` — **660 backend, 189 frontend** (from 641/183 at Sprint 039 closure).
- `npm run test:e2e` — **103 passed, 2 skipped**, unchanged.
- Walkthrough: migration applied to a **copy** of the real database (results in criterion
  6), then 4 of 4 browser checks at 390x844 in
  `frontend/e2e/scratchpad/progress-walkthrough.spec.ts`, asserting the rendered reading,
  that an emptied box PATCHes `null`, that `0` PATCHes `0` and reads `0 / 170 episodes`,
  and that a book offers no control. Live `data/` never opened for writing and still has
  no `progress` column.

### What the rebuild taught, and what nearly went wrong

Two things cost failed attempts and are now asserted rather than assumed. A `copy_from`
that already spells the new column **dies on the row copy** — the column must arrive
inside the `with` block. And a rebuild is a `DROP TABLE`, so under `PRAGMA
foreign_keys=ON` it would fire the `ON DELETE CASCADE` on `entry_shelves` and
`entry_formats`, emptying both with no error and a migration reporting success.
`alembic/env.py` never enables that pragma, unlike `database.py`; that was load-bearing,
undocumented, and already depended on by `0013` and `0014`. The test seeds a shelf and a
format and asserts both survive, and pins the six indexes a drifted `copy_from` would
silently drop.

`0014`'s docstring is also wrong on one point and `0015` states the correct reason:
SQLAlchemy 2.0 *does* reflect named SQLite CHECK constraints. `copy_from` is still right,
because a reflected rebuild drops an **unnamed** CHECK and downgrades `ON DELETE
RESTRICT` to a bare reference.

### Deviations and prerequisite repair

- **A Sprint 038 miss, repaired here.** Its deliverable 5 claimed "the entry panel's last
  hardcoded book word" and fixed two of the **three** render sites. `AddForm.tsx` still
  spelled `Started`, `Finished` and `Reread count` verbatim, so adding an anime by hand
  read "Reread count" where the detail page read "Rewatches".
- **`test_backup.py` hardcoded the head revision** and failed with no behaviour changing.
  It derives it now — the third instance of that defect class in three sprints
  (DEC-090's `provider_health`, DEC-091's, and this).
- **A fixture without the key broke the dialog.** `String(undefined)` made the form
  permanently invalid and unsaveable. The client tolerates a response omitting the field
  now, which is the defensiveness the rest of that file already has.

### Impact on Sprint 041

None adverse; it is unblocked. The importer writes a watched-episode count through
`ImportEntry.values`, which all three `EntryRow` constructions now carry, and
`validate_progress` polices it on the import path beside `validate_entry_fields`. Bulk
deliberately carries no progress and 041 should not add it.
