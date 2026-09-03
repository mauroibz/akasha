# Sprint 065 — Insights: rankings from the fields items already declare

**Status:** planned
**Depends on:** 023, 026, 027, 040, 044, 064
**Roadmap revision:** 35

## Objective

Ask the library a question it already has the answer to — *which authors do I rate highest,
which bands do I own most of, which decade do I keep going back to* — and get a ranked
answer, per domain, from the fields those items already declare. Ships as **v1.6.0, the
insights release**.

## Required context

- `docs/spotify-import-and-insights-viability.md` §Part 2 — **read first.** The sizing, the
  measured key distribution, and the three design questions this sprint answers.
- `docs/decisions.md` DEC-051 (the creator-sort heuristic and its override), DEC-052 and
  DEC-077 (why an Author or an Artist is deliberately *not* an entity here — this feature
  exists to keep it that way), DEC-067 row 4 (a domain may not widen a central list from
  its own package), DEC-114 (pay once for evidence), DEC-116 (a declaration beats a
  constant).
- `docs/specs/product-spec.md` §9 and the `v2` entries — **`v2` is a reserved term in this
  product**: auth, multiuser, sharing, Calibre write-back. Insights is none of those, so
  it is a `v1.Y` feature release in the shape of v1.5 ("the series release"), not a 2.0.
- `docs/specs/technical-spec.md` §6.2, §6.6.
- Code, read fresh: `domain/spec.py` (`FieldSpec`, `Domain`), each
  `domains/*/__init__.py` field list, `infrastructure/models.py` (`ItemRow.year`,
  `creator_primary`, the three `*_normalized` columns and the mapper event that maintains
  them), `application/library.py` (`_filtered_entries` and the existing `facets` block —
  the nearest thing to this and deliberately not general), `domain/normalization.py`,
  `api/library.py`, `frontend/src/App.tsx`, `frontend/src/pages/HomePage.tsx`,
  `frontend/src/features/library/`.
- Tests: `test_library_queries.py`, `test_domain_conformance.py`,
  `scripts/benchmark_library.py`.

## Current implementation baseline

- **The groupable surface is already declared, but not marked.** Every domain publishes its
  fields with a `multiplicity`, and `/api/item-types` already serves them. What is missing
  is which of those fields it is *meaningful* to group by — see the design note below.
- **Aggregation exists once, narrowly.** `/api/entries` returns `facets`, a hand-written
  status × type count over a filtered subquery. It is the pattern to follow and not a
  general engine to extend.
- **The first creator is cheap; the rest are not.** `items.creator_primary` is a computed
  column (`json_extract(metadata, '$.creators[0]')`) with a normalized twin. Every creator
  beyond the first lives in a JSON array that no query here reads yet; grouping over them
  needs `json_each`.
- **Name-variant correction already exists** as `creator_sort_override`, per item, for the
  primary creator (DEC-051).
- **`year` is not a metadata field.** It is `items.year`, an integer column every domain
  has. The owner's request for "years for both" therefore cannot be served by a `FieldSpec`
  flag alone.
- **Score density is unknown and is the feature's main risk.** The measurement that would
  settle it does not exist: the live library holds 13 entries, 6 scored. Sprint 064 exists
  partly to produce a real dataset. **This sprint is designed so that it is useful even if
  scores turn out to be sparse** — see deliverable 4.
- Measured proxy for what a ranking will look like, from the owner's Spotify library: 157
  albums → 88 distinct artists, of which **only 14 have three or more albums**;
  normalization merged **zero** variants (Spotify's strings are already canonical, unlike
  Calibre's author names); and **`Various Artists` holds 7 albums** and would rank third.

## Design notes that shaped the deliverables

**Scope is per-domain, and deliberately so.** A ranking never merges keys across domains.
"Top creators across books, films and albums" would need a creator identity that survives
across domains — which is the entity DEC-052 and DEC-077 twice declined to create, and the
whole reason this feature is shaped as an aggregate rather than a subdomain. The same key
*name* may exist in several domains (`creators` in all five) and still produces five
separate rankings.

**`multiplicity == "many"` is the wrong rule for what is keyable.** `tracklist` is a `many`
field of row objects; `catalog_number`, `original_title` and the two anime title fields are
scalar text that is near-unique per item. Grouping by any of them is noise. The rule is
therefore an explicit declaration, one reviewed decision per field, in the style
`completeness_fields` and `fuller_answer_fields` already set.

## Deliverables

1. **`FieldSpec.groupable: bool = False`, declared true per domain.** The starting set, which
   is the owner's list plus the fields that obviously belong beside it:

   | Domain | Groupable metadata fields |
   |---|---|
   | book | `creators` (authors), `subjects`, `publisher`, `language`, `series` |
   | album | `creators` (bands), `label`, `country`, `language`, `format` |
   | movie | `creators` (directors), `genres`, `cast`, `countries`, `languages` |
   | series | `creators`, `genres`, `cast`, `countries`, `languages`, `network` |
   | anime | `creators`, `genres`, `kind`, `source`, `season`, `airing_status` |

   Explicitly **not** groupable: `tracklist` (rows), `catalog_number`, `original_title`,
   `english_title`, `japanese_title`, `synopsis`, `description`, and every `number` field.
   A conformance test asserts no `rows` or `long_text` field is ever marked groupable.

2. **Two built-in keys every domain offers: `year` and `decade`.** `year` is
   `items.year`; `decade` is derived from it (`1994 → 1990s`). They need no per-domain
   declaration because every item has a year, and they are what makes the owner's "years
   for both" work without pretending `year` is metadata. `decade` exists because a ranking
   over sixty distinct years is a list, not an insight.

3. **`GET /api/insights` — one endpoint.** Parameters: `type` (required, one domain),
   `key` (a groupable field name, or `year`/`decade`), `metric` (`count` | `score`),
   `min_rated` (default 2), `limit`, `after`. Returns per key value: the display label, the
   number of entries, the number of *rated* entries, the mean score, and its spread. It
   reuses `_filtered_entries` so a ranking can later be taken over a filtered library rather
   than the whole domain.

4. **Two metrics, because one of them works with no scores at all.** `count` ranks by how
   many entries carry the key — "the authors I own most of" — and is meaningful the day the
   library is imported. `score` ranks by mean score among keys with at least `min_rated`
   rated entries, with the count shown beside it so a single 10 never masquerades as a
   record. This is the deliberate hedge against the unmeasured score density: **if scores
   turn out to be sparse the feature is diminished, not useless.**

5. **Grouping is normalized; display is not.** Keys group on `normalize_text` (case and
   diacritics folded) and each row displays the most frequent original spelling among its
   members. The measurement says this will merge nothing for Spotify-sourced artists and a
   great deal for Calibre-sourced authors, which is exactly why it is not optional.

6. **A declared, visible suppression list per domain.** `Various Artists` is not an artist
   and would rank third in the owner's library. `Domain.insight_suppressed_keys` holds the
   normalized values a ranking omits; the response names what it suppressed so the screen
   can say so, rather than the rows vanishing without explanation. A query parameter
   includes them back.

7. **`/api/entries` gains a precise `key`/`value` filter**, so a ranking row links to the
   items behind it. Without this the feature is a table you cannot click, and the existing
   `q` text search is not a substitute — it would match `Gorillaz` inside a description.

8. **An Insights page** at `/insights`: domain picker, key picker built from
   `/api/item-types`, a metric toggle, the threshold control, and the ranked table whose
   rows link into the filtered library. Reachable from the main navigation.

## Acceptance criteria

1. Ranking books by `creators`/`count` lists authors by how many of their books are in the
   library; ranking by `creators`/`score` lists them by mean score, excludes anyone below
   `min_rated`, and shows the rated count beside each mean.
2. The same works for albums by `creators` (bands), movies by `creators` (directors), and
   every other field marked groupable — driven by the declaration, with no per-domain branch
   anywhere in the query.
3. `year` and `decade` rank in every domain, from `items.year`, with items whose year is
   null excluded and their number reported rather than silently dropped.
4. A creator appearing beyond the first position counts: a film credited to two directors
   contributes to both rankings, and a book whose second author is someone else's first
   groups with that person.
5. `Julio Cortázar` and `julio cortazar` are one row, displayed with the spelling that
   occurs most.
6. `Various Artists` does not appear in an album ranking by default, the response says it
   was suppressed, and a parameter brings it back.
7. No ranking mixes domains, and no groupable field is a `rows` or `long_text` field.
8. Clicking a ranking row shows exactly the entries behind that number.
9. **Performance:** a ranking over a library of 5,000 entries returns within the same budget
   the library list holds itself to, measured with `scripts/benchmark_library.py` extended
   for this query — not asserted from a small fixture.
10. A domain with no scored entries still produces a `count` ranking, and a `score` ranking
    says plainly that there is nothing to rank rather than returning an empty table.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Count ranking over a `many` field, all positions counted | repository | `test_insights.py` (new) |
| Score ranking honours `min_rated`; the mean is right | repository | `test_insights.py` |
| Scalar metadata keys (`publisher`, `label`, `network`) rank | repository | `test_insights.py` |
| `year` and `decade` rank; null years are excluded and counted | repository | `test_insights.py` |
| Case/diacritic variants group; display picks the commonest | repository | `test_insights.py` |
| Suppression omits by default, reports, and can be reversed | repository | `test_insights.py` |
| A ranking never crosses domains | repository | `test_insights.py` |
| No `rows`/`long_text` field is groupable; every domain declares at least one | conformance | `test_domain_conformance.py` |
| `key`/`value` filter returns exactly the ranked members | application | `test_library_queries.py` |
| Endpoint validates `key` against the domain's declaration | api | `test_insights_api.py` (new) |
| Zero-score domain: `count` ranks, `score` says so | api | `test_insights_api.py` |
| The page renders, switches key and metric, and links through | component | `InsightsPage.test.tsx` (new) |
| The ranking at 5,000 entries stays inside budget | benchmark | `scripts/benchmark_library.py` |

## Verification

- `python scripts/validate_project.py`, `make check`, `make test`, `make smoke-container`
- `npx playwright test` — **owed**: a new screen and a new request path. Sprint 061's
  blocker (`frontend/node_modules/.vite/deps` owned by `root`) is a prerequisite; fix the
  ownership or record the gate as blocked, do not quietly skip it.
- **Walkthrough (DEC-025):** against a library with real imported data — Sprint 064's
  Spotify albums and the Calibre books — rank each domain by each of its keys, follow a row
  into the library, and **report what the rankings actually looked like**, including whether
  score density made the score metric worth having. That last observation is the sprint's
  most valuable output and belongs in the Outcome whatever it says.
- **Release:** cut **v1.6.0**, the insights release, with release notes covering it and
  Sprint 064's importer. Publishing the tag is an owner action
  (`docs/operations/publishing-images.md`).

## Explicit non-scope

- **Cross-domain rankings.** Explicitly excluded by the owner and by design: they need the
  creator entity this feature exists to avoid.
- **Author, artist or director pages.** A ranking row links to a filtered library view, not
  to a new entity screen. The moment a key gets a page it is a subdomain.
- **Ranking by anything other than count and mean score** — no time series, no "your year in
  review", no comparison against other users' data (there are no other users).
- **Grouping by entry fields** — status, shelf, format, or the year you *finished*
  something. Defensible and interesting, and a separate sprint; this one ranks by what the
  *item* is, not by what you did with it.
- **Editing a key's display name globally.** `creator_sort_override` is per item and stays
  that way; a global rename is an alias table and a different feature.

## Commit checkpoints

1. `[ADD] Declare which fields are worth grouping by`
2. `[ADD] Rank a domain's entries by a declared key`
3. `[ADD] Filter the library by a metadata key and value`
4. `[ADD] The insights screen`
5. `[DOCS] Release notes for v1.6.0`
6. `[DOCS] Close sprint 065 and hand off`

## Risks and decisions to surface

- **Score density is still unmeasured when this sprint starts.** Deliverable 4 is the
  mitigation and AC10 is its proof, but if the walkthrough finds almost nothing is rated,
  the honest outcome is to ship the count metric and say the score metric awaits a rated
  library. That is a finding, not a failure.
- **`json_each` over metadata cannot use an index.** For a personal library this is
  expected to be fine and AC9 is written to prove it rather than assume it — Sprint 017
  measured a normalization UDF at 8× an indexed column and that lesson stands. If the budget
  is missed, the fallback is a maintained key table populated by the same mapper event that
  already maintains the normalized columns; that is a migration and would need saying.
- **A ranking over a small library is a short list.** 157 albums produced 14 artists with
  three or more. The threshold control exists so the owner can see that for themselves
  rather than the product picking a number that makes the screen look full.
- **`groupable` is a judgement per field and will be argued with.** It is a declaration, so
  changing one's mind is a one-line diff and a test, which is the point of declaring it
  rather than deriving it.

## Outcome

_Not started._
