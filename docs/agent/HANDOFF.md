# Agent handoff

**State:** Sprint 010 completed; Sprint 011 is ready and unclaimed.
**Active sprint:** [`011-durable-enrichment-undo.md`](../sprints/011-durable-enrichment-undo.md)
**Worktree expectation:** clean after the Sprint 010 closure commit.

## Current reality

- The application has a responsive editorial shell (AppShell) with desktop/mobile navigation for
  Library, Add, Import, and Shelves. Unknown routes show a 404 with recovery links.
- Virtual library rows open detail by clicking the title/cover or pressing Enter; inline score/status
  controls remain independently operable. Library filters (status, shelf, query, sort) are URL-backed
  and reload-stable. New entries return to `/` with a highlight ring; exact duplicates open detail with
  a toast.
- Detail page shows all cached metadata, identifiers, sources, dates, notes, shelves, and cover state
  in personal-reading and edition-facts regions. Edit/refresh/delete dialogs trap focus, close on
  Escape, and preserve input on failure. Confirmed deletion calls DELETE, invalidates caches, and
  returns to the library with a toast.
- `/shelves` provides create, rename, confirmed delete with entry counts. Backend `ShelfResponse`
  includes `entry_count` via a count subquery. Duplicate slugs surface actionable errors.
- Segmented ScorePicker (1–10) is used in add, detail, and inline library editing. CoverImage provides
  skeleton placeholders and broken-cover fallbacks without layout shift.
- Import flows (Goodreads and Calibre) retain all tested behavior inside the new shell.
- The verified baseline is 92 backend tests, 37 frontend component tests, and 19 Chromium e2e flows.
- OpenAPI and typed frontend clients include the `entry_count` shelf response field.

## First action

Expand Sprint 011 from `TEMPLATE.md` into `docs/sprints/011-durable-enrichment-undo.md`, incorporating
actual deviations from Sprint 010. The sprint delivers DB-backed job polling, enrichment, and safe
24-hour undo using the import-effect ledger already recorded by Sprints 007–009.

## Known blockers

None. Isolated `uv build` may need approved network access for Hatchling when its cache is cold.
