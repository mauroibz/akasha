# Handoff — Sprint 044 ready after the v1.3 release

Sprint 043 is complete in `bb474c7`; **Sprint 044 is `ready` and not started.** It is the
domain-contract QOL sprint planned from the anime retrospective (DEC-094), renumbered only because
the owner inserted two Triage correction sprints ahead of it.

The v1.3.0 release tree has passed its exhaustive gates and is ready for the owner-authorized
no-fast-forward merge, annotated tag and push. Release preparation adds anime/MyAnimeList README
coverage, synchronized 1.3.0 version surfaces and release notes. The container smoke harness was
also corrected to use the current domain-neutral add payload after its stale book-only shape
produced a useful 422 on the first run.

## Next sprint

Read `docs/sprints/044-sharpening-the-domain-contract.md` and DEC-094 in full. Its six non-visual
deliverables are: one allowlisting entry-value validator used by all three write paths; an
application-wiring conformance tier; a head-schema guard against vocabulary-freezing CHECKs; one
`EntryRow` factory; the load-bearing Alembic foreign-key comment; and the table-rebuild/UI-driving
recipes. It has no walkthrough gate.

The owner has directed the work after Sprint 044: create a separate movies branch, evaluate the
documented movies proposal and real metadata providers, inspect the root Letterboxd export as
read-only sample input, and plan at least two future sprints—movies/domain providers first, then a
Letterboxd importer. Do not commit, delete or rewrite
`letterboxd-tomateperitarg-2026-08-27-22-42-utc.zip`; it is private user data.

## Verified state

- Focused Sprint 043: 20 Triage browser tests, 3 accessibility tests, frontend type checking.
- Release gates: `make check`; `make test` (698 backend / 189 frontend); full Playwright (106 passed,
  2 skipped); `make build`; complete container smoke.
- Realistic walkthrough: 81 MyAnimeList rows + 18 Calibre books in disposable data at mobile width,
  including navigation/reload draft persistence and three row commits; no console/page errors.
- Live application data was never opened for writing. The Letterboxd archive remains untracked.
