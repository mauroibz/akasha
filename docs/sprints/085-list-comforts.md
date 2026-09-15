# Sprint 085 — List comforts

**Sprint:** 085
**Status:** completed
**Roadmap revision:** 43
**Depends on:** 084
**Owner:** Mauro

## Objective

The owner's 2026-09-15 validation feedback on the any-domain list importer,
shipped as v2.2.1: four usability asks that all serve one goal — typing a few
entries by hand should be a first-class path, not a workaround.

## Owner feedback (verbatim, 2026-09-15)

1. "add a text editor on the UI so i can check what i uploaded, make small
   corrections to the file, or just quickly type out 3 entries and send,
   without uploading a file."
2. "make the creators column optional via a checkbox, in my experience most
   queries work without them, + for series is hard to define or know."
3. "move custom list to be the very first importer in the list."
4. "can we add a colored inidicator above or below each importer saying what
   domain they are for? Any for custom list, Books for goodreads/calibre, etc."

## Current implementation baseline

Measured 2026-09-15 in this worktree (all file:line from live source):

- The list preview posts the file as a multipart upload
  (`api/imports.ts` `previewImport`, `spec.kind === "upload"`); no typed-text
  path exists on the screen.
- The reader maps the creator column whenever the domain declares creator
  words and the header matches, or by position (first two columns) for a
  domain that expects a creator (`domain/list.py` `sniff_mapping`); the
  explicit-mapping form fields (`title_column`, `author_column`) can already
  point at the same column or out of range — there is no "no creators" answer.
- Importer order is the registry's `REGISTERED_IMPORTERS` tuple
  (`domain/registry.py:46`); the screen renders in catalog order.
- The strip is a scrolling `TabsList` (DEC-137); each tab shows the connector
  label only.

## Deliverables

### D1 — A paste-or-type editor beside the file input

1. The list connector's input grows a textarea ("Or type your list here")
   for `kind === "upload"` connectors whose bytes are text: typing or pasting
   populates it, the file input still works, and the two stay in sync (the
   last one edited wins; a dropped file fills the editor so "check what i
   uploaded" and "make small corrections" are literal).
2. Preview sends whichever source has content; empty both is the existing
   refusal.
3. The editor's content becomes the multipart body when no file is chosen
   (a synthesized File from the textarea, or the connector's text overload if
   the route accepts raw text — resolve on evidence from `api/imports.py`).

### D2 — The creators column is optional, by checkbox

1. A checkbox "No creators column" (or the equivalent honest label) beside the
   mapping fields, for the picked domain only when it declares creator words.
   Checked: the reader maps title only and treats a missing creator as an
   empty fact — the same rule a no-creator-words domain already follows.
2. Unchecked (default): today's behavior, byte-for-byte.
3. The reader's positional fallback for creator-expecting domains must not
   fire when the checkbox is set; the explicit column numbers still override.

### D3 — The custom list moves first in the strip

1. `REGISTERED_IMPORTERS` reorders to put the list first (a one-line registry
   change; the derived indexes and everything downstream follow).
2. The DEC-137 phone-fit spec and the e2e stubs' connector order follow.

### D4 — A per-importer domain indicator

1. Each connector tab carries a small colored indicator naming its target
   domains — "Any" for the list, "Books" for goodreads/calibre, "Films" for
   IMDb/Letterboxd, "Anime" for MyAnimeList, etc. — from the connector's own
   `item_types` declaration (no hardcoding; the label is the domain's
   published singular label).
2. Color comes from the design tokens (DEC-026); the indicator is presentational
   and must not collide with status semantics (the ScorePicker's rule:
   no color that already means something else).
3. The DEC-137 phone-fit constraint holds: the indicator must not overflow the
   scrolling strip at 390px.

## Acceptance criteria

1. **Typed entries import without a file.** Typing three CSV rows into the
   editor and clicking Preview produces the same `matching` → search →
   confirm → commit flow as an uploaded file. (tests: Vitest + e2e)
2. **The editor shows what was uploaded.** Dropping a file fills the editor
   with its text; editing the editor and previewing imports the edited text.
   (tests: Vitest)
3. **The creators checkbox opts out of the creator column.** With it checked,
   a two-column book list imports with titles only — the search query carries
   no creator; the positional fallback does not fire. Unchecked is v2.2.0
   byte-for-byte. (tests: backend reader + Vitest)
4. **The custom list is the first tab.** (tests: e2e order assertion)
5. **Each tab names its domains.** The indicator renders from `item_types`
   for every connector; "Any" for the list. (tests: Vitest + e2e)
6. **The phone fit holds.** DEC-137's spec still passes with the indicators
   present. (tests: e2e)
7. **No domain branch above the registry.** The indicator and the checkbox are
   declaration-driven; `if domain == "book"` anywhere in the diff is a defect.
   (tests: conformance neutrality already covers; review)

## Verification

- Focused: `cd backend && uv run pytest tests/test_list_import.py -x -q`
- Frontend: `npm run test -- --run` and the import e2e specs.
- Backend exhaustive: `make test`; `make check`.
- Full e2e: `npm run test:e2e`.
- Walkthrough on a fresh data dir: type three album rows by hand through the
  editor (no file), commit, undo; a two-column list with the creators
  checkbox checked; the strip order and indicators on a phone viewport.
- Container: not owed (no deployment change).

## Commit checkpoints

- [ADD] The list editor: paste, correct, or type entries
- [ADD] The creators column is optional, by checkbox
- [ADD] The custom list leads the strip, and every tab names its domains
- [FIX] Specs and stubs follow the new order
- [DOCS] Close sprint 085 and hand off

## Risks and decisions to surface

- **The editor's send format** (D1.3): multipart-with-synthesized-File vs the
  connector's text overload. Resolve on evidence from the route's accepted
  content types; prefer the shape that adds no route surface.
- **"No creators" and identity**: with no creator in the query, search results
  may be noisier for common titles. The owner's call (his feedback says most
  queries work); the edit-and-research affordance is the designed answer.
- **Indicator color vocabulary**: must not collide with existing semantics
  (score ramp, destructive). The token palette is small; naming by text may
  be enough with a neutral tint. Surface a screenshot pass if ambiguous.

## Explicit non-scope

- Mapping a list's extra columns to domain fields (unchanged, "queda a futuro").
- Mixed-domain batches (unchanged).
- Any new connector or provider.

## Outcome

_Delivered 2026-09-15. All seven acceptance criteria verified live; the
walkthrough found two defects the suites could not see, both fixed and
re-proven. Shipped as v2.2.1._

**Delivered behavior.**

- **AC1/AC2 (typed entries, editor mirrors uploads).** A paste-or-type
  editor beside the file input: typed rows preview with no file at all —
  the bytes travel as the upload the connector declared
  (`pasted-list.csv`), same route, same reader, no new API surface. A
  dropped text file fills the editor through a `FileReader` (jsdom's File
  has no `.text()`, so the component tests and the browser agree), and
  editing the editor makes it the source.
- **AC3 (the creators checkbox).** `ImportInputSpec.flags` declares a
  connector's boolean options the way `fields` declares string ones (the
  route forwards exactly what was declared); the list declares
  `no_creators`. The reader maps titles only on any domain — the same rule
  a no-creator-words domain follows — lifts the two-column minimum,
  refuses an `author_column` sent beside the flag as the contradiction it
  is, skips the positional creator fallback, drops the row-level
  `author missing` error, and composes the fingerprint (`#nocreator`), so
  the same file with and without its creators is two imports. Unchecked is
  v2.2.0 byte-for-byte.
- **AC4 (order).** The custom list leads `REGISTERED_IMPORTERS` (order is
  presentation only; the derived indexes are order-independent). The one
  test that read connectors positionally now keys by id — the same defect
  class its own comment documents.
- **AC5 (badges).** Each tab names its libraries from its own
  `item_types`: "Any library" for the list, the domain's own published
  label for single-domain connectors. Muted dot, no semantic collision
  (the ScorePicker rule); the accessible name grows to include it, which
  is more information, not less.
- **AC6 (phone fit).** DEC-137's spec passes with the badges present.
- **AC7 (no domain branch).** The editor, checkbox and badges are all
  declaration-driven; the conformance suite's neutrality check covers the
  connector; review found no domain branch in the diff.

**Walkthrough findings (fixed in-sprint).**

1. The source strip inherited shadcn's `justify-center`: once the badges
   widened the tabs past the strip's width, centered flex content
   overflowed BOTH sides and the first tab painted left of the scroll box,
   unreachable by any scroll — unclickable for a user, not just the
   script. Left-anchored now (`justify-start`).
2. The drop zone's `autoFocus` — harmless when Goodreads led — rendered on
   first paint with the list leading and scrolled every visit to /import
   mid-viewport, burying the strip under the fixed header. Removed (the
   input is one Tab away).
3. The no_creators flag mapped titles only but the row still carried the
   `author missing` error a creator-expecting domain records, so the
   commit gate counted 0 ready. The flag now opts the row out of the
   requirement too.

**Commands and actual results.**

- `uv run pytest tests/` — **1601 passed**.
- `npm run test -- --run` — **337 passed**.
- `make check` — green (ruff, mypy, eslint, prettier, OpenAPI no-drift,
  validator; OpenAPI regenerated for `flags` and the version bump).
- `npm run test:e2e` — **137 passed, 2 skipped** (full parallel run).
- Live walkthrough (`frontend/scripts/walkthrough-list-comforts.mjs`,
  fresh /tmp/akasha-s085, real providers) — **CLEAN**: 3 typed film rows
  committed with no file; the checkbox batch committed Rayuela with
  `creators: []`; a dropped CSV filled the editor and an inline correction
  re-sourced the batch; the strip shows the list first with its badges.

**Commits.** c32fc12 (the creators checkbox), 2911354 (editor, order,
badges), 033944a (the two walkthrough defects), 12d16b7 (script lint).

**Deviations.** The plan's D1.3 resolved to the synthesized-File shape (no
route surface added) — the option the plan preferred. The commit tags use
CONTRIBUTING's `[TAG]` form rather than the plan's checkpoint wording.

**Impact on future sprints.** `ImportInputSpec.flags` is a new declared
channel available to any connector needing a boolean option. No open work;
version surfaces at 2.2.1.
