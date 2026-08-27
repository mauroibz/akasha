# Handoff — Sprint 040 closed, Sprint 041 ready

The entry holds a progress count. Plan revision 20, `FINAL_SPRINT` 41, active sprint
**041 — The MyAnimeList import**, status `ready`. It is the **last sprint in the anime
line**. Branch **`sprint-038-anime`**, cut from `main` at `bcb11ca` under DEC-053.
Nothing pushed; merging is the owner's call once the line closes.

## What Sprint 040 delivered

DEC-077's shape (a), built: a `ProgressSpec` a domain declares, a nullable
`entries.progress`, a fourth validator, the control on the detail page and in the
opinion dialog, and the value in the JSON export. Books and albums declare `None`.
Reasoning in **DEC-092**; delivered detail in the sprint Outcome.

Closure verification: `make check` green, `make test` **660 backend / 189 frontend**,
Playwright **103 passed / 2 skipped**, migration applied to a copy of the real 16-entry
database with everything preserved, and a 4-of-4 browser walkthrough. Live `data/` was
never opened for writing and still has no `progress` column — **it will be migrated the
first time the real application starts after this branch merges.**

## Sprint 041 in one paragraph

The MyAnimeList connector, against the owner's real 81-row export. Its sharpest
acceptance criterion is a negative one: **no change to `application/imports.py`,
`api/imports.py`, `ImportPage.tsx` or `TriagePage.tsx`.** Sprint 032 made connectors
self-describing so adding one is a package plus one tuple entry; whether that held for a
connector written by somebody who did not write the pipeline is the finding, either way
it goes. The sprint file carries the source measured row by row — do not re-derive it.

## What 041 inherits, and the two things it must not get wrong

- **Progress is written through `ImportEntry.values`.** All three hand-enumerated
  `EntryRow` constructions in `infrastructure/repositories.py` now carry `progress`, and
  `validate_progress` polices it on the import path beside `validate_entry_fields`. Put
  `my_watched_episodes` in `values` and it lands.
- **`0` is a real value and `None` is not.** `Gake no Ue no Ponyo` sits at 0 of 1 under
  `Plan to Watch`. A row with no count recorded must send `None`, not `0` — the two mean
  different things all the way down.
- **`my_score` of `0` means unrated**, so it maps to `None` and not to a score of zero.
  MyAnimeList's scale is already 1–10, so scores transfer straight across and are **not**
  provisional, unlike Goodreads' doubled stars.
- **Enrichment already works.** An imported row is a `mal` id and little else; Sprint
  039's backfill fills the rest from AniList. Watch the volume: one job per item, so 81
  rows is 81 jobs against a provider publishing `X-RateLimit-Limit: 30`.
- **Bulk deliberately carries no progress.** Setting one episode count across a selection
  means nothing. Do not "complete" the set.

## Things a fresh session will otherwise rediscover

- **A test that enumerates what exists today is a test the next change breaks.** Three
  instances in three sprints: `provider_health` (DEC-090), the enrichment lists
  (DEC-091), and `test_backup.py`'s hardcoded head revision (DEC-092). Assert against the
  registry or read the head.
- **Rebuilding `entries` has two traps**, both now asserted in `test_migrations.py`: a
  `copy_from` that spells a new column dies on the row copy, and a rebuild is a `DROP
  TABLE` that would cascade away `entry_shelves` and `entry_formats` if `alembic/env.py`
  ever enabled `PRAGMA foreign_keys`. It does not, and that is load-bearing.
- **A route docstring is its OpenAPI description** — rewording one fails `make check`
  until `make openapi`.
- **Writing a walkthrough?** The domain chooser is a `radiogroup`, the library status
  filter is a popover whose options carry facet counts, and library row controls are
  popovers where Triage's are native selects (DEC-086). Two working examples live in the
  gitignored `frontend/e2e/scratchpad/`: `anime-walkthrough.spec.ts` and
  `progress-walkthrough.spec.ts`.
- **Observed and unowned:** `JobRepository.complete` never clears `error`/`error_code`, so
  a job that failed then succeeded shows `succeeded` beside stale failure text
  (DEC-091). And `createEntry`'s body type in `frontend/src/api/add.ts` is out of sync
  with what `AddForm` sends — the extra keys slip past excess-property checking via
  conditional spreads.

## The owner's export

Gitignored at the repository root. Use it for 041's walkthrough only; commit trimmed,
anonymised fixtures instead — `myinfo` stripped of `user_id` and `user_name`.
