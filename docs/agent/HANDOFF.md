# Handoff — current reality

**Last completed:** Sprint 028 (the domain contract), 2026-08-15. Both phases ran.
**Next:** Sprint 029 (one search bar) — status `ready`, file at
`docs/sprints/029-one-search-bar.md`. Plan revision **11**. Then Sprint 030 (per-domain imports),
which has no file yet. The plan ends there.

## Do this first

**You are on branch `sprint-025-albums`, not `main`.** Sprints 025 through **028** ran and closed
there; thirty-plus commits are local and nothing has been pushed. **Merging back is the owner's
decision** — that is the entire reason the branch exists (DEC-053, amended by DEC-061, DEC-063 and
DEC-066). Ask before merging.

**The domain contract is written down.** `docs/specs/technical-spec.md` **section 6.6** is the whole
of it: what a domain supplies, the rules each part must satisfy, what it may never touch, where its
code lives, what the core does for it, how it is verified. **Read that instead of reading how albums
were built.** Sprints 025–027 are history, not instructions.

**A third domain now costs** (DEC-069): its own package under `backend/src/book_tracker/domains/`,
one entry in `DOMAINS`, its provider wired in the lifespan, three lines in the published enums, one
cover-host allowlist line if its art is hosted somewhere new, and configuration if its provider needs
credentials. **No migration, and no edit to another domain's files.**

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
  in `labels.ts`. Do not "fix" these without re-reading why.
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

- **The dev library at `data/` is 13 entries**, books plus *Discovery*, *Kind of Blue* and *Humanz*.
  Migrated to `0014` on 2026-08-15 after writing `backups/pre-migration-20260815T223017Z`. The
  Sprint 028 walkthrough moved album entry 16's status to `wishlist` and back to `owned`; it is where
  it started.
- **`data/` has been made group/other-writable and the container has been run against it.** Files the
  container creates are owned by uid 10001; hand ownership back with
  `docker run --rm --user 0 -v "$PWD/data:/data" akasha:local chown -R 1000:1000 /data`.
- **`README.md` still describes a book-only product.** The album domain has never been released or
  merged, so advertising it there would describe something no user can run.
- **The library tab strip still reads `All | Book | Album`.** DEC-065 removes "All" in Sprint 029.
- **The Inbox label is ambiguous on `/`**: the header badge and each domain's `unsorted` chip all read
  "Inbox". Correct in each place, confusing together. Unscheduled.
- **Release selection is still arbitrary between same-day originals** — resolving a "Kind of Blue"
  release-group URL returns the Swiss Blues Authority record. Stable but not meaningful.
- The manual add path is still a book form bound to `DEFAULT_DOMAIN`, and three
  `itemType === "book"` branches remain in `pages/AddPage.tsx` (DEC-067 row 6). Sprint 029 rebuilds
  that screen.
- The import layer is still book-only above the domain packages — `application/imports.py` and
  `api/imports.py`. That is Sprint 030's whole outcome.
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
