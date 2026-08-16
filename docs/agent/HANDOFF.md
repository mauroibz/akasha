# Handoff — current reality

**Sprint 029 (one search bar) is `in_progress`, and all of its code and verification are
done.** What remains is documentation and the close. Plan revision **12**.

## Do this first

**Finish Sprint 029's documentation.** Nothing is broken and nothing is half-built; the
worktree is clean and every gate is green. The remaining work is listed at the end of the
2026-08-16 worklog entry, and it is:

1. **Product spec section 7** still describes `/add` as the screen you search from. It is
   the manual-entry route now; searching and adding happen on `/`.
2. **Technical spec sections 7.1 and 8** describe the two debounces (250 ms library,
   300 ms provider). The library's 250 ms is unchanged; the provider search is now the
   settled-and-empty rule instead — ~800 ms still, at least three characters, the URL
   caught up, the library answered, and it answered with zero rows, never twice for the
   same string, with **Add** as the override.
3. **A decision entry** is owed. Four things want recording: the firing rule as actually
   built; `/add` losing its domain chooser; the results rendering *below* the library
   rather than above; and deliverable 6 needing **no new `Domain` field** after all.
4. Then the sprint `Outcome`, the ROADMAP impact review, `state.json`, this file, and
   `docs(sprint-029): close sprint and hand off`.

**The album work merges into `main` after 029 closes (DEC-072)** — that is the next thing
after the close, and two things go in with it: `README.md`'s feature copy stops being
book-only, and `docs/operations/release-notes-v1.2.md` is written, following the v1 and v1.1
precedent.

**You are on branch `sprint-025-albums`, not `main`.** Sprints 025 through 028 closed there and 029
is running there; forty-odd commits are local and nothing has been pushed. The branch exists so
merging is a deliberate act (DEC-053, amended by DEC-061, DEC-063 and DEC-066).

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

**The chrome no longer says "book"** (DEC-071, built in 029). It was twenty-four strings across
eleven files, not the eighteen across eight the sprint file first claimed. **AC9 is a runnable
command**, in the sprint file: grep `book` under `frontend/src`, excluding tests, comments, the
`/books/:entryId` route and the identifiers. It returns two lines, both JSX comment continuations,
and nothing that reaches a screen. Run it before claiming the criterion — it caught a regression
once already, when a `git checkout` used to undo a mutation test restored "Add a book".

**The music release is not gated on a third domain** (DEC-071). A release waits for a feature, not
for a validation exercise — and it is now scheduled for right after 029 (DEC-072).

## Read this first

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

- **The dev library at `data/` is 16 entries**, up from 13. The Sprint 029 walkthrough added *The
  Left Hand of Darkness* (19), *Selected Ambient Works 85–92* (20), *Kid A* (21) and *OK Computer*
  (22), two of them carrying a `Walkthrough, sprint 029.` note, and created a shelf named
  **Walkthrough** (id 5). Left in place rather than deleted; the pre-walkthrough database is at
  `backups/pre-sprint029-20260816T042730Z/books.db`. Migration head is still `0014`.
- **`data/` has been made group/other-writable and the container has been run against it.** Files the
  container creates are owned by uid 10001; hand ownership back with
  `docker run --rm --user 0 -v "$PWD/data:/data" akasha:local chown -R 1000:1000 /data`.
- **`README.md` describes a book-only *product* on purpose.** Its Development section now documents
  the domain structure, because that is true of this branch, but the feature copy still says books:
  the album domain has never been released or merged, and advertising it would describe something no
  user can run. Change that copy when the branch merges, not before.
- **The Inbox label is ambiguous on `/`**: the header badge and each domain's `unsorted` chip all read
  "Inbox". Correct in each place, confusing together. Unscheduled.
- **Release selection is still arbitrary between same-day originals** — resolving a "Kind of Blue"
  release-group URL returns the Swiss Blues Authority record. Stable but not meaningful.
- **The manual add path is still bound to `DEFAULT_DOMAIN`** (DEC-067 row 6). Sprint 029 removed
  `/add`'s domain chooser rather than leaving it lying: it showed a record's statuses and fields and
  then wrote a book. Giving manual entry a real domain is unscheduled and needs an API change.
- **A provider fetch can fail at add time.** One album add in the Sprint 029 walkthrough returned
  **502** from `POST /api/entries` (MusicBrainz, at the payload fetch); the identical retry returned
  201. The dialog stays open and the error is shown, which is right, but the failure is invisible in
  any test because it is upstream. Watch it if album adds start failing more often.
- The import layer is still book-only above the domain packages — `application/imports.py` and
  `api/imports.py`. That is Sprint 031's whole outcome.
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

Migration head `0014_status_is_the_domains`. Worktree clean; all commits local on
`sprint-025-albums`, nothing pushed.
