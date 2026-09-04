# Sprint 068 — Export the way we import

**Status:** completed
**Depends on:** 067
**Roadmap revision:** 37

> Planned from [`../export-proposal.md`](../export-proposal.md). **Accepted as DEC-135.**

## Objective

Give export the shape import already has: a declared view per format, registered by the
domain that owns it, rendered by a shared streaming walk — and a `table` view so that
every domain, including the four that have no ecosystem format, can leave in something
another application opens. Backend only.

## Required context

- [`../export-proposal.md`](../export-proposal.md) — **read first.** §1 is the evidence,
  §2.1–2.4 and §2.6 are this sprint's deliverables, §5 is what it must not do.
- `docs/technical-spec.md` §6.6 — the domain contract, and the rule that a shared layer
  never branches on item type. This sprint removes the last branch that does.
- `docs/decisions.md` DEC-054 (owner data in, derived data out; attachments by reference
  plus `sha256`), DEC-080 (a connector declares itself and the screen renders the
  declaration), DEC-025 (a mock in place of the unit under test does not satisfy a
  correctness criterion).
- [`024-export.md`](024-export.md) — what shipped, why it streams, and the memory
  regression its own comment records.
- Code, read fresh: `backend/src/book_tracker/application/export.py` (all of it — the
  keyset `_batches` walk, `iter_items`, `iter_entries`, `GOODREADS_COLUMNS`,
  `_safe_cell`, `_row`, `export_csv`, and the `item.type != DEFAULT_DOMAIN.item_type`
  branch at `:421`), `backend/src/book_tracker/api/export.py`,
  `backend/src/book_tracker/domain/importers.py`,
  `backend/src/book_tracker/domain/registry.py:43-59`,
  `backend/src/book_tracker/domains/book/goodreads.py`,
  `backend/src/book_tracker/api/imports.py:157` (`GET /api/importers`).
- Tests: `backend/tests/test_export.py` (including its peak-memory test),
  `backend/tests/test_goodreads_import.py`, `backend/tests/test_domain_conformance.py`.

## Current implementation baseline

Verify each of these at activation rather than trusting the list.

- `GET /api/export` with `format=json|csv` is the entire export surface. No other route,
  no declaration endpoint.
- `application/export.py` holds Goodreads' seventeen columns, its 1–5 rating halving, its
  `Exclusive Shelf` spelling and its date format, and skips every non-book row at `:421`.
  It is a shared module doing one domain's work, and its own comment says so.
- `_safe_cell` neutralizes leading `=`, `+`, `-`, `@`. Any new spreadsheet view inherits
  that rule.
- The JSON path is entity-shaped, streams in keyset batches, and selects columns rather
  than entities on purpose — the identity map otherwise holds the library.
- `domains/book/goodreads.py` is the **reader** of the same file this sprint learns to
  write. It is the round-trip partner.

## Deliverables

1. **`domain/exports.py`** — the `ExportView` protocol of proposal §2.1: `name`, `label`,
   `item_types`, `media_type`, `lossless`, `filename`, `guide`, `help_url`, `carries`, and
   `write(rows) -> Iterator[str]`. Plus `ExportRow`, the neutral row the walk hands over.
2. **Registration, derived not hand-maintained.** Views register the way importers do;
   `EXPORTS_BY_DOMAIN` is built from what the views declare (`registry.py:43-59` is the
   pattern). A domain that declares no view still has the `table` view.
3. **The shared walk keeps the streaming discipline.** `application/export.py` keeps the
   keyset batching, the child-row grouping and the column-level select, and hands the view
   one `ExportRow` at a time. The view holds no session and writes no SQL.
4. **The `table` view** — proposal §2.2. One CSV for any domain, columns asked of the
   registry: the neutral entry layer (title, creator, year, status, score, shelves,
   formats, dates, progress, notes) plus the domain's declared metadata fields under their
   declared labels. It is written against the contract, not against a domain.
5. **The Goodreads writer moves to `domains/book/`**, beside the reader of the same file.
   `application/export.py` loses its `item.type` branch, and with it the last type branch
   in a shared layer.
6. **`GET /api/exports`** — the declarations, shaped like `GET /api/importers`, with the
   entry count each view would write for the library as it stands.
7. **`GET /api/export/{view}?type=<domain>`** — one view, streamed, `Content-Disposition`
   named from the declaration. Unknown view or a domain the view does not carry is a 404
   with the standard error envelope.
8. **Nothing that works today stops working.** `GET /api/export` and `?format=csv` keep
   their exact bytes, filenames and media types; `?format=csv` becomes an alias of the
   `goodreads` view. `openapi.json` is regenerated.

## Acceptance criteria

1. A seeded book library exported through the `goodreads` view and fed to
   `domains/book/goodreads.py` comes back with the same status, score, shelves, dates,
   review and read count for every entry.
2. Every registered domain — all five — returns a non-empty `table` CSV whose header
   carries that domain's declared field labels, with no code path naming a domain.
3. Adding a domain to the registry adds it to `GET /api/exports` and to `table` with no
   edit to `application/export.py` or `api/export.py`. Asserted in
   `test_domain_conformance.py` against every registered domain, not against a fixture.
4. `GET /api/export?format=csv` returns byte-identical output to the pre-sprint
   implementation for the same seed, with the same filename and media type.
5. A notes field containing `=cmd()` is neutralized in every view that writes a
   spreadsheet format, not only in the Goodreads one.
6. Peak memory for every view is flat against library size, measured the way
   `test_export.py` already measures JSON — a view that materializes rows fails the test.
7. `GET /api/export/nonsense` and `GET /api/export/goodreads?type=album` both return 404
   with the standard error envelope, not a 500 and not an empty file.
8. `GET /api/exports` carries, for each view, its label, what it carries in words, its
   guide steps, its help URL and the number of entries it would write — enough for a
   screen to render it without knowing any view's name.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Goodreads round trip: export → our own reader → same entries | integration | `test_export.py` |
| `table` renders every registered domain from its declaration | integration | `test_export.py` |
| Every registered domain is exportable; conformance over the registry | integration | `test_domain_conformance.py` |
| `?format=csv` is byte-identical to the shipped output | integration | `test_export.py` |
| Formula prefixes neutralized in every spreadsheet view | unit | `test_export.py` |
| Peak memory flat for each view, not only JSON | integration | `test_export.py` |
| Unknown view, and a domain a view does not carry, are 404s | api | `test_export.py` |
| `GET /api/exports` carries label, carries, guide, help URL and count | api | `test_export.py` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`
- The exhaustive backend suite, and the regenerated `openapi.json` committed.
- **Walkthrough (DEC-025):** export a seeded library through every view of every domain
  over real HTTP, open each file in a spreadsheet, and re-import the Goodreads one through
  the running application's own import pipeline. Report the row counts and what the files
  actually contained.
- No frontend gate is owed: this sprint changes no `.tsx` file. If it does, that is a
  deviation and is recorded.

## Explicit non-scope

- **Any UI.** The screen is Sprint 069. No route, no nav, no component.
- **MyAnimeList, Letterboxd and the series decision** — Sprint 070.
- Everything in proposal §5: attachment bytes, scheduled or remote export, an `akasha`
  re-importer, filtered export, new columns in the database.
- Changing the JSON export's shape. It is correct (finding 6) and it is the lossless path.

## Commit checkpoints

1. `[ADD] Let an export view declare itself the way an importer does`
2. `[MOD] Hand the view a row and keep the walk in one place`
3. `[ADD] Every domain leaves in a table it never had to write`
4. `[MOD] Move the Goodreads columns next to the Goodreads reader`
5. `[ADD] Say what can leave and where it goes`
6. `[ADD] One view, streamed, named after where it is going`

## Risks and decisions to surface

- **The memory test is the load-bearing one.** The reason the shipped walk selects columns
  is a regression its own comment records. A view that sorts or buffers would undo it
  quietly, so the test covers every view or the deliverable is not done.
- **`?format=csv` is a published contract** — product spec and `openapi.json`. Alias, not
  deprecation, and the byte-identical test is what proves it.
- **`carries` is prose, and prose in a declaration drifts.** Keep it to the entry fields
  the view actually writes, and let the round-trip test be what says whether it is true.
- **The `table` column order is a product decision.** Propose one, state it in the outcome,
  and let the owner change it — it is one tuple.

## Outcome

**Done.** All 8 deliverables and all 8 acceptance criteria. Three commits:
`bf86712` (`domain/exports.py` — the `ExportView` protocol, `ExportRow`, `safe_cell`,
and the generic per-domain `table` view; `GoodreadsExportView`/`EXPORT` moved beside the
reader in `domains/book/goodreads.py`), `7c93377` (the shared walk — `iter_export_rows`/
`stream_export_view` in `application/export.py`, replacing the old `export_csv` and its
`item.type` branch; `REGISTERED_EXPORTS`/`EXPORTS_BY_DOMAIN`/`find_export_view` in
`domain/registry.py`; `GET /api/exports` and `GET /api/export/{view}` in `api/export.py`;
`?format=csv` now an alias), `c358e66` (the new tests). The suggested six commit
checkpoints were combined into three — the module boundaries didn't split more finely
without leaving an intermediate commit red, and each of the three was verified green on
its own (1333, 1333, 1352 backend tests respectively) before being made.

**Two implementation decisions the sprint left open, resolved and recorded here rather
than guessed past:**

1. **One `table` view instance per domain, not one shared instance across all five.**
   The proposal's pseudocode suggests a single view; building it that way would have
   left `_TableExportView.write()` unable to know which domain's columns to render
   without either inferring from the first row (silent and wrong for an empty domain)
   or breaking the `write(rows) -> Iterator[str]` signature to take a second argument.
   `make_table_view(domain)` is instead called once per registered domain in
   `registry.py`, so each instance's columns and count are fixed at construction and
   correct even for zero rows. Consequence: `GET /api/exports` lists six views (one
   `goodreads`, five `table`), not two — `name` is unique *within* one domain's
   `EXPORTS_BY_DOMAIN` tuple, not across the whole registry, and dispatch on
   `GET /api/export/{view}?type=<domain>` is what disambiguates. Documented on
   `REGISTERED_EXPORTS`'s own comment in `registry.py`.
2. **`type` on `GET /api/export/{view}` is a required query parameter**, not optional
   with a default. The proposal's AC7 example (`GET /api/export/nonsense`) doesn't show
   one, but every other example in the same acceptance criterion does, and a required
   parameter is what makes dispatch unambiguous for `table`, which five domains
   register under the same name. Tests pass `type=` on every call.
3. **The `table` column order** (proposal's own flagged product decision): the twelve
   neutral columns first (Title, Creator, Year, Status, Score, Shelves, Formats, Date
   added, Date started, Date finished, Progress, Notes — `Creator` read from
   `metadata.creators`, the one field name every domain declares for it), then the
   domain's own declared metadata fields in their declared order, under their declared
   labels, with `creators` itself excluded from that second group so it is never
   printed twice. A `rows` field (album's `tracklist`) renders each row's non-empty
   cells space-joined and rows semicolon-joined; a `many` field joins with `, `. All
   driven from `FieldSpec.type`/`multiplicity`/`columns`, not from any field's name, so
   a future domain's fields render correctly by declaring themselves.

**Verified:** `make check` green. Backend **1,352** passed (1,333 + 19: 12 in
`test_export.py`, 7 in `test_domain_conformance.py`). No frontend gate owed — this
sprint changes no `.tsx` file, confirmed by the diff (`git diff --stat` against `main`
before this sprint touches no `frontend/src` path); `frontend/openapi.json` regenerated
and `npm run api:check` passes. `python scripts/validate_project.py` green.

**Walkthrough (DEC-025), done.** A throwaway backend (`scripts/walkthrough.py --keep`)
on an ephemeral port against a fresh `/tmp` data directory, seeded directly against its
own SQLite file (this sprint touches no add/import behavior, so seeding through
`DomainRepository` — the same object the test suite uses — rather than through search
providers kept the walkthrough proportionate): one book with an ISBN, formula-injection
notes and a shelf; one book with no metadata at all; one album, one anime, one movie,
one series, each with a couple of domain-specific fields set. Over real HTTP:
`GET /api/exports` listed all six views with correct per-domain counts, labels, guide
steps and help URLs; each of `goodreads` and the five `table` views was downloaded and
read back with Python's own `csv` module (not this repository's code) — every header
carried the expected neutral columns plus that domain's declared field labels, and
every value round-tripped correctly, including the album's `vinyl` format and the
anime's `progress`; `?format=csv` and `/api/export/goodreads?type=book` were confirmed
programmatically byte-identical; the formula-injection note (`=SUM(A1:A2)...`) came
back neutralized (`'=SUM(...)`) in the `table` view, not only in `goodreads`;
`/api/export/nonsense` and `/api/export/goodreads?type=album` both returned 404 with
`{"error": {"code": "export_view_not_found", ...}}`, never a 500 or an empty body; the
exported Goodreads CSV was fed back through the real running `POST /api/import/
goodreads/preview` → `commit` pipeline — the ISBN-bearing book matched its own item
exactly (an identity round trip through the export and back), the untitled second book
came back as an expected title-only ambiguity and was resolved by merging into its own
candidate, and the commit landed one already-known entry in the book Triage inbox
exactly as Goodreads import always has. Nothing looked wrong; no defect found. The
throwaway backend and its data directory were torn down at close; the owner's own
instance was untouched.

**Consequences:** `GET /api/exports`, `GET /api/export/{view}` are new OpenAPI surface;
`GET /api/export` and `?format=csv` are byte-identical to what Sprint 024 shipped.
`application/export.py` no longer names `book`, `GOODREADS_COLUMNS` or Goodreads' column
spellings anywhere — the last item-type branch in a shared layer is gone. No schema
change, no migration, no frontend change. Sprint 069 (the door) and Sprint 070
(MyAnimeList/Letterboxd/series) build directly on `GET /api/exports`'s declarations and
are otherwise unaffected by the two decisions above beyond what is written here.
