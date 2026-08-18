# Sprint 026 — Statuses, formats and tracklists

**Status:** completed
**Depends on:** 025
**Roadmap revision:** 11

## Objective

**Music is finished as a domain.** An album's entry offers the statuses an album can actually be in,
records how you own it — or how you intend to — and shows what is on it. The sprint succeeds when
the owner can filter to what they own and see the format, mark a wishlist record as the pressing they
mean to buy, and read a tracklist without leaving the page.

Seam 5b is the structural half of that; DEC-057 and DEC-059 are the product half, already decided.

## Required context

1. `AGENTS.md`, `docs/agent/WORKFLOW.md`
2. **`docs/domain-architecture-proposal.md` section 4 seam 5 and section 7**, which split this seam
   in two and explain why 5b waited for two domains
3. `docs/decisions.md`: **DEC-057 first** (the owner's answer: an album's status is possession),
   then **DEC-052** (the split, and the owner's three answers), **DEC-055** (where the seams
   actually landed — read this before assuming anything about the registry), DEC-051 (owner data
   versus derived), DEC-019 if the status suggestion logic moves
4. Sprint 025's Outcome, especially its walkthrough findings: "Rereads: 0" and "Your reading data" on
   an album detail page are this sprint's two visible symptoms
5. `docs/specs/product-spec.md` sections 3.2, 5, 7; `docs/specs/technical-spec.md` sections 5.1, 7.1
6. `docs/agent/HANDOFF.md` and the last worklog entry

## Current implementation baseline

Observed 2026-08-14 at Sprint 025's close. **Re-derive at activation.**

- `EntryStatus` is a global `StrEnum` in `backend/src/book_tracker/domain/types.py`, used as the
  validation type on `EntryCreateBody.status`, `EntryPatch.status`, `BulkSet.status` and the
  `status` query parameter of `GET /api/entries` (`api/library.py`).
- `Domain` in `backend/src/book_tracker/domain/domains.py` carries `status_labels`, a *partial*
  override map served at `GET /api/item-types`. Albums override `read`/`reading`/`to_read` only.
  **There is no per-domain list of which statuses exist.**
- Frontend: `statusLabels`, `chooseableStatuses` and `statusHotkeys` are one table in
  `frontend/src/features/library/labels.ts`; `statusLabelsFor(itemType, types)` applies a domain's
  overrides. `StatusSelect` takes a `labels` prop and hardcodes `orderedStatuses`. The triage bulk
  chooser and the library filter chips deliberately use the shared vocabulary, because a selection
  or a facet count can span domains.
- `facets.status_counts` is computed across the whole library and keyed by the global status values.
- `suggested_status` (Goodreads' shelf mapping) is book-only in practice but not by declaration.

## Deliverables

1. **Read the product decisions; they are made.** **DEC-057**: an album's status records
   *possession* (`wishlist` / `pending` / `owned`), not consumption, and `reread_count`,
   `date_started` and `date_finished` are meaningless for it. **DEC-059**: status and format are
   independent axes, format hangs on the **entry** rather than the item, it is multi-valued, and its
   vocabulary is the domain's. Neither needs re-litigating; both need building.
2. **Per-domain status vocabularies.** `Domain` gains the ordered statuses it has and which of them
   are directly choosable; `unsorted` stays universal, because imports land there and the default
   library view hides it. Validation moves from the global `EntryStatus` to a per-type lookup keyed
   on the item's own type, with a clear 422 when a status does not belong to the domain.
3. **The surfaces that follow it:** `StatusSelect`'s ordered list, the triage keyboard map, and the
   library filter chips. Decide explicitly what a chip means in a mixed library — a count for a
   status only one domain has is either hidden, or shown with its own domain's name.
4. **The Goodreads status suggestion stays book-only by declaration**, not by accident.
5. **The entry panel's copy** stops calling itself "Your reading data" for every domain, and an
   album stops showing `reread_count`, `date_started` and `date_finished` (DEC-057).
6. **Formats (DEC-059).** An `entry_formats` join table with a closed per-domain vocabulary on
   `Domain` — `Vinyl`/`CD`/`Digital` for albums, `Physical`/`Borrowed`/`Digital` for books. Copy the
   shelf machinery for the join, the facet count and the bulk path; do **not** render it as a shelf
   or let it become free text. A format is legal on any status, which is what makes
   "wishlist → vinyl" expressible.
7. **Tracklists.** Measured on 2026-08-14: adding `recordings` to the release fetch's existing `inc`
   returns every track's position, title and length in the same request — 6.4 KB for *Kind of Blue*,
   no extra call and no extra rate-limit budget. It needs a **new field-spec type**: an ordered list
   of structured rows, which is the first field the spec cannot currently describe. Tracks are
   metadata on the album, **not child entities** — that distinction is Sprint 028's to revisit if a
   later epic needs it, and this sprint must not blur it.

## Acceptance criteria

1. An album's status control offers the album's statuses, and a book's offers the book's, with no
   `type === "album"` branch in a component.
2. Setting a status a domain does not have is refused with a 422 naming the domain, not stored.
3. Every existing entry keeps its status across the change: no data migration silently remaps a
   value, and if one is genuinely needed it is a migration with a test, not a default.
4. The triage keyboard sets the right status for the row it is on, whatever domain it belongs to.
5. Filter chips and `status_counts` are correct and legible in a mixed library, per the choice made
   in deliverable 3.
8. **The owner can filter to `owned` and see how they own it from the list**, and can mark a
   `wishlist` album `Vinyl` without either value implying the other. Demonstrated in a browser.
9. An album's detail page lists its tracks in order with their lengths, and a book's detail page
   gains no empty tracklist.
6. An album shows no reread count and no started/finished dates, per DEC-057, and a book still
   shows all three. The remaining ownership/format question is answered in `docs/decisions.md`
   before any code depends on it.
7. Every book behaviour the suite covers is unchanged: imports, triage, undo, bulk edit, backup.

## Required tests (TDD)

- A status outside a domain's vocabulary is refused on create, patch and bulk-set.
- A format outside a domain's vocabulary is refused; a format on a `wishlist` entry is accepted, and
  an entry carrying two formats keeps both.
- The tracklist survives a metadata refresh without being rebuilt into a different order, and an
  album with no recordings renders no empty list.
- Every entry's status survives the change, proven against a database seeded before it.
- The triage hotkey map is derived from the domain, and the drift assertion in `labels.test.ts`
  still holds for every domain rather than for one.
- A mixed library's facet counts are correct with statuses that do not exist in both domains.
- The Goodreads importer still suggests book statuses and suggests nothing for a domain that does
  not declare them.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && make build && make smoke-container
git diff --check
```

Plus the walkthrough gate against a real library holding both books and albums: set statuses on both
from the library grid, the detail page and triage; filter by each chip; and report what you saw.

## Explicit non-scope

- Games and series, which DEC-058 moved out of this plan entirely and into future epics.
- **Tracks as entities.** A tracklist is metadata here. Entry hierarchy is not this sprint's
  question and possibly not this plan's.
- The library shell — domain tabs, full-page scroll, shelf ergonomics. That is Sprint 027, and
  keeping it out is what stops this sprint from becoming two.
- Per-domain **entry** models beyond whatever deliverable 1 decides — hierarchy is Sprint 028's
  question, and it is a much larger one.
- Re-opening seam 5a. Labels are done; this sprint is about which statuses exist.

## Commit checkpoints

1. `feat: give each domain its own statuses`
2. `feat: follow the domain vocabulary in triage and the filters`
3. `feat: record how a copy is owned`
4. `feat: read an album's tracklist`
5. final `docs(sprint-026): close sprint and hand off`

## Risks and decisions to surface

- **This sprint has three deliverables that could each fill it.** Statuses are the structural one and
  land first; formats are the product one and are why the sprint exists; tracklists are the small
  one and land last **because they are the slice to defer to 027 if the sprint runs long** — not the
  one to rush at the end. Deferring them is a note in the outcome, not a failure.
- **Entry fields become per-domain, not only statuses.** DEC-057 means an album hides
  `reread_count`, `date_started` and `date_finished`. That reaches the opinion dialog, the detail
  panel, the export and the Goodreads CSV mapping. Check whether hiding is enough or whether the
  fields should be refused on write for a domain that does not have them.
- **A mixed filter chip has no obviously right answer.** "Listened 3" and "Read 6" as separate chips
  is honest but doubles the row; one "Finished 9" chip is compact and lies slightly. This is a
  product judgement worth surfacing with a recommendation rather than settling silently.
- **`EntryStatus` is a validation type in four API models.** Moving off it touches the OpenAPI
  surface, so regenerate and re-check the frontend types in the same commit.
- The branch question is settled by DEC-053: this is a domain-line sprint, so cut a branch from
  `main` at activation.

## Outcome

**Closed 2026-08-15 on `sprint-025-albums` (DEC-061), six commits `ebe6827`..`7246134`, nothing
pushed. All nine acceptance criteria met, including the tracklist slice the risk note allowed to be
deferred.** DEC-060 records seam 5b as built; DEC-061 records the branch.

### Delivered

1. **Per-domain statuses (AC1, AC2).** `Domain` declares an ordered status vocabulary with its own
   labels and triage keys, the default a new entry takes, which passage fields exist, its formats,
   and the personal region's heading. `status_labels` is gone — a label lives on the status it names.
   No component branches on `type === "album"`. A foreign status is refused with a 422 naming the
   domain, on create, patch and bulk.
2. **The surfaces that follow it (AC4, AC5).** `StatusSelect` has no list of its own; the triage
   keyboard reads the focused row's domain, and the bulk chooser narrows to the statuses every
   selected row can take, because the server refuses a mixed write whole. **Filter chips are one row
   per domain** (owner's choice, DEC-060).
3. **The Goodreads suggestion is book-only by declaration** (deliverable 4), with a test asserting
   every suggested value is one of `BOOK`'s statuses.
4. **DEC-057 in the UI and the API (AC6).** An album shows no reread count and no dates, a book still
   shows all three, and the fields are **refused on write** rather than merely hidden — the owner's
   third judgement.
5. **Formats (AC8).** `entry_formats`, a closed per-domain vocabulary on `Domain`, the filter and
   facet copied from the shelf machinery, the format on the library row and in the export. A
   `wishlist` record can be `vinyl` with neither implying the other.
6. **Tracklists (AC9).** One `inc=…+recordings` parameter, no extra request. A new `rows` field type
   with declared columns; a book declares none and gains no empty list.
7. **AC3, AC7.** No status was remapped: album entries were deleted and re-added per the owner, and a
   test seeds one entry per book status before the change and reads all six back. The whole suite
   covering imports, triage, undo, bulk edit and backup is unchanged and green.

### Verified

`python scripts/validate_project.py`, `make format`, `make check`, `make test` (**411 backend, 110
frontend**), `npm run test:e2e` (**84 passed, 2 skipped**), `make build`, `make smoke-container`,
`git diff --check` — all green.

**Walkthrough** in Chromium against the real dev library at `127.0.0.1:8123`, which auto-migrated it
0012 → 0013 and wrote `backups/pre-migration-20260815T145406Z` first. Added *Discovery* through
MusicBrainz with **no status in the request** and it landed `owned`; added *Kind of Blue* as
`wishlist` and marked it `Vinyl` — neither value moved the other. Both fetched cover art through the
whole Cover Art Archive redirect chain. Confirmed by hand: `read` on an album, `owned` on a book,
`reread_count` on an album and `borrowed` on an album are each a 422 naming the domain; a book still
takes rereads, dates and `physical`. The album detail page reads "YOUR COPY" with no rereads and no
dates and lists five tracks as `A1 So What 9:05` … `B2 Flamenco Sketches 9:24`; the book's still
reads "YOUR READING DATA" with all three and no tracklist. Triage `o` set the focused album to
`owned`. No console errors.

### Deviations, all deliberate

- **Checkpoints 1 and 3 are partly merged.** Migration `0013` had to carry both the new table and the
  `entries` rebuild, so the formats *storage* shipped with the statuses commit and the formats *UI*
  with checkpoint 2's. The four named checkpoints all exist; two of them straddle.
- **A `rows` field is not hand-editable.** The metadata dialog skips it. Correcting a tracklist is a
  table editor, and `Refresh from provider` is the repair path (DEC-060).
- **Two fixtures were re-recorded** (`9821d30`), in their own commit as the fixture README requires,
  because the adapter's own request changed. Verified byte-identical apart from the new `tracks`
  array.
- **The dev library's three albums were deleted** rather than migrated, per the owner: "just delete
  the albums, this is a test db". Backed up to `backups/pre-sprint026-20260815T142246Z` first.

### What the walkthrough caught that the suite could not

Both are fixed in `7246134`, and both are the gate working as designed:

- **A status two domains share was counted once**, so the wishlisted record showed as
  "Book · Wishlist 1". `facets.status_counts_by_type` now splits the counts by item type beside the
  whole-library total the inbox badge uses.
- **`digital` is declared by both domains**, so the format filter listed "Digital" twice under one
  value. The list is flat now; an entry carries formats, not a domain.

### Impact on later sprints

- **Sprint 027** inherits a `type` dimension already present in the facets, which is half of the
  domain tab strip it has to build, and chip rows that will scope to one domain rather than being
  rewritten. Its shelf work must keep DEC-059's boundary: formats are not shelves.
- **Sprint 028** gains three more things a domain must supply and its conformance suite must check —
  a status vocabulary with a default, an entry-field declaration, and a format vocabulary — plus the
  `rows` field type, which is the first field the spec could not describe and the one most likely to
  need generalizing.
- **Sprint 029** is unaffected: the importers stayed book-only, now by declaration.
