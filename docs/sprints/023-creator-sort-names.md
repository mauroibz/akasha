# Sprint 023 — Creator sort names

**Status:** ready
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
7. `backend/alembic/versions/0007_normalized_sort_projection.py` — the closest prior art for a
   migration that rewrites every row in `items`
8. Sprint 021 Outcome and `docs/agent/HANDOFF.md`

## Current implementation baseline

Re-derive at activation. As of Sprint 022's close: `sort_author` is
`Computed("json_extract(metadata, '$.authors[0]')")`, and `sort_author_normalized` is a plain column
maintained by a `before_insert`/`before_update` mapper event, because SQLite generated columns may
only call built-in functions. The migration head is still `0010_attachments` — Sprint 022 added no
migration — pinned by literal in `test_migrations.py` (twice) and `test_backup.py`.

## Deliverables

1. A stored creator sort name, seeded by a heuristic and correctable by the owner. **Name it
   creator, not author** — an album has an artist and a game has a studio, and Sprint 025 should not
   have to rewrite this.
2. A migration that backfills it for every existing row, following `0007`'s shape.
3. An edit surface, because the heuristic is *known* to be wrong for this library and a value nobody
   can fix is worse than no value.
4. Sorting, filtering and keyset cursors moved onto it.

## Acceptance criteria

1. "Gabriel García Márquez" sorts under G**arcía Márquez**, "Adolfo Bioy Casares" under B**ioy
   Casares**, and "Juan Rulfo" under R**ulfo** — the three cases the roadmap names, because a
   last-space split gets the first two wrong and the third right.
2. A corrected sort name survives a provider refresh and a re-import; it is owner data, not cache.
3. Keyset pagination stays stable across the change — a cursor issued before the migration must not
   silently skip or repeat rows after it.
4. The projection is maintained by whatever mechanism replaces the mapper event, and a new write
   path cannot forget it (DEC-036's requirement, inherited).

## Required tests (TDD)

- The three Spanish surname cases above, plus a mononym and an empty author list.
- A round trip proving a hand-corrected sort name is not overwritten by refresh or import.
- Migration test: rows written before the migration carry the backfilled value after it.
- Cursor stability across the projection change.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && make build && make smoke-container
git diff --check
```

Plus a walkthrough against the container with the real library, checking that the sort order in the
library list is actually what the acceptance criteria claim.

## Explicit non-scope

- The domain generalization itself. Name the column for creators; do not build albums or games here.
- Search relevance and `merge_and_rank`, including the reprint-over-original ordering DEC-044
  deferred.
- The unbuilt *Add shelves* bulk action (DEC-043).

## Commit checkpoints

1. `feat: store a creator sort name and backfill it`
2. `feat: sort the library by the stored creator name`
3. `feat: correct a creator sort name by hand`
4. final `docs(sprint-023): close sprint and hand off`

## Risks and decisions to surface

- The heuristic will be wrong often enough that the edit surface is the feature, not the polish. If
  measurement shows it is wrong more often than right, say so rather than tuning it silently.
- Renaming a column that sorting, filtering and cursors all read is the kind of change that passes
  every unit test and breaks pagination in the browser. The walkthrough is not optional here.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
