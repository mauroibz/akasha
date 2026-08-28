# Handoff — the plan is complete; movies and Letterboxd both ship

Sprint 047 closed on `sprint-045-movies` in `a076f0c`. It was the last numbered sprint in the
roadmap, so `docs/agent/state.json` reads `complete` with null active fields. **There is no active
sprint.** Nothing has been tagged, released or pushed; the movie line is entirely local on this
branch.

Akasha now holds four domains — books, albums, anime and movies — and five connectors: Goodreads,
Calibre, MyAnimeList and Letterboxd.

## Read this before trusting Sprint 047's green

Sprint 047 was verified at a **reduced level, by the owner's explicit direction** (DEC-102). Its
focused suite, the conformance and every other importer suite, `make check`, both full unit suites
and a real end-to-end pass on the owner's own archive all ran and passed. Playwright, the walkthrough
gate through the real screens, and frontend tests for the new connector declaration **did not run**.

Concretely, and this is the part that matters to whoever goes next:

- Nobody has seen the Letterboxd connector rendered on the Import page.
- Nobody has approved a movie row from the Triage UI.
- **Undo has no coverage in that sprint at any level.**

The risky logic is covered — archive handling, the mapping matrix, the matcher scope, enrichment
against live Wikidata. The screen is not. Treat a UI defect there as expected rather than surprising.

## Known defects, recorded and not repaired

From Sprint 046 (DEC-100), neither of them movie-specific:

- `_backfillable_items` (`application/enrichment.py`) counts a null `cover_path` or `year` as "worth
  a lookup" in every domain, regardless of that domain's `completeness_fields`. Movies are
  deliberately coverless, so `POST /api/enrichment/backfill` re-queues every movie on every call and
  each job asks Wikidata for a cover it never returns.
- `GET /api/search/resolve` maps every exception from `resolve_input` to HTTP 502 `provider_failure`.
  A typed `record_not_found` is an answer, not an outage, and the reader is told the provider failed.

## If the next session picks something up

Nothing is scheduled. The obvious candidates, in the order they seem worth doing:

1. The UI surface DEC-102 leaves untested — the Import page declaration, a movie Triage approval, and
   an undo of a Letterboxd batch, driven through the real screens.
2. The two defects above.
3. A v1.4 release for the movie line, if the owner wants one. Sprint 018's release procedure and the
   `make build` / container smoke path are unchanged and were last exercised for v1.3.0.

Any of those needs a new sprint file, a roadmap entry, and `FINAL_SPRINT` in
`scripts/validate_project.py` moved past 47.

## Private and operational constraints

- `letterboxd-tomateperitarg-2026-08-27-22-42-utc.zip` is the owner's real export and remains
  untracked private data, byte-identical at 2,908 bytes. It is read-only walkthrough input and never
  a fixture. Every committed Letterboxd fixture is invented in `tests/test_letterboxd_import.py`.
- Wikidata needs no key, only `USER_AGENT_CONTACT`. A movie search costs four bounded requests.
- `frontend/e2e/scratchpad/movie-walkthrough.spec.ts` drives the movie domain through the real UI and
  is the place to start on item 1 above. The scratchpad directory is gitignored, so it is local only.
- The v1.3.0 anime/MyAnimeList release remains merged, tagged and pushed on `main` at `3bce2de`.
