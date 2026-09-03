# Implementation Roadmap

**Plan revision:** 33
**Delivery rule:** one sprint must leave a demonstrably usable or risk-reducing increment, green quality gates, updated documentation, and a clean worktree.
**Active sprint:** none — every planned sprint (001–062) is complete; see `docs/agent/state.json`.

## Shape of the plan

Sprints 001–018 delivered v1 as a single dependency chain, each sprint depending on the one before
it. That chain is closed. Its contracts live in the individual sprint files linked below, which are
the source of truth for what each one promised and what it delivered; they are not restated here.

Post-v1 work branches:

```text
018 v1 released
 └─ 019 Post-v1 polish
     └─ 020 Metadata completeness  [GATED]
         ├─ 021 Attachments        [GATED]
         │   └─ 022 Attachment lifecycle
         ├─ 023 Creator sort names
         ├─ 024 Export
         └─ 025 Second domain: albums — the six seams
             └─ 026 Statuses, formats and tracklists
                 └─ 027 Library shell and shelves
                     └─ 028 The domain contract  [GATED]
                         └─ 029 One search bar
                             └─ 030 Entry depth  [GATED, Phase A only]
                                 └─ 031 Per-domain imports
                                └─ 032 Import UX and connector extensibility
                                   └─ 033 Calibre without a mount
                                      └─ 034 Incremental import
                                         └─ 035 Ebook attachments on a toggle
                                            └─ 036 Import and triage flow
                                               └─ 037 Triage page flow and staged statuses  ✓
                                                  └─ 038 Anime: the third domain  ✓
                                                      ├─ 039 Enrichment beyond the ISBN  ✓
                                                      └─ 040 Entry progress  ✓
                                                           └─ 041 The MyAnimeList import  ✓
                                                               └─ 042 One decision per Triage row  ✓
                                                                   └─ 043 Row-only Triage decisions  ✓
                                                                      └─ 044 Sharpening the domain contract  ✓
                                                                          └─ 045 Movies viability  [GATED]  ✓
                                                                              └─ 046 Movie domain on Wikidata
                                                                                  └─ 047 Letterboxd import
                                                                                      └─ 048 Movie posters  ✓
                                                                                          └─ 049 Series domain on Wikidata
                                                                                              ├─ 050 TVmaze, the second provider
                                                                                              └─ 051 The verification gates get faster
                                                                                                  └─ 052 One source, many libraries
                                                                                                      └─ 053 The IMDb import
                                                                                                          └─ 054 The Trakt import
                                                                                                              └─ 055 The recorded defects

v1.5.0 released
 └─ 056 Deployment defaults          v1.5.1
     ├─ 057 Product names           v1.5.1
     ├─ 058 A published image       v1.5.3
     ├─ (out-of-sprint e2e CI fix)   v1.5.4 — see DEC-121
     ├─ 059 Nothing blocks the loop  v1.5.5  [GATED]
     └─ 060 Storage housekeeping     v1.5.6
```

**Sprints 019–037 closed the line DEC-058 drew.** Sprint 025 asked whether a second domain was
affordable and answered yes; Sprint 028 turned that answer into a contract so that a third domain
would be an epic on top of it rather than another sprint chain through the core.

**Sprints 038–041 are that third domain, and they exist to test the claim** (DEC-089). The owner
asked for anime, with an importer for their own MyAnimeList export, explicitly as a trial run whose
findings feed back into the repository. Sprint 038 is the contract's promise kept — a package, two
adapters, small registration points, no migration and no screen. Sprints 039 and 040 are the two
seams the export forces, both of them foreseen, costed and deliberately left unbuilt by the decisions
that deferred them: enrichment on a key that is not an ISBN (DEC-067 row 3) and a per-domain progress
count on the entry (DEC-077 shape (a)). Sprint 041 is the connector, which lands complete because the
other two precede it.

Anime is therefore **no longer an unnumbered epic**. Games, series and the Spotify connector remain
so, and are named under [Future epics](#future-epics-after-this-plan).

**The line closed on 2026-08-27 and the trial run returned a verdict.** Both halves of the domain
contract were built by a session that did not write them. The domain half held outright; the
connector half held in code — `api/imports.py` and both import screens were never touched — and
failed once in the schema, on a frozen `kind IN ('goodreads','calibre')` that migration `0016`
deleted. Adding a domain cost about 45 lines of shared registration; adding a connector cost one
tuple entry and one migration whose only purpose was removing a constraint that should not have
existed. Everything else the line spent went on two seams the owner's export forced, both of which
earlier decisions had already foreseen and priced (DEC-090, DEC-091, DEC-092, DEC-093).

**Sprints 049–055 are the fifth domain and the last new one planned, plus two infrastructure
sprints.** Series were an unnumbered epic from Sprint 028 until plan revision 27, described as gated
on a product decision about entry hierarchy — a decision DEC-077 had already made and Sprint 040 had
already built. What was left was measurement, and it was done before this line was written: two
keyless providers, a poster source already allowlisted, and both of the owner's real exports parsed
(DEC-104, `docs/series-domain-viability.md`). The line's centre is not the domain, which the contract
makes cheap; it is Sprint 052, where the shared import pipeline learns to hold more than one domain
at once because a television tracker tracks films too (DEC-106). Sprint 051, inserted at plan
revision 28 (DEC-111), is not series work at all: it implements the four items in TESTING.md's
optimization backlog so the three import sprints after it run against faster, quieter gates. Sprint
055, inserted at plan revision 29 (DEC-114), closes the line: the defects the movie and series
sprints recorded and left, and the three gates that measurement showed had stopped paying for
themselves — including one of Sprint 051's own four items.

**Sprints 056–060 are the deployment line, and they build no product** (DEC-117; DEC-119 inserted 057). v1.5.0 released
five domains and six import sources; what had never been examined was what a real installation of it
meets on the first day and on every upgrade after. The image itself held — the container smoke test
passes end to end from a clean build — and the gaps were all one layer out: defaults that fight the
host, an upgrade that is a full rebuild on the server, write paths whose contention has never been
measured, and three places that write bytes with nothing to collect them. Each sprint ships one patch
release. 058, 059 and 060 depend on 056 alone and are otherwise independent; 058 runs first because
a published image makes delivering the other two cheap. Nothing in the line changes what a person
sees in the application, and none of it adds authentication — product spec §9 keeps that a v2
deferral, reaffirmed by the owner while commissioning these sprints.

020 precedes the domain work because its Phase A settles how a candidate record is verified before
its fields are merged, and that is the provider contract every later domain inherits. 022 precedes
it because the fix generalizes from author to creator, and N domains should not inherit a broken
sort projection. 021 and 023 are independent of the domain line and may be reordered freely against
each other.

**GATED** marks a sprint whose first phase decides whether its second phase happens. Phase A
measures and produces a written verdict in `docs/decisions.md`, changing nothing user-visible;
Phase B builds only what that verdict and an explicit owner go-ahead justify. Phase A concluding
*no* is a complete, correct outcome. This is the owner's preferred shape for any item large enough
that its cost is unknown — see DEC-035 and DEC-042.

## Sprint index

| Sprint | Outcome | Depends on | Status |
|---|---|---|---|
| [001](001-foundation.md) | Reproducible monorepo foundation | — | completed |
| [002](002-domain-persistence.md) | Domain model and durable persistence | 001 | completed |
| [003](003-entries-shelves-api.md) | Entries, shelves, filtering, keyset API | 002 | completed |
| [004](004-frontend-library.md) | Design system and virtualized library | 003 | completed |
| [005](005-providers-add-api.md) | Metadata providers and cached add API | 002 | completed |
| [006](006-add-detail-edit-ui.md) | Add, detail, and metadata-edit UI | 004, 005 | completed |
| [007](007-goodreads-import.md) | Goodreads preview and commit | 006 | completed |
| [008](008-book-metadata-covers.md) | Working book metadata and covers | 007 | completed |
| [009](009-calibre-import.md) | Calibre preview and commit | 008 | completed |
| [010](010-editorial-ui-redesign.md) | Editorial UI redesign and completion | 009 | completed |
| [011](011-durable-enrichment-undo.md) | Durable jobs, enrichment, ledger undo | 010 | completed |
| [012](012-bulk-first-triage.md) | Bulk-first triage | 011 | completed |
| [013](013-library-grid-layout-repair.md) | Library grid layout diagnosis and repair | 012 | completed |
| [014](014-metadata-correctness-search.md) | Metadata correctness and search relevance | 013 | completed |
| [015](015-design-system-components.md) | Design system and component foundation | 014 | completed |
| [016](016-motion-interaction-polish.md) | Motion and interaction polish | 015 | completed |
| [017](017-scale-accessibility-resilience.md) | Production-quality hardening | 016 | completed |
| [018](018-container-backup-release.md) | Deployable v1 | 017 | completed |
| [019](019-post-v1-polish.md) | Post-v1 polish and ledger clearing | 018 | completed |
| [020](020-metadata-completeness.md) | Metadata completeness: viability, then build | 019 | completed |
| [021](021-attachments.md) | Attachments: viability, then a narrow slice | 020 | completed |
| [022](022-attachment-lifecycle.md) | Attachment lifecycle: reclaim, rename, edges | 021 | completed |
| [023](023-creator-sort-names.md) | Creator sort names | 020 | completed |
| [024](024-export.md) | Export | 020 | completed |
| [025](025-second-domain-albums.md) | Second domain — albums: the six seams | 024 | completed |
| [026](026-statuses-formats-tracklists.md) | Statuses, formats and tracklists | 025 | completed |
| [027](027-library-shell-and-shelves.md) | Library shell and shelves | 026 | completed |
| [028](028-the-domain-contract.md) | The domain contract | 027 | completed |
| [029](029-one-search-bar.md) | One search bar | 027, 028 | completed |
| [030](030-entry-depth.md) | Entry depth: the decision **[GATED]** | 029 | completed |
│ [031](031-per-domain-imports.md) | Per-domain imports | 030 | completed |
| [032](032-import-ux-and-connector-extensibility.md) | Import UX and connector extensibility | 031 | completed |
| [033](033-calibre-without-a-mount.md) | Calibre without a mount | 032 | completed |
| [034](034-incremental-import.md) | Incremental import | 033 | completed |
| [035](035-ebook-attachments.md) | Ebook attachments on a toggle | 034 | completed |
| [036](036-import-triage-flow.md) | Import and triage flow | 035 | completed |
| [037](037-triage-page-flow.md) | Triage page flow and staged statuses | 036 | completed |
| [038](038-anime-domain.md) | Anime: the third domain | 037 | completed |
| [039](039-enrichment-beyond-isbn.md) | Enrichment beyond the ISBN | 038 | completed |
| [040](040-entry-progress.md) | Entry progress | 038 | completed |
| [041](041-myanimelist-import.md) | The MyAnimeList import | 039, 040 | completed |
| [042](042-one-decision-per-triage-row.md) | One decision per Triage row | 041 | completed |
| [043](043-row-only-triage-decisions.md) | Row-only Triage decisions | 042 | completed |
| [044](044-sharpening-the-domain-contract.md) | Sharpening the domain contract | 043 | completed |
| [045](045-movies-viability.md) | Movies viability: providers and Letterboxd shape **[GATED]** | 044 | completed |
| [046](046-movie-domain.md) | Movies: the fourth domain on Wikidata | 045 | completed |
| [047](047-letterboxd-import.md) | Letterboxd import for movies | 046 | completed |
| [048](048-movie-posters.md) | Movie posters, without a setup step | 047 | completed |
| [049](049-series-domain.md) | Series: the fifth domain, with posters on day one | 048 | completed |
| [050](050-tvmaze-provider.md) | TVmaze: the second series provider | 049 | completed |
| [051](051-verification-gate-optimization.md) | The verification gates get faster | 050 | completed |
| [052](052-multi-domain-imports.md) | One source, many libraries | 049, 051 | completed |
| [053](053-imdb-import.md) | The IMDb import | 049, 052 | completed |
| [054](054-trakt-import.md) | The Trakt import | 049, 052, 053 | completed |
| [055](055-recorded-defects.md) | The recorded defects, and the gates that stopped paying | 054 | completed |
| [056](056-deployment-defaults.md) | The deployment defaults a home server needs | 055 | completed |
| [057](057-product-names.md) | The names the product actually uses | 056 | completed |
| [058](058-published-image.md) | An image you pull, not a build you run | 056 | blocked |
| [059](059-off-the-event-loop.md) | Nothing blocks the event loop **[GATED]** | 056 | planned |
| [060](060-storage-housekeeping.md) | The disk stops filling quietly | 056 | planned |

## Sprint contracts

These are the binding outcome boundaries for the post-v1 line. Sprints 019 through 037 are closed.
Their individual Outcome sections record delivered reality.

### [Sprint 019 — Post-v1 polish and ledger clearing](019-post-v1-polish.md)

Three small user-visible defects that survived v1: the score chip reads as colour-on-dark instead
of a filled chip, `s` does nothing on `/triage` despite product spec section 7, and a committed
import lands rows `unsorted` where the default library hides them, so it looks as though nothing
happened. Deliberately small and independent of everything after it.

### [Sprint 020 — Metadata completeness: viability, then build](020-metadata-completeness.md)

**Gated.** DEC-035 records that the owner wants richer metadata built up from whichever provider
has the missing piece, and specifically the ability to choose a cover from the editions actually
fetched — and that what was *not* decided is whether it is affordable. Phase A measures provider
rate limits, wall-clock import cost, whether a candidate can be verified as the same edition before
merging, disk cost of multiple cover candidates, failure semantics, and whether DEC-008's
fill-empty-only invariant survives. Phase A may conclude a narrow slice — cover choice alone, on
demand — carries most of the value at a fraction of the risk.

One item does not wait on the gate: `GoogleBooksProvider.fetch_by_isbn` takes the first hit of an
`isbn:` search, which is not guaranteed to carry the requested ISBN13. That is a live defect and is
repaired whatever the verdict.

This sprint sets the provider contract Sprint 025 inherits, so its reasoning matters as much as its
verdict.

[Closed 2026-08-13. **Phase A concluded against building**: cross-provider completion buys a
description in 22% of cases and 0% for cover, year, publisher and authors, while breaching the
Google free tier on a large import. The edition defect and the placeholder cover were both repaired.
**Phase B was then authorized by the owner (DEC-045)** and the sprint reopened to build it:
cover choice from Open Library work-record candidates, which cost no extra requests, plus a
provider-agnostic daily quota guard. Provider order stays Open Library first, measured rather than
assumed. Both shipped; the walkthrough found five defects the suite could not, including a
correction to DEC-044's placeholder rule. See DEC-044 and DEC-045.]

### [Sprint 021 — Attachments: viability, then a narrow slice](021-attachments.md)

**Gated.** The owner wants to attach arbitrary files to an entry — epubs for books — while keeping
the metadata-first framing. The scope risk is real and has a precise boundary: **an attachment is
an opaque file, or it is a reader.** Everything that expands this feature past its usefulness
follows from crossing that line.

Phase A must answer:

- **Backup.** `ARCHIVED_DIRECTORIES = ("covers", "imports")` in `backend/src/book_tracker/backup.py`
  tars everything into every backup. Covers are ~50 KB; an epub is 1–5 MB and a comic or audiobook
  far more. Seven nightly backups against a few hundred attached files is a different machine's
  worth of disk. Either attachments go in the tar under a size cap, or they are excluded with a
  documented separate story. **This is the decision that scopes the feature.**
- **Where it hangs.** Item or entry. An epub is a property of the edition; an annotated personal
  copy is a property of your entry. Item is the default and matches the metadata-first framing.
- **Serving.** Covers go through a validated pipeline with a host allowlist and a pixel bound. An
  arbitrary blob has no such thing, so size limits, content-type handling, and
  `Content-Disposition: attachment` are required rather than optional.

Phase B narrow slice, if justified: one or more opaque files per item, uploaded manually,
size-capped, listed with filename and size, downloadable from the detail page. **No format parsing,
no in-browser reader, no reading progress, no device sync.**

Reading an uploaded epub's OPF as another metadata provider filling empty fields under DEC-008 is
genuinely cheap and on-brand, and is named here so it is recognized as the natural next step rather
than smuggled into the first slice. It is explicit non-scope for Phase B.

### [Sprint 022 — Attachment lifecycle](022-attachment-lifecycle.md)

Sprint 021 shipped the storage design and the happy path. A review of what it left found the flows
around a file are thinner than the storage under it, and one genuine hole.

**The hole is reclamation.** `delete_blob_if_unreferenced` has exactly one caller, so a blob can end
up with nothing pointing at it and no way to find it — via the `CASCADE` on item delete, via a crash
between writing a blob and inserting its row, or via an item orphaned by entry deletion. At 2.5 MB a
file this is a different problem from the 39 KB orphaned cover the product spec waved through.

The rest is smaller: no rename, though the filename is already only metadata; no confirmation on
remove, though the product spec says deletes confirm and *Delete entry* on the same page does; and
upload and download both hold the whole file in memory, up to 25 MiB per request.

**No new feature surface.** An attachment stays an opaque file. Multiple selection, drag-and-drop and
progress bars are named as non-scope: real improvements, but polish rather than correctness.

**Delivered** (DEC-050). `akasha-attachments reclaim`, dry-run by default. Rename, inline. A
confirmation on remove. Streaming both ways, measured at +29.9 → +2.6 MiB peak RSS on a 25 MiB
upload. Replace was put to the owner and deliberately not built: with rename in place it is remove
plus attach. The orphaned *cover* is still not collected — the reclaim is scoped to the attachment
store on purpose, since a cover is cache the application can re-fetch.

### [Sprint 023 — Creator sort names](023-creator-sort-names.md) — completed

Delivered as planned (DEC-051): `creator_sort_override` is the owner's value, `creator_sort` and
`creator_sort_normalized` are derived from it or from a heuristic by the DEC-036 mapper event, and
migration `0011_creator_sort_names` backfilled every row.

Two things later sprints inherit. **Ordering moved to the creator column but search did not** —
the `q` filter still reads `sort_author_normalized`, because a reader types the name as written.
And **Calibre's `authors.sort` seeds the override as owner data**, which is what makes the
heuristic's known failure ("Jorge Luis Borges" → "Luis Borges, Jorge", 2 of 16 items on the
walkthrough library) survivable rather than a defect to tune out.

`sort_author` deliberately kept its name and its display role; the rename waits for Sprint 025,
which changes the metadata key from `authors` to `creators` and can do both in one pass.

### [Sprint 024 — Export](024-export.md) — completed

`GET /api/export` dumping entries and items as JSON, plus a Goodreads-shaped CSV. Product spec
section 9 deferred this to v2 as agreed-in-principle; the owner has now scheduled it. Backups
(DEC-039, DEC-040) removed the urgency, but the repository is public and portability is now a
user-facing story rather than only the owner's.

**Sprint 021 left this one question to answer** (DEC-048): whether an export carries attachment
bytes, references, or neither. Bytes make an export a multi-gigabyte archive rather than a file;
references make it portable but incomplete. Decide it explicitly rather than by omission.

Sprint 022 narrows it slightly: the filename is now **owner-edited data**, not something derivable
from the uploaded file, so whichever of the three an export carries, it has to carry the name. An
export that reconstructs names from digests loses a correction the owner made by hand (DEC-050).

Sprint 023 adds a second field of that kind: `creator_sort_override` (DEC-051). It is not derivable
from `metadata.authors` — that is the entire reason it exists — so an export that omits it loses a
correction in exactly the same way. `creator_sort` and `creator_sort_normalized` are derived and
should **not** be exported; they rebuild themselves on import.

One design constraint, because it decides whether this survives the domain work: **export the
entity shape — `type`, identifiers, and an opaque `metadata` object — not a book-specific schema.**
The database is already shaped that way. A book-shaped export format would need a v2 the moment
Sprint 025 lands.

The Goodreads-shaped CSV is a book-only convenience and is allowed to stay book-only.

[Closed 2026-08-14. Delivered as planned. **Attachments are carried as references plus their sha256,
not bytes (DEC-054)** — the blob is already held live and in every nightly backup, and a digest
resolves against a backup because the blob's path *is* its digest, verified by matching the exported
digest against the file on disk. "Neither" was never available: the sprint's own first criterion
requires the owner-typed filename to survive. Streaming needed two repairs the memory measurement
caught and the functional tests could not see — mapped entities held the whole library in the
`Session` identity map, and `yield_per` did not help because SQLite materializes the result anyway.
Measured at x1.07 (JSON) and x1.66 (CSV) peak for x10 output. The CSV neutralizes leading `=` so a
spreadsheet reads a note as text, which makes the JSON the lossless artifact. **There is no export
button in the UI** — the route is the surface, and no screen in product spec 7 asks for one.]

### [Sprint 025 — Second domain, albums: the six seams](025-second-domain-albums.md)

**No longer gated, and no longer a blind pilot.** DEC-052 accepted
`docs/domain-architecture-proposal.md`, which answered by measurement what this sprint's Phase A was
going to answer by walking: the album mapping was validated against live MusicBrainz and Cover Art
Archive responses on 2026-08-14. The gate's purpose — do not build an abstraction whose cost is
unknown — is served better by six named seams that can each be proved wrong than by an unstructured
verdict at the end.

**The core is already neutral.** `items` has been `type`/`title`/`subtitle`/`year`/`cover_path`/
`identifiers`/opaque `metadata` since Sprint 002. What is book-shaped is every layer above it, so
the work is lifting book logic out of the shared layers into a per-domain plugin. Albums are never
translated into book vocabulary.

Two measured facts rejected the tempting shortcut of casting albums into book fields:

- **MusicBrainz ships a curated sort name and only inverts people.** `Miles Davis` is a `Person` and
  sorts `Davis, Miles`; `Daft Punk` is a `Group` and does not invert. DEC-051's heuristic assumes a
  person's name and would produce `Punk, Daft`. Seam 1 generalizes the Calibre seed instead: a
  source that knows the sort name seeds the override, and the heuristic runs only when nothing knew.
- **Barcode is not a unique edition key** — one barcode was observed on three distinct releases —
  so cross-provider identity does not exist for albums. Seam 2 is therefore a strategy
  (`identity_key() -> str | None`, `None` meaning never merge), not a configurable identifier field.

Seams 1–4, 5a and 6 land here; **seam 5b is Sprint 026**. The split answers the owner's objection
that six seams is too much for one sprint, and it cuts in the only place that survives cutting:
extracting seams *before* albums would design the abstraction from one domain, which is the failure
mode the whole approach exists to avoid.

The largest blast radius is the `metadata.authors` → `creators` and `sort_author` renames DEC-051
deferred to here: 55 occurrences across 27 files, seven e2e specs, a migration and the benchmark.

[Closed 2026-08-14 on a branch (DEC-053). All six seams landed where section 4 put them and **none of
the three tripwires fired** — keyset pagination, the job runner and the ledger needed no change, and
no seventh seam appeared (DEC-055). `Daft Punk` sorts under D because MusicBrainz's curated
`sort-name` seeds the override and the DEC-051 heuristic never runs. Two seams reached slightly
further than written: the https upgrade has to apply to **every** redirect hop, because the Cover Art
Archive answers `http://` on all of them, and the field spec reaches the export — the walkthrough
caught the Goodreads CSV emitting albums as books. The API also stopped inventing empty metadata
defaults (DEC-056).]

### [Sprint 026 — Statuses, formats and tracklists](026-statuses-formats-tracklists.md)

**Music, finished as a domain.** Sprint 025 shipped albums carrying books' status *values* under
album *labels* — honest, visible, and a one-sprint debt. This clears it and adds the two things the
owner found missing once albums were real.

Three decisions arrive with it, all already made, none needing re-litigation:

- **DEC-057** — an album's status records **possession**, not consumption: `wishlist` / `pending` /
  `owned`, with no relisten counter and no started/finished dates. That makes status a per-domain
  *concept* rather than a per-domain vocabulary, which is what seam 5b was always for.
- **DEC-059** — **format is an independent axis on the entry**: multi-valued, per-domain vocabulary,
  and legal on any status, so "wishlist → vinyl" is expressible and "sort by owned, see how" is one
  filter plus a card. It reuses shelves' machinery and none of shelves' meaning — shelves stay the
  higher tier ("work", "fiction").
- **Tracklists**, measured at one `inc=recordings` parameter and no extra request. They need the
  first field type the spec cannot yet describe: an ordered list of structured rows. Tracks are
  metadata, **not** child entities.

The sprint's own risk note names the tracklist slice as the one to defer to 027 if it runs long,
rather than the one to rush.

### [Sprint 027 — Library shell and shelves](027-library-shell-and-shelves.md)

The polish pass on the screen the owner spends their time in, scheduled by DEC-058 as the last
feature work before the contract sprints. Three findings from the Sprint 025 walkthrough, all in the
"Owner feedback" section below with their causes already traced:

- **A domain tab selector.** Sprint 025 deliberately left the list endpoint with no `type` filter,
  because AC4 only required that a mixed library paginate correctly — which it must either way. This
  is the other half: books and albums together read as a mixed bag rather than as one library. The
  tab strip is fed by `GET /api/item-types`, which already serves the domains and their labels; the
  open question is only what the default is.
- **The library grid is a fixed-height window inside the page** (`h-[min(70vh,760px)]` on the
  virtualizer's scroll container), so the primary surface scrolls inside a box. Letting the page
  scroll and having the virtualizer measure the window is the fix, and it is the one thing Sprint 013
  was called in to repair — so it re-runs the scale and feed-semantics checks rather than assuming
  them.
- **Shelves are edited from a dialog named after something else.** Shelf membership lives inside
  `OpinionDialog`, and creating a shelf is a whole route. The API already does what is needed, so
  this is UI-shaped: inline shelf editing with create-on-type. DEC-059 fixed the boundary this must
  respect — shelves are the higher tier ("work", "fiction"); formats are not shelves and must not be
  rendered as one.

Sprint 026 did **not** defer its tracklist slice, so this sprint carries only the three items above.
It also inherits `facets.status_counts_by_type`, which is half of the tab strip already built.

[Closed 2026-08-15. All three delivered, plus a fourth the sprint's own baseline got wrong: **the
bulk *Add shelves* action in triage had never been built** — `add_shelves` existed on the endpoint
and was tested, but no control sent it, and product spec §7 said so. The tab default was settled
with the owner as **the last domain used** (DEC-062), which also records why `type` clears the
status facets but applies to `format_counts`. The library now virtualizes against the window;
Sprint 013's scale and feed-semantics checks were re-run against that rather than assumed. Ran on
`sprint-025-albums` per DEC-063.

**Reopened the same day** at the owner's request to fold in the add flow, which is the same
complaint one screen over: the confirm screen showed three of the fields the search had already
returned and discarded the rest. It now shows all of them for free and fetches the full record on a
button (DEC-064), shelves and the whole opinion can be set while adding, and one shared control per
concept replaced two rows of checkboxes.]

### [Sprint 028 — The domain contract](028-the-domain-contract.md)

**Gated**, and the first of the two sprints DEC-058 makes the gate to further domains.

Albums proved the seams exist. What does not exist yet is a **written contract**: a new domain is
currently built by reading how albums were built and inferring the rules. Phase A produces that
contract — what a domain must supply (`Domain` and its registry entry, an adapter, a field spec, a
status vocabulary, a format vocabulary, a URL recognizer), what it may never touch, and where its
code lives — plus **a conformance suite a domain must pass**, run against books and albums first to
prove it describes reality rather than intentions.

Phase A also measures what is still misplaced: book-shaped logic sitting in shared layers that two
domains happened not to collide over. Phase B moves only what the suite proves is misplaced.

**The baseline was re-derived on 2026-08-15 and sharpened the sprint.** A domain is not yet a unit of
code: adding a third one edits nine shared files, two of them badly. `entries.ck_entries_status`
holds a status list frozen at migration-write time, so a domain declaring a status books and albums
lack is accepted by the API and refused by SQLite — **a new domain currently needs a migration on a
shared table.** And enrichment is book-shaped below its seam (`_backfillable_items` joins on ISBN),
which albums never tested because they declare `enriches=False`. The owner settled two things at
planning time: that constraint is measured and costed here rather than pre-authorized, and **the
contract prescribes a per-domain code home, with books and albums moved into it in Phase B** as the
proof that the layout exists.

**This is where DEC-052's falsifiable prediction gets tested properly.** "Games need no seam albums
did not" is checked by writing the conformance suite against the seams and seeing whether a paper
walk through IGDB passes it — which is cheaper and more honest than another bespoke sprint.

[Closed 2026-08-15. **Both phases ran.** Phase A wrote the contract (technical spec 6.6), the
conformance suite (`test_domain_conformance.py`, parametrized over `DOMAINS`), the costed measurement
(DEC-067, four of ten rows recommending no work) and the IGDB paper walk (DEC-068: **no seventh
seam**, but the first adapter needing mutable state and a secret pair, and six shared files plus one
alembic head that two parallel domain teams would contend over). The suite found a live defect on its
first run — `urlsplit` raises on `http://[`, and one domain's raising recognizer denied every domain
after it its turn. **The owner authorized all four Phase B items** (DEC-069): per-domain packages,
`provider_health` read from the registry, the cover chooser declared per domain, and migration `0014`
dropping `ck_entries_status`. The move itself exposed three more shared things quietly shaped like
books, all repaired. **A third domain now costs its own package, one registry entry, provider wiring,
three enum lines, and no migration.** Reopened once more for the documentation pass (DEC-070):
`docs/guides/adding-a-domain.md`, `CONTRIBUTING.md` and `docs/README.md`, with the guide proved by
building a throwaway third domain from it — which found three closed-world assumptions and removed
them.]

### [Sprint 029 — One search bar](029-one-search-bar.md)

Accepted as DEC-065 and scoped in `docs/unified-search-proposal.md`. `/` is rebuilt around a single
bar that searches the library and adds to it, with the domain selector beside it and **"All" removed
as a filter**, so the tab strip always names exactly one domain. The full description, including the
owner's two amendments, is under *Scheduled from owner feedback* below.

It runs after 028 because it is the sprint most likely to amend the contract's account of what a
*screen* renders from the registry. **Narrowed 2026-08-16:** this paragraph originally said the
backend contract and the conformance suite were untouched by it, which was written before DEC-071
added copy neutrality as the sprint's sixth deliverable. That deliverable may add **one declarative
field** to `Domain` for a per-domain search placeholder, with the conformance check such a field
requires. The invariant that holds either way is the one that matters: no shared layer branches on
which domain it is holding.

**Delivered 2026-08-16, closed 2026-08-17 (DEC-073), and the narrowing is narrowed back:** the field
was authorized and **not taken**. One neutral placeholder naming title, creator, ISBN and link serves
every domain, so the backend contract and the conformance suite are untouched after all, as this
paragraph first claimed. What the sprint did change is the account of the *screen*: `/` is now where
you search and add, `/add` is manual entry, results render below the library rather than above it,
and a provider is reached only on settled-and-empty or on **Add** — a rule verified by counting
requests. The full Outcome is in the sprint file.

**Reopened for a second pass, 2026-08-17 (DEC-074)**, on the owner's report after using it: the
confirm step gives a `long_text` field both columns, the bar clears in one press, an active query
that misses gets one line instead of the tall empty state, the status chips fold into a fourth
filter beside sort/shelf/format, and Files becomes its own region on the detail page. Five frontend
changes, no API and no schema.

### [Sprint 030 — Entry depth: the decision](030-entry-depth.md)

**Gated, and Phase A only by design.** Scheduled by DEC-071 after the Sprint 028 assessment
(`docs/domain-expansion-assessment.md`) named it as the **one thing on the whole list that could
force a redesign rather than an extension**. Everything else the assessment found — sorting, search,
facets, field types, manual entry, chrome copy, attachments — is additive and can wait for a real
domain to ask. This cannot: an entry is flat, and hierarchy reaches the entry model, keyset
pagination and its cursor, triage selection, bulk operations, every facet count and the library row.

**It runs before per-domain imports and before any third domain**, because a domain built against
the wrong answer is the expensive mistake, and the answer costs half a sprint.

**The owner's hypothesis, to be tested rather than assumed** (DEC-071):

> Most scenarios can be modelled by going **one level down only** — series into seasons, books into
> chapters if any, albums into songs, at most. And the depth available is decided by **how the
> provider stores it**: if a TV provider returns one entry per season, no finer grain exists to
> model. In the other direction, items can be **grouped into sets** — the individual Harry Potter
> books as one set — and a set may be useful for things other than depth.

**One precedent already exists and Phase A must start from it.** A tracklist is one level down, and
it is modelled as **metadata rows on the item, not as entities** (Sprint 026, DEC-057). It works, it
cost one `inc=recordings` parameter, and nothing hangs off a track. So the question is not "can we
represent children" — we can, today. The question is narrower and sharper:

**Does a child need state of its own?** A tracklist is read-only display. *"Watched through season 3,
episode 7"* is a status on a child. That difference is the whole sprint.

Phase A must produce a written verdict answering, with evidence:

1. **What the providers actually return** — TMDB seasons and episodes, IGDB DLC and editions,
   MusicBrainz recordings — measured against the live APIs the way DEC-052 was, not reasoned about.
2. **Which of three shapes wins**, costed as a table: (a) a per-domain `progress` field on the
   existing flat entry; (b) `rows` metadata plus a progress marker into it; (c) real child entities
   with their own status. And what each costs in pagination, triage, bulk operations, counts,
   export, the import ledger and undo.
3. **Whether "a set" is the same concept as depth or a different one**, since the owner names it as
   possibly useful for other fields. A set that groups items across a domain is not a parent entity.

   **This question is already open in the spec and the two must be answered together.** Product spec
   section 11 item 4 adopts a default — *series is free text in `metadata`, not modelled* — and names
   its own breaking point: *"show me the Malazan books in reading order"*, which needs a real series
   and position pair. DEC-058 flagged the vocabulary collision separately. The owner's Harry Potter
   set and the spec's Malazan series are the same feature asked for twice, four months apart, and
   Phase A answers them once or leaves both open honestly.
4. **What the cheapest thing that satisfies a real user sentence is** — "I'm on season 3" — because
   the assessment's own warning applies here: designing depth from zero serial domains is the
   Strategy-B failure DEC-052 rejected on evidence.

**Phase A concluding "flat, with a per-domain progress field" is a complete and correct outcome**,
and on current evidence the likeliest one. Phase B, if it happens at all, is authorized separately.

### Sprint 031 — Per-domain imports

The last sprint in the plan. Import is book-only today. Sprint 028 moved the two readers into the
domain they serve — `domains/book/goodreads.py` and `domains/book/calibre.py` — so what remains
book-shaped is the layer *above* them: `application/imports.py` and `api/imports.py` assume books
throughout, while the ledger, the preview and undo are genuinely shared and must stay that way. The
boundary this sprint draws is therefore between the shared pipeline and importers that already live
in the right place (DEC-069).

**The coupling was measured on 2026-08-20 (DEC-076), and it is five specific places, not a
feeling.** `api/imports.py` exposes routes named after the two book sources and types the preview
record with book fields (`goodreads_book_id`, `calibre_book_id`, `isbn`, `page_count`, `series`).
`application/imports.py` is two service classes with copy-pasted preview/match/plan logic whose
match call passes `first_author=` and whose identity is ISBN/`calibre_uuid` only.
`ImportRepository.commit` is the worst spot: a *shared* layer that reads `payload["isbn"]` for
identity, builds item metadata from a fixed book key list, sets `type=DEFAULT_DOMAIN.item_type` on
created items, and writes entry fields (`date_finished`, `reread_count`, `review`) that a domain
without those passage fields refuses — the exact shared-layer branching technical spec §6.6
forbids everywhere else. `ImportPage.tsx` and `api/imports.ts` hardcode the two sources as tabs and
typed fields. What is already neutral and must survive the refactor untouched: the batch/record/
effect tables keyed by an opaque `normalized_payload` and a `kind` string, undo, fingerprint
idempotency, and triage — which is domain-agnostic end to end and needs no per-domain expansion at
all, a finding worth stating because it halves the imagined scope.

The outcome is a pipeline where `calibre → books` is one importer among several rather than the
shape of importing itself, so that `spotify → music` and `steam → games` are **epics somebody else
can build in parallel** without touching the core (DEC-058). Concretely: an `Importer` contract
living beside the `Provider` protocol, registered per domain; one generic preview/commit service
and `/api/import/{importer}/...` routes replacing the per-source ones, with the set of available
importers published over the API the way `GET /api/item-types` publishes domains, so
`ImportPage.tsx` renders its tabs from data rather than literals; normalized records validated
against the target domain's own declaration (metadata against `fields`, entry values against
`entry_fields` — the validators `AddService` already uses); and conformance checks in
`test_domain_conformance.py` so an importer is held to the contract by existing. Calibre and
Goodreads are re-expressed against that boundary with **no behavior change** — their existing
suites (`test_goodreads_import.py`, `test_calibre_import.py`) are the regression net. No second
importer is built here, because building one would be the epic this sprint exists to make possible.

**This sprint also absorbs DEC-067 row 6** (DEC-076): manual entry honours the domain. The row was
parked for Sprint 029's rebuild of the add screens and 029 deliberately left it unbuilt
(`/add` names the one domain it can actually make rather than promise one it cannot — DEC-073).
031 is where it lands: `AddService.add` takes the manual payload's domain from the client and
validates it against that domain's field spec instead of binding every manual item to
`DEFAULT_DOMAIN`, and `/add` gains the chooser back — truthfully this time. That is what makes the
+Add surface indicate the domain on *every* path, not only provider adds, and it is what gives a
future third domain a manual fallback from day one.

**And it owns the user-facing account of these flows** (DEC-076): the README names import as
supported and extensible in one bullet and never says what triage is, when a re-run is relevant
(Calibre re-sync fills empty fields only; your edits always win), or that committed rows land
`unsorted` and the default library hides them — the thing that made a successful import look like
a no-op until Sprint 019's copy fix. A real *Importing and triage* section is part of this sprint's
documentation deliverable, and `docs/guides/adding-a-domain.md` gains the importer half of the
story beside the provider steps, so a contributor can build a connector from the guide alone the
way the throwaway game domain proved the domain half.

Closed 2026-08-21. The importer protocol, generic pipeline and routes, registry-driven import UI,
domain-aware manual entry, and contributor/user documentation shipped. The project state is
`complete` per `WORKFLOW.md`'s final-sprint rule; future work begins as a separately scheduled epic.

### [Sprint 032 — Import UX and connector extensibility](032-import-ux-and-connector-extensibility.md)

The last sprint in the plan. Sprint 031 shipped the `Importer` contract and generic routes, but left two owner-visible defects and one architectural gap. Triage is a dead tab unless Import is run first; the Goodreads tab is a bare file input with no guidance on obtaining the CSV; the Calibre tab says only "relative folder only" with no anchor to the filesystem. And the contract has no declarative way for a connector to publish its own help copy, a drag-and-drop affordance, a browsable path picker, or a typed error with a user-actionable message — so the next importer would be a package plus a screen patch, not a package.

The outcome is an import flow that explains itself and a contract that lets a connector guide its own users. Concretely: Triage folded into Import as a tab; Goodreads guidance and drag-and-drop; Calibre guidance and a browsable folder picker rooted at the configured mount; `ImportInputSpec` extended with optional `guide`, `empty_state`, `help_url`; `ImportReadError` extended with `user_message` and `action`; conformance checks so a malformed declaration fails by existing. The existing reader suites are the no-behavior-change net. Documentation follows: README, the domain guide, technical spec §6.5/§7.1, product spec §7.

**Delivered 2026-08-21 (DEC-080).** All of the above, plus one field the contract needed and the plan did not name: `ImportInputSpec.browsable` with a separate `BrowsableImporter` protocol, because an upload has nothing to browse and every future connector would otherwise implement a method it has no use for. `error_codes` became a required member rather than a convention, so the closed set is enforced at the boundary and not merely asserted. `/triage` redirects rather than 404s. The walkthrough gate produced three fixes no test would have: a preview belongs to the connector that produced it, the folder picker states its situation once, and the triage tab does not repeat the surface's own back link. See the sprint file's Outcome.

### [Sprint 033 — Calibre without a mount](033-calibre-without-a-mount.md)

Added at plan revision 15, after the owner used 032's picker against a real library and hit what the
mount actually costs: `CALIBRE_DIR` is a container-level setting, so pointing Akasha at a different
library means editing `.env` and restarting, and the library on the NAS is held open by
calibre-web-automated, which does not support several services reading it at once. Neither problem is
about the picker. They are both about the mount being the only way in.

Measurement said the obvious alternative is not enough on its own: uploading `metadata.db` alone is
one small file, but covers live one-per-book-directory and only 19% of that library carries an ISBN,
so enrichment would refill four covers out of twenty-one and the rest would stay blank. The browser
can read the whole folder, though, and filter it — `metadata.db` plus the covers is 8.7 MB of a 95 MB
library.

The outcome is a Calibre tab you point at a folder on your own machine, with covers, no `CALIBRE_DIR`
and no restart. `ImportInputSpec` gains `kind="directory"` and a one-deep `alternate`, so the mount
picker and the typed path stay on the same tab underneath it (the owner's call — nothing is
deleted). The uploaded bundle is materialized into a temporary directory and read by the **existing**
`CalibreAdapter`, so both paths normalize through identical code and `test_calibre_import.py` remains
the net.

**Delivered 2026-08-21 (DEC-081).** All of it, plus `accepts_files` and one correction the plan
needed: `ImportSource` carries a materialized bundle directory rather than a mapping of bytes, which
the plan's own memory bound ruled out. Measured on the owner's library with the mount empty: 71 files
offered by the browser, 2 sent, 18 covers staged, 10.0 MB. See the sprint file's Outcome.

### [Sprint 034 — Incremental import](034-incremental-import.md)

Added at plan revision 16, from the owner's question about Sprint 033's result: is it reasonable to
drag a 600 MB folder into a browser every time you sync? It is not, and the reason is that
content-addressing dedupes *storage* but not *transfer* — the server can only recognise bytes it has
already received, so an unchanged re-sync pays full price. Measured today: re-importing an unchanged
library still uploads 10.0 MB of covers.

The obvious fix, hashing in the client and asking which digests are missing, was ruled out by
measurement rather than taste: `crypto.subtle` needs a secure context, and while `localhost:8000` is
one, the reverse-proxied `http://books.home.lan` in the runbook is not — `crypto.subtle` is
`undefined` there. It would work when the owner browses the box directly and fail silently from
anywhere else on the LAN.

So the server decides. The client uploads `metadata.db` plus a manifest of `{path, size}`, and the
connector answers which files it actually wants by comparing identities it already holds. On an
unchanged library that is a 416 KB round trip instead of the whole bundle. `ImportInputSpec` gains
`incremental`, matching the `browsable`/`BrowsableImporter` shape, and the plan is never load-bearing:
if it fails, the client sends everything and says so.

**Delivered 2026-08-21 (DEC-082).** Measured through a counting proxy, because Playwright reports a
multipart body of this size as zero bytes: a first import moves 10.55 MB and an unchanged re-sync
0.99 MB — 90.6% less, the gap from 96% being `metadata.db` travelling twice exactly as the plan
predicted. See the sprint file's Outcome.

This is deliberately **before** ebook attachments, which is the next thing the owner wants. Shipping
attachments first would mean 163 MB on every sync — exactly the problem this sprint removes.

### [Sprint 035 — Ebook attachments on a toggle](035-ebook-attachments.md)

Added at plan revision 17, from the owner's question about Sprint 033's copy: why does the Calibre
import promise that ebooks never leave the machine, when attachments already exist and this is their
ideal use case? The owner settled the scope boundary in the same message — attaching files is a
feature of **the importer**, and Akasha's own file surface stays simple and file-type agnostic rather
than growing toward an ebook manager.

Measured on the owner's library: 18 books, 18 epub at 95.4 MB, 14 azw3 at 67.4 MB, and nothing above
the 25 MiB attachment cap. So one file per book in preference order, epub first: 95 MB rather than
163 MB, and one row per book in a list that does not know what a format is.

The files go up **one request each, after the batch commits**, rather than inside the preview bundle.
The bundle route's ceiling is per request, so folding them in would cap the feature at roughly forty
books; per file it is bounded by the attachment cap instead, a bad file costs one book rather than
the import, and skip-and-report above the cap falls out of per-file error reporting instead of being
built.

The real work is undo. DEC-047 made "this item has an attachment" mean "the owner did something
deliberate here, do not delete it" — and an import that attaches files makes that false. Only the
ledger can tell the two apart, so it gains a sixth entity type and reverses an attachment only while
the row still matches what the import recorded. Wrong in one direction it destroys an owner's file;
wrong in the other every imported book becomes permanently un-undoable.

**Delivered 2026-08-21 (DEC-083).** The off-by-default toggle attaches one preferred ebook per
book after commit, one bounded request per file. Planning skips files already present, deleting one
makes only it return, over-cap files are named and skipped, and the undo ledger distinguishes
import-created attachments from owner-created or later-edited ones. The owner-library walkthrough
attached and downloaded 18 epubs (95.4 MB), sent none on an unchanged re-sync, returned one deleted
file, and removed all attachment rows and blobs on undo. The disk cost remains stated rather than
bounded: roughly 3.2 GB for 600 books at the measured mean, with backups holding ~1.0 effective
copies only while `BACKUP_DIR` shares a filesystem with the data directory.

### [Sprint 036 — Import and triage flow](036-import-triage-flow.md)

Added at plan revision 18 from the owner's first use of the completed Calibre import. Connector tabs
and Triage were peers even though they answer different questions: which source to import, then how
to review what arrived. Triage also made every pointer edit pretend to be bulk work — click the row
to select, open a bulk menu, choose one score — when the common action is reading down a list and
deciding each entry independently.

**Delivered.** The route and high-volume workflow remain. `/import` has a visible two-step hierarchy
with source tabs nested under Import. A row's status and score edit that row directly; only its
checkbox selects, while Shift ranges, Ctrl/Cmd+A, the bulk toolbar and keyboard shortcuts remain.
Row-body clicks open detail. Native selects stay in the row's tree, mobile rows do not overflow,
and a short inbox no longer reserves an empty 70vh panel (DEC-085, DEC-086).

### [Sprint 037 — Triage page flow and staged statuses](037-triage-page-flow.md)

Added at plan revision 19 from the owner's first sustained use of row-local Triage controls. The
fixed-height virtual inbox still nested a 70vh scroll surface inside a page, wasting the document's
vertical space. More importantly, changing status immediately invalidated the Inbox-only query, so
the row blinked back or left before the owner could finish reading its neighbors.

Move Triage to the same window-virtualization contract as the Library. Keep row status choices as
visible drafts until an explicit apply, with discard and retryable partial failure; scores and
explicit bulk actions keep saving immediately.

**Delivered.** Triage uses document scrolling with bounded window-virtualized rows. Status choices
stay visibly staged until Apply or Discard; Apply groups equal choices into existing bulk requests,
clears successful groups and retains failed groups for retry. The pending and explicit-bulk action
surfaces form one non-overlapping sticky stack, while score edits and explicit bulk actions remain
immediate (DEC-087).

### [Sprint 038 — Anime: the third domain](038-anime-domain.md)

The domain contract's promise, exercised by somebody following it rather than by the person who wrote
it: a package under `domains/anime/`, two provider adapters, small explicit registration points, **no
migration and no screen**. Providers were measured live rather than chosen from documentation
(DEC-088) — AniList first, Kitsu second, and Jikan rejected after returning HTTP 504 to every request
across a forty-minute window while MyAnimeList itself answered in 0.66s.

Two things here are new. It is the **first domain since books with a real cross-provider identity**:
both providers publish the MyAnimeList id, so `identity_key` returns `mal:<id>` and candidates
genuinely merge, where albums correctly answered `None`. And AniList is the first provider that a
missing User-Agent turns into a Cloudflare 403, which the adapter owns.

A deliverable of equal weight to the code: **a written report on whether
`docs/guides/adding-a-domain.md` was sufficient on its own.** The guide claims a third domain never
needs to read how the second was built. This is the sprint that finds out.

### [Sprint 039 — Enrichment beyond the ISBN](039-enrichment-beyond-isbn.md)

DEC-067 row 3 named its own trigger — "the first domain that wants background enrichment on a
non-ISBN key pays for (b) then, with a real case to design against instead of a hypothetical one" —
and costed it at about half a sprint. Anime is that case. An imported MyAnimeList row is an id, a
title, a type and an episode count; `_backfillable_items` joins on the literal `'isbn'` and `_fetch`
calls `fetch_by_isbn` against a module constant naming two book providers.

A domain declares its enrichment key and its provider order; nothing above the registry names an
identifier kind or a provider afterwards. **Books' behaviour must not change**, and the existing
enrichment tests are the guard rather than something to relax. No migration: a job is a row with a
JSON payload, and this changes what is written into one — including a compatibility path for jobs
already queued under the old shape, which is the failure nobody would notice.

### [Sprint 040 — Entry progress](040-entry-progress.md)

DEC-077 priced entry depth over nine shared surfaces, rejected child entities on evidence, chose
shape (a) — "a per-domain `progress` field, declarative under the Domain contract" — and **built
none of it**. Every row of the owner's export carries `my_watched_episodes`; one is `Black Clover`,
dropped at 20 of 170. The entry model has three passage fields and nowhere to put that number.

A `ProgressSpec` on the domain, a nullable `entries.progress`, a validator beside the three that
already exist, a control that renders only where a domain declares one, and the value carried in the
export. **This is the only shared-table change in the whole line**, which is precisely why it is its
own sprint and its own migration. It adds a field to the flat entry; it must not add depth, and
`test_flat_entry_contract.py` is what says so.

### [Sprint 041 — The MyAnimeList import](041-myanimelist-import.md)

The connector, against the owner's real 81-row export, parsed and measured at planning time rather
than assumed: gzipped XML, `series_animedb_id` distinct on every row, `my_score` of `0` meaning
unrated, `0000-00-00` meaning absent, and scores that map 1:1 rather than doubling the way Goodreads'
stars do. It lands complete because 039 fills the records and 040 holds the watched-episode counts.

Its sharpest acceptance criterion is a negative one: **no change to `application/imports.py`,
`api/imports.py`, `ImportPage.tsx` or `TriagePage.tsx`.** Sprint 032 made connectors self-describing
so that adding one is a package plus one tuple entry. Whether that held for a connector written by
somebody who did not write the pipeline is the finding, either way it goes.

### [Sprint 042 — One decision per Triage row](042-one-decision-per-triage-row.md)

Inserted by owner direction at plan revision 22 after the first real anime triage. The screen
currently presents the same decision twice: the persisted Inbox status in a select and an imported
target in a separate chip. Rows without an imported target present no useful default, and approving
an already-correct row requires leaving it for a page-level toolbar.

Each row instead presents one target in its native select: the importer suggestion when present,
otherwise the domain's declared default. Inbox is implied by the screen and is neither displayed
nor choosable. A row-level Apply commits the displayed target in one click; the existing page-level
staging, discard, partial-failure and explicit bulk flows remain for multi-row work.

**Delivered 2026-08-27 (DEC-095).** The target precedence and row Apply shipped without a backend,
API or schema change. The real-data walkthrough imported 81 anime and 18 Calibre books into a
disposable Inbox and verified both sources use the same row flow at mobile width.

### [Sprint 043 — Row-only Triage decisions](043-row-only-triage-decisions.md)

Added at plan revision 23 from the owner's hands-on approval pass over Sprint 042. The row action
becomes a quiet icon-only check, and the now-redundant global Apply/Discard toolbar disappears. A
row's target remains a draft until its own check is pressed, but that draft survives navigation and
refresh within the browser tab so reviewing a detail cannot erase work in progress. Explicit
checkbox bulk actions remain.

**Delivered 2026-08-27 (DEC-096).** The final approved interaction shipped in `bb474c7`. The
real-data walkthrough proved a draft survives Library navigation and refresh before its row check
commits it, and exercised direct and overridden anime targets without console or page errors.

### [Sprint 044 — Sharpening the domain contract](044-sharpening-the-domain-contract.md)

The anime-line retrospective originally planned as Sprint 042 moved twice without changing its
scope. It followed the owner-visible Triage corrections and remained deliberately non-visual.

**Delivered 2026-08-27 (DEC-097).** Every entry write path now shares an allowlisting validator;
the conformance suite proves built provider/recognizer/cover wiring; the head-schema suite rejects
application vocabularies frozen into CHECK constraints; `EntryRow` has one construction site; and
the load-bearing migration and UI-driving recipes are recorded. No runtime behavior, migration,
API contract or screen changed.

### [Sprint 045 — Movies viability: providers and Letterboxd shape](045-movies-viability.md)

**Gated.** The historical metadata survey calls TMDB the strongest next provider, but that report is
not current live evidence. This sprint tests credible movie providers against real responses and
current official constraints, walks flat films through the domain contract, and measures the
owner's private Letterboxd export structurally. It writes no movie runtime code.

The gate closes by planning at least two ordered implementation sprints: movie domain and valid
providers first, Letterboxd importer second. A credential or terms decision that only the owner can
make is reported explicitly rather than worked around with scraping.

**Measured and closed 2026-08-27 (DEC-098).** Wikidata passed current live film search, localized
structured-data and exact external-identity probes and is the launch provider. TMDB's richer API is
not selected: no credential exists and its six-month content-cache rule is incompatible with the
current permanent owner-editable cache. The private ZIP's topology and semantics were measured
without committing personal data. Sprints 046 and 047 are the executable result.

### [Sprint 046 — Movies: the fourth domain on Wikidata](046-movie-domain.md)

**Completed.** The flat movie domain and the keyless provider Sprint 045 measured live. Wikidata
supplies stable cross-catalogue identities, Spanish/English labels and structured film metadata
through its official API. Arbitrary `P18` photography is not called a poster. External Wikidata,
IMDb, TMDB and Letterboxd URLs resolve through exact claims; short Letterboxd URLs use HEAD only and
no page scrape. No migration and no movie-specific screen.

Two things the plan did not know, both now measured and recorded in DEC-099: a search is six
candidates in bounded batches rather than twenty in one read, because ten entities are 1.9 MB against
a 2 MiB response limit; and a `haswbstatement` hit is not proof of the claim, so an identity lookup
re-checks the value on the fetched entity.

### [Sprint 047 — Letterboxd import for movies](047-letterboxd-import.md)

The owner's multi-CSV ZIP becomes one movie record per exact Letterboxd URI, with watched/watchlist,
half-star-to-ten-point scores, dates, rewatches, plain-text reviews and tags mapped explicitly.
Wikidata enrichment resolves the stored short URI after commit. A neutral title+year matcher offers
an ambiguity for a movie already added through Wikidata and never auto-merges. Private data remains
walkthrough input; synthetic fixtures prove every source shape and archive failure.

**Completed**, and at a reduced verification level the owner directed (DEC-102): the API and
enrichment path was exercised against the owner's real archive, and Playwright, the walkthrough gate
and frontend tests for the new declaration were not run. Undo has no coverage in this sprint.

Three things Sprint 046 settled or found that this sprint inherited. The adapter already accepts a
short URI, a slug and a film URL for the same `letterboxd` identity, so no normalization pass is
needed at import time (DEC-100). `DomainRepository.match` scans **every** item row with no
`items.type` filter — tolerable for title+author, wrong for title+year, where a novel and its
adaptation routinely share both — so the year suggestion must be scoped to the importer's target
domain. And Triage has never been exercised with a movie row, because nothing produced an unsorted
film before this connector; the walkthrough here is its first real test.

### [Sprint 048 — Movie posters, without a setup step](048-movie-posters.md)

**Completed.** Added at plan revision 26 from the owner's first real Letterboxd import: the films arrived, and every
one of them was a blank tile. Sprint 046 shipped movies coverless because Wikidata has no posters,
which was correct about Wikidata and wrong about what the owner would see. Posters come from
Stremio's keyless image service, measured at 14 of 14 on a deliberately hard sample and costing zero
API calls because its URL is deterministic from the IMDb id already stored. TMDB fills only the ~2%
of films that carry a TMDB id and no IMDb id.

### [Sprint 049 — Series: the fifth domain, with posters on day one](049-series-domain.md)

Television series, flat, on keyless Wikidata, with a working poster and a working episode-progress
control from the first commit. **Sprint 048's lesson applied before the fact:** movies shipped
coverless because the provider had no posters, which was true about the provider and wrong about what
the owner would see. Series has posters in the same sprint as the domain, from the source and the
allowlisted host that already serve films.

The domain introduces **no new status and no new format** — anime's five statuses and the movie
four formats are exactly right and already published — so registration points 4 and 5 of the guide do
not apply and `ItemTypeName` is the only published-vocabulary change. Progress is `ProgressSpec` over
an `episodes` total: the case DEC-077 rejected hierarchy for and Sprint 040 built.

One measured finding drives the adapter and is the reason this is not a copy of the movie one: the
movie search filter **does not transfer**. A single `haswbstatement:P31=Q5398426` found the right
series for 9 of 14 titles and nothing at all for two; a five-class filter found 14 of 14 (DEC-104).

### [Sprint 050 — TVmaze: the second series provider](050-tvmaze-provider.md)

The fallback, keyless like the primary. It supplies the three things Wikidata structurally does not:
a synopsis somebody would read, an airing status, and the Spanish-language shows Wikidata's title
index does not surface. Both providers publish the IMDb id, so candidates genuinely merge — the first
domain since anime where that is true.

Two deliberate refusals inside it. `episodes` is **not** taken from TVmaze, because its count and
Wikidata's disagree and `fill_empty` would let whichever answered second win a field that drives a
progress control. Covers are **not** taken from TVmaze either: its variants measured 210×295 and
2000×3000, either side of the pipeline's target, while Stremio's 500×750 is already installed.

It ships a credit line. TVmaze's licence asks for one and the owner chose to give it, having declined
TMDB's three days earlier — DEC-105 records why the two are different questions, and defers CC BY-SA's
share-alike half explicitly so that it is found if sharing is ever built.

### [Sprint 051 — The verification gates get faster](051-verification-gate-optimization.md)

The four items in `docs/agent/TESTING.md`'s *Optimization backlog*, implemented as a sprint so the
three import sprints after it pay cheaper gates. Owner-directed at plan revision 28 (DEC-111).

The backlog items, verbatim from TESTING.md: split Playwright into a parallel ordinary project and a
serial heavy-library project (today the whole suite uses one worker because two `library.spec.ts`
invariants are load-sensitive); remove the known Vitest harness noise (a deliberate
`window.scrollTo` shim — already present — defined attachment-query fixtures, and properly awaited
Radix/motion state updates), preserving real console failures; promote the local realistic-data
flow to a tracked, sanitized launcher that creates a temporary data directory, starts and stops the
backend, and accepts the library path in one command; and add bounded test timeouts or phase timing
where a deadlock currently looks like slow work.

No application behavior changes; every acceptance criterion is a gate property. The backlog section
is removed from TESTING.md at closure because nothing is left in it.

### [Sprint 052 — One source, many libraries](052-multi-domain-imports.md)

The seam both importers force, built before either of them. A television tracker tracks films too:
IMDb's CSVs and Trakt's archive each carry films and shows in one file, and `Importer.item_type` is a
single string the shared service resolves once per batch.

The owner was offered the cheap alternative — two connectors per source, one per domain, nothing
shared changed — and chose against it: importers should hold multi-domain sources properly, and
*"users choose the importer SOURCE, not the target type, that is decided downstream"* (DEC-106).

Measured against the code, that costs less than it looks. The Import screen is **already**
source-shaped and ignores `item_type` entirely; Triage **already** renders statuses and hotkeys from
each row's own type; `_backfillable_items` **already** loops over every domain. What is left is the
declaration, per-record domain resolution at three call sites, the commit signature, a target
selector rendered from the declaration, and folding the chosen targets into the preview fingerprint —
without which the same file imported as films and then as series silently returns the first preview.

Built and proved against a **test** connector, not against IMDb. A seam proved only by the connector
it was built for is not proved, which is DEC-093's lesson applied ahead of the failure this time.

**Delivered as planned.** Per-record resolution reached exactly the call sites the plan named and no
further — Triage and undo needed no change at all, only proof. The two mechanisms DEC-106 left open
became DEC-112: a reader reports what it cannot target as a tally rather than as discarded records,
and the chosen target set folds into the fingerprint only when it is a strict subset, which is what
makes the change migration-free.

### [Sprint 053 — The IMDb import](053-imdb-import.md)

The owner's real exports, measured at planning time: **two different CSV shapes**, a ratings export
and a list export (the Watchlist is one), sharing a core of columns but differing in header and in
where the rating columns sit. Both carry the `tt` id on every row, which is the identity both target
domains already resolve — so a film imported from Letterboxd and enriched through Wikidata matches
**exactly** rather than by title and year.

`Title Type` routes each row, through a declared table whose default is *skip and count*. A title type
IMDb has not published yet must appear as a number on the preview screen, never as a failed import.

Its sharpest acceptance criterion is the negative one Sprint 041 established: **no change to
`application/imports.py`, `api/imports.py`, `ImportPage.tsx` or `TriagePage.tsx`.** If that cannot be
met, the finding is the deliverable and Sprint 052 was incomplete.

**Delivered, and the negative criterion held**: the connector is one new module plus one line in the
registry, and no shared file changed. What did not hold was enrichment — the movie domain enriched on
`letterboxd` alone, so every film from an IMDb export would have stayed permanently thin in silence.
`EnrichmentSpec.identity_kinds` is a tuple now (DEC-113). The walkthrough ran against the owner's real
exports and paid Sprint 047's debt (DEC-102) on the way.

### [Sprint 054 — The Trakt import](054-trakt-import.md)

A ZIP of 43 verbatim `/sync/*` responses, 26 of them empty in the owner's archive. The interesting
half is the roll-up: `watched-history.json` is the only member with episode detail, and distinct
`(show, season, number)` events excluding season 0 become the entry's progress, against
`aired_episodes` as the total at export time. In the owner's archive that produced 76 and 38, matching
`plays` exactly — which is why the `plays` fallback needs a synthetic fixture of its own.

Two members are **never opened**: `user-settings.json` and `user-profile.json` carry the owner's email
address, and a test asserts nothing reads them. Season and episode ratings are counted and discarded,
because a series holds one score — DEC-077's line, restated where somebody would otherwise be tempted.

Closing this sprint used to put the release decision in front of the owner. Sprint 055 now sits
between, so that decision is made on a library with no known open defects in it.

### [Sprint 055 — The recorded defects, and the gates that stopped paying](055-recorded-defects.md)

Short, and last. Every defect the movie and series lines recorded and left, plus the three places the
verification gates now cost more than the evidence they buy. No new product behaviour.

The product half: a series stores the synopsis somebody would actually read rather than Wikidata's
one-line description, which is the fill-empty rule (DEC-110) being right for most fields and wrong
for one class of them; and the two defects DEC-100 named — a backfill that re-queues rows for ever on
conditions their domain never declared, and a `resolve` route that calls a clean miss a provider
outage.

The gate half is measured rather than asserted (DEC-114). Sprint 051 bought four things; three held.
The parallel Playwright split has **not passed once** — 1 to 2 failures on three of three runs, always
the same two rendering-timing tests, both green serially — so a session runs the 101.7 s serial gate
afterwards anyway and the split costs more than it saved. Two larger costs that sprint never looked
at: coverage sits in `addopts` and charges 26 s and a 60-line table to *every* backend run including
the focused ones the playbook asks for, and the lint gate reads `frontend/e2e/scratchpad/`, so
writing a local walkthrough turns `make check` red on a file that is not in the repository.

### [Sprint 056 — The deployment defaults a home server needs](056-deployment-defaults.md)

The shipped configuration and the operator documentation, with the container smoke test as its gate.
No application behaviour changes.

The published port becomes **4441** — 8000 is among the most contended ports on a machine that runs
anything else, and this is the one default in the line that breaks an existing install, so the
release notes lead with it. Container logs get a size bound, because Docker's `json-file` default has
none and uvicorn's access log is on. The three settings that are documented in `.env.example` or live
in `config.py` but never reach the container — the attachment cap, the SQLite busy timeout, the TMDB
token — become explicit passthroughs, deliberately not `env_file:`, which would inject the example's
`BOOK_TRACKER_ENVIRONMENT=development` and disable the production guard on `USER_AGENT_CONTACT`. The
healthcheck's start period grows to admit DEC-039's pre-migration backup on a slow disk. A third
overlay lets `/backups` go to a second disk while `/data` stays a named volume, which is what DEC-040
asks for and DEC-075 currently makes impossible to have at the same time. And the exposure boundary
gains the sentence it has always been missing: a host joined to a VPN or mesh network carries an
extra interface that `AKASHA_BIND=0.0.0.0` publishes on too.

### [Sprint 057 — The names the product actually uses](057-product-names.md)

The two cheap layers of the naming assessment (DEC-119): the environment prefix becomes `AKASHA_` — a clean break, owner-directed, no alias, landing before v1.5.1 is tagged — and the API title drops "Book Tracker" for the brand. The `book_tracker` package itself is untouched: DEC-042's rejection and the internal-names invariant stand. Full gate owed (backend/src and generated contracts change).

### [Sprint 058 — An image you pull, not a build you run](058-published-image.md)

An upgrade becomes `docker compose pull && docker compose up -d`. Today `compose.yaml` carries
`build: .`, so every server needs the source tree, both toolchains and three reachable registries,
and pays a full frontend build per upgrade — while the artifact CI already smoke-tests is thrown
away.

A workflow publishes the image on a `v*` tag using the workflow's own token, so no secret is created.
Compose points at the published image and the local build moves to its own overlay, because a service
carrying both `image:` and `build:` builds silently when the image is missing — which is the failure
this sprint exists to remove, arriving disguised as success. Base images get pinned by digest, and
Dependabot opens the pull requests that keep them current, gated by the three CI jobs that already
exist. Three steps need the owner's own account — allowing the workflow to write packages, pushing
the tag, and deciding the package's visibility — and they are written out step by step, with expected
results, in the sprint and in `docs/operations/publishing-images.md`.

### [Sprint 059 — Nothing blocks the event loop](059-off-the-event-loop.md) **[GATED]**

Every API handler is `async def` and there is no `to_thread` or `run_in_threadpool` anywhere in the
backend, so every SQLite query, Pillow resize and import parse runs on the single event loop of a
single worker. That is a legitimate design for one user. What is missing is evidence: DEC-036's 82 ms
idle against 312 ms contended is the only contended number this project has, it was a *read* path,
and it was measured on a workstation.

Phase A measures request latency while a large import commits, while enrichment installs covers and
while an attachment uploads — inside the container, under an explicit CPU constraint, because a
measurement taken on fast hardware answers a question nobody asked. Phase B moves work off the loop
through one seam, and only for what Phase A named. **Phase A concluding that nothing needs changing
is a pass**, written into the acceptance criteria as one, following DEC-035 and DEC-042. If Phase B
does run, the load-bearing proof is that foreign keys, WAL and the busy timeout still hold on a
connection used from a worker thread.

### [Sprint 060 — The disk stops filling quietly](060-storage-housekeeping.md)

Three growth paths have no collector. `/data/imports/<batch_id>` is written by every preview — one
prepared JPEG per book for a Calibre library — and removed by nothing, not by commit, not by the
expiry of the undo window, not by `akasha-attachments reclaim`. `covers.tar.gz` and `imports.tar.gz`
are rebuilt in full on every backup, where DEC-047 already solved exactly that problem for
attachments by hardlinking them, with the measurement that made the case. `pre-migration` backups
accumulate for ever: never pruned by nightly retention, which is right and is DEC-039's whole point,
but removable by no command either. And there is no free-space check anywhere in the codebase, so a
full disk is discovered halfway through a write.

Each gets a collector or a documented reason it has none, and a write that cannot complete is refused
before it starts rather than failing partway. The highest risk in the line lives here: changing what a
backup contains means an older backup must still restore, and if that cannot be proved, the sharing
does not ship.

### [Sprint 061 — Drag Calibre's own export bundle into the Calibre tab](061-calibre-export-bundle.md)

A third way into the Calibre tab, beside the folder picker and the mount: the
`part-NNNN.calibre-data` files Calibre's own *Export/import all calibre data* feature produces, with
the same preview/commit/undo experience every other Calibre path has. Generalizes
`ImportInputSpec.alternate` to `alternates`, adds an `"export"` input kind for a set of opaque files
a source's own export feature produced, and takes the ebook attachment for free — the export's bytes
are already local once uploaded. See DEC-124.

### [Sprint 062 — Search and add survive a provider having a bad day](062-providers-under-strain.md)

Three providers were degraded at once on 2026-09-02, and each one exposed something of ours behind
it. Wikidata's query-service replicas are chronically lagged, so the contractual `maxlag=5` both
adapters send refuses every read and blacks out the single-adapter movie domain. That outage
uncovered two defects latent since Sprint 050: TVmaze hardcodes `language="en"`, which the add path
folds into a metadata patch the series domain refuses, so every TVmaze-sourced series add is a 422;
and TVmaze never builds the keyless Stremio poster from the IMDb id it already holds, so a
Wikidata-less series has no cover. MusicBrainz's `503` throttling outlives a two-attempt budget, and
Kitsu's measured latency sits above the 5 s search bound that AniList's upstream shutdown now leaves
it alone inside.

The unifying fix is the second one: a candidate's `language` reaches metadata only where the domain
declares that field. The rest is a provider telling the truth about what it observed, and two budgets
matched to measurements rather than guesses. See DEC-125.

### [Sprint 063 — A second source for films and shows](063-cinemeta-second-source.md) **[PLANNED]**

Sprint 062 removed the self-inflicted half of the movie outage; this adds the redundancy the other
half needs. Movies are served by one adapter, and the blocker to adding a second is not the adapter
but the identity: `MOVIE_IDENTITY` keys on the Wikidata `Q` id, so any second provider would
duplicate every film rather than merge with it. Series already key on IMDb and need no such change.

Cinemeta — Stremio's keyless, IMDb-keyed metadata service, measured on 2026-09-02 at 6/6 searches
and full field coverage in 0.09–4.45 s — becomes a complementary source for both domains through one
shared reader, ranked behind the sources already there and never displacing them. It is not a new
third party: DEC-103 already routes every movie and series poster through the same infrastructure.
The film identity moves to IMDb, which the Wikidata adapter already emits on every measured result.

Gated on a measured coverage assessment first (the DEC-104 method, with a stop condition), because a
fallback that answers worse than the thing it backs up is not a fallback.

### Sprint 064 — A second source for anime and albums **[PLANNED, not yet written]**

The other two single-provider domains, split from 063 because each is blocked on something 063 is
not. **Anime:** Jikan is the obvious candidate — it is MyAnimeList's API, and `mal:` is already the
anime domain's declared identity, so it would merge with Kitsu for free. But its search endpoint
answered `504` on every attempt on 2026-09-02 while MyAnimeList itself was up, so the sprint opens
by re-measuring whether it is dependable enough to be worth the adapter. **Albums:** blocked by
DEC-052, which found deliberately that albums have *no* cross-provider identity — barcode
`888837168625` appeared on three distinct releases — so a second provider means un-mergeable
duplicate rows in every search. That is a product decision to reopen with the owner, not an adapter
to write. Deezer and iTunes were both measured keyless and working; neither can merge until the
identity question is answered.

### [Sprint 065 — The Spotify import, and the album domain's first enrichment](065-spotify-album-import.md) **[PLANNED]**

The epic DEC-076 declined to commit to, now measured and buildable — see
[`spotify-import-and-insights-viability.md`](../spotify-import-and-insights-viability.md). The
finding that unlocks it is that MusicBrainz stores Spotify links as URL relationships, so an
exported `spotify:album:` id resolves to an exact release: 73% of the owner's saved albums by
relation alone, ~95% once a strict title-and-artist search covers the rest. That turns what DEC-052
would otherwise force into a fuzzy-matching exercise into an ordinary importer, and the remainder
goes to Triage rather than being guessed at.

Its one structural change is giving the album domain an `EnrichmentSpec`, which it deliberately
lacks: one MusicBrainz fetch really does return everything a *search-added* album has, but an
imported stub is the case background enrichment was built for. Keyed on `spotify`, so a
search-added album is still never queued.

Scope is narrower than the export: the 157 saved albums, not the 406 reachable through playlists,
and track roll-up opt-in and threshold-gated because it adds only 41 albums of which just 9 have
more than one saved track.

### Sprint 066 — Insights: rankings from the fields items already declare **[PLANNED, not yet written]**

Aggregate entry scores by a keyed field — creators, genres, publisher, label, network — and rank
the keys, so "top authors" and "top artists" fall out of the ratings already recorded instead of
each becoming a domain with its own identity, providers and screens. The domain spec already
publishes the groupable surface, and `creator_sort_override` already solves the name-variant
problem, so perhaps a quarter of the backend is standing.

Three things make it a real sprint rather than an endpoint: `multiplicity == "many"` is the wrong
rule for which fields are keyable (`tracklist` is a list of rows; `catalog_number` is near-unique),
so `FieldSpec` needs an explicit `groupable`; ranking needs a statistic that does not put one 10
above eleven 9s; and `Various Artists` — 7 albums in the owner's Spotify library — is not an artist.

**Deliberately sequenced after 065**, because the feature is worth exactly as much as the share of
entries carrying a score, and that is unmeasurable against a 13-entry library. The Spotify import
produces the dataset this would be judged by.

## Future epics, after this plan

These are not sprints and remain deliberately unnumbered (DEC-058). Each becomes an epic on top of
Sprint 028's contract and Sprint 031's import boundary.

Each of these inherits the **extended** import contract (DEC-080): a connector declares its own
guide, empty state, help link, browsability and error vocabulary, so it is a package rather than a
package plus a patch to `ImportPage.tsx`. A Steam or Spotify connector writes its guidance steps and
its `action` sentences beside its reader, and the shared screen renders them without being told.

- **Games — IGDB.** Carries DEC-052's prediction that games need no seam albums did not; Sprint 028's
  conformance suite is where that gets checked. The new infrastructure is authentication: IGDB needs
  Twitch OAuth client credentials and token refresh, where every provider so far has needed at most a
  static API key. `steam → games` is the import.
- **Series — ~~TMDB~~.** **No longer an epic: scheduled as Sprints 049–054** at plan revisions 27–28.
  The product decision this was gated on had already been made — DEC-077 priced entry hierarchy across
  nine shared surfaces, rejected it, and chose a per-domain `progress` field, which Sprint 040 built
  and anime has used since Sprint 041. What remained was a provider question, and the answer is not
  TMDB: Wikidata and TVmaze both answered live with no credential (DEC-104), where TMDB needs a key
  and carries the six-month cache limit Sprint 045 measured. The vocabulary collision this entry
  warned about still stands — book-series remains a free-text `metadata` field and product spec §11
  item 4 records the deliberate choice not to model it.

- **Music imports — `spotify → music`.** The natural first exercise of Sprint 031's boundary, and
  deliberately **an architecture goal, not a commitment** (DEC-076): the owner is in no hurry to
  build it and wants the ground stable underneath first. Its design constraint is real, though —
  Spotify imports are playlist/saved-*track* shaped, so whether it rolls tracks up to albums or
  models songs directly is a Sprint 030 question, and the epic is shaped by that verdict whenever
  it is picked up. **The verdict (DEC-077) answers it:** a track is metadata on the album (the
  `rows` precedent), not a child entity — so a Spotify importer rolls saved tracks up to their
  albums and never touches the entry model. That is precisely the "plug and play with the music
  system" outcome the boundary exists to make possible. Spotify is an OAuth source rather than a file, a
  folder or a mount, so it is the first test of whether `ImportInputSpec`'s kinds are enough —
  `upload | path | directory` are all still things you hand over, and an authorization handshake is
  none of them.

## Owner feedback — recorded 2026-08-14, unscheduled

Raised while trying Sprint 025's albums in the running application. **All of it is now delivered**:
items 2 and 3 by Sprint 026, items 1, 4 and 5 by Sprint 027. The causes below were
traced when the feedback was recorded, so the sprints that pick them up start from evidence rather
than from a rediscovery. The status half became **DEC-057** and the ownership half **DEC-059**.

### 1. The library should select a domain, not mix them

**Delivered by Sprint 027.** The default was the one real question and the owner settled it: the last domain used, remembered between visits (DEC-062).

> "The main library should really have a tab selector to choose between domains, there is no point
> in showing books and albums combined."

Sprint 025 deliberately left the list endpoint with **no `type` filter** — AC4 asked only that a
mixed library paginate correctly, and it does. This is the other half of that decision, and the
walkthrough supports it: books and albums beside each other read as a mixed bag rather than as one
library.

Small, and it lands naturally beside Sprint 026's filter-chip work: a `type` parameter on
`GET /api/entries`, a tab strip fed by `GET /api/item-types` (which already serves the domain list
and labels), and a remembered choice in the URL the way every other filter already is. The one real
question is what the default is — all, or the last domain used.

### 2. Albums should carry their tracklist

> "Albums should really come with songlists as metadata."

**Measured 2026-08-14: this is one query parameter.** The release fetch already asks MusicBrainz for
`inc=artist-credits+labels+media+release-groups`; adding `recordings` returns every track's position,
title and length in the same request — 6.4 KB for *Kind of Blue*, no extra call, no extra rate-limit
budget.

Sprint 025's non-scope said "tracks as entities" belongs to Sprint 028's entry-hierarchy question,
and that still holds: a tracklist stored as **metadata** on the album is not that. It needs a field
type the spec does not have yet — an ordered list of structured rows rather than a line of text —
which is the only reason this is not already done.

### 3. Format and ownership tags

> "Maybe categories like CD/Digital/Vinyl as tags? It can transfer to books as well
> (physical/borrowed/digital)."

Cuts across domains, which is what makes it interesting and what makes it need a decision first: it
overlaps `owned` as a status. **DEC-057 states the overlap and recommends an answer**; Sprint 026
has to settle it before either is built. Note that an album's `format` already arrives from
MusicBrainz as metadata (`CD`, `12" Vinyl`) — as a *property of the release*, not as a fact about
your copy, which is a different thing wearing the same word.

### 4. The library grid is a window inside the page

**Delivered by Sprint 027.** The virtualizer measures the window; Sprint 013's scale and feed-semantics checks were re-run against the new model rather than assumed.

> "The main coverart/library scroll does not use the entire page, it's a window, even though it's
> the primary thing we are looking at."

Concrete cause: `frontend/src/features/library/VirtualLibrary.tsx` gives the scroll container
`h-[min(70vh,760px)]`, so the grid is a fixed box with its own scrollbar inside a `max-w-7xl` page
(`pages/HomePage.tsx`). The virtualizer measures that element, which is why it was written that way
— it is not decorative.

The fix is to let the **page** scroll and have the virtualizer measure the window instead, which
`@tanstack/react-virtual` supports directly. Not a large change, but it touches the one thing Sprint
013 was called in to repair, so it wants its own slice with the scale tests (10,000 entries, the
accessibility feed semantics) run against it rather than being folded into a feature sprint.

### 5. Shelves are too far from the thing being shelved

**Delivered by Sprint 027**, on the detail page and — a third friction nobody had named — in the triage bulk bar, where *Add shelves* had been specified since v1 and never built.

> "Shelves kinda suck, having to create them by going on a new screen + having to click 'edit
> opinion' to be able to change them is not ideal."

Two separate frictions, and the second is the sharper one: shelf membership lives inside
`OpinionDialog`, so putting a book on a shelf means opening a dialog named after something else.
Creating a shelf is a whole route (`/shelves`).

Both are UI-shaped rather than model-shaped — `POST /api/shelves` and the entry's `shelf_ids` already
do what is needed, and bulk shelf assignment already exists in triage. Likely shape: shelf editing
inline on the detail page and on a card, with create-on-type in the same control.

## Scheduled from owner feedback

### One search bar on `/` — adding and searching in the same place

Owner feedback, 2026-08-15, after Sprint 027's second pass: *"the main page should have both
functionalities open to the user: adding and searching for your data… 1 large searchbar up top for
both,"* with the domain selector to its left and an **Add** button to its right, a local search that
consults no provider when it hits, and a web search below when it misses.

**Scoped in `docs/unified-search-proposal.md`, accepted as DEC-065, and scheduled as
[Sprint 029](029-one-search-bar.md).** The owner amended it twice: **"All" is removed as a filter**,
so the tab strip always names exactly one domain and nothing has to ask which domain a search
means; and the confirm step becomes a dialog **on condition that no functionality is lost**, which
the sprint carries as an eleven-row inventory rather than an intention. A web search fires only once
a query has settled and returned nothing, or on the button — the literal "no local hit" rule fires
once per keystroke while typing any new title, which breaches the Google free tier DEC-044 already
measured.

**Delivered and closed 2026-08-17.** The inventory grew to thirteen rows during the sprint and all
thirteen carried over; the firing rule gained three clauses in the building and is recorded as built
in DEC-073.

## Not scheduled

- **Auth.** Product spec section 9 keeps this a v2 deferral with no sprint number, reaffirmed by the
  owner during the revision-8 re-plan. It remains the gate on any exposure beyond LAN: no public
  DNS, port-forwarding, tunnel, or internet-reachable proxy until it exists.
- **Sharing, multiuser, Calibre write-back, OPDS.** Product spec section 9, unchanged.
- **The owner feedback above**, until it is scheduled.
- **Wine and the remaining exploratory domains.** `docs/domain_metadata_roadmap_report.md` assesses
  them; none is scheduled. Wine's weakness is access economics rather than catalogue geography. That
  report's anime verdict — "a good domain, wrong default provider" — is **superseded by DEC-088**,
  which measured the providers instead of reading their documentation and reached a different answer.
- **Re-file an item into another domain** — "this series is really an anime", or "I imported this into
  the wrong library". Raised by the owner on 2026-08-31 while reviewing the series plan, costed, and
  deliberately **not** made a sprint in that line.

  It is not a "move to anime" button, and `docs/guides/adding-a-domain.md` §8 explains why: there is
  no item-type change path anywhere in the application, `items.type` is written at creation only, and
  a moved item would carry an `imdb:` identifier into a domain whose enrichment looks for `mal:` —
  stranding it from every anime provider for ever. Six of a series' twelve metadata fields have no
  home in anime and would sit orphaned in `metadata_json`; a `DVD` format would become undeclared.
  Status and progress are the only two things that survive a naive move intact.

  The shape that works is a **re-file**: search the target domain's providers by title, have the
  person confirm the match through the ambiguity-confirm flow Triage already has, create the item
  properly in the target domain, transfer the *entry* — status, score, progress, dates, shelves,
  notes — remove the old item, and record an undo effect. **Roughly a third to a half of a sprint**,
  and worth more than this one case: it is also the general answer to an import that landed in the
  wrong library. It needs the series line closed first, because until then there is only one pair of
  domains it could move between.

- **Manga.** Refused by name in Sprint 041's connector rather than half-supported. A separate domain
  if it is ever wanted, and not a mode of the anime one.

## Cross-sprint definition of done

Every sprint must:

- satisfy every acceptance criterion or remain incomplete;
- add tests at the correct layer and run focused plus regression suites;
- preserve data and security invariants;
- update OpenAPI/types/docs when contracts move;
- record material deviations in `docs/decisions.md`;
- review downstream sprint impact;
- pass `python scripts/validate_project.py`, `make check`, and `make test` when available;
- end with a clean worktree and an updated next-agent handoff.
