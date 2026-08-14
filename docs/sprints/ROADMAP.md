# Implementation Roadmap

**Plan revision:** 10
**Delivery rule:** one sprint must leave a demonstrably usable or risk-reducing increment, green quality gates, updated documentation, and a clean worktree.
**Active sprint:** [Sprint 026](026-status-vocabulary.md)

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
             └─ 026 Status vocabulary (seam 5b)
                 ├─ 027 Third domain: games
                 └─ 028 Fourth domain: series  [GATED]
```

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
| [026](026-status-vocabulary.md) | Status vocabulary (seam 5b) | 025 | **ready** |
| 027 | Third domain — games | 026 | planned |
| 028 | Fourth domain — series | 026 | planned |

## Contracts for planned sprints

These are binding outcome boundaries. Before a planned sprint becomes active, the closing agent for
the prior sprint must expand it into a dedicated `docs/sprints/NNN-*.md` file using `TEMPLATE.md`,
incorporating actual deviations. Sprints 019 through 026 have files; 027 and 028 do not.

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

### [Sprint 026 — Status vocabulary (seam 5b)](026-status-vocabulary.md)

The one seam Sprint 025 deliberately leaves half-done, pulled out because it is the largest single
piece and the only one carrying a genuine product decision (DEC-052).

Sprint 025 ships albums carrying books' status *values* under album *labels* — `read` renders as
"Listened". That is honest and visible, and it costs nothing structurally, because the standing
invariant already says internal names are permanent while user-facing copy is free to move. What it
does not do is let a domain have *different statuses*.

This sprint does: per-domain status vocabularies, validation moving off the global `EntryStatus`
StrEnum, filter chips, the triage keyboard map, and the Goodreads status suggestions staying
book-only. Sprint 025 collapses the duplicated `statusLabels` in `pages/TriagePage.tsx:42` first, so
this sprint is not fighting two copies.

**The product question it must answer, which is the owner's and not the implementer's:** an album is
re-listened continuously in a way a book is not re-read, so `reread_count` and `date_finished` may
be meaningless for the domain. Deliberately scheduled after albums exist, because the answer is much
better with two domains in hand than with one.

### Sprint 027 — Third domain, games

IGDB. Not gated: by this point the seam model exists and this sprint either fits it or proves it wrong
cheaply. **It carries a falsifiable prediction from DEC-052** — games should need no seam that
albums did not. If it needs a seventh, the abstraction was wrong.

The new infrastructure is authentication — IGDB requires Twitch OAuth client credentials and token
refresh, where every provider so far has needed at most a static API key. Localization is
enrichment, not a guarantee: keep the original title plus whatever alternate names the provider
exposes rather than assuming a single translated-title field.

### Sprint 028 — Fourth domain, series

**Gated on a product decision, not on a provider integration.** TMDB is the strongest provider in
the research and the integration is the easy half.

The entry model is one score, one status, one `reread_count` per item — settled deliberately in
product spec section 10, item 4. A television series does not fit it. Either a series is one entry
and "watched through season 3" is not expressible, or entries gain hierarchy, which reaches keyset
pagination, triage selection semantics, bulk operations, and every count in the UI.

Phase A decides that and nothing else. It is last on the roadmap because the decision is much
better made with three working domains in hand than with none.

Note the vocabulary collision before it causes confusion: book-series already exists as a free-text
`metadata` field, and product spec section 11 item 4 records the deliberate choice not to model it.

## Not scheduled

- **Auth.** Product spec section 9 keeps this a v2 deferral with no sprint number, reaffirmed by the
  owner during the revision-8 re-plan. It remains the gate on any exposure beyond LAN: no public
  DNS, port-forwarding, tunnel, or internet-reachable proxy until it exists.
- **Sharing, multiuser, Calibre write-back, OPDS.** Product spec section 9, unchanged.
- **Wine and the remaining exploratory domains.** `docs/domain_metadata_roadmap_report.md` assesses
  them; none is scheduled. Wine's weakness is access economics rather than catalogue geography.

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
