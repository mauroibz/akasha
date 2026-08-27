# Sprint 043 — Sharpening the domain contract

**Status:** planned
**Depends on:** 042
**Roadmap revision:** 22

## Objective

Close the frictions the third domain actually hit, so the fourth does not hit them again.
Nothing user-visible changes.

## Required context

- `docs/decisions.md`: **DEC-094** (the retrospective this sprint implements), and the
  four it draws on — DEC-090, DEC-091, DEC-092, DEC-093. Also DEC-067 row 1 (the frozen
  vocabulary), DEC-057 and DEC-060 (what a domain declares about its entries), DEC-077.
- `docs/guides/adding-a-domain.md` in full. **This sprint edits it, and the point is that
  it stops describing intentions.**
- `docs/agent/TESTING.md` — walkthrough reuse, which is where the UI-idiom note belongs.
- Code: `domain/spec.py` (`validate_entry_fields`, `validate_progress`, `PASSAGE_FIELDS`),
  the three call sites at `application/library.py:163`, `application/add.py:187` and
  `application/imports.py:157`; `tests/test_domain_conformance.py` (the
  `REGISTRY_CHECKS` / `CORE_CHECKS` split and the two decorators at lines 161-170);
  `tests/test_enrichment_pipeline.py:550`; `infrastructure/repositories.py:256,382,774`;
  `alembic/env.py`.

## Current implementation baseline

Observed on 2026-08-27 at `0f1b86e`, the close of the anime line. **Sprint 042 was
inserted ahead of this one by owner direction and touches `TriagePage.tsx` only**, so every
fact below still holds — but re-check rather than trusting this line.

- **`validate_entry_fields` is a denylist.** It refuses only names *inside*
  `PASSAGE_FIELDS` that the domain lacks; every other key passes through untouched, and
  the return value is discarded at two of its three call sites. This is why `progress`
  reached the column unvalidated on the import path through all of Sprint 040, and why
  that sprint's Outcome claimed a guard that did not exist (corrected in DEC-093).
- **`validate_progress` is called from two of the three paths** — `library.py:169` and
  `add.py:189` — and was added to `imports.py` only in Sprint 041.
- **Conformance has two tiers and no third.** `REGISTRY_CHECKS` take a `Domain` alone;
  `CORE_CHECKS` take a `Domain` and an `Engine`. Neither has the built application, so a
  domain naming a provider nobody constructed is invisible to the suite. The one check
  that does test wiring lives in `tests/test_enrichment_pipeline.py:550`, which is not
  where anybody would look for it.
- **`repositories.py` constructs `EntryRow` in three places** (lines 256, 382, 774), each
  spelling its columns by hand. Sprint 040 had to edit all three to add one field.
- **`alembic/env.py` never enables `PRAGMA foreign_keys`,** unlike `database.py`. Three
  migrations now depend on that silence — a table rebuild is a `DROP TABLE`, which under
  the pragma would cascade children away and still report success. **The file says
  nothing about this.**
- **No live CHECK constraint freezes an application-owned vocabulary.** Verified:
  `grep CheckConstraint alembic/versions | grep " IN ("` returns only boolean checks and
  the two downgrade snapshots. Both offenders are gone (`0014`, `0016`) and nothing stops
  a third being written.
- **The UI's control idioms are written down nowhere.** Every walkthrough in this line
  needed two to four selector corrections on its first run, and in every case the
  assumption was wrong rather than the product.

## Deliverables

### 1. One allowlisting validator for a domain's entry values

Replace the denylist with `validate_entry_values(domain, values) -> dict[str, Any]` in
`domain/spec.py`, owning **all** of it: the passage fields a domain declares, `progress`,
and a refusal of any key that is neither. Keep `validate_entry_fields` and
`validate_progress` as the pieces it composes if that reads better, but the three call
sites — `library.py:163`, `add.py:187`, `imports.py:157` — call one function and use its
return value.

This is the root-cause fix. A denylist is silent about what it has not been told to
refuse, which is exactly how a per-domain value reached storage unchecked for a sprint.
The next domain that adds an entry value inherits the guard rather than the gap.

### 2. A wiring tier in the conformance suite

Add `APP_CHECKS`, taking a `Domain` and the built application, beside the two tiers that
exist. Move `test_every_enriching_domain_names_providers_this_build_actually_wires` into
it from `test_enrichment_pipeline.py:550`, and add at least:

- every provider a domain names in `identity.source_preference` **or** in its
  `EnrichmentSpec.provider_order` is constructed by the lifespan and serves that domain;
- every provider a domain's `recognize` can route to exists;
- a domain declaring `chooses_covers` is served by a provider that can offer candidates.

The split earns its keep the way the first two did: a domain can be complete on its own,
hostable by the core, and still name an adapter nobody built. That failure currently
surfaces at runtime as `enrichment_not_configured`, which reads like a missing API key.

### 3. A guard against the next frozen vocabulary

A test asserting that no live CHECK constraint enumerates a vocabulary the application
owns. Two have been written and both had to be deleted (`ck_entries_status` in `0014`,
`ck_import_batches_kind` in `0016`); the class is closed today and nothing keeps it closed.
Read the schema at head rather than the migration files, so a constraint added by any
route is caught. Boolean checks (`IN (0, 1)`) and numeric bounds are legitimate and must
still pass.

### 4. One `EntryRow` factory

Collapse the three hand-enumerated constructions in `repositories.py` into one helper, so
a new entry column is one edit rather than three. Behaviour identical; the unsorted
default's `progress=None` and the import path's `entry_values.get("progress")` keep their
comments, because the *reason* differs at each site even though the code will not.

### 5. Say why `alembic/env.py` is silent

A comment naming the load-bearing fact: this configuration deliberately does not enable
`PRAGMA foreign_keys`, three migrations rely on it, and a batch rebuild is a `DROP TABLE`
that would otherwise cascade `entry_shelves`, `entry_formats` and
`import_records`/`import_effects` away without an error. Cross-reference DEC-092.

### 6. Two pages of documentation that would have saved this line real time

- **A table-rebuild recipe** in `docs/guides/adding-a-domain.md`: `copy_from` describes the
  table *as the previous revision left it* and the new column arrives inside the `with`
  block; `copy_from` is a declaration and not a check, so anything omitted is dropped in
  silence; build columns inside the helper because a `Column` belongs to one `Table`; and
  the `DROP TABLE` cascade above.
- **A UI-idiom note** for walkthroughs, in `docs/agent/TESTING.md` beside the existing
  walkthrough-reuse section: the domain chooser is a `radiogroup`, the library status
  filter is a popover whose options carry facet counts, library rows use popovers where
  Triage uses native selects (DEC-086), the Triage heading reads `Inbox N unsorted`, and
  the detail route is `/books/:id` for every domain. Point at the two working scratchpad
  specs rather than restating them.

## Acceptance criteria

1. An entry value a domain does not declare is refused with 422 naming the domain, on
   **all three** write paths — PATCH, add and import — and a test covers each path.
2. `progress` on a domain declaring none is refused on all three paths; clearing with
   `null` is still allowed everywhere, as DEC-092 requires.
3. A key that is neither a passage field nor `progress` is refused rather than stored.
4. The conformance suite gains a wiring tier, the enrichment wiring check moves into it,
   and a deliberately broken fixture proves each new check can fail.
5. A CHECK constraint enumerating an application-owned vocabulary fails a test. Add one
   temporarily to prove the guard bites, then remove it.
6. `EntryRow` is constructed in exactly one place.
7. `make check` and `make test` pass with **no behaviour change**: every existing test
   passes unmodified except where it names `validate_entry_fields` directly.
8. No migration. No API change. No screen change. `make openapi` produces no diff.

## Required tests (TDD)

- `tests/test_domain.py` — the allowlisting validator: a declared passage field passes, an
  undeclared one is refused, `progress` is refused on a domain without it, `null` clears
  anywhere, and an unknown key is refused.
- `tests/test_library_api.py`, `tests/test_cached_add.py`, `tests/test_generic_imports.py`
  — one test each proving the same refusal reaches all three write paths.
- `tests/test_domain_conformance.py` — the new tier, plus a malformed fixture per check.
- `tests/test_migrations.py` — the frozen-vocabulary guard, proved by a constraint added
  and then removed.
- `tests/test_repositories.py` (or nearest) — the factory produces the same rows the three
  call sites produced.

## Verification

```bash
cd backend && uv run pytest tests/test_domain.py tests/test_domain_conformance.py \
  tests/test_migrations.py tests/test_library_api.py tests/test_generic_imports.py -q
make check && make test
cd frontend && npm run test:e2e
```

**No walkthrough gate.** Nothing user-visible changes, and TESTING.md's ladder does not
ask for one where no flow moves. If any acceptance criterion turns out to touch a screen,
that is a scope error — stop and re-plan rather than adding a gate.

## Explicit non-scope

- **The three entry-field render sites** (`DetailPage`, `OpinionDialog`, `AddForm`) keep
  their duplicated `has(...)`/`nameOf(...)`. A shared hook is the right idea and is a
  frontend refactor with its own risk; it is named here so it is recognised as deferred
  rather than missed. Sprint 040 already repaired the one real consequence.
- **The OAuth seam** IGDB will need (DEC-068). Speculative until a domain asks.
- **Generalising the cover chooser** (DEC-067 row 7). Still nothing needs it.
- **`goodreads.py`'s two shared defects** — an unguarded `shelf_slug` and a blank title
  left blank (DEC-093). Real, pre-existing, and a book-import change rather than a contract
  one. Named, not fixed here.
- Anything that changes what a reader sees.

## Commit checkpoints

1. `feat(sprint-043): one allowlisting validator for a domain's entry values`
2. `feat(sprint-043): hold a domain to the wiring this build actually has`
3. `test(sprint-043): refuse a CHECK that freezes an application vocabulary`
4. `refactor(sprint-043): construct an entry row in one place`
5. `docs(sprint-043): the rebuild recipe, the pragma, and how to drive these screens`
6. `docs(sprint-043): close sprint and hand off`

## Risks and decisions to surface

- **This is a sample of one domain.** Anime was the first with a cross-provider identity,
  the first needing enrichment on a non-ISBN key, and the first needing a per-entry number.
  Games would exercise OAuth instead and might surface a different list. Deliverables 1-3
  are about not repeating *known* mistakes rather than guessing at future ones, which is
  why they are the ones worth building now; if any of them starts to feel speculative
  mid-sprint, that is the signal to stop and hand the rest to the domain that asks.
- **Deliverable 1 touches every entry write path in the application.** The existing tests
  are the guard and must not be relaxed to fit the new signature. If one has to change,
  say exactly why in the Outcome.
- **Branch.** This depends on the anime line's code, which is not on `main`, so it
  continues on `sprint-038-anime` under DEC-053 unless the owner merges first.
- If deliverables 1 and 2 together run long, 3-6 are the clean split point: they are
  independent of each other and of the two.

## Outcome

_Not started._
