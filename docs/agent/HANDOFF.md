# Handoff — current reality

**Last completed:** Sprint 019 (post-v1 polish), 2026-08-13.
**Next:** Sprint 020 (metadata completeness) — status `ready`, file at
`docs/sprints/020-metadata-completeness.md`.

## Read this first

**Sprint 020 is an assessment, not a build.** DEC-035 approves measuring whether cross-provider
field completion and edition choice are affordable; DEC-042 made that gate shape the default for
Sprints 021, 024 and 026 too. Phase A concluding *no* is a complete, correct outcome. Do not start
Phase B without an explicit owner go-ahead recorded in `docs/decisions.md`.

**One item in Sprint 020 does not wait on the gate.** `GoogleBooksProvider.fetch_by_isbn` takes the
first hit of an `isbn:` search, which is not guaranteed to carry the requested ISBN13. DEC-042
promoted it to a live defect repaired whatever the verdict.

**A green test suite is not evidence about the shipped artifact.** Sprint 018's walkthrough found
the production bundle had been a blank page since Sprint 017 — every gate green the whole time,
because Playwright ran only against the Vite dev server, which serves unbundled modules and cannot
express a chunking failure. There is now a second Playwright project, `production-bundle`, that
builds and loads a real bundle. Run `npm run test:e2e` (both projects), not just
`--project=chromium`, before believing anything about the frontend.

**Migrations run at startup and take an online backup first** (DEC-039). If the backup cannot be
written, startup fails rather than migrating. Any new migration therefore gets a rollback point for
free, and should assume it will run unattended on the owner's real data. Backups live outside the
data volume (DEC-040) on a `${BACKUP_DIR:-./backups}:/backups` mount; retention is label-scoped, so
nightly backups expire at seven and pre-migration backups are never pruned.

**`book_tracker/__init__.py` is deliberately empty.** It used to re-export `create_app`, so
importing anything from the package built the whole FastAPI app — which made
`akasha-backup restore` fail on a missing `USER_AGENT_CONTACT`, on a bare machine being restored
onto. Import `create_app` from `book_tracker.main`. Do not put imports back in the package init.

**The package stays `book_tracker` and the entities stay `items`/`entries`** regardless of the
Akasha brand or of future domains (`AGENTS.md`, reaffirmed in DEC-042). Do not rename them.

## Plan shape

| Sprint | Scope | Status |
|---|---|---|
| 020 | Metadata completeness, **gated** | `ready` |
| 021 | Attachments, **gated** | `planned` |
| 022 | Creator sort names | `planned` |
| 023 | Export | `planned` |
| 024–026 | Domains: albums (**gated**), games, series (**gated**) | `planned` |

Only 020 has a sprint file. The rest are contracts in `ROADMAP.md` and get expanded from
`TEMPLATE.md` when activated.

## What Sprint 020 must know

- Phase A can measure against a **running container**, and `scripts/backup.sh` means an experiment
  that damages a library is recoverable. `scripts/benchmark_library.py` already measures at 10,000
  entries idle and with the queue draining; adding provider-request counting extends it rather than
  starting a harness.
- Sprint 019's walkthrough saw both long-standing observations again in earlier sprints but did not
  re-look for them: a provider "image not available" placeholder stored as a real cover, and search
  for *Pedro Páramo* offering a 2024 reprint above the 1955 original.
- `unsorted_entries` now rides on the import commit response, so an assessment can report triage
  state without a second query.
- **New in Sprint 019, and unowned:** a provider description containing HTML renders as literal
  markup on the detail page (`<p>To stay competitive…`). It is escaped, so it is a display decision
  rather than an injection risk, and it depends on which provider answered. It sits closest to this
  sprint's provider work.

## Provider recordings

`backend/tests/fixtures/providers/` holds verbatim responses captured from Open Library and Google
Books on 2026-08-09, with a README naming the exact URL behind each file. They exist because
DEC-025 forbids proving provider behavior with a mock of the method under test. **Never re-record
them silently** — a fixture is a pinned observation of an external contract, and quietly refreshing
one turns a regression test into a rubber stamp. This matters more in Sprint 020 than anywhere else,
because the whole sprint is about provider behaviour.

## Gotchas that will cost you an hour each

Deployment and container:

- **`chown 10001:10001` the data and backup directories.** Missing it surfaces as `attempt to write
  a readonly database`, which reads like corruption and is only permissions. This cost the most
  time in Sprint 018. Without root, `chmod -R 777` on a throwaway copy is enough for a walkthrough.
- Compose runs the image under tini, so a perfectly graceful stop exits **143**, not 0. Assert the
  application logged `Application shutdown complete`; the exit code proves nothing.
- **The SPA catch-all answers every unmatched path with index.html and a 200.** A test that fetches
  an asset and checks the status code passes even when the asset is missing. Check the content type.
- `restart: unless-stopped` turns any startup failure into a loop. Anything startup does as a side
  effect must be idempotent — the pre-migration backup was not, and wrote ten copies in ninety
  seconds.
- **Vendor chunks are assigned by resolved package name, never by a hand-written list** (DEC-041).
  Rollup's object form assigns only the exact entry modules named and leaves their transitive
  runtime unassigned. Any new grouping must be a package-name match with the fall-through to
  `vendor` intact, and must include its transitive members — `motion` means `framer-motion`,
  `motion-dom` and `motion-utils`, and missing one produced a second, different cycle.
- `compose.yaml` requires `USER_AGENT_CONTACT`, and the owner's `.env` carries only
  `GOOGLE_BOOKS_API_KEY`. Export it in the shell for a one-off container rather than editing `.env`.

Backend and tests:

- **Build fixture ISBNs by querying `/api/search` first.** Invented ISBNs resolve to real but
  unrelated editions and every cover comes out wrong. Sprint 019 proved it again by ignoring it.
- **httpx normalizes `/../x` to `/x` before sending it**, so the obvious path-traversal test proves
  the client normalizes and nothing about the server. Use `%2e%2e` / `..%2f`.
- Do not do `root.handlers = [handler]` in logging setup; it removes pytest's `caplog`.
- `ImportRepository.commit` has **two** return paths — the normal one and an already-committed
  replay that rebuilds its answer from the batch's persisted `counters`. Any field added to the
  commit response must be added to both, or a re-commit answers a different shape.

Frontend and e2e:

- Provider search takes about five seconds. A four-second wait reports zero results and looks like
  a bug.
- The library card score picker is plain buttons whose accessible names are `Score 8`, not options.
  The card itself also carries `data-provisional`, so a selector for the trigger needs
  `button[data-provisional]`. Add-page results are buttons wrapping the whole card; clicking one
  selects it, and a separate `Add to library` confirms. Notes and shelves live in the
  `Edit opinion` dialog, not on the page.
- Radix `Tabs` writes `aria-controls` on every trigger whether or not a matching `TabsContent`
  exists. Assert axe results as one-line strings, or a failure is a several-thousand-line diff.
- An e2e test that wants a visible error state cannot "fail only the first request": the URL-sync
  effect re-keys the query on mount and the retry heals it. Use a flag.
- A new **runtime** dependency must go in `optimizeDeps.include` in `vite.config.ts` or the dev
  server force-reloads mid-run and drops whatever Playwright was doing.
- Motion: timings live in `frontend/src/lib/motion.ts`; `layout`/`layoutId` are inert (DEC-030);
  import `m` from `motion/react`; `tailwindcss-animate` redefines `duration-*`;
  `setPrefersReducedMotion(false)` must precede `render`.
- Components: `eslint --max-warnings=0` means a component file exports components only; jsdom has
  neither Pointer Capture nor `scrollIntoView`; a Radix `AlertDialog` is addressed by its visible
  title.
- `/triage` shows two headings matching `/inbox/i` when the inbox is empty — the `h1` and
  "Inbox is clear". Address the `h1` by `level: 1`.

## Things noticed and deliberately left

- **Author sort is a given-name sort.** `sort_author` is `$.authors[0]` as providers give it, so
  "Adolfo Bioy Casares" sorts before "Jorge Luis Borges" — Sprint 022, where the Spanish
  double-surname problem is why it needs a stored sort name rather than a heuristic.
- **The *Add shelves* bulk action in product spec section 7 is unbuilt and unowned.** DEC-043
  retired the `s` shortcut and named this in the same entry rather than quietly leaving it. If it is
  ever scheduled, it and `s` are the same feature from two angles and should be built together: one
  autocomplete surface, reachable from the action bar and from the keyboard. The bulk API is already
  there (`add_shelves`/`remove_shelves` on `PATCH /api/entries/bulk`); the surface is the work.
- **A provider description containing HTML renders as literal markup** on the detail page. Escaped,
  so cosmetic rather than dangerous. Publisher can also arrive quoted: `"O'Reilly Media, Inc."`.
- Entries added through the UI carry no score until you set one.

## State

- Planning revision 8; state points to Sprint 020, project status `ready`.
- Gates at Sprint 019's close: validator passed, `make check` passed, `make test` backend **187** /
  frontend **83**, Playwright **75 passed / 2 skipped** across both projects, `make build` with no
  chunk-size warning, `git diff --check` clean.
- The two skipped e2e tests are `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a
  live backend. `make smoke-container` was not re-run in Sprint 019; the walkthrough exercised a
  real container instead, including startup migration, backup and graceful shutdown.
- **`v1.0.0` exists** as an annotated local tag at `4ccf431`. Nothing was pushed;
  `git push origin v1.0.0` publishes it.
- Image `akasha:local`, user 10001:10001, no Node, `STOPSIGNAL SIGTERM`.
- Migration head is `0007_normalized_sort_projection`. The repo's own `data/books.db` is one
  migration behind, so the next container start against it will back up and migrate.
- `.env` exists locally with the owner's `GOOGLE_BOOKS_API_KEY` and is gitignored. `make dev-backend`
  does not load it; export it yourself for a walkthrough. Compose does load it.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
