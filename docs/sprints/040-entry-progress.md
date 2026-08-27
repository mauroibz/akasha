# Sprint 040 — Entry progress

**Status:** planned
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
declares none, refuses a negative value, and refuses a value above the declared total when the item
carries one. The message names the domain, as the others do.

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
2. A negative progress is refused. A progress above the item's declared total is refused; an item
   with no total accepts any non-negative value.
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

_Not started._
