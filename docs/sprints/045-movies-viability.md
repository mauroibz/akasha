# Sprint 045 — Movies viability: providers and Letterboxd shape

**Status:** in_progress
**Depends on:** 044
**Roadmap revision:** 24

## Objective

Turn the historical movies proposal into measured, current evidence before movie code is written.
Select viable metadata provider boundaries, understand the owner's real Letterboxd export without
committing private data, and leave two implementation sprints detailed enough to execute in order:
the movie domain first, then its importer. Nothing user-visible changes in this sprint.

## Required context

- `docs/README.md` for the status of every source document.
- `docs/specs/product-spec.md` and `docs/specs/technical-spec.md`, especially technical spec 6.6.
- `docs/guides/adding-a-domain.md` in full, including the Sprint 044 conformance tiers.
- `docs/domain_metadata_roadmap_report.md`, treating its movies/TMDB conclusions as a historical
  hypothesis rather than current evidence.
- `docs/decisions.md`: DEC-052, DEC-067, DEC-077, DEC-089, DEC-094 and DEC-097.
- `docs/agent/TESTING.md` for recorded-real-response and closure rules.
- The untracked root Letterboxd archive named in `docs/agent/HANDOFF.md`, read-only and private.
- Current official provider documentation, terms and live responses.

## Deliverables

### 1. Measure candidate movie metadata providers now

Evaluate at least two credible provider paths. TMDB is the historical front-runner, not a foregone
conclusion. Record current authentication, rate/usage constraints, stable identities, Spanish and
regional title support, creators, dates, descriptions, genres and poster candidates. Exercise live
responses for a bounded set that includes an Argentine or Spanish-language film, an older film, a
recent film and an ambiguous/remade title. Never infer correctness from documentation alone.

If a candidate needs an unavailable credential, verify its absence without printing environment
values, exercise the boundary as far as safely possible, and name the exact owner action. That does
not excuse testing every credential-free candidate. Prefer official APIs and primary documentation;
do not scrape consumer sites.

### 2. Walk a movie through the domain contract

Write an evidence-backed seam inventory for the package, identity/recognizer, providers, cover
host policy, enrichment, formats, statuses, score and any entry fields. Distinguish a flat film from
the already-deferred television-series hierarchy. Name any genuinely new shared seam; do not add
one speculatively. The result must make clear whether movies are viable in the current architecture
and what remains owner choice.

### 3. Measure the Letterboxd export shape

Inspect the supplied ZIP without modifying it or committing its contents. Record file names,
headers, row counts and cross-file relationships—not the owner's titles or prose. Determine stable
identity, duplicates/rewatches, diary dates, ratings, reviews, watched and watchlist membership,
likes, deleted rows and orphaned rows. State which files an initial importer consumes and which it
deliberately ignores. Check any format assumptions against Letterboxd's current official export
documentation where available.

### 4. Plan the build in at least two future sprints

Add and fully contract:

1. a movie-domain sprint with the provider(s) that survived live measurement and recorded-real
   response tests; and
2. a following Letterboxd-import sprint using the supplied archive as private walkthrough input.

Each plan names acceptance criteria, TDD tests, verification and walkthrough data, dependencies,
privacy constraints, provider credentials and explicit non-scope. The importer may depend only on
the completed movie domain, never land as a partial domain in the same sprint, and must preserve the
rule that re-import does not overwrite owner data.

## Acceptance criteria

1. The provider verdict is based on current official documentation and live calls, with response
   observations for the representative set and no scraped consumer endpoint.
2. At least one viable primary provider is identified, or the sprint records a concrete blocker and
   evidence that available alternatives do not satisfy the minimum movie metadata contract.
3. The movie seam inventory says whether any shared runtime, schema, API or UI change is required;
   flat films are not conflated with series or episodes.
4. The private Letterboxd sample is summarized structurally, never added to git, copied into a
   fixture, or quoted for personal content.
5. Rating, status, identity, diary/rewatch and duplicate semantics are explicit enough that importer
   tests can be written before its implementation.
6. Two later sprint files—movie domain/providers, then Letterboxd importer—are `planned`, ordered,
   complete with required context and executable acceptance criteria.
7. Canonical specs, roadmap, decisions, state and handoff reflect the verdict without claiming any
   movie runtime behavior was delivered.

## Verification

```bash
python scripts/validate_project.py
git diff --check
```

Provider probes and archive-inspection commands are recorded in the Outcome with secrets and
private values redacted. This documentation-only feasibility sprint does not run application,
frontend, Playwright, build or container suites unless it changes their code or configuration.

## Explicit non-scope

- No movie domain package, registration, provider adapter, migration, API or UI behavior.
- No Letterboxd reader, import route behavior or committed sample fixture.
- No television/series hierarchy and no change to DEC-077's entry-depth verdict.
- No scraping IMDb, Letterboxd, TMDB's website, or another consumer interface.
- No paid subscription, account creation, key issuance or acceptance of provider terms on the
  owner's behalf.

## Commit checkpoints

1. `docs(sprint-045): measure movie metadata providers`
2. `docs(sprint-045): define the Letterboxd import shape`
3. `docs(sprint-045): plan movie domain and importer sprints`
4. `docs(sprint-045): close sprint and hand off`

## Risks and decisions to surface

- Provider terms, auth and image policies are current facts and must be checked, not inherited from
  the historical survey.
- A tiny personal export can prove topology but not all value variants. Separate observed sample
  facts from official-format facts and adversarial cases.
- Letterboxd URL, TMDB id and title/year are not interchangeable identities. The plan must choose a
  canonical provider identity and retain source identity without fuzzy matching silently.
- A half-star Letterboxd scale can map exactly onto Akasha's integer 1–10 score, but unrated and
  zero are distinct; prove the source encoding before contracting it.

## Outcome

_Not started._
