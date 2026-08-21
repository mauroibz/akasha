# Handoff — current reality

**Sprint 030 is closed: the entry-depth verdict is flat, and nothing was built.** Plan revision
**13**. The worktree is clean, every gate is green, and **Sprint 031 — the plan's last sprint — is
`ready`** with its file expanded (`docs/sprints/031-per-domain-imports.md`).

**DEC-077, in one paragraph.** A child of an entry does not need state of its own. MusicBrainz
hands depth over as metadata on the parent (re-measured live 2026-08-20: one `inc=recordings`
parameter, no extra request, tracklist identical to the 2026-08-15 capture); IGDB's would-be
children are siblings with typed edges. Shape (c) — real child entities — is rejected on evidence:
the only shape that taxes all nine shared surfaces, asked for by no measured provider. Depth, when
a domain needs it, is a per-domain `progress` field or a marker in provider `rows`. **A set is not
depth**: Harry Potter / Malazan are ordered shelves, deferred alongside product spec §11 item 4,
which now points at `docs/entry-depth-verdict.md`. The flat-entry contract is guarded by
`backend/tests/test_flat_entry_contract.py` — a parent pointer on `entries` fails CI.

**Two honest gaps, carried in the verdict and DEC-077.** TMDB and IGDB are **paper walks**: both
probed live to 401, no credentials available (owner asked, none supplied). The TMDB arm's first
draft was model memory; the owner challenged it and it was re-grounded against the published API
reference the same day — still documented, not observed. Closing each arm is a token plus two
requests; the TMDB future epic inherits that measurement as its first task. The Spotify epic got
the verdict's answer: saved tracks roll up to albums, never touch the entry model.

**The Phase B gate question is with the owner** (recommendation: NO — build nothing, proceed to
031). DEC-077's reopen conditions: a measured provider returning children with their own
user-facing state; the owner stating the Malazan sentence as a need; two domains' `progress`
vocabularies drifting.

## Do this first

**Claim Sprint 031** (`docs/sprints/031-per-domain-imports.md`). Its contract carries three jobs:
the `Importer` boundary beside the `Provider` protocol (generic `/api/import/{importer}/...`
routes, importers published over the API, validation against the target domain's own declaration,
conformance checks), **DEC-067 row 6** (manual entry honours the domain; `/add` gains the chooser
back truthfully), and **the user-facing account** (README *Importing and triage* section, importer
half of `docs/guides/adding-a-domain.md`). Calibre and Goodreads are re-expressed with **no
behavior change** — their existing suites are the regression net. **Closing it sets the project
`complete`** per `WORKFLOW.md`'s final-sprint rule; no tag, push or deploy without the owner
asking.

**You are on `main`**, ahead of `origin` by the Sprint 030 commits (measurement, claim, table,
verdict, close-out). DEC-053's branch arrangement was discharged at v1.2.0; 030 ran on `main` and
nothing says 031 needs a branch — decide deliberately and record it if you take one. Pushing is
the owner's call.

## What Sprint 029 left behind

**`/` is now the screen you search from and add from** (DEC-065, as built in DEC-073). One bar:
domain selector, input, **Add**. Typing filters the library over SQL and reaches no provider. A
provider is reached only when *all* of — still for ~800 ms measured from the last keystroke, at
least three characters, the URL caught up, the library query **succeeded** and is not refetching,
and it returned **zero** rows — and never twice for the same string in a domain. **Add** overrides
every clause. **Verify any change to this by counting requests, not by feel**: that is the
acceptance criterion, and DEC-044 measured a tier breach once already.

**Results render *below* the library, and that is load-bearing.** The library virtualizes against
the window, so a variable-height block *above* it moves the `scrollMargin` every row measures itself
against — the Sprint 013 class of bug. Below avoids it by construction. Moving the block above
re-opens it.

**`/add` is manual entry with no domain chooser**, honest rather than missing today:
`LibraryService.add` types a manual item as `DEFAULT_DOMAIN.item_type` whatever the client sends
(DEC-067 row 6). **Sprint 031 is where that lands** — its deliverable 4.

**The chrome no longer says "book"** (DEC-071). Twenty-four strings across eleven files. **AC9 is a
runnable command**, in the sprint file: grep `book` under `frontend/src`, excluding tests, comments,
the `/books/:entryId` route and the identifiers. It returns two lines, both JSX comment
continuations, and nothing that reaches a screen. Run it before claiming the criterion — it caught a
regression once already, when a `git checkout` used to undo a mutation test restored "Add a book".
**Do not `git checkout <file>` to undo a mutation test**; copy the file aside and copy it back.

**The second pass (DEC-074) changed five things on the screens, and two of them carry a judgement
call.** A `long_text` field spans both columns of the confirm step, split on the declared type the
way `DetailPage` splits `inlineFields` from `blockFields`. The bar clears in one press — box, `q`
and web results together — sharing one function with the successful-add path. An active query with
no rows gets one line rather than the tall empty state, which is kept for a library that really is
empty. The status chips became a **fourth filter** beside sort, shelf and format, built on
`FormatPicker`'s popover shape because the filter is multi-valued; **the counts moved into the
panel, and if they turn out to be read constantly the answer is to surface them in the trigger, not
to bring the row back**. Files is its own region on the detail page, at the weight of *Edit
opinion*, with the component no longer owning its frame.

**The domain restore answers to the URL, not to the mount**, and that is the repair for the last
defect the second pass found. The shell's *Library* link is `/` with no query, so pressing it while
already on the library strips `type` — and every list request names a domain, so a restore that ran
once per mount left the page loading forever. A URL without a `type` is the state the restore exists
to fix, whenever it occurs; writing the value back is its own guard. **A control that clears the
domain from the URL is therefore already covered.** Held at the unit *and* e2e layers on purpose:
the unit layer alone missed this for a whole sprint because it never mounts the shell.

**Deliverable 6 needed no new `Domain` field.** One neutral placeholder serves every domain, so the
backend contract is untouched. The field is still the right shape the day a domain actually needs
different copy — DEC-073 says no domain needs it yet, not that it is disallowed.

## Read this first

**The domain contract is written down, twice.** `docs/specs/technical-spec.md` **section 6.6** is the
binding contract; **`docs/guides/adding-a-domain.md`** is how to satisfy it — diagrams, a nine-row
table of the whole job, the step-by-step, and a worked verdict. **Read those instead of reading how
albums were built.** Sprints 025–027 are history, not instructions, and their file paths predate
Sprint 028's move.

**`docs/README.md` is the documentation map**, and it labels every document canonical, historical or
proposal. `CONTRIBUTING.md` is the human entry point; `AGENTS.md` still governs agent sessions.

**A third domain now costs** (DEC-069): its own package under `backend/src/book_tracker/domains/`,
one entry in `DOMAINS`, its provider wired in the lifespan, three lines in the published enums, one
cover-host allowlist line if its art is hosted somewhere new, and configuration if its provider needs
credentials. **No migration, and no edit to another domain's files.**

**The layout, as of Sprint 028:**

- `domain/spec.py` — what a domain *is*: `Domain`, `FieldSpec`, `StatusSpec`, `FormatSpec`, the
  validators, `UrlMatch`, `split_url`. No domain lives here.
- `domain/registry.py` — which domains exist: `DOMAINS`, `DEFAULT_DOMAIN`, and the three published
  unions `EntryStatus` / `EntryFormat` / `ItemTypeName`.
- `domains/book/` — its declaration, `providers.py` (Open Library, Google Books), `goodreads.py`,
  `calibre.py`.
- `domains/album/` — its declaration and `providers.py` (MusicBrainz, Cover Art Archive).
- `infrastructure/providers.py` — the shared HTTP boundary only: `bounded_json`, `parse_year`, the
  retry policy, `create_provider_client`. It is 153 lines, down from 701.

**Five rules the code depends on:**

- **`Domain` has no book-shaped defaults any more.** `statuses`, `default_status`, `entry_fields`,
  `formats` and `entry_panel_label` are required; `chooses_covers` defaults to `False`. A domain that
  omits one now fails to construct rather than silently inheriting books' vocabulary.
- **A write is validated against the item's own domain**, in `LibraryService._validated`, refused
  with a 422 naming the domain. **There is no CHECK constraint behind it** — migration `0014` dropped
  `ck_entries_status` (DEC-067 row 1), so `validate_status` is the only authority and is strictly
  stronger than the constraint was.
- **`_filter_key` must list every filter.** It is what a keyset cursor is bound to; forgetting the
  next one is a silent paging bug, not a test failure.
- **A recognizer must answer for any string and never raise.** `resolve_input` asks every domain in
  turn, so one that raises denies every domain after it its turn. Parse through `split_url`. The loop
  isolates a raising recognizer as well, and the conformance suite refuses one.
- **A migration must never import the live registry.** `0013` did, so two installs applying the same
  revision a month apart could build different constraints. Both status lists are frozen literals.

**`backend/tests/test_domain_conformance.py` is the gate on all of it.** It is parametrized over
`DOMAINS`, so a domain is held to the contract *by existing*. Its checks split into what a domain
satisfies alone and whether the core can host it, and it must be able to fail — malformed domains are
declared inside the file for exactly that. **Adding a field to `Domain` without adding a check fails
`test_the_suite_covers_every_field_of_the_contract`.** That is intended.

## What Sprint 028 left behind

- **DEC-067** prices every coupling a third domain pays, one costed fork per row. **Rows 2, 4, 8 and
  10 recommend doing nothing** and are deliberate couplings that stay: the hand-spelled unions (three
  type-safe lines a test refuses to let drift), the central cover-host allowlist (central so a domain
  cannot widen it), the `/books/:id` route for every domain, and the book-shaped fallback vocabulary
  in `labels.ts` — which is now a **`Partial` record**, so a new domain needs no entry there and an
  unknown status renders its stored value. Do not "fix" these without re-reading why.
- **Row 3 is the one live risk left.** Enrichment is still ISBN-keyed below the `enriches` flag
  (`_backfillable_items`, `_fetch`, `PROVIDER_ORDER`). Albums declare `enriches=False`, so **no domain
  has ever exercised that seam**. The first domain wanting background enrichment on another key pays
  for it then, with a real case to design against.
- **DEC-068** is the IGDB paper walk: no seventh seam, but the first adapter needing mutable state
  and a secret pair (Twitch OAuth with refresh). It is **reasoned from published docs, not measured**,
  and carries the list of what to verify first. Do not cite it as measurement.
- `Domain.chooses_covers` gates the cover chooser. The shared chooser is still Open Library's
  work-editions path, so the conformance suite refuses a domain that declares it without preferring
  that source. Generalising the *mechanism* is DEC-067 row 7 option (b) and nothing needs it yet.
- `/api/health/providers` rows are derived: order from each domain's `identity.source_preference`,
  rows from the lifespan's provider catalog, reason from the provider. They now read
  `openlibrary`, `googlebooks`, `musicbrainz`.

## Known and left, in the order they are likely to bite

- **Stop the container before running the e2e suite.** The dev server proxies `/api` to
  `localhost:8000`, so a container left running there answers every request a spec forgot to stub —
  with the real dev library. `add-detail.spec.ts`'s stagger test then clicks a real *Rayuela* card
  instead of the web result and fails three runs out of three, looking exactly like a regression.
  It reproduces against older source, which is how to tell it apart from one (DEC-074).
- **The dev library at `data/` is 16 entries**, up from 13. The Sprint 029 walkthrough added *The
  Left Hand of Darkness* (19), *Selected Ambient Works 85–92* (20), *Kid A* (21) and *OK Computer*
  (22), tagged **`v1.2.0`**, two of them carrying a `Walkthrough, sprint 029.` note, and created a
  shelf named **Walkthrough** (id 5). Left in place rather than deleted; the pre-walkthrough
  database is at `backups/pre-sprint029-20260816T042730Z/books.db`. Migration head is still `0014`.
- **`data/` has been made group/other-writable and the container has been run against it.** Files the
  container creates are owned by uid 10001; hand ownership back with
  `docker run --rm --user 0 -v "$PWD/data:/data" akasha:local chown -R 1000:1000 /data`.
- **`README.md` describes both domains now** (it was book-only until the merge). Its screenshots
  under `docs/brand/screenshots/` predate Sprint 029 and still show the old library chrome — the
  status chip row and the separate add screen. Nothing depends on them; they are stale, not wrong
  about anything a reader would act on.
- **The Inbox label is ambiguous on `/`**: the header badge and each domain's `unsorted` chip all read
  "Inbox". Correct in each place, confusing together. Unscheduled.
- **Release selection is still arbitrary between same-day originals** — resolving a "Kind of Blue"
  release-group URL returns the Swiss Blues Authority record. Stable but not meaningful.
- **A provider fetch can fail at add time.** One album add in the Sprint 029 walkthrough returned
  **502** from `POST /api/entries` (MusicBrainz, at the payload fetch); the identical retry returned
  201. The dialog stays open and the error is shown, which is right, but the failure is invisible in
  any test because it is upstream. Watch it if album adds start failing more often.
- The import layer is still book-only above the domain packages — `application/imports.py` and
  `api/imports.py`. That is Sprint 031's whole outcome. Its *copy* is neutral already.
- `data/covers/` holds two stale `cover-*.jpg.tmp` files from an interrupted install; harmless.
- One dev-library item has **`OL14454691A` as its creator**; item 7 stores `"O'Reilly Media, Inc."`
  **with the quotes**. Both pre-existing.
- The list API takes repeated `status=`, `shelf=`, `format=` and `type=`; an unknown parameter is
  ignored silently, while an unknown *value* for any of the four is a 422.
- `HEAD` on any route returns 405, application-wide.
- "Replace cover" on the detail page is still a raw unstyled `<input type=file>`.
- The orphaned cover file is still not collected; the reclaim is scoped to attachments on purpose.
- `e2e/triage.spec.ts` "animates its action bar but not under reduced motion" flaked once several
  sprints ago and has passed every run since. Motion sampling timing; watch it.

## State

Migration head `0014_status_is_the_domains`. Released **v1.2.0**; `main` carries the Sprint 030
close-out commits, not yet pushed to `origin` — pushing is the owner's call. The worktree is clean.
`sprint-025-albums` is kept as history rather than deleted.
