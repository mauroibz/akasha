# Sprint 003 — Entries, shelves, filtering, and keyset API

**Status:** completed
**Depends on:** 002
**Roadmap revision:** 2

## Objective

Deliver the complete entries and shelves HTTP contract, including scalable, stable list filtering
and bulk mutations, on the persisted domain model from Sprint 002.

## Required context

Read in order:

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 2, 3, and 5
3. `docs/specs/technical-spec.md` sections 2, 5, 6.4, 7, and 10
4. `docs/decisions.md` DEC-005, DEC-008, DEC-010, and DEC-013
5. `docs/sprints/ROADMAP.md` Sprint 003 and downstream Sprints 004, 006, 010, and 011
6. `docs/agent/WORKFLOW.md`
7. `backend/alembic/versions/0002_domain_schema.py`, `backend/src/book_tracker/domain/`,
   `backend/src/book_tracker/infrastructure/`, and all backend tests

## Current implementation baseline

Sprint 002 provides a migrated complete v1 schema, mapped rows, canonical identity and text
normalization, typed match decisions, fill-empty behavior, and short transactional repositories.
Only health routes exist; there are no entry/shelf application services, transport models, list
queries, cursor codec, or domain HTTP error mappings.

## Deliverables

- Add application services for entry/item/shelf reads and mutations with explicit transactions.
- Add opaque versioned cursor encoding, validated filters, whitelisted sorting, facets, and exact
  counts with matching SQL ordering/seek expressions.
- Add `/api/entries`, `/api/items`, and `/api/shelves` routes and stable domain error responses.
- Add explicit-ID and filter-plus-exclusions bulk mutation and accept-suggested services.
- Keep OpenAPI and generated frontend contract artifacts synchronized.

## Acceptance criteria (ordered, TDD)

1. Entry/item/shelf read, edit, delete, create, rename, and attach/detach routes enforce the v1
   invariants; score edits clear provisional state and shelf deletion never deletes entries.
2. `GET /api/entries` defaults to excluding `unsorted`, while explicit repeated status, shelf, and
   text filters return exact totals and non-status facet counts.
3. Every allowed sort uses stable keyset pagination with ID tie-breaking and NULL-last behavior in
   ascending and descending order; duplicate/null values, deleted boundaries, and normalized text
   collation neither skip nor repeat rows.
4. Malformed, version-mismatched, or filter/sort-mismatched cursors return a stable validation error;
   common list queries use the intended indexes under `EXPLAIN QUERY PLAN`.
5. Bulk mutation accepts either explicit IDs or a server filter plus exclusions, never both, and
   applies atomically; accept-suggested uses the same validated filter contract.
6. Static `/entries/bulk` and `/entries/accept-suggested` routes cannot be shadowed by
   `/entries/{entry_id}`, and OpenAPI/frontend types describe all success and error shapes.

## Verification

Run and record:

```bash
python scripts/validate_project.py
make format
make check
make test
make build
git diff --check
```

Also run focused API contract tests, file-backed pagination/query-plan tests, and mutation rollback
tests through the ASGI application.

## Explicit non-scope

- No frontend library/triage UI, metadata provider/search/add orchestration, imports, or jobs.
- No offset pagination, count cache, auth, or network access.
- No changes to permanent internal package/entity names.

## Commit checkpoints

1. `feat: add entry and shelf application services`
2. `feat: add stable keyset list queries`
3. `feat: expose entries and shelves API contracts`
4. final `docs(sprint-003): close sprint and hand off`

## Risks and decisions to surface

- Cursor comparisons and SQL ordering must use identical null buckets and text collation.
- Bulk filters must be validated once and reused to avoid semantic drift from list filtering.
- Preserve imported personal values except through explicit user/API mutation.

## Outcome

Delivered typed entries/items/shelves CRUD, attachment replacement, stable domain errors, normalized
search, exact totals/facets, opaque query-bound cursors for every v1 sort, atomic bulk selection and
suggested-status acceptance, composite list indexes, and a generated OpenAPI contract.

- `7c8435b` adds application services, API schemas/routes, deterministic cursor and SQLite text
  normalization, migration `0003_list_indexes`, and focused ASGI/file-backed tests.
- `26c5c4f` fixes deterministic OpenAPI formatting by excluding the generated artifact from Prettier
  and makes response metadata pass strict typing.
- Verification: project validation, `make format`, `make check`, `make test` (49 backend and 2
  frontend tests), `make build`, and `git diff --check` passed. Focused tests cover all six sorts in
  both directions, duplicate/null values, deleted cursor boundaries, malformed/mismatched cursors,
  normalized search, composite query-plan selection, static-route precedence, and bulk rollback.
- Deviation: the planned generic “stored normalization/collation” was resolved to a deterministic
  per-connection SQLite `normalize_text` function so Unicode search/order/cursors share exact
  semantics without duplicated columns; technical spec section 7.2 and DEC-015 record this. Sprint
  011 retains measurement of whether a stored text-sort projection is warranted.
- Downstream review: Sprint 004 was expanded against the generated `EntryListResponse` contract;
  Sprints 006 and 010 can reuse typed CRUD/bulk filters unchanged, and Sprint 011 now explicitly
  owns measured text-sort index hardening if needed.
