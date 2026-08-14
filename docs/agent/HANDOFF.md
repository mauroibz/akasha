# Handoff — current reality

**Last completed:** Sprint 020 (metadata completeness, both phases), 2026-08-13.
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

**Sprint 020's Phase B is done.** The owner gave the go-ahead in DEC-045 and the sprint reopened
to build it rather than spawning a new one — worth knowing, because it is the precedent for how a
gated sprint's Phase B is handled here. Cross-provider metadata completion stays **abandoned**.

**Provider order is settled and measured, not a preference.** Open Library first, Google Books only
where Open Library misses: 1,333 Google calls per 5,000 books against 5,000 the other way, and 100%
of Open Library's answers verifiable against Google Books' 80.4%. Do not reorder them without new
measurements.

**Daily provider budgets exist and name nobody** (DEC-045). `ProviderQuota`, migration `0009` and
the enrichment loop are all provider-agnostic; limits live in `Settings.provider_daily_limits`
(default `{"googlebooks": 900}`), so a metered provider added in a domain sprint is a config entry.
Two rules to keep: exhaustion **defers** (`JobRepository.defer`, which does not touch `attempts`)
because `fail` dead-letters at the retry ceiling and would destroy a large import's backlog; and
interactive search is **counted but never blocked**, since the last request of a day belongs to
someone waiting for a result.

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

Sprint 020 **added** two files (`googlebooks_isbn_9780307474728.json`, the confirmed-edition case,
and `editions_OL14860424W.json`, the work behind the Rayuela edition) and re-recorded none. Worth knowing why: `googlebooks_isbn_9788437604572.json` turned out to *already*
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
  The head is now `0009_provider_usage`.
- **`JobRunner.tick` routes every unrecognised handler state to `fail`.** A handler that returns a
  new state must be given a branch there, or the runner undoes whatever the handler just did one
  layer above where a handler-level test is looking. This is exactly how the quota deferral broke.
- **The shared provider client has a hard 5 s timeout** and Open Library regularly exceeds it — 11.3 s
  for one edition record during Sprint 020's walkthrough. `_bounded_json`, `_json`, `work_id` and
  `resolve_work` all take an optional `timeout` for paths that can afford to wait.
- **`ProviderPayloadError` carries one type for two very different things.** `edition_not_found`
  means the provider answered and does not have it; `provider_unreachable` / `provider_http_error`
  mean it never answered. Branch on `code`, never on the type, or you will tell the reader their
  book has no editions when the provider is simply down.
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

- **Open Library's JSON API returns 503 under load**, repeatedly and for minutes at a time, while
  their website stays up. Sprint 020's walkthrough hit it throughout. Enrichment and the cover
  chooser both fail intermittently through no fault of ours, and **nothing retries**. Unowned, and
  the most consequential provider observation.
- **Provider search silently degrades to a single provider.** The client timeout is a hard 5 s while
  Open Library's search plus its year-resolution fan-out routinely exceeds it, so `/api/search`
  returns **Google Books only**. The user sees fewer and worse results with no indication anything
  failed. Sprint 020 gave the cover chooser its own longer timeout and deliberately did **not** fix
  search.
- **An Open Library placeholder cover cannot be detected by geometry.** DEC-044's rule catches
  Google Books' 6.25:1 banner; Open Library's "No image available" is portrait and ordinarily sized
  and sails through. `default=false` is the only reliable guard and `prepare_cover` now forces it
  for that host. If a third image provider is ever added, assume its placeholder needs its own
  answer rather than inheriting either of these.
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
- Gates at Sprint 020's close: validator passed, `make check` passed, `make test` backend **235** /
  frontend **85**, Playwright **77 passed / 2 skipped** across both projects, `make build` with no
  chunk-size warning, `make smoke-container` passed, `git diff --check` clean.
- The two skipped e2e tests are `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a live
  backend.
- **`v1.0.0` exists** as an annotated local tag at `4ccf431`. Nothing has been pushed;
  `git push origin v1.0.0` publishes it.
- Image `akasha:local`, user 10001:10001, no Node, `STOPSIGNAL SIGTERM`.
- **Migration head is `0009_provider_usage`.** The repo's own `data/books.db` is still at `0006`,
  so the next container start against it will back up and migrate three revisions. That path was
  exercised for real in Sprint 020's walkthrough against a copy.
- `.env` exists locally with the owner's `GOOGLE_BOOKS_API_KEY` and is gitignored.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
