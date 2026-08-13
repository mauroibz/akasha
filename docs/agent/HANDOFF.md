# Handoff — current reality

**Last completed:** Sprint 018 (container, backup, release), 2026-08-13.
**Next:** Sprint 019 (metadata completeness) — status `ready`, file at
`docs/sprints/019-metadata-completeness.md`. **It is gated. Read the gate before writing code.**

## Read this first

**Sprint 019 is an assessment, not a build.** DEC-035 approves measuring whether cross-provider
field completion and edition choice are affordable. Phase A concluding *no* is a complete, correct
outcome. Do not start Phase B without an explicit owner go-ahead recorded in `docs/decisions.md`.
Sprint 019 is also the last planned sprint: on close, follow `WORKFLOW.md`'s final-sprint rule.

**A green test suite is not evidence about the shipped artifact.** Sprint 018's walkthrough found
the production bundle had been a blank page since Sprint 017 — every gate green the whole time,
because Playwright ran only against the Vite dev server, which serves unbundled modules and cannot
express a chunking failure. There is now a second Playwright project, `production-bundle`, that
builds and loads a real bundle. Run `npm run test:e2e` (both projects), not just
`--project=chromium`, before believing anything about the frontend.

**Vendor chunks are assigned by resolved package name, never by a hand-written list** (DEC-041).
Rollup's object form assigns only the exact entry modules named and leaves their transitive runtime
unassigned. Any new grouping must be a package-name match with the fall-through to `vendor` intact,
and a group has to include its transitive members — `motion` means `framer-motion`, `motion-dom`
and `motion-utils`, and missing one of those produced a second, different cycle.

**Migrations run at startup and take an online backup first** (DEC-039). If the backup cannot be
written, startup fails rather than migrating. Any new migration therefore gets a rollback point for
free, and any new migration should assume it will run unattended on the owner's real data.

**Backups live outside the data volume** (DEC-040), on a `${BACKUP_DIR:-./backups}:/backups` mount.
`backup_dir` derives as a sibling of `data_dir`. Retention is label-scoped: nightly backups expire
at seven, pre-migration backups are never pruned.

**`book_tracker/__init__.py` is deliberately empty.** It used to re-export `create_app`, so
importing anything from the package built the whole FastAPI app — which made
`akasha-backup restore` fail on a missing `USER_AGENT_CONTACT`, on a bare machine being restored
onto. Import `create_app` from `book_tracker.main`. Do not put imports back in the package init.

## Plan shape

| Sprint | Scope | Status |
|---|---|---|
| 019 | Metadata completeness, **gated**, final sprint | `ready` |

## What Sprint 019 must know

- Phase A can measure against a **running container**, and `scripts/backup.sh` means an experiment
  that damages a library is recoverable. `scripts/benchmark_library.py` already measures at 10,000
  entries idle and with the queue draining; adding provider-request counting extends it rather than
  starting a harness.
- The sharp edge is on record: `GoogleBooksProvider.fetch_by_isbn` takes the first hit of an
  `isbn:` search, which is not guaranteed to carry the requested ISBN13. Merging its publisher or
  page count risks attaching one edition's data to another. Verification before merge is AC2.
- Both long-standing observations were seen again in Sprint 018's walkthrough: a provider "image
  not available" placeholder stored as a real cover, and search for *Pedro Páramo* offering a 2024
  reprint above the 1955 original.
- Anything user-visible needs the `production-bundle` project **and** a container walkthrough.

## Gotchas that will cost you an hour each

- **`chown 10001:10001` the data and backup directories.** Missing it surfaces as `attempt to write
  a readonly database`, which reads like corruption and is only permissions. This cost the most
  time in Sprint 018.
- Compose runs the image under tini, so a perfectly graceful stop exits **143**, not 0. Assert the
  application logged `Application shutdown complete`; the exit code proves nothing.
- **The SPA catch-all answers every unmatched path with index.html and a 200.** A test that fetches
  an asset and checks the status code passes even when the asset is missing. Check the content type.
- `restart: unless-stopped` turns any startup failure into a loop. Anything startup does as a side
  effect must be idempotent — the pre-migration backup was not, and wrote ten copies in ninety
  seconds.
- The library card score picker is plain buttons whose accessible names are `Score 8`, not options.
  Add-page results are buttons wrapping the whole card; clicking one selects it, and a separate
  `Add to library` confirms. Notes and shelves live in the `Edit opinion` dialog, not on the page.
- Provider search takes about five seconds. A four-second wait reports zero results and looks like
  a bug.
- **Build fixture ISBNs by querying `/api/search` first.** Invented ISBNs resolve to real but
  unrelated editions and every cover comes out wrong.
- **httpx normalizes `/../x` to `/x` before sending it**, so the obvious path-traversal test proves
  the client normalizes and nothing about the server. Use `%2e%2e` / `..%2f`.
- Do not do `root.handlers = [handler]` in logging setup; it removes pytest's `caplog`.
- Radix `Tabs` writes `aria-controls` on every trigger whether or not a matching `TabsContent`
  exists. Assert axe results as one-line strings, or a failure is a several-thousand-line diff.
- An e2e test that wants a visible error state cannot "fail only the first request": the URL-sync
  effect re-keys the query on mount and the retry heals it. Use a flag.
- Everything Sprint 016 recorded still holds: timings live in `frontend/src/lib/motion.ts`;
  `layout`/`layoutId` are inert (DEC-030); import `m` from `motion/react`; `tailwindcss-animate`
  redefines `duration-*`; `setPrefersReducedMotion(false)` must precede `render`.
- Everything Sprint 015 recorded still holds: `eslint --max-warnings=0` means a component file
  exports components only; jsdom has neither Pointer Capture nor `scrollIntoView`; a Radix
  `AlertDialog` is addressed by its visible title.
- A new **runtime** dependency must go in `optimizeDeps.include` in `vite.config.ts` or the dev
  server force-reloads mid-run and drops whatever Playwright was doing.

## Things noticed and deliberately left

- **`s` does nothing on `/triage`.** Product spec section 7 lists it as the shelf-autocomplete
  shortcut. Every other triage key works. It needs a sprint or a decision that the spec was
  aspirational.
- **Author sort is a given-name sort.** `sort_author` is `$.authors[0]` as providers give it, so
  "Adolfo Bioy Casares" sorts before "Jorge Luis Borges".
- Entries added through the UI carry no score until you set one; imports land `unsorted`, so the
  library looks briefly as though the import did nothing.
- **No v1 tag exists.** The owner declined it in Sprint 018. `docs/operations/release-notes-v1.md`
  has the one-line command if that changes.

## Provider recordings

`backend/tests/fixtures/providers/` holds verbatim responses captured from Open Library and Google
Books on 2026-08-09, with a README naming the exact URL behind each file. They exist because
DEC-025 forbids proving provider behavior with a mock of the method under test. **Never re-record
them silently** — a fixture is a pinned observation of an external contract, and quietly refreshing
one turns a regression test into a rubber stamp. This matters more in Sprint 019 than anywhere
else, because the whole sprint is about provider behaviour.

## State

- Planning revision 7; state points to Sprint 019, project status `ready`.
- Gates at close: validator passed, `make check` passed, `make test` backend **186** / frontend
  **74**, Playwright **75 passed / 2 skipped** across both projects, `make build` with no
  chunk-size warning, `make smoke-container` green, `git diff --check` clean.
- The two skipped e2e tests are `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a
  live backend.
- Image `akasha:local`, 242 MB, user 10001:10001, no Node, `STOPSIGNAL SIGTERM`.
- Migration head is `0007_normalized_sort_projection`.
- `.env` exists locally with the owner's `GOOGLE_BOOKS_API_KEY` and is gitignored. `make dev-backend`
  does not load it; export it yourself for a walkthrough. Compose does load it.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
