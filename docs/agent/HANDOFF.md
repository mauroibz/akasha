# Handoff — the numbered plan is complete

Plan revision 14. **Sprint 032 closed on 2026-08-21 and no sprint is active.** `state.json` reads
`complete` with null active fields and 001–032 in `completed_sprints`; `FINAL_SPRINT` in
`scripts/validate_project.py` is 32. Nothing has been tagged, pushed, released or deployed.

## What 032 changed, in one paragraph

Triage stopped being a top-level destination. It is a tab on `/import` beside one tab per registered
connector; `/triage` redirects there rather than 404ing, the nav item is gone, and the Inbox button
and the post-commit link both land on it. The tab lives in the URL (`?tab=`), and an unnamed one
falls back to the connector used last. Alongside that, a connector now guides its own users: it
publishes ordered `guide` steps, an `empty_state`, an https `help_url`, whether its source is
`browsable`, and a closed `error_codes` set whose errors carry `user_message` and `action` — one
imperative sentence a reader can act on. The import screen renders all of it without knowing which
connector wrote it. Calibre is browsed through `GET /api/import/{importer}/browse`, which returns
directory names only and resolves confinement with the same code the reader uses. DEC-080 is the
record; the sprint file's Outcome carries the evidence.

## Where things stand

- Gates green as of closure: validator, `make check`, `make test` (backend 502, frontend 164),
  `npx playwright test` (95 passed, 2 skipped), `git diff --check`. The full `make test` that
  Sprint 031 left waived was run to completion.
- The walkthrough gate ran against realistic data and produced three fixes, all recorded in the
  worklog. Read that entry before touching the import screen: two of the three were copy defects
  that no test would have caught and that a later edit could reintroduce.

## If you pick up the import boundary next

`docs/guides/adding-a-domain.md` is the instruction; `docs/specs/technical-spec.md` §6.5 is the
contract. Three things a new connector will meet:

1. **`ImportInputSpec.kind` is still `upload | path`.** A Spotify connector authorizes rather than
   uploading or pointing at a mount, and neither kind fits. That is the first design question the
   music epic hits, and nothing in 032 pre-empted it.
2. **`error_codes` is required.** An undeclared code is republished as `undeclared_import_error`
   rather than reaching the client, so a connector that forgets to list one will see that instead of
   its own code.
3. **`browsable` implies `BrowsableImporter`.** The conformance suite refuses one without the other,
   and it refuses `browsable` on an upload connector.

## Known and left

- The folder picker issues its listing request twice on mount under the dev server. That is React
  StrictMode double-invoking the effect; a production build does one. The e2e assertion is written
  not to depend on the sequence.
- **The e2e suite proxies unstubbed `/api` calls to whatever is listening on :8000**, which on this
  machine is the running Compose container holding the real library
  (`frontend/vite.config.ts` → `BOOK_TRACKER_E2E_BACKEND ?? "http://localhost:8000"`). It was found
  the honest way: `accessibility.spec.ts` and `feedback.spec.ts` were reading the container's
  `/api/importers` by accident, which is why they broke when the contract changed. They stub it
  through `stubImporters` in `e2e/seed.ts` now, and if you add a spec that opens `/import` use that
  helper rather than a fourth copy of the fixture. **Stub every route a spec touches, or set
  `BOOK_TRACKER_E2E_BACKEND` at a throwaway backend** — the suite contains delete, bulk-update and
  import-commit flows, and a gap in a stub points them at real data.
- **This deployment runs on bind mounts, not the default named volumes.** `./data` and `./backups`
  are the real storage, so it must be started as
  `docker compose -f compose.yaml -f compose.bind-mounts.yaml up -d`. A plain `docker compose up -d`
  silently starts it against the empty `akasha_data` volume instead, and the library looks wiped
  while the actual database sits untouched in `./data/books.db`.
- Triage is unchanged as a surface; 032 moved it and redesigned nothing. Its filters, grouping and
  conflict expansion are still what product spec §7 describes as intent rather than as built.
