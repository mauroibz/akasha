# Sprint 050 — TVmaze: a real synopsis, an airing status, and the shows Wikidata's search misses

**Status:** completed
**Depends on:** 049
**Roadmap revision:** 27

## Objective

The series domain gains its second keyless provider. A series gets a synopsis somebody would
actually read, an airing status that says whether it is still running, and a search that finds shows
Wikidata files where its title index does not reach.

## Required context

- `docs/series-domain-viability.md`, the TVmaze section and the rejected-sources table.
- Sprint 049's Outcome — the declaration, the identity strategy and the provider order it left ready.
- `docs/decisions.md`: DEC-088 (two providers that genuinely merge, and what a shared identity is
  worth), DEC-104, and the new DEC-105 for the attribution decision.
- `backend/src/book_tracker/domains/anime/providers.py` — the only existing two-provider domain, and
  the model for how a second adapter merges rather than overwrites.
- `backend/src/book_tracker/domain/merge.py` — `fill_empty`. A fallback fills; it never overwrites.

## Current implementation baseline

To be observed at activation. Expected: `domains/series/` holds one adapter, its
`IdentityStrategy` already declares `("wikidata", "tvmaze")`, and `synopsis` holds Wikidata's
one-line description.

## Deliverables

### 1. `TvmazeSeriesProvider`

Three official endpoints and nothing else:

| Operation | Endpoint |
|---|---|
| search | `GET api.tvmaze.com/search/shows?q=` |
| resolve by IMDb id | `GET api.tvmaze.com/lookup/shows?imdb=tt…` |
| fetch | `GET api.tvmaze.com/shows/<id>` |

No key, no account, no token. Rate limit is TVmaze's published *"at least 20 calls every 10 seconds
per IP address"* with an HTTP 429 on breach — wire it into the existing quota and retry machinery
rather than inventing a second one. A descriptive User-Agent is sent, as it is to every provider.

Mapping, all of it measured on live responses:

| Akasha | TVmaze |
|---|---|
| identity | `externals.imdb` → `imdb:tt…` |
| `synopsis` | `summary`, **parsed from HTML to plain text** |
| `airing_status` | `status` (`Running` / `Ended`) |
| `genres` | `genres` |
| `network` | `network.name`, falling back to `webChannel.name` |
| `episode_minutes` | `averageRuntime`, falling back to `runtime` |
| `year` | `premiered` |
| `episodes` | **not taken** — see below |

`summary` arrives as HTML. Parse it to text the way the Letterboxd reader parses a review, and never
render source markup.

**`episodes` is deliberately not taken from TVmaze.** Its count and Wikidata's disagree — 44 against
38 for one measured series, 76 against 77 for another — and `fill_empty` would let whichever
provider answered second win a field that drives a progress control. Wikidata's `P1113` is the
declared source for the total in this sprint. If the owner later wants the fresher number, that is a
decision with a reason, not a merge accident.

**Covers do not come from TVmaze.** Its `medium_portrait` measured 210×295, which the pipeline would
upscale, and its `original_untouched` measured 2000×3000 at 1.3 MB. Stremio's 500×750 is already the
right variant and is already installed. `static.tvmaze.com` must **not** join `ALLOWED_COVER_HOSTS`.

### 2. Merge order — which is mostly already built

**Do not write a fallback path. There is one, it is shared, and anime already uses it.**

`search_providers` fans out to **every** provider registered for the domain **in parallel** and hands
the results to `merge_and_rank(..., identity=domain.identity)`. `_merge_group` then groups candidates
by `identity_key`, picks a primary by `IdentityStrategy.source_preference`, and fills every empty
field on the primary from the rest — identifiers, metadata, cover and original year alike. That is
exactly the behaviour this sprint wants, and Sprint 049 already declared
`IdentityStrategy(imdb_identity, ("wikidata", "tvmaze"))` so the preference is in place.

So the merge deliverable is: **register the adapter and let the shared layer do its job.** A Wikidata
candidate and a TVmaze candidate for one series carry the same `imdb:tt…`, so they group; Wikidata
wins the primary slot by source preference; TVmaze's `synopsis`, `airing_status` and `network` fill
fields Wikidata left empty; nothing Wikidata supplied is overwritten. There is no "consult on miss"
branch to write, and writing one would be a second mechanism competing with the shared one.

Two consequences follow, and both are the reason `episodes` is excluded above:

- A search costs **both** providers on every query, not one. TVmaze's published budget is at least 20
  calls per 10 seconds, and a series search is one call to it. Wire it into the existing quota.
- `_merge_group` fills any field the primary left empty. If Wikidata's entity happens to lack
  `P1113`, TVmaze's differing episode count would land in it through the shared path. **The only
  reliable way to keep it out is not to emit it**, which is what deliverable 1 says.

The enrichment side is the ordered one: `EnrichmentSpec.provider_order` becomes
`("wikidata", "tvmaze")`, and `_fetch` walks it in order until a record is returned.

The provider object needs an `item_type` attribute equal to `"series"`. `resolve_input` selects
providers with `getattr(provider, "item_type", DEFAULT_DOMAIN.item_type)`, so an adapter without one
is silently treated as a book provider.

### 3. The credit line

TVmaze's licence is CC BY-SA and asks that TVmaze be *"properly credited as source"*. The owner
directed that the credit be given. Add a small, permanent attribution line naming the sources of
series data — Wikidata and TVmaze — where a reader can find it without hunting: the About/footer
surface, plus the series Detail page's metadata panel if it already has somewhere a source line fits.

This is one line of copy and one line of markup. It is a deliverable rather than a footnote because
the alternative was chosen against explicitly, and DEC-105 records why.

## Acceptance criteria

1. A series search reaches **both** providers and returns one merged list, against recorded
   responses. A query Wikidata answers with nothing still returns TVmaze's candidates.
2. `Los Simuladores` and `Okupas` — Spanish-language shows Wikidata's title search does not surface —
   resolve through TVmaze with the correct premiere year.
3. A candidate from each provider for the same series merges into **one** record on `imdb:tt…`,
   through `merge_and_rank` and with no domain-specific merge code.
4. TVmaze fills an empty `synopsis`, `airing_status` and `network`, and **overwrites nothing** that
   Wikidata supplied. A test asserts a Wikidata-supplied field survives a TVmaze fetch.
5. `episodes` is never sourced from TVmaze, asserted with a response whose episode count differs from
   the stored one.
6. `summary` HTML reaches the field as plain text; no markup is stored or rendered.
7. `static.tvmaze.com` is **not** in `ALLOWED_COVER_HOSTS`, and a series cover still comes from
   Stremio.
8. An HTTP 429 is retried under the existing policy and never fails the search it is part of.
9. The credit naming Wikidata and TVmaze is visible in the running application, verified in a browser.
10. No migration, no new route, no new published vocabulary.

## Required tests (TDD)

- Adapter against recorded responses: search, IMDb lookup, fetch, an HTML summary, a show with a
  `webChannel` and no `network`, a show with `runtime: null`, and a 404 from `/lookup`.
- Cross-provider merge on `imdb:` through the shared `merge_and_rank`, and the fill-empty
  guarantee in both directions. A test asserting no domain-specific merge code exists.
- Both providers are called for one search, and one failing does not fail the search.
- `episodes` provenance.
- 429 handling through the existing retry path.
- A frontend test for the credit line.
- The series conformance and provider suites from Sprint 049 pass unchanged.

## Verification

```bash
cd backend && uv run pytest tests/test_tvmaze_provider.py tests/test_series_domain.py \
  tests/test_wikidata_series_provider.py tests/test_domain_conformance.py tests/test_covers.py -q
cd frontend && npm run test
make check
make test
```

Then in a browser: search a series Wikidata alone could not find, open it, read the synopsis, and
find the credit line.

## Explicit non-scope

- Episodes, seasons, cast lists or air dates as stored entities. TVmaze publishes all of them and
  none of them are in this domain.
- TVmaze as a cover source.
- Backfilling `episodes` from TVmaze for series already in the library.
- Any importer.

## Commit checkpoints

1. `[ADD] Read series from TVmaze`
2. `[ADD] Merge Wikidata and TVmaze on the IMDb id`
3. `[ADD] Credit the series data sources`
4. `[DOCS] Close sprint 050 and hand off`

## Risks and decisions to surface

- **CC BY-SA is a share-alike licence.** The credit line satisfies the attribution half. The
  share-alike half concerns redistribution, and Akasha is LAN-only with no auth and no publishing
  surface (product spec §9), so nothing is redistributed today. If sharing or export-to-public is
  ever built, this needs revisiting — DEC-105 says so explicitly so that it is found.
- TVmaze is English-only. Spanish labels and descriptions remain Wikidata's job, and a Spanish
  synopsis is not available from either. The viability document costs the Wikipedia-extract option if
  that becomes a requirement.

## Outcome

**Delivered.** The series domain has its second keyless provider. A series search now reaches both
Wikidata and TVmaze and returns one merged list; the shows Wikidata's title index does not surface
resolve through TVmaze with the right year; and a permanent credit line naming both sources sits in
the application footer.

- `backend/src/book_tracker/domains/series/tvmaze.py` — `TvmazeSeriesProvider`, the three official
  endpoints and nothing else. `summary` HTML is parsed to plain text; `network` falls back to
  `webChannel`; `episode_minutes` reads `averageRuntime` then `runtime`; `episodes` and covers are
  never emitted (the two deliberate refusals, AC5 and AC7). The `/lookup/shows?imdb=` hit is a 301
  the shared client follows; a miss is a 404 with a `null` body, read as `record_not_found`.
- The shared `bounded_json` boundary was widened from `Mapping[str, Any]` to `Any` for TVmaze's
  list-shaped `/search/shows`, and a typed `bounded_json_object` companion was added so the seven
  existing object callers keep their malformed-shape guard. No caller was weakened; the list caller
  judges its own shape. Recorded as DEC-110.
- The merge is the shared `merge_and_rank` + `fill_empty`, nothing local. The series identity
  strategy already declared `("wikidata", "tvmaze")`, so this sprint registered the adapter and let
  the shared layer group both candidates on `imdb:tt…`. `EnrichmentSpec.provider_order` is now
  `("wikidata", "tvmaze")`. The recognizer routes `tvmaze.com` URLs to the adapter.
- `frontend/src/.../DataCredit.tsx` — the credit line, mounted in the AppShell footer (AC9). A
  Detail-panel variant that branched on `item.type === "series"` was reverted: that is the forbidden
  seam violation, and the footer is the domain-neutral surface.

**Acceptance criteria, verified.** 1 — both providers answer one search into one merged list, against
recorded responses (`test_a_candidate_from_each_provider_merges_into_one_record`, and the walkthrough's
single Breaking Bad row). 2 — `Los Simuladores` (2002) and `Okupas` (2000) resolve through TVmaze
(`test_the_shows_wikidata_s_title_search_misses`, and the walkthrough). 3 — one record on `imdb:tt…`
through `merge_and_rank`, no domain-specific merge code. 4 — TVmaze fills empty `synopsis`,
`airing_status` and `network` and overwrites nothing Wikidata supplied
(`test_tvmaze_fills_what_wikidata_left_empty_and_overwrites_nothing`); the walkthrough asserts the
designed rule. 5 — `episodes` is never sourced from TVmaze (`test_it_emits_no_cover_and_no_episode_count`;
the merged record keeps Wikidata's P1113 = 62). 6 — `summary` HTML reaches the field as plain text, no
markup stored (`test_the_synopsis_arrives_as_plain_text`). 7 — `static.tvmaze.com` is not in
`ALLOWED_COVER_HOSTS` and the cover still comes from Stremio (`test_tvmaze_s_host_is_not_allowlisted`;
the walkthrough fetches the real poster). 8 — a 429 is retried under the shared `bounded_json` policy
and never fails the search (`test_a_429_is_retried_under_the_existing_policy`,
`test_a_search_is_not_failed_by_one_provider_s_429`). 9 — the credit naming both sources is visible in
the running application, verified in a browser. 10 — no migration, no new route, no new published
vocabulary (`make openapi` is clean).

**Verification.** Focused backend suites — 229 passed. `make check` — lint, typecheck, format,
OpenAPI-type parity, project validation all pass. `make test` — 989 backend + 190 frontend, zero
warnings from this sprint (the one warning is a pre-existing Letterboxd zipfile duplicate-name in
`test_letterboxd_import.py`). `make openapi` — no diff. The walkthrough
(`frontend/e2e/scratchpad/series-050-walkthrough.spec.ts`, local-only) ran 5/5 green against recorded
Wikidata and TVmaze with a live Stremio cover fetch: one merged row, Los Simuladores by year, the
merged record's fill-empty rule, the credit line, and a real >10 KB poster.

**Deviations and notes.**

- The walkthrough ran against **recorded** provider responses, not live (DEC-108's substitution rule):
  what is proven is the rendered flow, the merge, the credit and the poster pipeline; what is not
  proven is that the adapters' request shape is still what live Wikidata and TVmaze answer today.
- One intermittent `422 POST /api/entries` appeared during the add-tests only when two adds ran
  back-to-back against a reused walkthrough data dir. Static analysis (`application/add.py:197-202`)
  identifies it as the designed `near_match_confirmation_required` guard firing on a leftover row from
  a prior run; it does not reproduce on a fresh data dir and all five tests pass clean. Recorded as a
  walkthrough-harness state artifact, not a product defect.
- The walkthrough spec initially asserted TVmaze's synopsis would appear on the merged record. That
  misread the contract: `fill_empty` only fills empty fields, and Breaking Bad's Wikidata synopsis is
  non-empty, so Wikidata's sentence correctly survives. The assertion was corrected to the designed
  rule (fill when empty, overwrite nothing); the merge was already correct.

**Commits.** `0e96e9a` Read series from TVmaze · `e094a4b` Merge Wikidata and TVmaze on the IMDb id ·
`ff4ec35` Credit the series data sources · `d279341` fixture provenance · `e1f8719` format.
