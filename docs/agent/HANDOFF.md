# Handoff — current reality

**Last completed:** Sprint 027 (library shell and shelves), 2026-08-15.
**Next:** Sprint 028 (the domain contract) — status `ready`, file at
`docs/sprints/028-the-domain-contract.md`. Plan revision **11**.
**Then Sprint 029 (one search bar)**, accepted by the owner as DEC-065 and already written up at
`docs/sprints/029-one-search-bar.md`. It rebuilds `/` around a single bar and **removes "All" as a
filter**, so read it before writing 028's account of what a screen renders — that is the one section
029 is expected to amend. Per-domain imports is now Sprint 030.

## Do this first

**You are on branch `sprint-025-albums`, not `main`.** Sprints 025, 026 *and* 027 ran and closed
there. Twenty-three commits are local and nothing has been pushed. **Merging back is the owner's
decision** — that is the entire reason the branch exists (DEC-053, amended by DEC-061 and DEC-063).
Ask before merging, and cut Sprint 028's branch from whatever the owner settles on.

**Sprint 028 is gated (DEC-035, DEC-042).** Phase A produces a written contract, a conformance suite
and a verdict, and changes nothing user-visible. **Phase A concluding that almost nothing is
misplaced is a complete, correct outcome** — do not pad it into a refactor to justify the sprint.
Phase B runs only on that verdict plus an explicit owner go-ahead.

**Sprint 027 was reopened once**, after the owner tried it and reported the add flow, and closed
again the same day. Its file carries both passes; DEC-064 is the second one. That is the precedent
Sprint 020 set for its Phase B, not an inconsistency to repair.

**Music, the library shell and the add flow are finished.** Do not re-litigate DEC-057 (an album's status is
possession), DEC-059 (format is an independent, entry-level, multi-valued, per-domain tag) or
DEC-062 (the tab remembers the last domain; `type` clears the status facets and applies to
`format_counts`). All three are built.

## Read this first

**`Domain` is the whole per-domain contract**, in `backend/src/book_tracker/domain/domains.py`. It
carries `item_type`, `label`, `identity`, `fields`, `enriches`, `recognize`, `statuses`,
`default_status`, `entry_fields`, `formats` and `entry_panel_label`. `GET /api/item-types` publishes
all of it and every screen renders from it — the library's tabs, chips and format selector included
since Sprint 027. There is no `type === "album"` branch anywhere, and adding one is the thing to
catch in review. **Writing that contract down, and a suite that enforces it, is Sprint 028.**

**Four rules the code depends on:**

- **A write is validated against the item's own domain**, in `LibraryService._validated`, refused
  with a 422 naming the domain. A bulk write spanning domains is refused *whole*.
- **`_filter_key` must list every filter.** It is what a keyset cursor is bound to. Sprint 027 added
  `type` there; forgetting the next one is a silent paging bug, not a test failure.
- **The published unions (`EntryStatus`, `EntryFormat`, `ItemTypeName`) are spelled out** and pinned
  to the registry by a test. A dynamically built `StrEnum` is opaque to mypy, so the drift assertion
  is the safety net rather than the construction. Sprint 028's suite should absorb this pattern.
- **`type` is not an ordinary facet dimension** (DEC-062). Both status facets clear it, so the inbox
  badge keeps agreeing with the domain-agnostic `/triage` and an unselected tab still has a count;
  `format_counts` applies it, because that selector sits under the tab.

## What Sprint 027 left behind

- **The library virtualizes against the window** (`useWindowVirtualizer`), with a `scrollMargin` read
  from `getBoundingClientRect().top + window.scrollY` — *not* `offsetTop`, which walks offset parents
  the motion wrapper interrupts — and a `ResizeObserver` on `document.body` as well as the list,
  because the chips above it reflow without the list's own size changing. The DEC-023 mounted-DOM
  bounds are unchanged and re-asserted at 10,000 entries against the window.
- **`/triage` deliberately keeps its `h-[min(70vh,760px)]` container.** A dense working table inside
  a page is the intent there; only the library was the owner's complaint.
- **Shelf membership left `OpinionDialog`** for an inline create-on-type control on the detail page.
  The format checkboxes stayed in the dialog and must not converge with it (DEC-059).
- **The triage bulk *Add to shelf* now exists.** It had been in product spec §7 since v1 and was
  never built, which Sprint 027's own baseline got wrong.
- **`src/test/setup.ts` shims `ResizeObserver`** because jsdom has none and cmdk constructs one.

## What Sprint 027's second pass left behind

- **`GET /api/search/preview`** fetches one candidate's full record and writes nothing. It is one
  live provider request per call — there is no provider response cache — which is why it is a button
  on the add screen and not an effect. It follows `search`'s quota rule (DEC-045): recorded, never
  blocked.
- **`POST /api/entries` now takes the whole opinion** — notes, formats and the passage fields — each
  validated against the item's own domain **before** the write, so a 422 leaves no half-added row.
- **One control per concept, shared.** `features/shelves/ShelfPicker` (create-on-type) is used by the
  detail page and the add screen; `features/library/FormatPicker` (closed, no create) is used by the
  add screen and the opinion dialog. **They must stay distinct** — DEC-059 is about a shelf being a
  tier you invent and a format being a vocabulary the domain declares, and one widget doing both
  would erase that.
- **`CandidateFacts` de-duplicates against the field spec.** Both domains declare `language` and
  books declare `original_year`, while a candidate carries columns of the same name; the domain's
  label wins and the column is its fallback value.

## Known and left, in the order they are likely to bite

- **The dev library at `data/` is 8 books plus items 13 *Discovery* and 14 *Kind of Blue***, both
  `owned` with formats and covers. Backed up before the Sprint 027 walkthroughs to
  `backups/pre-sprint027-20260815T154413Z` and `backups/pre-container-*`. The walkthroughs left a
  shelf "Latin American" on item 6, four books on "Work", and **entry 17** — a *Rayuela* added with
  a shelf "Rayuelas", notes, a format, a finished date and two rereads, all set in one action. All
  realistic test data and kept deliberately.
- **`data/` has been made group/other-writable and the container has been run against it** so the
  owner could test Sprint 027 in Docker. Files the container creates are owned by uid 10001; if
  running the app directly fails on permissions, hand ownership back with
  `docker run --rm --user 0 -v "$PWD/data:/data" akasha:local chown -R 1000:1000 /data`.
- **`README.md` still describes a book-only product.** The album domain has never been released or
  merged, so advertising it there would describe something no user can run.
- **The Inbox label is ambiguous on `/`**: the header badge and each domain's `unsorted` chip all
  read "Inbox", so three buttons share it. Correct in each place, confusing together. Unscheduled.
- **"Choose a cover" still appears on an album and can only say no** — the chooser is Open Library's
  work-editions path. Unchanged since Sprint 025, and Sprint 028 is told to decide it rather than
  leave it unmentioned a fourth time.
- **Release selection is still arbitrary between same-day originals**, stable but not meaningful.
- `data/covers/` holds two stale `cover-*.jpg.tmp` files from an interrupted install; harmless.
- One dev-library item has **`OL14454691A` as its creator**; item 7 stores `"O'Reilly Media, Inc."`
  **with the quotes**. Both pre-existing.
- The list API takes repeated `status=`, `shelf=`, `format=` and `type=`; an unknown parameter is
  ignored silently, while an unknown *value* for any of the four is a 422.
- `HEAD` on any route returns 405, application-wide.
- "Replace cover" on the detail page is still a raw unstyled `<input type=file>`.
- The orphaned cover file is still not collected; the reclaim is scoped to attachments on purpose.
- `e2e/triage.spec.ts` "animates its action bar but not under reduced motion" flaked once in a
  full-file run and passed alone and on every re-run. Motion sampling timing; watch it.

## State

Migration head `0013_entry_formats` — Sprint 027 added no migration. Worktree clean; all commits
local on `sprint-025-albums`, nothing pushed.
