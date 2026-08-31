# Sprint 051 — One source, many libraries

**Status:** ready
**Depends on:** 049
**Roadmap revision:** 27

## Objective

A connector may target more than one domain, and one archive may land films in the Movies library
and shows in the Series library in a single import. The reader chooses the **source**, not the
target; what the source contains is declared by the connector and chosen with a checkbox.

No existing connector changes behaviour. No import screen is rebuilt.

## Required context

- `docs/series-domain-viability.md`, "The shape both sources share, and the problem it creates".
- `docs/decisions.md`: DEC-080 (a connector declares its own guidance and the screen renders it),
  DEC-081 (one source, one tab), DEC-093 (what the connector boundary cost when it was first tested
  by somebody who did not write it), DEC-077, and the new DEC-106.
- `backend/src/book_tracker/domain/importers.py` in full — this is the contract being widened.
- `backend/src/book_tracker/application/imports.py` in full, and
  `infrastructure/repositories.py` `commit`/`commit_batch`.
- `backend/src/book_tracker/api/imports.py` — `ImporterResponse` and the preview route.
- `frontend/src/pages/ImportPage.tsx` and `frontend/src/pages/TriagePage.tsx`.
- `backend/tests/test_domain_conformance.py` — parametrized over registered importers, and the guard
  that must grow with the contract.

## Current implementation baseline

Observed 2026-08-31, and three of these findings shrink the sprint considerably:

- **`Importer.item_type` is a single string.** `ImportService.__init__` resolves
  `self.domain = DOMAINS[importer.item_type]` **once**, and that one object reaches `_validate`,
  `commit(domain=…)` and the enrichment guard. This is the whole problem and it is three call sites.
- **The Import screen is already source-shaped, not domain-shaped.** `ImportPage.tsx` calls
  `getImporters()` and renders one tab per connector — Goodreads, Calibre, MyAnimeList and Letterboxd
  side by side. It reads `item_type` from the registry response for nothing at all. The UX the owner
  asked to keep is the UX that already ships.
- **Triage already renders per row.** `TriagePage.tsx` resolves statuses, hotkeys and labels from
  `entry.item.type` on each row, not from a page-level domain. A mixed batch renders correctly today.
- **Enrichment is already domain-agnostic.** `_backfillable_items` loops over every registered domain
  and restricts by item id. The only single-domain thing in the path is the `if self.domain.enriches`
  guard in `ImportService.commit`.

The genuinely new work is therefore: the declaration, per-record domain resolution, the commit
signature, the target selector, and the fingerprint.

## Deliverables

### 1. The contract: a connector declares the domains it can produce

`Importer.item_type: str` becomes `Importer.item_types: tuple[str, ...]`, ordered, first-declared
first. Every existing connector declares a one-element tuple and changes in no other way.

`NormalizedImportRecord` gains `item_type: str | None = None` — the domain **this row** targets.
`None` means the connector's first declared type, so a single-domain reader emits exactly what it
emits today and its tests do not move.

A record naming a type the connector did not declare is a defect in the connector, refused at the
boundary the way an undeclared identity and an undeclared error code already are.

### 2. Per-record domain resolution in the shared service

`ImportService.domain` is replaced by a lookup keyed on the record. Three call sites:

- `_validate` resolves the record's domain before `validate_metadata_patch`,
  `validate_entry_values` and `validate_status`. A movie row is validated against the movie domain
  and a series row against the series domain, in the same batch.
- `commit` passes a domain **per record** rather than one for the batch. Concretely:
  `ImportRepository.commit(…, domain: Domain)` becomes `domains: Mapping[str, Domain]`, keyed by item
  type and holding exactly the domains the connector declared; `commit_batch` reads each record's
  `item_type` from its stored `normalized_payload` and looks the domain up there, replacing the
  single `type=domain.item_type` at the `ItemRow` construction site. The record's `item_type` must be
  written into `normalized_payload` at preview time so commit never re-opens the source — that is the
  existing rule (`ImportSnapshot` is stable; commit never re-reads), not a new one.
- The enrichment guard becomes "enqueue if any domain this batch touched enriches", which is a
  narrowing of an already domain-agnostic scan.

Nothing above the registry branches on which domain it is holding. This is a shared layer learning
to hold N domains, which is the opposite of an `if item_type == "series"`.

### 3. The target selector

The connector declares what it can produce; the screen renders a checkbox per declared type, labelled
from `GET /api/item-types`, all checked by default:

```text
IMDb
  What should this import?   [x] Movies   [x] TV series
  [ drop your export here ]
```

The chosen subset travels with the preview request. **The service, not the reader, applies it**: a
reader always emits every row it can parse, and the service drops records whose `item_type` was not
requested before staging, counting what it dropped. A connector cannot get the filter wrong, one rule
covers every connector present and future, and conformance can assert it.

A connector declaring one type renders no checkboxes at all — Goodreads and Calibre look exactly as
they do today.

`ImporterResponse.item_type: str` becomes `item_types: list[str]`, mirrored in
`frontend/src/api/library.ts`. This is a breaking change to a published response shape; the OpenAPI
regeneration and the client test that pins it are the guard.

### 4. The fingerprint has to know about targets

Preview is idempotent on `(connector, fingerprint)`: a repeat preview of the same source returns the
stored batch. Two previews of the **same file with different targets are different imports**, so the
chosen target set is folded into the fingerprint. Without this, importing an IMDb export as films and
then importing it again as series silently returns the first preview — a wrong answer that looks like
a working feature, which is the failure mode worth spending a test on.

### 5. Skipped rows are reported, never silently dropped

Two different things get skipped and they must not be conflated:

- **Not requested** — a series row when only Movies was ticked. Reported as a count with its reason.
- **Not importable** — a row whose source type maps to no domain at all (an IMDb `TV Episode`, a
  Trakt `season` rating). Also a count, also with a reason, and **never a row error**: a person who
  exports their whole IMDb account should not see 40 red rows for podcasts they rated.

The preview summary carries both counts. `PreviewSummary` gains the fields; the screen renders them
under the existing summary line.

### 6. Conformance

`test_domain_conformance.py` grows to reject: an empty `item_types`, a duplicate entry, a type that
is not a registered domain, a connector registered under a domain it does not declare, and a reader
emitting a record whose `item_type` is undeclared. The registry's `IMPORTERS_BY_DOMAIN` now indexes a
connector under **every** domain it declares, and `IMPORTERS` stays keyed by name.

## Acceptance criteria

1. A connector declaring two domains previews one source into records of both types, and commit
   creates items of both types in one batch.
2. Every existing connector — Goodreads, Calibre, MyAnimeList, Letterboxd — behaves identically:
   their suites pass **unmodified** except where a one-element `item_types` tuple replaces a string.
3. A movie row and a series row in one batch are each validated against their own domain: a status
   legal for series and illegal for movies is refused on the movie row and accepted on the series row.
4. Triage shows a mixed batch with the right statuses and hotkeys per row, verified in a browser.
5. Undo of a mixed batch removes both domains' items and entries, and leaves nothing behind.
6. Enrichment is queued for every enriching domain the batch touched, and for no item outside it.
7. Unticking a target excludes its rows from preview and from commit, and the count of what was
   excluded is displayed.
8. The same file previewed with different target sets produces **different** batches.
9. Rows whose source type maps to no domain are counted and reported, and are not row errors.
10. `GET /api/importers` publishes `item_types`; OpenAPI and the client array are regenerated and
    pinned by their existing tests.
11. No migration.

## Required tests (TDD)

- A two-domain test connector, registered only in tests, exercising preview, commit, undo, target
  filtering and the undeclared-type refusal. Building the seam against a fixture connector rather
  than against IMDb is what keeps Sprints 052 and 053 honest about whether the seam holds.
- Per-record validation, with a status legal in one target domain and illegal in the other.
- Fingerprint divergence across target sets.
- Enrichment enqueued per domain, scoped to the batch.
- Conformance rejections, one test per new rule.
- Frontend: the selector renders for a multi-target connector and not for a single-target one; the
  selection reaches the request; the skipped counts render.
- Every existing importer suite, unchanged.

## Verification

```bash
cd backend && uv run pytest tests/test_imports.py tests/test_domain_conformance.py \
  tests/test_goodreads_import.py tests/test_calibre_import.py \
  tests/test_myanimelist_import.py tests/test_letterboxd_import.py -q
cd frontend && npm run test
make check
make openapi
make test
```

Then the walkthrough gate, with the test connector or with a hand-made two-domain CSV: preview,
untick a target and preview again, commit, approve rows of both types in Triage, and undo.

## Explicit non-scope

- **The IMDb and Trakt readers.** Sprints 052 and 053. This sprint's own connector is a test fixture,
  on purpose: a seam proved only by the connector it was built for is not proved.
- Mixed-domain *sources* other than imports — search, add-by-URL and export are unaffected.
- Any change to how Triage groups or filters rows.
- Splitting one preview into two batches. One source is one batch; the rows inside it carry types.

## Commit checkpoints

1. `[ADD] A connector declares the domains it produces`
2. `[ADD] Resolve the target domain per import record`
3. `[ADD] Choose what an import brings in`
4. `[TEST] Conformance for multi-domain connectors`
5. `[DOCS] Close sprint 051 and hand off`

## Risks and decisions to surface

- **`ImporterResponse.item_type` is a published field.** Changing it to a list is the one breaking
  contract change in the line. It is caught by generation and by the client test rather than by a
  reader noticing, which is the point of that chain.
- **The fingerprint change alters idempotency semantics.** A source imported before this sprint has a
  fingerprint computed without targets. Existing batches must keep resolving; the change applies to
  new previews. Name this in the tests rather than discovering it on the owner's library.
- If per-record domain resolution turns out to reach further than the four call sites named above,
  **stop and record it** rather than widening the sprint. That finding is worth more than the feature.

## Outcome

_Not started._
