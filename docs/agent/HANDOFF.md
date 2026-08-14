# Handoff — current reality

**Last completed:** Sprint 020 (metadata completeness), 2026-08-13.
**Next:** Sprint 021 (attachments) — status `ready`, file at `docs/sprints/021-attachments.md`.

## Read this first

**Sprint 021 is an assessment, not a build.** Phase A measures whether attaching arbitrary files is
affordable and Phase B builds only what the verdict *and an explicit owner go-ahead* justify. Phase A
concluding *no* is a complete, correct outcome. **Sprint 020 is the worked example**: its Phase A
concluded against the main feature, shipped two defect repairs, and closed as a complete sprint. Do
not read a gated sprint as permission to build.

**For Sprint 021 the measurement that scopes everything is backup growth.**
`ARCHIVED_DIRECTORIES = ("covers", "imports")` in `backup.py` tars everything into every backup,
seven nightly deep. A cover is **38.8 KB** measured; an epub is 1–5 MB. Either attachments go in the
tar under a size cap or they are excluded with a documented separate story, and that decision scopes
the feature.

**A Phase B from Sprint 020 is available and unstarted.** DEC-044 declined cross-provider field
completion but identified a cheap slice the owner has not yet ruled on: **cover choice from Open
Library work-record candidates**. The work record is *already fetched* during every enrichment and
lists 28 covers for Rayuela, 33 for *Cien años de soledad*, so candidate discovery costs zero extra
provider requests; only the thumbnails cost anything, and only on demand. It needs an explicit
go-ahead recorded in `docs/decisions.md` before anyone builds it.

**A provider record is merged only when it can be tied to the identifier that was requested**
(DEC-044). Verification is a tri-state — confirmed, contradicted, unverifiable — and **unverifiable
is rejected exactly like contradicted**. That is not squeamishness: the observed failure was a wrong
*work*, not a wrong printing, so merging "only the safe fields" would have preserved the worst error.
`ItemPayload.edition_match` carries the verdict, and it is `None` for payloads reached without a
requested ISBN. **Sprint 024 inherits this contract.**

**A green test suite is not evidence about the shipped artifact.** Sprint 018's walkthrough found the
production bundle had been a blank page since Sprint 017 with every gate green, because Playwright
ran only against the Vite dev server. There is a second Playwright project, `production-bundle`. Run
`npm run test:e2e` (both projects), not just `--project=chromium`.

**Migrations run at startup and take an online backup first** (DEC-039), and this was exercised for
real in Sprint 020's walkthrough: a copy at `0006` was backed up and taken to `0008` unattended.
Backups live outside the data volume (DEC-040); retention is label-scoped, so nightly backups expire
at seven and pre-migration backups are never pruned.

**`book_tracker/__init__.py` is deliberately empty.** It used to re-export `create_app`, which made
`akasha-backup restore` fail on a missing `USER_AGENT_CONTACT`. Import `create_app` from
`book_tracker.main`. Do not put imports back in the package init.

**The package stays `book_tracker` and the entities stay `items`/`entries`** regardless of the Akasha
brand or of future domains (`AGENTS.md`, DEC-042). Do not rename them.

## Plan shape

| Sprint | Scope | Status |
|---|---|---|
| 021 | Attachments, **gated** | `ready` |
| 022 | Creator sort names | `planned` |
| 023 | Export | `planned` |
| 024–026 | Domains: albums (**gated**), games, series (**gated**) | `planned` |

Only 021 has a sprint file. The rest are contracts in `ROADMAP.md` and get expanded from
`TEMPLATE.md` when activated — the closing agent of the prior sprint does that, and
`validate_project.py` fails if it is skipped.

## Provider recordings

`backend/tests/fixtures/providers/` holds verbatim responses captured from Open Library and Google
Books, with a README naming the exact URL behind each file. **Never re-record them silently** — a
fixture is a pinned observation of an external contract.

Sprint 020 **added** one file (`googlebooks_isbn_9780307474728.json`, the confirmed-edition case) and
re-recorded none. Worth knowing why: `googlebooks_isbn_9788437604572.json` turned out to *already*
contain the defect being investigated — its only hit carries a University of Michigan barcode and no
ISBN — and a live check confirmed the same volume still comes back. The fixture was evidence, not an
obstacle.

## Gotchas that will cost you an hour each

Deployment and container:

- **`chown 10001:10001` the data and backup directories.** Missing it surfaces as `attempt to write
  a readonly database`, which reads like corruption and is only permissions. Without root,
  `chmod -R 777` on a throwaway copy is enough for a walkthrough.
- Compose runs the image under tini, so a graceful stop exits **143**, not 0. Assert the application
  logged `Application shutdown complete`; the exit code proves nothing.
- **The SPA catch-all answers every unmatched path with index.html and a 200.** A test that fetches
  an asset and checks the status code passes even when the asset is missing. Check the content type.
- `restart: unless-stopped` turns any startup failure into a loop. Anything startup does as a side
  effect must be idempotent.
- **Vendor chunks are assigned by resolved package name, never by a hand-written list** (DEC-041).
  Any new grouping must be a package-name match with the fall-through to `vendor` intact, and must
  include its transitive members.
- `compose.yaml` requires `USER_AGENT_CONTACT`, and the owner's `.env` carries only
  `GOOGLE_BOOKS_API_KEY`. Export it in the shell for a one-off container.

Backend and tests:

- **Build fixture ISBNs by querying `/api/search` first.** Invented ISBNs resolve to real but
  unrelated editions and every cover comes out wrong.
- **An anonymous Google Books request is answered 429 immediately.** Export the key from `.env`;
  `make dev-backend` does not load it, though compose does.
- **httpx normalizes `/../x` to `/x` before sending it**, so the obvious path-traversal test proves
  the client normalizes and nothing about the server. Use `%2e%2e` / `..%2f`.
- Do not do `root.handlers = [handler]` in logging setup; it removes pytest's `caplog`.
- `ImportRepository.commit` has **two** return paths — the normal one and an already-committed replay
  rebuilt from the batch's persisted `counters`. Any field added to the commit response must be added
  to both.
- **The migration head is pinned by literal in three tests** — `test_migrations.py` (twice) and
  `test_backup.py`'s manifest assertion. A new migration fails all three until they are updated.
- Adding a migration that imports a domain function couples the two: stashing the function while the
  migration file is present breaks every test that runs migrations.
- **There is no `/api/jobs` listing endpoint.** `POST /api/enrichment/backfill` exists, and
  `/api/import/jobs/{job_id}` takes an id you already have, so job state during a walkthrough is read
  from the database.

Frontend and e2e:

- **The detail route is `/books/:entryId` and it takes an *entry* id, not an item id.** `/items/7`
  renders "Page not found", which looks like a broken build and is a wrong URL.
- Provider search takes about five seconds, and see the open observation below about what happens
  when it takes longer.
- The library card score picker is plain buttons whose accessible names are `Score 8`, not options.
  The card carries `data-provisional`, so a trigger selector needs `button[data-provisional]`.
- Radix `Tabs` writes `aria-controls` on every trigger whether or not a matching `TabsContent`
  exists. Assert axe results as one-line strings.
- An e2e test that wants a visible error state cannot "fail only the first request": the URL-sync
  effect re-keys the query on mount and the retry heals it. Use a flag.
- A new **runtime** dependency must go in `optimizeDeps.include` in `vite.config.ts`.
- Motion: timings live in `frontend/src/lib/motion.ts`; `layout`/`layoutId` are inert (DEC-030);
  import `m` from `motion/react`; `setPrefersReducedMotion(false)` must precede `render`.
- `/triage` shows two headings matching `/inbox/i` when the inbox is empty. Address the `h1` by
  `level: 1`.

## Things noticed and deliberately left

- **Provider search silently degrades to a single provider.** The client timeout is a hard 5 s while
  Open Library's search plus its year-resolution fan-out routinely exceeds it, so `/api/search`
  returns **Google Books only** — observed in Sprint 020's walkthrough searching *Pedro Páramo*. The
  user sees fewer and worse results with no indication anything failed. Unowned, and the most
  consequential of these.
- **Search offers a reprint above the original.** `merge_and_rank` puts a 1969 printing at rank 0 and
  a 2024 edition at rank 1 for *Pedro Páramo*; the 1955 original is not in the top eight. Deferred
  with a reason in DEC-044: it is search ranking, and changing it is user-visible product behaviour.
- **Open Library returns mojibake for some titles** — `Cc3mo Leer a Garcc-A Mc!Rquez`. Upstream
  corruption this project cannot fix, but could detect.
- **Publisher can arrive quoted**: the detail page reads `"O'Reilly Media, Inc."`, quotes included.
- **Author sort is a given-name sort.** `sort_author` is `$.authors[0]` as providers give it —
  Sprint 022, where the Spanish double-surname problem needs a stored sort name.
- **The *Add shelves* bulk action in product spec section 7 is unbuilt and unowned** (DEC-043). If
  scheduled, it and the retired `s` shortcut are one feature and should be built together.
- Entries added through the UI carry no score until you set one.

## State

- Planning revision 8; state points to Sprint 021, project status `ready`.
- Gates at Sprint 020's close: validator passed, `make check` passed, `make test` backend **209** /
  frontend **83**, Playwright **75 passed / 2 skipped** across both projects, `make build` with no
  chunk-size warning, `make smoke-container` passed, `git diff --check` clean.
- The two skipped e2e tests are `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a live
  backend.
- **`v1.0.0` exists** as an annotated local tag at `4ccf431`. Nothing has been pushed;
  `git push origin v1.0.0` publishes it.
- Image `akasha:local`, user 10001:10001, no Node, `STOPSIGNAL SIGTERM`.
- **Migration head is `0008_plain_text_descriptions`.** The repo's own `data/books.db` is still at
  `0006`, so the next container start against it will back up and migrate two revisions.
- `.env` exists locally with the owner's `GOOGLE_BOOKS_API_KEY` and is gitignored.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
