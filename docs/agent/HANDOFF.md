# Handoff — Sprint 039 closed, Sprint 040 ready

Enrichment is off the ISBN. Plan revision 20, `FINAL_SPRINT` 41, active sprint **040 — Entry
progress**, status `ready`. Branch **`sprint-038-anime`**, cut from `main` at `bcb11ca` under
DEC-053. Nothing pushed. Merging is the owner's call at the line's close, not per sprint.

## What Sprint 039 delivered

A domain declares an `EnrichmentSpec` — the identifier kind it is keyed on, the providers that
answer it, and the metadata fields whose absence means "still worth a lookup". `PROVIDER_ORDER` is
gone; `fetch_by_identifier` replaced `fetch_by_isbn` as the interface enrichment asks through. Books
are unchanged and their existing tests passed unmodified. Details in the sprint Outcome, reasoning
in **DEC-091**.

Closure verification: `make check` green, `make test` **641 backend / 183 frontend**, Playwright
**103 passed / 2 skipped**, and a live walkthrough where an anime filled from AniList on a `mal` key
and a book filled from Open Library on an `isbn` key, in the same queue.

## Sprint 040 in one paragraph

DEC-077 priced entry depth, rejected child entities on evidence, chose shape (a) — a per-domain
`progress` field — and **built none of it**. Every row of the owner's MyAnimeList export carries
`my_watched_episodes`; one is `Black Clover`, dropped at 20 of 170, and the entry model has nowhere
to put it. A `ProgressSpec` on the domain, a nullable `entries.progress`, a fourth validator beside
the three that exist, a control that renders only where a domain declares one, and the value carried
in the export. **This is the only shared-table migration in the whole anime line** — back up before
the walkthrough, test the down-revision, and keep it in its own commit.

## Things a fresh session will otherwise rediscover

- **Adding a field to `Domain` is not free.** `test_the_suite_covers_every_field_of_the_contract`
  asserts `Domain.__dataclass_fields__` against a map, so a new field must arrive with a conformance
  check or an explicit note saying why it needs none. `ProgressSpec` needs one:
  `total_field`, when present, must name a `number` field the domain declares.
- **Watch for the "always incomplete" shape of bug.** Sprint 039's sharpest finding was a rule that
  judged a domain by fields it never stores. `total_field` has the same smell — a total pointing at a
  field nothing holds makes a bound nothing can satisfy. Conformance is where that gets caught.
- **A route docstring is its OpenAPI description.** Rewording one makes `frontend/openapi.json`
  stale and fails `make check` until `make openapi`. Cheap to hit, cheap to fix, easy to be confused
  by.
- **`Domain.enriches` is a property now**, not a field. `enrichment` is the field.
- **The frontend fallbacks are deliberately not book-shaped.** `labels.ts` falls back to `Item` and
  `Repeats` rather than `Book` and `Rereads`; a `progressFor` helper should follow that, and should
  tolerate a registry that never arrived without hiding a reader's own data.
- **Writing a walkthrough?** The domain chooser is a `radiogroup`, the library status filter is a
  popover whose options carry facet counts, and library row controls are popovers where Triage's are
  native selects (DEC-086). `frontend/e2e/scratchpad/anime-walkthrough.spec.ts` is the working
  example; it is gitignored.
- **Observed and unowned:** `JobRepository.complete` never clears `error`/`error_code`, so a job that
  failed then succeeded shows `succeeded` beside stale failure text. Pre-existing, in DEC-091, nobody's
  sprint yet.

## After 040

**041 — The MyAnimeList import** depends on both 039 and 040 and is the last sprint in the line. The
owner's export is gitignored at the repository root; use it for 041's walkthrough only and commit
trimmed anonymised fixtures instead. One thing already known for it: the backfill queues one job per
item, so 81 rows is 81 jobs against a provider publishing `X-RateLimit-Limit: 30`.
