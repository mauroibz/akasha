# Sprint 023 — Creator sort names

**Status:** in_progress
**Depends on:** 020
**Roadmap revision:** 9

## Objective

"Gabriel García Márquez" sorts under G today. After this sprint the library sorts by a stored
creator sort name that the owner can correct, and no later domain inherits a broken projection.

## Required context

1. `AGENTS.md`
2. `docs/sprints/ROADMAP.md`, the Sprint 023 section — it names the trap this sprint exists to avoid
3. `docs/decisions.md`: DEC-036 (the normalized projection and *why it is maintained by a mapper
   event*), DEC-015 (what DEC-036 superseded), DEC-042 (why creator precedes the domain line)
4. `backend/src/book_tracker/infrastructure/models.py` — `ItemRow.sort_author` is a generated column
   and `_project_normalized_text` is the mapper event that keeps the normalized columns in step
5. `backend/src/book_tracker/domain/normalization.py`
6. `backend/src/book_tracker/application/library.py`, the sort and cursor paths
7. `backend/src/book_tracker/domain/pagination.py` — `CursorState.v` is the version this sprint bumps
8. `backend/src/book_tracker/domain/calibre.py` — the reader that will learn to read `authors.sort`
9. `backend/alembic/versions/0007_normalized_sort_projection.py` — the closest prior art for a
   migration that rewrites every row in `items`
10. Sprint 021 Outcome and `docs/agent/HANDOFF.md`

## Owner decisions taken at planning (2026-08-14)

Both were put to the owner before this sprint was scoped, and both narrow the work rather than
widen it.

- **Calibre's `authors.sort` seeds the sort name, stored as owner data.** A real Calibre database
  carries a human-curated sort name per author and this library came from Calibre, so the seed is
  curated truth rather than a guess. The heuristic becomes the fallback, not the primary path.
- **`sort_author` keeps its name and its display role.** It holds the verbatim first author for the
  detail page, the grid, and the `q` search filter; the new column owns *ordering* only. Renaming
  the display field would touch three components, seven e2e seeds, the benchmark and several
  backend tests, in the sprint whose own risk note says pagination breaks in ways unit tests miss.
  The rename happens once in Sprint 025, alongside the metadata key `authors` → `creators`.

## Current implementation baseline

Re-derive at activation. As of Sprint 022's close: `sort_author` is
`Computed("json_extract(metadata, '$.authors[0]')")`, and `sort_author_normalized` is a plain column
maintained by a `before_insert`/`before_update` mapper event, because SQLite generated columns may
only call built-in functions. The migration head is still `0010_attachments` — Sprint 022 added no
migration — pinned by literal in `test_migrations.py` (twice) and `test_backup.py`.

## Deliverables

1. A stored creator sort name, seeded and correctable by the owner. **Name it creator, not
   author** — an album has an artist and a game has a studio, and Sprint 025 should not have to
   rewrite this. The shape is three columns: `creator_sort_override` (owner input, and where the
   Calibre seed lands), plus `creator_sort` and `creator_sort_normalized` derived from
   `override or heuristic(first_author)` by the existing mapper event.
2. A migration that backfills them for every existing row, following `0007`'s shape.
3. An edit surface, because the heuristic is *known* to be wrong for this library and a value nobody
   can fix is worse than no value.
4. The Calibre import reads `authors.sort` where the column exists and stores it as the override.
5. Sorting and keyset cursors moved onto the normalized creator column. The `q` filter stays on
   `sort_author_normalized`: search matches the name as written, so `gabriel garcia` must keep
   matching a row that now sorts as `garcia marquez gabriel`.

## Acceptance criteria

1. "Gabriel García Márquez" sorts under G**arcía Márquez**, "Adolfo Bioy Casares" under B**ioy
   Casares**, and "Juan Rulfo" under R**ulfo** — the three cases the roadmap names, because a
   last-space split gets the first two wrong and the third right.
2. A corrected sort name survives a provider refresh and a re-import; it is owner data, not cache.
3. Keyset pagination stays stable across the change — a cursor issued before the migration must not
   silently skip or repeat rows after it. The mechanism is a `CursorState.v` bump: a stale cursor
   fails loudly with `400 invalid_cursor`, which the library page already renders.
4. The projection is maintained by whatever mechanism replaces the mapper event, and a new write
   path cannot forget it (DEC-036's requirement, inherited).
5. A Calibre import of a database carrying `authors.sort` seeds the override from it; a database
   without that column still imports.

## Required tests (TDD)

- The three Spanish surname cases above, plus a mononym, an empty author list, an already-inverted
  `"García Márquez, Gabriel"`, and `"Ursula K. Le Guin"`.
- A round trip proving a hand-corrected sort name is not overwritten by refresh or import.
- Migration test: rows written before the migration carry the backfilled value after it.
- Cursor stability across the projection change, including that a `v: 1` cursor is rejected rather
  than silently mis-paginating.
- Calibre import with and without the `authors.sort` column.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && make build && make smoke-container
git diff --check
```

Plus a walkthrough against the container with the real library:

1. Sort by Author, page past the first screen, and read the order — the acceptance criteria are a
   claim about what is on screen, not about a test.
2. Correct one name by hand, confirm the list re-sorts, then refresh that item from the provider and
   confirm the correction survived.
3. **Measure the seed.** Count how many items took their sort name from Calibre versus the
   heuristic, and read a sample of the heuristic's output. If it is wrong more often than right,
   report the number plainly rather than tuning it silently.
4. Re-run `scripts/benchmark_library.py` for `sort_author` and compare against the 78 ms p95 at
   page 26 that DEC-036 recorded.

## Explicit non-scope

- The domain generalization itself. Name the column for creators; do not build albums or games here.
- Search relevance and `merge_and_rank`, including the reprint-over-original ordering DEC-044
  deferred.
- The unbuilt *Add shelves* bulk action (DEC-043).

## Commit checkpoints

1. `feat: store a creator sort name and backfill it`
2. `feat: sort the library by the stored creator name`
3. `feat: correct a creator sort name by hand`
4. `feat: seed creator sort names from Calibre`
5. final `docs(sprint-023): close sprint and hand off`

## Risks and decisions to surface

- The heuristic will be wrong often enough that the edit surface is the feature, not the polish. If
  measurement shows it is wrong more often than right, say so rather than tuning it silently.
- Renaming a column that sorting, filtering and cursors all read is the kind of change that passes
  every unit test and breaks pagination in the browser. The walkthrough is not optional here.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
