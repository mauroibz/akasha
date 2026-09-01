# Sprint 057 — The names the product actually uses

**Status:** ready
**Depends on:** 056

**Roadmap revision:** 31

## Objective

The environment prefix becomes `AKASHA_` and the API title stops saying "Book Tracker". Two
cheap layers of the naming assessment (DEC-119), both landing before v1.5.1 is tagged — the
last moment the prefix change is not a release note's lead item.

The `book_tracker` package itself is untouched: DEC-042's rejection and the internal-names
invariant in `AGENTS.md` stand. This sprint changes what operators configure and what the API
calls itself, nothing else.

## Required context

- `backend/src/book_tracker/config.py` — the `env_prefix` line and every setting's
  `validation_alias`.
- `backend/src/book_tracker/main.py:261` — the FastAPI title.
- `compose.yaml`, `Dockerfile`, `Makefile`, `.env.example`, `scripts/smoke_container.sh`,
  `scripts/walkthrough*.py`, `frontend/vite.config.ts`, `frontend/playwright.config.ts` —
  every live consumer of the `BOOK_TRACKER_` prefix.
- `docs/specs/technical-spec.md`'s environment table; `docs/agent/TESTING.md`'s scratchpad
  invocation; the runbook; README's configuration table.
- `docs/decisions.md`: DEC-042 (the package-name rejection that stands), DEC-119 (this
  revision).
- `docs/operations/release-notes-v1.5.1.md` — the breaking-change paragraph this sprint adds.
- Historical records (closed sprints, worklog, decisions before DEC-119) keep `BOOK_TRACKER_`
  where it describes the past; they are not edited.

## Current implementation baseline

Measured 2026-09-01 at Sprint 056's closure (3409ae2), all live surfaces:

- `config.py:8` — `env_prefix="BOOK_TRACKER_"`; 10 distinct prefixed variables exist across
  the surfaces: `AKASHA_`-bound today already are `AKASHA_BIND/PORT/DATA_VOLUME/
  BACKUP_VOLUME/VERSION/LOG_MAX_SIZE/LOG_MAX_FILE` (compose-interpolated, never reach
  pydantic). Pydantic-bound: `BOOK_TRACKER_DATA_DIR`, `CALIBRE_DIR`, `DATABASE_URL`,
  `BACKUP_DIR`, `STATIC_DIR`, `ENVIRONMENT`, `ATTACHMENT_MAX_BYTES`, `SQLITE_BUSY_TIMEOUT_MS`,
  `PROVIDER_DAILY_LIMITS`, plus test/walkthrough-only `BOOK_TRACKER_BASE_URL`,
  `WALKTHROUGH_LIBRARY`, and frontend tooling's `BOOK_TRACKER_INCLUDE_SCRATCHPAD`,
  `BOOK_TRACKER_E2E_BACKEND`.
- `Dockerfile` ENV block sets four prefixed variables (`DATA_DIR`, `BACKUP_DIR`, `STATIC_DIR`,
  `ENVIRONMENT`); `compose.yaml` passes `BOOK_TRACKER_BACKUP_DIR=/backups` and Sprint 056's
  three bare pass-throughs; `Makefile` dev-backend sets `BOOK_TRACKER_DATA_DIR`.
- FastAPI title "Akasha Book Tracker", version "1.5.0" — lands in `frontend/openapi.json`.
  All version surfaces still read 1.5.0; v1.5.1 is untagged, so the bump rides this sprint.
- `test_backup.py:327` sets `BOOK_TRACKER_ENVIRONMENT`; the smoke test asserts prefixed names
  in five places; six walkthrough scripts print/read them.
- The prefix collision to design around: `AKASHA_BIND`/`AKASHA_PORT` already exist as
  compose-side variables. They do not reach pydantic (no alias), so `env_prefix="AKASHA_"`
  would newly resolve them into `Settings` as unknown-but-ignored (`extra="ignore"`) — safe,
  but must be verified, not assumed.

## Deliverables

1. **The prefix flip.** `env_prefix="AKASHA_"` in `config.py`. No alias: a `BOOK_TRACKER_*`
   variable in an operator's `.env` is silently ignored from v1.5.1 on — the owner directed
   a clean break. Compose pass-throughs, Dockerfile ENV, Makefile dev-backend, `.env.example`,
   smoke test, walkthrough scripts, playwright/vite config, and every doc table move to
   `AKASHA_*` names. The two compose-only variables (`AKASHA_BIND`, `AKASHA_PORT`) gain a
   documented note that they are compose-side, not application settings.
2. **The API title.** `FastAPI(title="Akasha", ...)`; version surfaces move to `1.5.1`
   (pyproject, package.json, main.py, regenerated `openapi.json`). Release notes describe
   the API title change.
3. **The breaking-change paragraph** in `release-notes-v1.5.1.md`, stating the rename table
   (`BOOK_TRACKER_X` → `AKASHA_X`) and the one-line remedy (rename the variable in `.env`).

## Acceptance criteria

1. A settings value set as `AKASHA_DATA_DIR` reaches the application; the same variable under
   `BOOK_TRACKER_DATA_DIR` is ignored — proved in a unit test, and through the running
   container for the attachment cap.
2. `AKASHA_BIND` and `AKASHA_PORT` in the environment do not change any application setting
   (ignored via `extra="ignore"`), and the smoke test's port/bind behavior is unchanged.
3. The smoke test passes end to end with `AKASHA_*` names, including Sprint 056's five
   pass-through assertions.
4. `/api/health/ready` served by the built image reports the OpenAPI title `Akasha`; the
   generated `frontend/openapi.json` says the same, and the frontend type check passes.
5. No live doc instructs a reader to set a `BOOK_TRACKER_` variable; historical records are
   untouched (grep proves the split).
6. The version surfaces (`backend/pyproject.toml`, `frontend/package.json`, `main.py`,
   `openapi.json`) all read `1.5.1`.
7. `python scripts/validate_project.py` passes.

## Required tests (TDD)

- `test_config.py` (new or the config-suite nearest neighbour): `AKASHA_DATA_DIR` is read,
  `BOOK_TRACKER_DATA_DIR` is not; `extra="ignore"` still absorbs `AKASHA_BIND`/`AKASHA_PORT`
  unknown keys; the production guard still fires on missing `USER_AGENT_CONTACT`.
- `test_backup.py`'s environment fixture moves to `AKASHA_ENVIRONMENT`.
- The smoke test's five env assertions move names, not semantics.

## Verification

```bash
python scripts/validate_project.py
make check
make test
make smoke-container
```

**This sprint owes the full gate** — no narrowed gate: the diff touches `backend/src/`,
`frontend/` config files and a generated contract (`openapi.json`), which is exactly the
narrowing's withdrawal condition. `npm run test:e2e` is owed the request-path/screen check
only if a screen changed; none does, but the Playwright config rename means the scratchpad
invocation in TESTING.md must be re-verified by hand once if any scratchpad spec is run.

## Explicit non-scope

- The `book_tracker` package name, `books.db`, the `/books/:id` route — DEC-042 and DEC-067
  stand; not reopened.
- Historical documents — closed sprints, the worklog, DEC-001–118 — keep `BOOK_TRACKER_`.
- Renaming `docs/` paths or the Docker volume names.
- Any alias/compatibility layer for old names — the owner directed a clean break.

## Commit checkpoints

1. `[CHANGE] The environment prefix becomes AKASHA_`
2. `[CHANGE] The API stops calling itself a book tracker`
3. `[DOCS] Breaking-change notes for v1.5.1 and the renamed variable table`
4. `[DOCS] Close sprint 057 and hand off`

## Risks and decisions to surface

- **The prefix change breaks every operator `.env` that sets a prefixed variable.** Recorded
  in the release notes with the remedy. The owner directed no alias.
- **`AKASHA_BIND`/`AKASHA_PORT` now fall inside the pydantic prefix.** They must stay ignored
  (`extra="ignore"`) — the unit test proves it rather than assuming it.
- The version bump is forced by the title change (OpenAPI contract), not chosen for its own
  sake; it also corrects the drift Sprint 056's release notes acknowledged.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
