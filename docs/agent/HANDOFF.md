# Handoff — current reality

**Last completed:** Sprint 021 (attachments, both phases), 2026-08-14.
**Next:** Sprint 022 (attachment lifecycle) — status `ready`, file at
`docs/sprints/022-attachment-lifecycle.md`.

## Read this first

**Attachments shipped and they are content-addressed** (DEC-048). A blob lives at
`data/attachments/{sha256[:2]}/{sha256}` and the uploaded filename is held in the database, never on
disk. Four things follow, and all four are load-bearing: identical bytes cost one blob; the path is
the digest, so integrity is free; the backup's hardlink sharing is correct by definition; and
**traversal is structural, not filtered** — no caller-supplied string reaches the filesystem, which
is why the `%2e%2e` tests pass without a filter to maintain. Do not "simplify" this to
`{item_id}/{filename}`.

**The backup shares attachment blobs and the fallback chain matters.** Link from the live store;
failing that, link from a sibling backup; copy only if neither works. The middle step is not an
optimisation — **Compose mounts `/data` and `/backups` as separate volumes, so the live-store link
fails `EXDEV` on every single run in the real deployment.** The first version had only the first and
third steps and silently wrote a full copy nightly, 67.9x instead of 10.5x, with every gate green,
because every test runs inside one filesystem. Sprint 021's walkthrough caught it; the regression
test monkeypatches `os.link` to fail the way a volume boundary does.

**Attachments are not compressed and not tarred, deliberately.** DEC-047 measured gzip's ratio on an
epub corpus at **1.0003** — the archive comes out larger than the input — while costing 20.4s per
backup against 2.0s. A tar also shares nothing with the tar written the night before, which is
exactly what makes the naive design cost seven copies.

**An attachment is an opaque file, or it is a reader.** That line is the scope boundary and it held:
no format parsing, no in-browser reading, no reading progress, no device sync. Reading an uploaded
epub's OPF as a metadata provider is named in DEC-047/048 as the natural next step precisely so it
is recognised rather than smuggled in.

**Undo retains an item that carries an attachment**, the way it already retains one whose fields
were hand-edited. Without that guard, undoing an import destroys an uploaded file. **That is a guard,
not a fix** — see below.

**Sprint 022 exists because nothing reclaims an orphaned blob** (DEC-049).
`delete_blob_if_unreferenced` has exactly one caller, so three routes leak bytes with nothing able to
find them: the `CASCADE` on item delete, a crash between `store_blob` and the row insert, and an item
orphaned by entry deletion. At 2.5 MB a file this is not the 39 KB orphaned cover the product spec
waved through. The sprint also carries rename, a confirmation on remove (the product spec says
deletes confirm, and *Delete entry* on the same page does), and streaming — upload and download both
hold the whole file in memory, 25 MiB per request. **Multiple selection, drag-and-drop and progress
bars are explicit non-scope**: real improvements, but polish rather than correctness, and the owner
asked for no creep.

**Provider order is settled and measured, not a preference.** Open Library first, Google Books only
where Open Library misses: 1,333 Google calls per 5,000 books against 5,000 the other way, and 100%
of Open Library's answers verifiable against Google Books' 80.4%. Do not reorder them without new
measurements.

**Daily provider budgets exist and name nobody** (DEC-045). `ProviderQuota`, migration `0009` and
the enrichment loop are all provider-agnostic; limits live in `Settings.provider_daily_limits`
(default `{"googlebooks": 900}`). Two rules to keep: exhaustion **defers** (`JobRepository.defer`,
which does not touch `attempts`) because `fail` dead-letters at the retry ceiling and would destroy
a large import's backlog; and interactive search is **counted but never blocked**.

**A provider record is merged only when it can be tied to the identifier that was requested**
(DEC-044). Verification is a tri-state and **unverifiable is rejected exactly like contradicted**,
because the observed failure was a wrong *work*, not a wrong printing. `ItemPayload.edition_match`
carries the verdict. **Sprint 024 inherits this contract.**

**A green test suite is not evidence about the shipped artifact.** Sprint 018's walkthrough found
the production bundle had been a blank page since Sprint 017 with every gate green; Sprint 021's
found the backup copying what it claimed to share. Run `npm run test:e2e` (both projects), and
remember `docker build -t akasha:local .` — `make build` builds the wheel and the frontend, **not
the image**, so a walkthrough against a stale image tests the previous commit.

**Migrations run at startup and take an online backup first** (DEC-039), exercised for real again in
Sprint 021's walkthrough: a copy at `0006` was backed up and taken to `0010` unattended. Backups live
outside the data volume (DEC-040); retention is label-scoped.

**`book_tracker/__init__.py` is deliberately empty.** It used to re-export `create_app`, which made
`akasha-backup restore` fail on a missing `USER_AGENT_CONTACT`. Import `create_app` from
`book_tracker.main`.

**The package stays `book_tracker` and the entities stay `items`/`entries`** regardless of the Akasha
brand or of future domains (`AGENTS.md`, DEC-042). Do not rename them.

## Plan shape

| Sprint | Scope | Status |
|---|---|---|
| 022 | Attachment lifecycle | `ready` |
| 023 | Creator sort names | `planned` |
| 024 | Export | `planned` |
| 025–027 | Domains: albums (**gated**), games, series (**gated**) | `planned` |

Only 022 has a sprint file. **The tail renumbered at plan revision 9** (DEC-049) to fit Sprint 022 in
ahead of the existing plan — the same forced renumber DEC-042 hit, because the validator requires
`active_sprint == len(completed_sprints) + 1`. The rest are contracts in `ROADMAP.md` and get expanded from
`TEMPLATE.md` when activated — the closing agent of the prior sprint does that, and
`validate_project.py` fails if it is skipped.

## Provider recordings

`backend/tests/fixtures/providers/` holds verbatim responses captured from Open Library and Google
Books, with a README naming the exact URL behind each file. **Never re-record them silently** — a
fixture is a pinned observation of an external contract.

Sprint 021 added and re-recorded none. Sprint 020 **added** two files (`googlebooks_isbn_9780307474728.json`, the confirmed-edition case,
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
  The head is now `0010_attachments`.
- **`make build` does not build the container image.** It builds the wheel and the frontend bundle.
  A walkthrough needs `docker build -t akasha:local .` first, or it exercises the previous commit —
  this cost half an hour in Sprint 021, twice, and looked like the fix not working.
- **`/tmp` on this machine is tmpfs.** Any measurement of disk or wall time must set `TMPDIR` to a
  path on real storage, or the numbers are RAM-speed fiction.
- `scripts/assess_attachment_cost.py` keeps its corpus under `assess-corpus` / `assess-payload`
  precisely so the shipped backup ignores it and all seven hypothetical strategies stay comparable.
- **`JobRunner.tick` routes every unrecognised handler state to `fail`.** A handler that returns a
  new state must be given a branch there, or the runner undoes whatever the handler just did one
  layer above where a handler-level test is looking. This is exactly how the quota deferral broke.
- **The shared provider client has a hard 5 s timeout** and Open Library regularly exceeds it — 11.3 s
  for one edition record during Sprint 020's walkthrough. `_bounded_json`, `_json`, `work_id` and
  `resolve_work` all take an optional `timeout` for paths that can afford to wait, and an `attempts`
  count for how patient they may be. **Patience is a UX decision, not a default** (DEC-046): 3
  attempts for background enrichment, 2 for the cover chooser, **1 for search**. A new provider call
  on an interactive path should ask for fewer, not inherit `PROVIDER_ATTEMPTS`.
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
  their website stays up. **Now handled, not unowned** (DEC-046): transient failures are retried
  with jittered backoff, and — the repair that mattered more — a failed job's retry is scheduled
  into the future instead of for *now*, so an outage no longer burns three attempts in three seconds
  and dead-letters the book permanently. What remains unhandled is an outage longer than the backoff
  window, which still exhausts a job; DEC-046 names the fix and why it was not built yet.
- **Provider search silently degrades to a single provider.** The client timeout is a hard 5 s while
  Open Library's search plus its year-resolution fan-out routinely exceeds it, so `/api/search`
  returns **Google Books only**. The user sees fewer and worse results with no indication anything
  failed. Still unfixed, and deliberately so: DEC-046 gives search **no retries at all**, because
  spending its 5 s budget on a second attempt returns nothing sooner and nothing better. If this is
  ever addressed it wants a visible signal, not more patience.
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
- **Re-uploading identical bytes under a different name renames the existing attachment** instead of
  adding a second row. Deliberate — `(item_id, sha256)` is unique, last name wins — but it silently
  changes a name the owner chose, and it surprised the walkthrough.
- **No cover file is ever unlinked when an item is deleted.** Unchanged. Product spec open question 2
  justified that with "covers are ~50KB each"; it now says so explicitly rather than implying the
  same is true of a 2.5 MB attachment. Attachment blobs *are* reclaimed, by refcount.
- **No `createObjectURL` anywhere in the frontend**, so the classic blob-URL leak does not exist
  here. Checked during the DEC-049 review; keep it that way if a preview is ever added.
- `disabled={remove.isPending}` is on every Remove button, so removing one file disables all of
  them, and the `sr-only` file input is focusable with the same accessible name as its button — two
  tab stops for one action. Both are Sprint 022's.
- **The attachment download is `Cache-Control: immutable` for a year with no validator, while the
  filename is mutable.** A re-upload of identical bytes under a new name renames the row, so an
  already-downloaded file keeps its old name. Rename and caching are one question, not two.
- Entries added through the UI carry no score until you set one.

## State

- Planning revision 9; state points to Sprint 022, project status `ready`.
- Gates at Sprint 021's close: validator passed, `make check` passed, `make test` backend **293** /
  frontend **95**, Playwright **79 passed / 2 skipped** across both projects, `make build` with no
  chunk-size warning, `docker build` + `make smoke-container` passed, `git diff --check` clean.
- The two skipped e2e tests are `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a live
  backend.
- **`v1.0.0` exists** as an annotated local tag at `4ccf431`. Nothing has been pushed;
  `git push origin v1.0.0` publishes it.
- Image `akasha:local`, user 10001:10001, no Node, `STOPSIGNAL SIGTERM`.
- **Migration head is `0010_attachments`.** The repo's own `data/books.db` is still at `0006`, so the
  next container start against it backs up and migrates four revisions. Exercised for real against a
  copy in Sprint 021's walkthrough.
- `.env` exists locally with the owner's `GOOGLE_BOOKS_API_KEY` and is gitignored.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
