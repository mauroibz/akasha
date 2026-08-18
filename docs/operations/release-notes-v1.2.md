# Akasha v1.2 — release notes

**The release where Akasha stops being only a book tracker.** Sprints 025 through 029,
developed on `sprint-025-albums` and merged in one go (DEC-072). A second domain —
music — and the screen rebuilt around a single bar that both searches your library and
adds to it.

**Tagged `v1.2.0`** at the merge, after Sprint 029 and its second pass closed.

## A note on versioning

`1.2.0` on the same reading as `1.1.0`: a feature release on top of what came before,
breaking nothing. Nothing you have needs migrating by hand, and the two structural
migrations in it (`0013`, `0014`) run on startup with a backup written first.

The four places that carry a version — `backend/pyproject.toml`, `frontend/package.json`,
the FastAPI `version` string and, through it, `frontend/openapi.json` — all say `1.2.0`.
The FastAPI string is part of the API contract, so the frontend type check is what
catches a forgotten regeneration.

## What's new since v1.1.0

- **Music is a domain, not a special case** (Sprints 025–026). Records arrive from
  MusicBrainz with their art from the Cover Art Archive, and they bring their **own**
  vocabulary rather than borrowing books': *owned*, *on the way*, *wishlist*; vinyl, CD,
  digital; a label, a catalogue number, a tracklist. A record has no reread count and no
  reading dates, because it has no such thing — the domain declares which fields it has
  and the screens render what it declares.
- **One bar that searches and adds** (Sprint 029). Typing filters your library over local
  SQL and reaches **no provider** for as long as the library has a match. When it has
  none and the query has settled — about eight tenths of a second, at least three
  characters — one search goes out, once per string. **Add** overrides that whenever you
  want it. Results land below the library in their own region, and choosing one opens the
  confirm form over the library instead of taking you to another screen.
- **The domain you are in is always named** (Sprint 029). The tab strip picks the rows you
  see *and* the providers a search would reach, in one control, so nothing ever has to ask
  which you meant. "All" is gone deliberately; `/triage` and the export still span
  everything.
- **The interface stopped calling everything a book** (Sprint 029). Twenty-four strings
  across eleven screens now come from the domain's own label or say nothing about a
  domain at all. Adding a record says *Album added*. A shelf holding both counts *items*,
  which is what a shelf always held.
- **A library shell that fits two domains** (Sprint 027). Status filters, format filters
  and shelves all narrow to the domain on screen, and the counts are per domain, because
  a status two domains share is not one number.
- **Screen polish the owner asked for** (Sprint 029, second pass). A description spans the
  full width of the confirm panel instead of becoming a ribbon; the search bar clears in
  one press; a search that matches nothing gets one line instead of a screenful of empty
  state; the status filters fold into one control beside sort, shelf and format; and
  *Attach a file* is its own region on the detail page at the weight of *Edit opinion*.

## Under it, for anyone extending this

- **A domain is a package** (Sprint 028). `backend/src/book_tracker/domains/book/` and
  `.../album/` each hold a declaration, adapters and importers; `domain/spec.py` says what
  a domain *is* and `domain/registry.py` says which exist. **No shared layer branches on
  which domain it is holding** — `if item_type == "book"` above the registry is a defect,
  and a conformance suite parametrized over the registry holds every domain to the
  contract by existing.
- **A third domain costs**: its own package, one entry in `DOMAINS`, its provider wired in
  the lifespan, three lines in the published enums, one cover-host allowlist line if its
  art is hosted somewhere new, and configuration if its provider needs credentials. **No
  migration, and no edit to another domain's files.**
  [`docs/guides/adding-a-domain.md`](../guides/adding-a-domain.md) is how; technical spec
  §6.6 is the contract.
- **Statuses are the domain's, and validated against the item's own domain.** Migration
  `0014` dropped the CHECK constraint that could only hold the union of every domain's
  vocabulary and so accepted `owned` on a book; the validator is strictly stronger.

## Known and left

- **Manual entry (`/add`) is bound to the default domain.** It offers no domain chooser,
  and that is honest rather than missing: the API types a manual add as the default
  domain whatever the client sends, so a chooser would show one domain's fields and write
  another's row. Giving manual entry a real domain needs an API change and is unscheduled.
- **Importing is still book-only** — Goodreads and Calibre. The readers moved into the
  book domain, but the pipeline above them has not been generalised yet; that is the next
  planned sprint after this release.
- **Release selection between same-day releases is arbitrary.** Resolving a "Kind of Blue"
  release-group URL returns a record that is stable but not necessarily the one you meant.
- **A provider fetch can fail at add time**, and one album add in testing returned a 502
  from MusicBrainz that succeeded on an identical retry. The dialog stays open and shows
  the error.
- The *Inbox* label appears both as the header badge and as a status, which is correct in
  each place and ambiguous together.
- No export button in the UI; the route is the surface. `HEAD` on any route returns 405.
  "Replace cover" is an unstyled file input. Orphaned *cover* files are still not
  collected, deliberately — a cover is cache the application can re-fetch.

## Still true from v1

No authentication. **LAN only** — no public DNS, port forwarding, tunnel, or
internet-reachable proxy until authentication exists. The nightly database backup remains
non-optional in production: export is a portability story, not a restore story.
