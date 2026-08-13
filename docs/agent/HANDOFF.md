# Handoff — current reality

**Last completed:** Sprint 017 (scale, accessibility, resilience), 2026-08-12.
**Next:** Sprint 018 (container, backup, release) — status `ready`, file at
`docs/sprints/018-container-backup-release.md`.

## Read this first

**Text sorting reads a stored column, not a function (DEC-036).** `items.title_normalized` and
`items.sort_author_normalized` hold exactly what the domain `normalize_text` returns, maintained by
a mapper `before_insert`/`before_update` event in `infrastructure/models.py`. Ordering, the `q`
filter and the cursor all read them; the cursor reads the stored value back rather than recomputing
it, because a divergence would silently skip a page. Any new write path to `items` is covered
automatically — that is why the event is on the mapper and not at the call sites.

**The columns are deliberately not indexed.** The list query drives from `entries` and reaches
`items` by rowid, so SQLite builds a temp B-tree for the ORDER BY with or without the null-bucket
CASE; verified both ways. The entire win was deleting 10,000 Python UDF calls per page. Adding an
index would cost import writes and buy nothing.

**Both list surfaces are `role="feed"` with `article` children (DEC-038).** Neither `/` nor
`/triage` is an ARIA table; they have no column headers and no cells, and claiming otherwise was a
critical axe failure. Articles carry `aria-posinset`/`aria-setsize` from the server total.

**Routes are lazy (DEC-037).** Only `/` is in the entry chunk. A navigation can now fail because a
chunk did not arrive, which is why the error boundary is keyed on the pathname and why
`e2e/resilience.spec.ts` tests exactly that.

**Every e2e test fails if the page logged an error.** `e2e/console.ts` is an auto fixture across
all nine specs. A test that deliberately provokes an error must annotate itself with
`ALLOW_CONSOLE_ERRORS`.

## Plan shape

| Sprint | Scope | Status |
|---|---|---|
| 018 | Container, backup, release | `ready` |
| 019 | Metadata completeness, **gated** | roadmap contract |

## What Sprint 018 must know

- **Migration `0007` backfills every row in `items`.** It is the first migration in this project
  that does real work on the owner's data at deploy time, so "do migrations run at container start
  or as an explicit step" is a real decision now. Exercise the upgrade against a pre-`0007`
  database and confirm accented sorting and search still work afterwards.
- **The frontend emits several chunks, not one.** Four are eager (511.55 kB total); the rest arrive
  on navigation. Anything assuming a single asset filename needs checking.
- `make smoke-container` exists and runs in CI, but nothing in Sprint 018's acceptance list has
  actually been verified against a running image — non-root, persistence, read-only Calibre,
  healthcheck, signals.
- No backup script exists yet.

## Gotchas that will cost you an hour each

- **httpx normalizes `/../x` to `/x` before sending it.** A path-traversal test written the obvious
  way proves the client normalizes and nothing about the server. Use `%2e%2e` / `..%2f`.
- **Do not do `root.handlers = [handler]` in logging setup.** It removes pytest's `caplog` and
  breaks unrelated tests. `configure_logging` now replaces only the handler it installed.
- Radix `Tabs` writes `aria-controls` on every trigger whether or not a matching `TabsContent`
  exists; the import page had none at all.
- `@axe-core/playwright` is a dev dependency and must **not** go in `optimizeDeps` — that list is
  for runtime deps.
- Assert axe results as one-line strings; the raw violation objects produce a several-thousand-line
  diff on failure.
- An e2e test that wants a visible error state cannot "fail only the first request": the URL-sync
  effect re-keys the query on mount and the retry heals it first. Use a flag.
- Selector names that are not what you would guess: score options are `Score N`, the add search is
  `role="searchbox"`, the triage bulk controls are comboboxes.
- Everything Sprint 016 recorded still holds: every timing lives in `frontend/src/lib/motion.ts`;
  `layout`/`layoutId` are inert application-wide (DEC-030); import `m` from `motion/react`, not
  `motion/react-m`; `tailwindcss-animate` redefines `duration-*` to set `animation-duration`; and
  `setPrefersReducedMotion(false)` must come **before** `render`.
- Everything Sprint 015 recorded still holds: `eslint --max-warnings=0` means a component file
  exports components only; jsdom has neither Pointer Capture nor `scrollIntoView`; a Radix
  `AlertDialog` is addressed by its visible title.
- A new **runtime** dependency must be added to `optimizeDeps.include` in `vite.config.ts` or the
  dev server force-reloads mid-run and drops whatever Playwright was doing.

## Things noticed and deliberately left

- **`s` does nothing on `/triage`.** Product spec section 7 lists it as the shelf-autocomplete
  shortcut. `j`/`k`, digits, the status letters, `Enter` and `Escape` all work. Adding a shortcut is
  feature work, so Sprint 017 recorded it instead of slipping it in. It needs a sprint or an
  explicit decision that the spec was aspirational.
- **Author sort is a given-name sort.** `sort_author` is `$.authors[0]` as providers give it, so
  "Adolfo Bioy Casares" sorts before "Jorge Luis Borges". Correct against its own definition;
  probably not what the owner means by author order.
- **Metadata completeness is Sprint 019, and it is gated.** DEC-035 approves an *assessment*, not
  an implementation. **Do not start building cross-provider merging because the feature is
  "approved".** Phase A is allowed to conclude it is not worth building. Phase A does inherit a
  harness: `scripts/benchmark_library.py` already measures under a draining queue.
- Two long-standing observations are folded into 019: a provider "image not available" placeholder
  JPEG stored as a real cover, and `100 años de Soledad` (ISBN 9781516909629) having no cover.
- Entries added through the UI carry no score; the detail page shows an unset control.
- Imports land `unsorted`, so the library looks briefly as though the import did nothing. One click
  of "Accept all suggested" clears it.

## Walkthrough notes for whoever runs the next one

Run the backend with `BOOK_TRACKER_DATA_DIR` pointed at a throwaway directory rather than deleting
`data/`. The owner's `data/` was not touched this sprint. **Build fixture ISBNs by querying
`/api/search` first and copying the ISBN13s it returns** — invented ISBNs resolve to real but
unrelated editions and every cover comes out wrong, which looks exactly like a bug and is not one.
The import page needs `Preview import` clicked before a commit button exists, and provider search
takes about five seconds, so a four-second wait reports zero results.

## Provider recordings

`backend/tests/fixtures/providers/` holds verbatim responses captured from Open Library and Google
Books on 2026-08-09, with a README naming the exact URL behind each file. They exist because
DEC-025 forbids proving provider behavior with a mock of the method under test. **Never re-record
them silently** — a fixture is a pinned observation of an external contract, and quietly refreshing
one turns a regression test into a rubber stamp.

## State

- Planning revision 7; state points to Sprint 018, project status `ready`.
- Gates at close: validator passed, `make check` passed, `make test` backend **164** / frontend
  **74**, Chromium e2e **73 passed / 2 skipped**, `make build` succeeded (no chunk-size warning),
  `git diff --check` clean.
- The two skipped e2e tests are `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a
  live backend. Run them with
  `BOOK_TRACKER_E2E_BACKEND=http://127.0.0.1:8100 LIVE_METADATA_MODE=add npx playwright test e2e/live-metadata.spec.ts`.
- Migration head is `0007_normalized_sort_projection`.
- `.env` exists locally with the owner's `GOOGLE_BOOKS_API_KEY` and is gitignored. `make dev-backend`
  does not load it; export it yourself for a walkthrough.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
