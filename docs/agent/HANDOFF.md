# Handoff — Sprint 047 ready: the Letterboxd importer

Sprint 046 is complete on `sprint-045-movies` in `6e53952`, `1cd443e` and `20fda58`. **Movies ship.**
`domains/movie/` is the fourth domain and `WikidataMovieProvider` is its one adapter: film-filtered
search, exact Wikidata/IMDb/TMDB/Letterboxd identity resolution, HEAD-only `boxd.it` resolution,
Spanish labels with English fallback, and no cover under any circumstance. Nineteen fixtures recorded
live from Wikidata back every parser branch. DEC-099 and DEC-100 hold what was measured.

## Next sprint

Sprint 047 is ready. Read `docs/sprints/047-letterboxd-import.md` and every required source, then
inspect the actual `domains/movie/` code and the current `ImportMatcher`/`ImportRepository` behaviour.
It is a user-visible connector sprint with a real Import → Triage walkthrough.

**Two constraints Sprint 046 found for it, already written into its plan:**

- `DomainRepository.match` (`infrastructure/repositories.py:138`) scans **every** item row with no
  `items.type` filter. Fine for title+author; wrong for title+year with no creator, where a novel
  and its adaptation routinely share both. Scope the year suggestion to the target domain.
- `fetch_by_identifier("letterboxd", …)` **already accepts** a bare `P6127` slug, a full
  `letterboxd.com/film/<slug>/` URL and a `boxd.it` short URI. Store the export's URI as it comes;
  do not add a normalization pass that spends a network request per row (DEC-100).

Sprint 047 also gets Triage's first real movie row. Nothing has produced an unsorted film yet, so
that half of the domain is genuinely untested until this connector exists.

## Known defects, recorded and not repaired (DEC-100)

Neither is a movie defect; both predate this sprint and affect every domain.

- `_backfillable_items` (`application/enrichment.py:428`) counts a null `cover_path` or `year` as
  "worth a lookup" regardless of the domain's `completeness_fields`. Movies are deliberately
  coverless, so `POST /api/enrichment/backfill` will re-queue every movie on every call and each job
  will ask Wikidata for a cover it never returns. Harmless until someone calls that route often.
- `GET /api/search/resolve` maps every exception from `resolve_input` to HTTP 502
  `provider_failure`. A typed `record_not_found` is an answer, not an outage, and the reader is told
  the provider failed.

## Private and operational constraints

- `letterboxd-tomateperitarg-2026-08-27-22-42-utc.zip` remains untracked private data. Sprint 047 may
  use it as **read-only walkthrough input only** — never a fixture, never committed, never modified.
  Tests use synthetic archives.
- Wikidata needs no key, only `USER_AGENT_CONTACT`. It is live and answering; a movie search costs
  four bounded requests and measured 1.6–2.8 s end to end.
- Provider fixtures must be freshly recorded, bounded, and given a README row stating the command and
  date. A synthetic fixture is allowed for an adversarial shape and must say so.
- `frontend/e2e/scratchpad/movie-walkthrough.spec.ts` is the working reference for driving the movie
  domain through the real UI. The scratchpad directory is gitignored, so that file is local only.
- The v1.3.0 anime/MyAnimeList release remains merged, tagged and pushed on `main` at `3bce2de`.
  Nothing in Sprint 046 has been released; the branch is local.
