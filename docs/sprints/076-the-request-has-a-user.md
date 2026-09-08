# Sprint 076 — The request has a user

**Status:** ready
**Depends on:** 075
**Roadmap revision:** 40

> Planned from [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §1.2, §2.1
> and §3. **Accepted by the owner as DEC-146.**

## Objective

Delete every hardcoded user in the application. One resolver decides who a request belongs to,
every service and every query receives that answer explicitly, and no `user_id` literal survives
anywhere else. The resolver still answers "user 1" every time, so nothing user-visible changes —
this sprint exists so that Sprints 077 through 081 are small.

## Required context

- [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §1.2 (the 24 sites),
  §2.1 (why the resolver is the whole architectural bet), §3 (why this sprint must not be merged
  into 077), §6 risk 2.
- `docs/decisions.md` **DEC-146**.
- `docs/specs/product-spec.md` §9 — *"Cheap if the list view is already `render(entries WHERE
  user=X, filter, sort)` and authorization is a separate check. Build the view that way now."*
  This sprint is the second half of that instruction being kept.
- Code, read fresh — **every one of these, none inferred from this list**:
  - `backend/src/book_tracker/api/library.py:48-52` — `service()` and the `Library` annotated
    dependency. This is where the resolver goes.
  - The other ten constructions in the same file: `:678`, `:714`, `:785`, `:813`, `:870`, `:924`,
    `:1007`, `:1020`, `:1093`, `:1115`.
  - `backend/src/book_tracker/api/imports.py:286`, `:592`, `:769`, `:793`.
  - `backend/src/book_tracker/api/export.py:53`, `:69`, `:103`.
  - `backend/src/book_tracker/application/add.py:44-45`,
    `application/imports.py:158`, `:438`, `application/undo.py:55`,
    `application/enrichment.py:90`, `:507`,
    `infrastructure/jobs.py:349`, `infrastructure/repositories.py:569`, `:628`.
  - `backend/src/book_tracker/application/library.py:135-137` — the `user_id: int = 1` default
    that has to become required.
  - `backend/src/book_tracker/application/enrichment.py:443` — `EntryRow.user_id == 1`, the one
    bare literal in the codebase.
  - `backend/src/book_tracker/infrastructure/repositories.py` — the five `user_id: int = 1`
    signatures at `:255`, `:319`, `:349`, `:486`, `:614`.
  - `backend/src/book_tracker/application/export.py:248` (`iter_entries`) and `:324`
    (`iter_export_rows`) — **neither filters by user at all.** See the baseline below.
- Tests: `backend/tests/test_library_api.py` (the `create_app(` pattern used 213 times across the
  suite), `test_export.py`, `test_enrichment_pipeline.py`, `test_jobs.py`, `test_undo.py`.

## Current implementation baseline

Read at `11db2c5`, 2026-09-07:

- `LibraryService.__init__(self, engine, user_id: int = 1)` and ten `self.user_id` filters inside
  it. The service is already correct; nothing ever passes it a user.
- **24 construction sites across 8 files**, listed above. Eleven are in `api/library.py`.
- `DomainRepository` carries `user_id: int = 1` on five signatures.
- `enrichment.py:443` filters `EntryRow.user_id == 1` outright.
- **The export is not user-scoped at any layer.** `iter_entries(session)` walks every entry row in
  the database with no `WHERE user_id`, and `export_json(engine)` calls it. Today that is
  invisible because there is one user. After Sprint 079 it is a data leak, and it is the clearest
  demonstration of why this sprint exists.
- `213` occurrences of `create_app(` across the backend tests, none of which pass a user.

## Deliverables

1. **One resolver.** A single FastAPI dependency — `current_user(request) -> Principal` — living
   in a new `backend/src/book_tracker/api/identity.py`. In this sprint it reads `AKASHA_AUTH`,
   sees `off`, and returns the single user. It is the only place in the application allowed to
   decide who a request belongs to.
2. **`Principal` is a value, not an integer.** `user_id`, `username`, `is_admin`, and
   `acting_as` (null here; Sprint 080 fills it). Passing an `int` around would have to be widened
   again twice, and the type is what makes the guard test in deliverable 6 possible.
3. **Every construction site takes it.** All 24, plus the export functions. `LibraryService`,
   `DomainRepository`, `UndoService`, `ImportService` and the export walkers lose their defaults
   and require a user. A missing argument becomes a type error, which is the point.
4. **Background work states its owner explicitly.** A job carries the `user_id` written in Sprint
   075; the runner reads it rather than assuming. `enrichment.py:443` takes the entry's owner from
   the job instead of the literal `1`, and an enrichment job with a null owner writes no entry
   note at all rather than guessing — record that behaviour change in the Outcome, because it is
   the one place this sprint is not purely mechanical.
5. **The export is scoped.** `iter_entries`, `iter_export_rows` and `export_json` take a user and
   filter on it. `iter_items` stays unscoped: items are the shared cache.
6. **A guard test.** A test that greps the backend source for `user_id` literals and
   `user_id: int = 1` defaults outside `api/identity.py` and fails if any reappears. Crude on
   purpose — this is the regression that would be invisible otherwise, and a linter rule is more
   machinery than one test.

## Acceptance criteria

1. `grep -rn "user_id: int = 1\|user_id=1\|user_id == 1" backend/src/` returns nothing outside
   `api/identity.py`.
2. Constructing `LibraryService`, `DomainRepository`, `UndoService` or `ImportService` without a
   user is a `mypy` error, and `make check` proves it.
3. `GET /api/export` returns only the requesting user's entries. Asserted with two users seeded
   directly in the database — the routes to create one do not exist yet, and the test does not
   need them.
4. An import committed through the API records `user_id` on its batch, records and effects, and
   its undo reverses only that batch.
5. An enrichment job with a null owner completes and writes no entry note; one with an owner
   writes the note onto that owner's entry.
6. **The existing suite passes unchanged.** All 213 `create_app(` call sites keep working because
   `AKASHA_AUTH` is `off` and the resolver answers user 1. Any test that has to change is named in
   the Outcome with the reason.
7. `python scripts/benchmark_library.py` shows no regression on the list, facet and insights paths
   — the queries gained a bound parameter, not a join, and the Outcome carries the numbers.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| The resolver returns the single user when `AKASHA_AUTH` is off | unit | `test_identity.py` (new) |
| No `user_id` literal survives outside the resolver | unit | `test_identity.py` (new) |
| `export_json` returns only one user's entries, with two seeded | integration | `test_export.py` |
| `iter_export_rows` is scoped the same way | integration | `test_export.py` |
| `iter_items` is *not* scoped — the cache is shared | integration | `test_export.py` |
| A committed import stamps its batch, records and effects | integration | `test_generic_imports.py` |
| Undo reverses only the batch belonging to the caller | integration | `test_undo.py` |
| An owner-less enrichment job writes no entry note | integration | `test_enrichment_pipeline.py` |
| An owned enrichment job writes the note on that owner's entry | integration | `test_enrichment_pipeline.py` |
| Entry list, facets and insights are scoped | integration | `test_library_queries.py` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `python scripts/export_openapi.py --check` — the contract must be **unchanged**. This sprint
  adds no field and no route; a diff here means scope leaked.
- `npx playwright test` — unchanged, and expected to pass without edits.
- `python scripts/benchmark_library.py --entries 5000 --jobs 100`, before and after.
- **Walkthrough (DEC-025):** with two users seeded directly into a throwaway database, run the
  application as each in turn by flipping the resolver's answer with a temporary override, and
  confirm that the library, shelves, insights, triage, export and an import round-trip each show
  one user's data only. This is the sprint's real acceptance and no unit test substitutes for it.

## Explicit non-scope

- **Authentication of any kind.** The resolver has one answer. Sprint 077.
- **Creating a second user through the application.** Sprint 079.
- **Any change to the OpenAPI contract or any screen.** If either moves, scope leaked.
- **Optimizing the newly-scoped queries.** The indexes are already user-leading (Sprint 075's
  baseline); if the benchmark says otherwise, record it and raise it rather than fixing it here.

## Commit checkpoints

1. `[ADD] Resolve who a request belongs to, in one place`
2. `[REF] Make every service take its user instead of assuming one`
3. `[FIX] Stop the export dumping every user's entries`
4. `[MOD] Let a job say whose work it is`
5. `[TEST] Fail if a hardcoded user reappears`

## Risks and decisions to surface

- **This is a 24-site refactor with no visible output**, which is exactly the sprint that gets
  half-done. The mitigations are that missing arguments are type errors (criterion 2), that the
  guard test makes a relapse loud (criterion 1), and that the existing suite must pass untouched
  (criterion 6). If those three hold, the refactor is complete by construction.
- **The export finding is a real defect discovered while planning, not invented scope.**
  `iter_entries` has never filtered by user. It is harmless today and it is a leak the day Sprint
  079 lands, so it is fixed here, in the sprint that owns scoping — not deferred to the sprint
  that would discover it as a failure.
- **The enrichment note behaviour genuinely changes** for an owner-less job: it used to write onto
  user 1 and will now write nothing. With one user those are the same thing. Surface it in the
  Outcome anyway; a future reader deserves to know it moved.
- Resist widening `Principal` here. It gains `acting_as` in Sprint 080 and nothing before.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
