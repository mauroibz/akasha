# Sprint 088 — One contract, generated

**Sprint:** 088
**Status:** ready
**Roadmap revision:** 45
**Depends on:** 087
**Owner:** Mauro

## Objective

The browser's view of the API is generated from the server's OpenAPI document instead of written
by hand, every failed request becomes one typed `ApiError`, and the small rot the proposal listed
under R8 is gone. Nothing changes on screen; what changes is that a contract drift fails the build
instead of a page.

## Required context

- `AGENTS.md`, `docs/agent/WORKFLOW.md`, `docs/agent/TESTING.md`.
- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.4 (R5, R8) and §6.4.
- DEC-165, DEC-166 (087's findings: the server already sends one envelope, and the OpenAPI
  document declares it for every 422).
- Technical spec §7 (the error envelope, `X-Request-Id`).
- `frontend/openapi.json`, `frontend/scripts/check-openapi-types.mjs`, `scripts/export_openapi.py`,
  the `openapi`/`openapi-check` targets in `Makefile`.
- `frontend/src/api/*.ts`, `frontend/src/pages/HomePage.tsx`, `frontend/src/pages/TriagePage.tsx`.
- `backend/src/book_tracker/main.py` (`create_app`), `compose.yaml`,
  `frontend/public/manifest.webmanifest`.

## Current implementation baseline

Measured 2026-10-21 after Sprint 087 (`6b0e08a`):

- Types are hand-written in `frontend/src/api/*.ts` (seven modules). `check-openapi-types.mjs`
  asserts that about fifteen property names exist in `openapi.json`; nothing checks types.
- 15 raw `fetch(` calls across those modules, eight of them in `auth.ts`. Error bodies are parsed
  separately in `auth.ts`, `request.ts`, `shelves.ts`, `library.ts` and `add.ts`.
- 42 inline `queryKey: [` arrays; no factory.
- The optimistic patch-entry mutation is written twice: `HomePage.tsx:358` and
  `TriagePage.tsx:228`.
- `create_app` starts at `main.py:168` of a 701-line file and holds settings, provider wiring, the
  job runner, middleware, exception handlers, health routes and the SPA fallback.
- `compose.yaml:28` defaults the image to `1.5.7`; the application is 2.3.0.
- `manifest.webmanifest` describes "A self-hosted personal book tracker".

## Deliverables

1. `openapi-typescript` generates `frontend/src/api/schema.d.ts` from `openapi.json`;
   `openapi-fetch` (or a thin typed wrapper over it) replaces raw `fetch` in every API module.
   `make openapi-check` regenerates and fails on any diff; `check-openapi-types.mjs` is removed.
2. One `ApiError` (status, code, message, details, `user_message`, `action`, request id from
   `X-Request-Id`) thrown by the wrapper; the five hand parsers go.
3. A query-key factory (`frontend/src/api/keys.ts`) and a shared `usePatchEntry` optimistic hook
   used by Library and Triage.
4. `create_app` split into `app/{providers,middleware,errors,health}.py`; the provider catalogue
   built by looping the registry rather than one `catalog.append` per provider.
5. `compose.yaml` defaults to the current version; a release check (`scripts/check_versions.py`,
   run by `make check`) fails when any version surface disagrees. The manifest names Akasha as a
   media library.

## Acceptance criteria

1. A field renamed in a backend response model fails `make check` until the frontend is
   regenerated and its callers updated.
2. Every failed API call in the browser surfaces as an `ApiError` carrying the server's code and
   request id; existing user-visible error copy is unchanged.
3. Library and Triage share one optimistic patch hook; a failed patch rolls back in both, proven
   by one test per page.
4. `create_app` is under 120 lines; the route table, OpenAPI document and middleware order are
   unchanged (the OpenAPI export diff is empty).
5. `make check` fails if `compose.yaml`, `pyproject.toml`, `package.json` or the FastAPI version
   disagree.
6. Full gate green; Playwright unchanged in count.

## Required tests (TDD)

- Vitest: `ApiError` parsing (envelope, envelope with `user_message`/`action`, non-JSON body,
  network failure); `usePatchEntry` rollback.
- Backend: the version check script; an app-factory test that the route table and middleware order
  match the pre-split snapshot.
- The regenerate-and-diff check as part of `make check`.

## Verification

- `make check`, `make test`, `cd frontend && npx playwright test`.
- Walkthrough: run against a copy of real data; edit a score in Library and in Triage, force a
  validation error and a 404, and confirm the on-screen messages match v2.3.0.

## Explicit non-scope

- New UI, themes or copy (090 onward). FTS5 and the event stream (089).
- Changing any response shape. This sprint generates from the contract; it does not redesign it.

## Commit checkpoints

1. `[ADD]` Generated schema and typed client; the regenerate check.
2. `[MOD]` API modules move to the typed client and `ApiError`.
3. `[MOD]` Query keys and `usePatchEntry`.
4. `[MOD]` `create_app` split.
5. `[FIX]` Version surfaces agree, and a check keeps them agreeing; manifest copy.
6. `[DOCS]` Close sprint 088 and hand off.

## Risks and decisions to surface

- `openapi-fetch` is a new runtime dependency (about 6 kB). If its types fight the existing
  multipart upload calls, keep those two calls on the wrapper's raw escape hatch and say so.
- Some hand-written types are narrower than the schema (string unions the server types as `str`).
  Prefer tightening the Pydantic model with `Literal` over widening the client.

## Outcome

_Not started._
