# Sprint 005 — Providers and cached add API

**Status:** ready
**Depends on:** 004
**Roadmap revision:** 2

## Objective

Deliver the provider and one-call add boundary that caches complete book metadata locally without
holding SQLite write locks during network or image work.

## Required context

Read in order:

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 2, 3, 4, and 6
3. `docs/specs/technical-spec.md` sections 4, 5, 6, 7, 9, and 10
4. `docs/decisions.md` DEC-003, DEC-007, DEC-010, DEC-011, DEC-012, and DEC-014
5. `docs/sprints/ROADMAP.md` Sprint 005 and downstream Sprints 006, 007, 009, and 011
6. `docs/agent/WORKFLOW.md`
7. `backend/src/book_tracker/domain/`, `backend/src/book_tracker/application/library.py`,
   `backend/src/book_tracker/infrastructure/repositories.py`, `backend/src/book_tracker/api/`,
   `backend/src/book_tracker/config.py`, and their focused tests

## Current implementation baseline

Sprint 004 provides a checked typed frontend boundary and virtualized library but intentionally no
add screen. The backend has relational identity/source repositories, typed library CRUD, and stable
error envelopes, but no provider models/adapters, search/resolve routes, add orchestration, HTTP
limits, cover pipeline, or `POST /api/entries` contract.

## Deliverables

- Add immutable provider domain models/protocols plus deterministic candidate merge/rank behavior.
- Add Open Library and optional Google Books adapters with bounded mocked HTTP, independent
  timeouts, partial failure, URL/ISBN resolution, and work-edition selection.
- Add manual and provider-backed one-call entry creation with exact duplicate/idempotency handling,
  near-match advisories, validated secondary identities, and typed responses.
- Add bounded cover download/validation/resize/temporary-file handling followed by post-commit
  atomic installation and non-fatal failure cleanup.
- Regenerate OpenAPI and keep the frontend checked contract synchronized; do not build Sprint 006's
  add UI.

## Acceptance criteria (ordered, TDD)

1. Provider search fans out concurrently with independent five-second limits, returns partial
   results when one enabled provider fails, and returns typed `providers_unavailable` only when all
   enabled providers fail; normal tests make no public requests.
2. Candidate merging retains all agreeing source identities, ranks deterministically, never maps an
   Open Library work year into edition year, and makes work URLs return ranked edition choices.
3. Bare validated ISBNs and supported Open Library/Google Books URLs resolve to edition candidates;
   malformed/unsupported inputs return stable typed errors and absent Google credentials disable the
   adapter without counting as failure.
4. `POST /api/entries` accepts manual or selected provider input in one call, performs network and
   cover preparation before its short write transaction, validates secondary identities, and
   returns a complete cached entry without requiring provider access to render it.
5. Exact identity double-submit is idempotent and returns `200` with `already_exists=true`; a
   title/author near edition is advisory only and remains addable, while contradictory exact
   identities return `identity_conflict` without attaching anything.
6. Cover payload limits, type/dimension validation, JPEG normalization, atomic placement, and
   cleanup are enforced; any cover failure leaves the committed entry valid with no broken path and
   no long-held SQLite lock.

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

Also run focused provider contract tests with mocked timeout/429/malformed/partial responses,
Open Library work/edition fixtures, URL/ISBN resolution tests, concurrent double-submit tests, a
write-lock timing proof, and cover size/type/pixel/install-failure filesystem tests.

## Explicit non-scope

- No add/detail UI, metadata editor, explicit refresh implementation, imports, jobs, or triage.
- No Goodreads scraping, plugin registry, authentication, live-provider normal-test dependency, or
  network access while rendering cached library pages.
- No automatic fuzzy merge and no arbitrary edition choice for work URLs.

## Commit checkpoints

1. `feat: add provider domain and search adapters`
2. `feat: add edition-safe search and resolution API`
3. `feat: add cached idempotent entry creation`
4. `feat: add bounded non-fatal cover pipeline`
5. final `docs(sprint-005): close sprint and hand off`

## Risks and decisions to surface

- Image decoding limits must reject decompression bombs before allocating unbounded memory.
- Secondary source references are untrusted client input until provider agreement or canonical ISBN
  validation proves identity.
- Tests must distinguish a disabled optional provider from a configured provider failure.
- Filesystem and relational commits cannot be atomic; DEC-011's post-commit installation and cleanup
  contract is authoritative.

## Outcome

_Not started. The implementing agent replaces this section with delivered behavior, tests/commands
and results, commit IDs, deviations, and downstream changes before marking the sprint complete._
