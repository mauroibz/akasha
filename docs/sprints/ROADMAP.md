# Implementation Roadmap

**Plan revision:** 8
**Delivery rule:** one sprint must leave a demonstrably usable or risk-reducing increment, green quality gates, updated documentation, and a clean worktree.
**Active sprint:** [Sprint 021](021-attachments.md)

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
         ├─ 022 Creator sort names
         ├─ 023 Export
         └─ 024 Second domain: albums  [GATED]
             ├─ 025 Third domain: games
             └─ 026 Fourth domain: series  [GATED]
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
| [021](021-attachments.md) | Attachments: viability, then a narrow slice | 020 | **ready** |
| 022 | Creator sort names | 020 | planned |
| 023 | Export | 020 | planned |
| 024 | Second domain — albums: pilot, then verdict | 020 | planned |
| 025 | Third domain — games | 024 | planned |
| 026 | Fourth domain — series | 024 | planned |

## Contracts for planned sprints

These are binding outcome boundaries. Before a planned sprint becomes active, the closing agent for
the prior sprint must expand it into a dedicated `docs/sprints/NNN-*.md` file using `TEMPLATE.md`,
incorporating actual deviations. Sprints 019, 020 and 021 already have files; the rest do not.

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

This sprint sets the provider contract Sprint 024 inherits, so its reasoning matters as much as its
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

### Sprint 022 — Creator sort names

`sort_author` is `json_extract(metadata, '$.authors[0]')` verbatim, so "Adolfo Bioy Casares" sorts
under A and "Gabriel García Márquez" under G.

The obvious repair is wrong for this library specifically. Splitting on the last space gives
*Márquez* for García Márquez and *Llosa* for Vargas Llosa, both of which are wrong, while giving
the right answer for Rulfo. Spanish double surnames have no reliable heuristic, so the shape is a
stored sort name seeded by a heuristic and correctable by the owner — a migration plus an edit
surface, not a one-line fix.

Name it **creator**, not author. An album has an artist and a game has a studio, and this projection
should not need rewriting when Sprint 024 lands. Note that `title_normalized` and
`sort_author_normalized` are maintained by a mapper event (DEC-036) precisely so a new write path
cannot forget them; whatever replaces `sort_author` inherits that requirement.

### Sprint 023 — Export

`GET /api/export` dumping entries and items as JSON, plus a Goodreads-shaped CSV. Product spec
section 9 deferred this to v2 as agreed-in-principle; the owner has now scheduled it. Backups
(DEC-039, DEC-040) removed the urgency, but the repository is public and portability is now a
user-facing story rather than only the owner's.

One design constraint, because it decides whether this survives the domain work: **export the
entity shape — `type`, identifiers, and an opaque `metadata` object — not a book-specific schema.**
The database is already shaped that way. A book-shaped export format would need a v2 the moment
Sprint 024 lands.

The Goodreads-shaped CSV is a book-only convenience and is allowed to stay book-only.

### Sprint 024 — Second domain, albums: pilot, then verdict

**Gated, and its Phase A is a build rather than a document.** `docs/domain_metadata_roadmap_report.md`
already did the provider research; repeating it as prose would produce a confident answer about
this codebase that the research cannot support.

Phase A: implement one domain end to end on a branch — search, add, cover, library card, detail,
edit. The deliverable is **the list of everything that had to be touched that was not the provider
adapter.** If that list is a type column, a provider registry, a per-type field config and a status
vocabulary, the abstraction is justified and Phase B builds it properly. If it reaches into keyset
pagination, the job runner, or the import ledger, that is the finding and it changes the plan.

What is already generic, and should be confirmed rather than rebuilt:

- `items.type` exists and product spec 3.1 always described `items` as a domain-agnostic shell.
- `Provider` in `domain/providers.py` is already a two-method protocol carrying `item_type`.
- `normalize_identifier` in `domain/identity.py` already has a generic non-ISBN path.
- `items`/`entries` are already split, which product spec section 9 called the entire preparation.

What is hardcoded, and is the real work:

- `type="book"` at three `infrastructure/repositories.py` call sites, and `SOURCE_PREFERENCE` as a
  module constant in `domain/providers.py`.
- Book fields in `features/detail/MetadataDialog.tsx` and `features/detail/schemas.ts`, which a
  per-type display config replaces.
- **Status vocabulary.** "To read / Reading / Read" does not fit an album. This reaches the filter
  chips, the triage keyboard map, the Goodreads status suggestions, and `entryStatuses`. Expect it
  to be the largest single piece.
- Literal "book"/"books" copy in `ShelvesPage.tsx` and `ImportPage.tsx`.

Albums first, among the three domains the owner named. MusicBrainz needs no OAuth, unlike IGDB's
Twitch credentials; release-group versus release maps directly onto the work-versus-edition problem
this codebase already solved for books; and Cover Art Archive as a separate image provider exercises
the two-provider composition Sprint 020 has now settled: DEC-044 fixes the rule that a provider
fills fields only when its candidate can be tied to the identifier that was requested, and that an
unverifiable candidate is rejected rather than partially merged. MusicBrainz's release-versus-
release-group split is that same problem, so albums inherits the answer rather than re-deriving it.

The Goodreads and Calibre import pipelines stay book-only. That is not a gap.

### Sprint 025 — Third domain, games

IGDB. Not gated: by this point the architecture verdict exists and this sprint either fits it or
proves it wrong cheaply.

The new infrastructure is authentication — IGDB requires Twitch OAuth client credentials and token
refresh, where every provider so far has needed at most a static API key. Localization is
enrichment, not a guarantee: keep the original title plus whatever alternate names the provider
exposes rather than assuming a single translated-title field.

### Sprint 026 — Fourth domain, series

**Gated on a product decision, not on a provider integration.** TMDB is the strongest provider in
the research and the integration is the easy half.

The entry model is one score, one status, one `reread_count` per item — settled deliberately in
product spec section 10, item 4. A television series does not fit it. Either a series is one entry
and "watched through season 3" is not expressible, or entries gain hierarchy, which reaches keyset
pagination, triage selection semantics, bulk operations, and every count in the UI.

Phase A decides that and nothing else. It is last on the roadmap because the decision is much
better made with two working domains in hand than with none.

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
