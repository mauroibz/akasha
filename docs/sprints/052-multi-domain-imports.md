# Sprint 052 — One source, many libraries

**Status:** completed
**Depends on:** 049, 051
**Roadmap revision:** 28

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
`frontend/src/api/imports.ts` (planning named `library.ts`; the importer client is `imports.ts`).
This is a breaking change to a published response shape; the OpenAPI regeneration and the client
test that pins it — `frontend/scripts/check-openapi-types.mjs` — are the guard.

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
  than against IMDb is what keeps Sprints 053 and 054 honest about whether the seam holds.
- Per-record validation, with a status legal in one target domain and illegal in the other.
- Fingerprint divergence across target sets.
- Enrichment enqueued per domain, scoped to the batch.
- Conformance rejections, one test per new rule.
- Frontend: the selector renders for a multi-target connector and not for a single-target one; the
  selection reaches the request; the skipped counts render.
- Every existing importer suite, unchanged.

## Verification

```bash
cd backend && uv run pytest tests/test_generic_imports.py tests/test_multi_domain_imports.py \
  tests/test_domain_conformance.py \
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

- **The IMDb and Trakt readers.** Sprints 053 and 054. This sprint's own connector is a test fixture,
  on purpose: a seam proved only by the connector it was built for is not proved.
- Mixed-domain *sources* other than imports — search, add-by-URL and export are unaffected.
- Any change to how Triage groups or filters rows.
- Splitting one preview into two batches. One source is one batch; the rows inside it carry types.

## Commit checkpoints

1. `[ADD] A connector declares the domains it produces`
2. `[ADD] Resolve the target domain per import record`
3. `[ADD] Choose what an import brings in`
4. `[TEST] Conformance for multi-domain connectors`
5. `[DOCS] Close sprint 052 and hand off`

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

**Completed 2026-08-31.** Every acceptance criterion is implemented and verified; no criterion was
reduced and nothing is owed.

### What was delivered, against the plan

| # | Criterion | How it was proved |
|---|---|---|
| 1 | Two domains from one source, both committed | `test_one_source_previews_and_commits_rows_of_both_types`; and in a browser — one commit, `{"movie": 2, "series": 2}` |
| 2 | Existing connectors behave identically | Their four suites pass with only the one-element tuple changed; one summary-equality assertion widened, see deviations |
| 3 | Each row validated against its own domain | `test_each_row_is_validated_against_its_own_domain` — `watching` refused on the film row, accepted on the show |
| 4 | Triage renders a mixed batch per row | Walkthrough: `Apply Watchlist to Arrival`, `Apply Plan to watch to The Wire`, one inbox |
| 5 | Undo removes both domains, leaves nothing | `test_undo_of_a_mixed_batch_leaves_nothing_behind`; and live — items, entries and identifiers all zero after undo |
| 6 | Enrichment per enriching domain, scoped | `test_enrichment_is_queued_for_every_domain_the_batch_touched` — 4 jobs, kinds `{letterboxd, imdb}` |
| 7 | Unticking a target excludes and counts | `test_unticking_a_target_excludes_its_rows_and_says_how_many`; rendered as "2 rows are for libraries you did not choose" |
| 8 | Same file, different targets, different batch | `test_the_same_source_with_different_targets_is_a_different_import`; and in a browser — 2 rows, then 4 from the same file |
| 9 | Untargetable rows counted, not errors | `test_rows_the_reader_could_not_target_are_counted_not_failed` — 44 skipped, 0 errors |
| 10 | `GET /api/importers` publishes `item_types` | `test_the_registry_publishes_every_domain_a_connector_targets`; OpenAPI regenerated, `check-openapi-types.mjs` updated |
| 11 | No migration | None added; the fingerprint rule is why none is needed |

### Commits

- `8c05dbe [ADD] A connector declares the domains it produces`
- `fecff78 [ADD] Resolve the target domain per import record`
- `79ffc97 [ADD] Choose what an import brings in`
- `2b2fe54 [TEST] Conformance for multi-domain connectors`
- `d91aaad [TEST] A two-domain walkthrough runner`

### The stop condition was not triggered

Per-record domain resolution reached **exactly** the call sites the plan named and no further:
`ImportService._validate`, `ImportRepository.commit`/`commit_batch`, and the enrichment guard.
`application/undo.py` names no domain at all and needed no change — only proof. `TriagePage.tsx`
needed no change: it already resolved statuses and hotkeys from each row's own `item.type`.

### Verification

- Focused: `tests/test_generic_imports.py tests/test_multi_domain_imports.py
  tests/test_domain_conformance.py` plus the four connector suites — **319 passed** (307 before this
  sprint; 12 of the new tests are the two-domain seam).
- `make test` — **1012 backend + 194 frontend**, one pre-existing Letterboxd zipfile warning.
- `make check` — lint, typecheck, OpenAPI-type parity and project validation all green.
- `make openapi` — regenerated; `ImporterResponse.item_types` and the three `PreviewSummary` fields
  are the whole diff.
- Playwright, serial — **106 passed, 2 skipped** in 1 m 43 s, the historical baseline exactly.
  Parallel, one intermittent pre-existing failure; see below.
- **Walkthrough gate**, against a real backend on a disposable data directory with a live provider
  boundary: `scripts/walkthrough.py --replay ../scripts/walkthrough_two_domains.py`, then
  `sprint52-walkthrough.spec.ts`. Passed. It exercised the target checkboxes named from the domain
  registry, unticking one, the skipped counts, the same file answering 4 rows after answering 2, one
  commit into two libraries, Triage's per-row vocabularies, a status change on a series row, and
  undo leaving an empty library.

### Deviations

1. **The sprint's Verification block named `tests/test_imports.py`, which does not exist.** The
   generic pipeline suite is `tests/test_generic_imports.py`. Corrected above; the sprint's own
   two-domain tests live in the new `tests/test_multi_domain_imports.py`.
2. **The client mirror is `frontend/src/api/imports.ts`, not `library.ts`.** Corrected above.
3. **`test_goodreads_import.py` changed by more than the tuple.** One assertion compared the whole
   `summary` object for equality, and the summary grew three fields by deliverable 5. It now asserts
   all seven, including that a single-domain connector skips nothing on either count — the same
   exhaustive strength, not a weakened test. No Goodreads behaviour changed.
4. **`useItemTypes` gained an `enabled` flag.** The Import screen needs domain labels only when a
   connector can fill more than one library, and none of the four that ship today can. Not in the
   plan; it keeps the screen from fetching the registry on every visit for nothing.
5. **The two new mechanisms DEC-106 left open are recorded as DEC-112** — the skip channel
   (`ImportSnapshot.skipped`, chosen by the owner over a per-row flag) and the fingerprint's
   strict-subset condition, which is what makes this migration-free.
6. **The domain checkboxes read "Movie" and "Series", not the plan's "Movies"/"TV series".** They
   are the registry's own labels, the same words the Add page's domain chooser uses. Introducing a
   second, plural set of domain names for one screen would be the kind of copy drift DEC-080 exists
   to prevent.

### Also observed, out of scope, recorded for the owner

- **A pre-existing intermittent accessibility failure, surfaced by Sprint 051's parallel Playwright.**
  Under six workers, axe reports `color-contrast [serious]` on `.text-muted-foreground/80` — one
  class, used once, at `frontend/src/features/library/VirtualLibrary.tsx:100` (the web-results
  caption). It passes every time serially, and it moves between the accessibility specs that render
  that caption, which is the signature of a sample taken mid-fade rather than of a genuine palette
  defect. Computed statically the composite is 5.26:1 on the page background and 4.88:1 on a
  surface, both above the 4.5:1 this text size needs. This sprint touches neither that file, that
  class, the palette nor the motion helpers. Worth a scoped look: either the caption should not fade
  before axe reads it, or that opacity should go.
- **Movie enrichment is keyed on `letterboxd`, and an IMDb export carries no Letterboxd id.**
  `movie.enrichment.identity_kind` is `letterboxd` while `series` is `imdb`. Sprint 053's IMDb rows
  will therefore enrich shows and not films, through no fault of this seam. Named here so 053 meets
  it as a known question rather than as a surprise.
- The `/api/search/resolve` 502-for-a-miss defect and the `_backfillable_items` completeness-field
  defect, both from Sprint 046 (DEC-100), are still open and still not domain-specific.
