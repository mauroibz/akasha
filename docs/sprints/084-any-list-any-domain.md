# Sprint 084 — Any list, any domain

**Status:** in_progress
**Depends on:** 083
**Roadmap revision:** 42

## Objective

Make the custom-list importer domain-selectable: one connector, any domain.
The owner's ask (2026-09-14): *"Given that the structure is 'read file, iterate
over rows, lookup for each', what is keeping us from having the target domain
be selectable? … a domain dropdown + change the column mapping, and reuse the
system."* The answer, measured, is: nothing structural. The connector's
`item_types` already drives every downstream seam (the reader's target
checkboxes, the per-row provider search's domain scoping, the confirm
re-staging, commit's per-row domain resolution); the only book-specific things
in `domains/book/list.py` are the header word lists and the `book` import.

This sprint moves the list reader from the book domain's package to the
shared registry as a **multi-domain connector** (`item_types` = every
registered domain), declares the column mapping per selected domain (title
words + the second column's name change with it: book → author, album →
artist, film/series → nothing-needed, anime → nothing-needed), and reuses the
entire search-then-confirm machinery unchanged. The screen gains a domain
dropdown beside the file input — the same declaration-driven choice the
target checkboxes already are, but single-pick for a source whose rows have
no identity to route them.

## Required context

- `docs/specs/product-spec.md` §4.3 (`merge_and_rank`), §5.3 (the shared
  import pipeline), §5.4 (the custom-list flow as shipped — this sprint
  generalizes it), §6 (route list — unchanged).
- `docs/specs/technical-spec.md` §6 (the import boundary), §6.6 (the domain
  contract — this sprint must not branch on which domain it is holding),
  the Sprint 083 paragraphs (the search job, the proposal store, confirm,
  exclusion, re-search).
- `docs/decisions.md` DEC-045 (quota split), DEC-080 (connector-declared
  guide/labels), DEC-106 (target selection belongs to the service), DEC-156
  (the original sprint contract), DEC-159 (the owner's first-pass feedback
  batch), DEC-025 (walkthrough rule), DEC-108 (boundary-down substitution),
  DEC-160 (this revision).
- Code, read fresh:
  - `backend/src/book_tracker/domains/book/list.py` — the reader as it stands:
    `TITLE_HEADERS`/`AUTHOR_HEADERS` word lists, auto-detect, the mapping
    form fields, match-always-NEW, `identity_kinds = frozenset()`.
  - `backend/src/book_tracker/domain/importers.py` — `Importer.item_types`
    (ordered, may name more than one), `ImportInputSpec.fields`,
    `SearchingImporter`, `ImportSource.options` (where the mapping rides).
  - `backend/src/book_tracker/application/imports.py` — `chosen_targets`,
    `_target_of`, `_stored_record` (`item_type` per row), `preview`'s
    target-filtering, `answer_proposal`, `exclude_row`/`include_row`,
    `research_row`.
  - `backend/src/book_tracker/application/import_search.py` — the per-row
    domain resolution (`payload["item_type"]` or the connector's first
    declared type), `search_row`'s provider scoping, `TOP_N`.
  - `backend/src/book_tracker/domain/spec.py` — `Domain.item_type`, `label`,
    `fields` (`FieldSpec.name`/`label` — the creators field's label is the
    domain's: Authors, Artists, Directors), `IdentityStrategy`.
  - Each domain's `__init__.py` — `item_type`, `label`, `fields`,
    `enrichment.identity_kinds` (what a confirmed proposal can land as).
  - `backend/src/book_tracker/domain/registry.py` — `REGISTERED_IMPORTERS`,
    `IMPORTERS`, `DOMAINS`; where the list importer is registered from.
  - `backend/src/book_tracker/api/imports.py` — the preview route's
    `targets` form handling, `_published_input`.
  - Frontend: `frontend/src/pages/ImportPage.tsx` (the target-checkbox
    pattern `item_types.length > 1`, the column-mapping inputs, the
    ProposalList/RowControls wiring), `frontend/src/api/imports.ts`
    (`previewImport`'s body), `frontend/src/features/import/RowControls.tsx`,
    `ProposalList.tsx`.
- Tests, read fresh: `backend/tests/test_list_import.py` (the owner-batch
  class included), `test_import_search_job.py`, `test_import_proposals.py`,
  `test_domain_conformance.py` (the importer contract suite — the
  one-importer-per-declaration assertions), `test_generic_imports.py`,
  `frontend/src/pages/ImportPage.test.tsx`, `frontend/e2e/import.spec.ts`.
- `docs/agent/WORKFLOW.md`, `docs/agent/TESTING.md` (the ladder, walkthrough
  reuse, DEC-025's recorded-response rule).

## Current implementation baseline

Measured in this worktree on 2026-09-14, after v2.1.0:

- The list connector is registered from the book domain's package
  (`domains/book/list.py`, `item_types=("book",)`), imported into
  `REGISTERED_IMPORTERS` via the book domain. Every surface downstream of it
  is already domain-keyed by declaration:
  - `ImportService.preview` already supports multi-target connectors
    (`chosen_targets`, the per-row `_target_of` filter, DEC-106) — the
    MyAnimeList connector is the live precedent.
  - The search job resolves each row's domain from the record's own
  `item_type` (the 2026-09-14 fix) and asks only that domain's providers.
  - Confirm re-stages from the proposal payload; commit resolves each row's
    domain per record. Nothing in the shared layers names the book domain.
- The book-specific parts of the reader, exhaustively: `TITLE_HEADERS` /
  `AUTHOR_HEADERS` word lists (Spanish + English, book-shaped: "libro",
  "escritor"), the `domains/book` import, `item_types=("book",)`, and the
  label/guide copy ("one book per line").
- The domain's own vocabulary already exists for the mapping to follow:
  `FieldSpec("creators", "Artists")` in album, `"Directors"` in movie —
  the second column's *name* per domain is a declaration away, not a
  hardcode.
- The screen renders target checkboxes when `item_types.length > 1`
  (ImportPage.tsx) — the shape exists but reads multi-pick; a source with no
  identity per row wants a single-pick domain choice made BEFORE preview,
  because the mapping's field labels and the reader's header words depend on
  it.
- `ImportInputSpec.fields` is a flat tuple of form-field names; the mapping
  values ride `ImportSource.options` into the reader. A per-domain word list
  changes which options the reader interprets, not the field names
  (`title_column`, `author_column` can stay — the *labels* are the domain's).
- Five domains are registered: book, album, movie, series, anime. All five
  have working `search` providers (openlibrary/googlebooks; musicbrainz;
  wikidata/cinemeta; wikidata/cinemeta/tvmaze; anilist/kitsu). Album's
  enrichment is the only one with `needs_item_context` — irrelevant to
  search, which passes the query string.
- The e2e suite's catalog stub (`frontend/e2e/seed.ts`) and the Vitest
  `listImporter` stub carry `item_types: ["book"]`; the DEC-137 strip test
  counts connectors at 7 with its own stub.

## Deliverables

### D1 — The reader becomes domain-declared and moves to the registry

1. The reader moves out of `domains/book/` into the registry's own module
   (`backend/src/book_tracker/importers/list.py` or the registry location
   the codebase prefers — follow where `REGISTERED_IMPORTERS` lives):
   `item_types` = every registered domain, ordered as `DOMAINS` declares
   them. **No file outside a domain's package may name a domain's fields**;
   the word lists move to per-domain declarations (D2).
2. `match` stays always-NEW, `identity_kinds` stays empty, `search_job`
   stays `search_import_rows` — the search-then-confirm contract is
   domain-blind and unchanged.
3. The header word lists become a **domain declaration**: a new optional
   `Domain` member (e.g. `list_headers: Mapping[str, tuple[str, ...]]` or a
   small `ListHeaderSpec` — pick the shape consistent with how
   `entry_field_labels` and `PASSAGE_FIELDS` are declared) holding the
   title-column words and the creator-column words per domain. Books keep
   their current lists verbatim; album adds artist words ("artista",
   "artist", "band", "músico"); movie/series/anime declare title words only
   ("título", "title", "nombre", "name", "film", "película", "serie",
   "anime") and NO creator words — the second column is optional for them
   (a film list is often one column), and the reader must treat a missing
   creator column as an empty creator, not an error.
4. The connector's guide/labels become domain-neutral ("one row per line")
   with the domain's own label appearing where the screen already shows it.
5. `docs/guides/adding-a-domain.md` gains the new declaration so a future
   domain knows it must provide list headers to be list-importable.

### D2 — The preview request carries the domain choice

1. The screen's domain dropdown (single-pick, from `item_types`) sends the
   chosen domain as the existing `targets` form field (one value — the
   service's `chosen_targets` already accepts a sequence; the reader only
   reads rows of that type). The mapping field labels localize to the
   domain's own (`FieldSpec` label for creators: Author/Artist/Director);
   the fallback sentence stays honest.
2. The connector's `fields` declaration stays `("title_column",
   "creator_column")`; the **labels** the screen renders beside the inputs
   come from the domain's declarations, not a connector hardcode.
3. The fingerprint already composes with the mapping; the domain choice
   composes too (re-previewing the same file for another domain is a
   different import — the same DEC-106-derived rule the target selector
   applies). The reader emits `item_type = <chosen domain>` per row.
4. A row that parses to an empty title is still an error row; a row with an
   empty creator is valid for domains without creator words and an error
   for domains with them (the declaration governs, not the reader).

### D3 — The search job and the confirm flow, unchanged and re-proven

1. No shared-layer code changes: the job already scopes providers per row
   domain; confirm already re-stages per payload; exclusion and re-search
   already carry through. The re-proof is the sprint's neutrality evidence:
   the full flow runs against a second domain's data end to end.
2. Recorded fixtures for at least one non-book query (a MusicBrainz album
   search capture, or a Wikidata film capture) committed under
   `backend/tests/fixtures/providers/` with provenance, and the job replay
   test extended to a non-book row — DEC-025's rule for the new boundary.
3. The proposal payload's `creators` for album rows must land as the
   domain's `Artists` field on confirm (the metadata cross-walk is the
   domain's `fields` declaration; verify `validate_metadata_patch` accepts
   it — the confirm path already writes `metadata.creators`, which every
   domain declares).

### D4 — The screen

1. ImportPage: when the active connector declares more than one domain AND
   is a list-style source (the declaration: a new optional
   `ImportInputSpec.single_domain_pick = True` or reusing the existing
   shape — pick the smallest declaration), render a single-pick dropdown
   (the domain chooser pattern from the add screen, not the multi-checkbox),
   defaulting to the first declared domain. The column-mapping labels and
   the guide follow the choice.
2. The preview records, proposal cards, exclusion and re-search controls are
   unchanged — they are domain-blind and render whatever the domain's
   providers returned.
3. The domain choice is required before preview for multi-domain lists (the
   dropdown defaults, so the common case is one click fewer).

### D5 — Conformance, docs and fixtures

1. `test_domain_conformance.py`: the importer contract suite asserts the
   multi-domain list connector declares every registered domain, its word
   lists are non-empty per declared domain, and the single existing
   searching connector is still exactly the one with empty `identity_kinds`.
2. Sanitized fixtures: one small per-domain CSV (a 4-row album list, a 4-row
   film list) shaped like real hand-written lists, committed under
   `backend/tests/fixtures/imports/`.
3. Canonical docs: product spec §5.4 generalizes (the flow is the same, the
   domain is a choice); technical spec §6 records the multi-domain
   declaration shape and the per-domain header words; the OpenAPI examples
   move with the catalog response; `docs/README.md` doc map unchanged.

## Acceptance criteria

1. **Any domain imports from a hand-written list.** For each registered
   domain, uploading a small hand-written list with the domain chosen in
   the dropdown produces a `matching` preview, a drained search with
   proposals from that domain's providers only, and a committed import
   whose entries land `unsorted` in that domain's library. Proven live for
   at least book + one non-book domain (the walkthrough), and against
   recorded fixtures for the job (AC2). (tests: `test_list_import.py`
   per-domain reader cases + `test_import_search_job.py` non-book replay)
2. **The declaration governs, not the code.** No file outside a domain
   package names a domain's header words or field labels; the reader reads
   the chosen domain's declaration; a new domain that declares list headers
   becomes list-importable with zero connector changes. (tests: conformance
   suite + the AC9-style grep)
3. **The domain choice is a first-class part of the import.** The same file
   previewed for two domains yields two batches (different fingerprints),
   each with rows of only its domain; re-previewing returns the stored
   batch per fingerprint. (tests: `test_list_import.py`)
4. **Header auto-detection follows the domain.** An album list with
   "Album"/"Artista" headers auto-maps; a film list with a single "Título"
   column auto-maps and imports with empty creators; a book list keeps
   working exactly as v2.1.0 did (regression: the existing suite passes
   byte-for-byte). (tests: `test_list_import.py`)
5. **Confirm works on non-book rows.** Confirming an album proposal lands
   the album with the provider's identifiers in the domain's declared
   identity kinds, the creators as Artists, and a cover through the
   enrichment path; discard and exclusion behave exactly as for books.
   (tests: `test_list_import.py` non-book confirm + the replay test)
6. **The screen is domain-aware before preview.** The dropdown renders for
   the list connector (and not for single-domain connectors), the mapping
   labels localize (Author/Artist/Director or the domain's own), and the
   commit gate counts are honest for mixed-domain… — a single batch is
   single-domain by construction (AC3), so the counts stay as they are.
   (tests: Vitest + e2e)
7. **No shared layer branches on the domain.** The reader, job, service,
   routes and screens hold the row's own `item_type` end to end;
   `if domain == "book"` anywhere above a declaration is a defect. The
   conformance suite's neutrality assertion covers the connector; the
   sprint's own review covers the diff. (tests: conformance)
8. **Docs move together.** Product spec §5.4, technical spec §6, the
   adding-a-domain guide, the OpenAPI examples and the conformance suite
   describe the same surface; the project validator passes.
9. **The flow works live for a non-book domain.** A walkthrough importing a
   hand-written album list (or film list) end to end on a fresh data dir:
   choose domain → upload → matching → confirm → commit → entries in the
   album library with covers → undo. Recorded in the worklog with observed
   counts. (scratchpad/live-run script, per TESTING.md)

## Required tests (TDD)

- `test_list_import.py` — per-domain reader: auto-detect with per-domain
  words, single-column film list (empty creators valid), the domain choice
  composing the fingerprint, per-row `item_type`, confirm on a non-book
  row, the second-domain batch being distinct.
- `test_import_search_job.py` — a non-book row's search against recorded
  provider fixtures (album or film), the provider scoping holding for it.
- `test_domain_conformance.py` — the multi-domain declaration assertions,
  every declared domain's word list non-empty, the searching-connector
  uniqueness unchanged.
- Route tests: the `targets` form field carrying one domain for the list
  connector; the catalog publishing the multi-domain `item_types`.
- Frontend Vitest: the domain dropdown rendering for the list connector and
  not for single-domain ones; localized mapping labels; the preview body
  carrying the choice.
- E2E: extend the list-connector spec with a domain-switch case (stubbed
  providers, per the DEC-025 split: stubs for the screen contract, recorded
  responses for the job contract).
- Walkthrough (AC9) on a fresh data dir with a real non-book list.

## Verification

- Focused: `cd backend && uv run pytest tests/test_list_import.py tests/test_import_search_job.py -x -q`
- Focused routes: `uv run pytest tests/test_generic_imports.py tests/test_domain_conformance.py tests/test_isolation.py -q`
- Backend exhaustive: `make test` (backend + frontend Vitest).
- Frontend: `npm run test:e2e` from `frontend/` (the parallel run is the gate).
- `make check` (validator + lint + typecheck + version surfaces + OpenAPI).
- OpenAPI regeneration check; regenerate, then re-run `make check`.
- Walkthrough (AC9) on a fresh disposable data dir, live boundary if it
  answers, recorded fixtures per DEC-108 otherwise.
- Container: not owed (no deployment change).

## Explicit non-scope

- Mapping a list's extra columns to domain fields (still the recorded
  "queda a futuro"; the columns ride `source_fields`).
- Mixed-domain batches — one list, one domain, per the fingerprint rule.
- New domains (manga stays refused); a future domain's list-ability is its
  own declaration away.
- Any change to the search-then-confirm machinery itself (D3 is re-proof,
  not rework).
- Version bump or release (no release in this sprint).

## Commit checkpoints

- `feat(registry): the list reader is domain-declared — per-domain header words, any target`
- `feat(imports): the domain choice rides the preview — fingerprint, labels, per-row type`
- `test(imports): recorded non-book search fixtures and the replay proofs`
- `feat(ui): the domain dropdown and localized mapping labels`
- `docs(specs): any list, any domain — the generalized contract`
- `e2e(imports): the domain-switch flow`
- `docs(sprint-084): close sprint and hand off` (closure, only after all gates)

## Risks and decisions to surface

- **Non-book provider relevance for hand-written text.** A film list's
  "Blade Runner" will match; a Spanish-titled album list may find
  MusicBrainz's text search weaker than Open Library's. The top-10 + edit
  + discard + exclude affordances are the designed answer; record observed
  relevance in the Outcome, do not attempt to fix providers.
- **The album creators label ("Artists") and the second column.** An album
  list often carries artist in the SECOND column and the reader's fallback
  is first-two-columns — that stays; only the words and labels localize.
- **Series/anime without a creator column.** A one-column list must work;
  the reader must not demand a creator when the domain declares no creator
  words.
- **The catalog response grows `item_types` for the list connector.** The
  screen's target-checkbox pattern must not render multi-checkboxes for it
  (single-pick instead) — the `ImportInputSpec` declaration (D4) is what
  distinguishes them, not a `importer.id === "list"` branch.
- **Conformance suite drift.** The suite asserts declarations about
  "the list connector"; generalizing it must keep every existing
  connector's assertions untouched (books included — the v2.1.0 suite is
  the regression contract).

## Outcome

_Planned. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
