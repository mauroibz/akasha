# Sprint 136 — Embeddings

**Sprint:** 136
**Status:** completed
**Roadmap revision:** 54
**Depends on:** 135
**Owner:** Mauro

## Objective

With an embedding endpoint configured, items carry a vector of their stored text; the pile
ranking and the candidates of other sources are re-ranked by similarity to what the person rates
highly, and *More like this* has a *From your library* segment that needs no network beyond the
embedding endpoint.

## Required context

- DEC-183 point 7; Sprints 132–135 Outcomes; `application/ranking.py`,
  `domain/recommendations.py`, the enrichment pipeline (where an item's text becomes known).
- DEC-186: a pile signal is one `(signal, points, text)` on the candidate in `ranking.py`, its
  weight a constant at the top; a new signal also joins `PileReason.signal` in `api/pile.py`.

## Deliverables

1. Configuration: `AKASHA_RECS_EMBEDDINGS_PROVIDER` (`gemini` | `openai`, the latter covering
   any OpenAI-compatible endpoint such as Voyage), `AKASHA_RECS_EMBEDDINGS_MODEL`,
   `AKASHA_RECS_EMBEDDINGS_KEY` (falling back to the provider's conventional variable), optional
   `AKASHA_RECS_EMBEDDINGS_URL`. The Claude API has no embeddings endpoint, so `anthropic` is not
   a choice here; with only a Claude key, embeddings are off and everything else works (DEC-187).
2. Migration `0038_item_embeddings`: `item_embeddings(item_id PK → items, model, dims, vector
   BLOB, text_hash, created_at)`. The text is title, creator, year, and the domain's declared
   descriptive fields (subjects, genres, synopsis) in a fixed order.
3. An `embed_items` job that embeds items missing a vector or whose text hash changed, batched,
   under a budget; triggered after enrichment and by a maintenance pass.
4. A `library` recommendation source: cosine similarity in Python over stored vectors (numpy if
   already a dependency, otherwise plain floats; a 10,000-item library must answer under 300 ms).
5. The ranked pile gains a similarity signal ("Close to what you scored 9: …"); other sources'
   candidates, once enriched, are re-ranked by it.
6. Recordings from a real endpoint when a key is present; otherwise fixtures in the documented
   response shape, marked unrecorded, as in Sprint 135. No model runs locally.

Notes from Sprint 133 (DEC-188): migration 0037 is `suggestions`, so 0038 stays this sprint's
number. The `library` source is one more factory in `SOURCE_FACTORIES` and a name in each
domain's `RecommendationSpec.sources`; its candidates are the person's own items, which the
store-time filter drops as already in the library, so it needs a way to keep planned entries
(for example a source-declared flag the store reads) — decide it here. An enriched suggestion
has `item_id`, which is what re-ranking other sources' candidates by similarity reads.

Notes from Sprint 134 (DEC-189): the *From your library* segment is one more entry in a
library's `recommendation.sources` on `/api/item-types` (give the source a `label`); the sheet
lists them. The job runner's `housekeeping` hook (hourly on an idle pass) is where any
periodic embedding upkeep would go. Home's `suggested` module shows only `enriched` rows.

Notes from Sprint 135 (DEC-190):

- A source may declare `resolved_only` (shown only once found, every pick resolved) and `about`
  (what Settings → Suggestions shows); the `library` source is the person's own items, so it
  declares neither. Settings lists every declared source from `/api/item-types`.
- Configuration follows the model's: `config.py` holds `recs_model_*` and the three
  provider keys as `SecretStr` with blank-is-unset validators, and `compose.yaml` and
  `.env.example` must list every new variable (`test_settings.py` checks both). `GEMINI_API_KEY`
  and `OPENAI_API_KEY` already exist as settings; reuse them as the embeddings fallback.
- A hosted endpoint is a plain-HTTP adapter over the shared client (`_post` in
  `model_clients.py` maps failures to `SourceError`); give it its own timeout.
- `scripts/walkthrough.py --replay` now replaces the lifespan's client factory, so a replay
  module sees every request; `scripts/record_model_fixtures.py` is the recorder pattern.
- `taste_profile` reads a work's `original_year` before the item's year.

## Acceptance criteria

1. With recorded vectors, *From your library* returns the nearest planned entries to the seed
   (tested).
2. Without configuration, ranking falls back to Sprint 132's signals unchanged (tested).
3. Changing an item's text re-embeds it once (tested).
4. Migration up/down clean.

## Verification

Per DEC-167; a live pass if a key is present (else recorded as pending) and a walkthrough of the segment and of *Up next*
with the similarity signal. Then, because this closes the line, `make test` and the full
Playwright suite before any release.

## Explicit non-scope

A vector database; cross-user similarity.

## Outcome

Closed 2026-11-23 (DEC-191). **No Gemini or OpenAI key was present in the environment, so no
real embedding was recorded and no live pass was run: the live check is pending, the owner's**
(export `GEMINI_API_KEY`, run `scripts/record_embedding_fixtures.py` from `backend/`, then open
*From your library* in the app). This closes DEC-183's line; `make test` and the full Playwright
suite are the release's, not run here (DEC-167, the coordinator's instruction).

Delivered:

- Configuration: `AKASHA_RECS_EMBEDDINGS_PROVIDER` (`gemini` default, `openai` for any
  OpenAI-compatible endpoint, Voyage included; `anthropic` refused), `_MODEL` (defaults
  `gemini-embedding-001` at 768 dimensions, `text-embedding-3-small`), `_KEY` falling back to
  `GEMINI_API_KEY` / `OPENAI_API_KEY`, `_URL`; in `compose.yaml`, `.env.example`, README, the
  technical spec and the runbook. A Claude key alone leaves embeddings off. All five keys are
  now scrubbed from logs.
- `infrastructure/embedding_clients.py`: two plain-HTTP adapters over the shared client
  (`batchEmbedContents`, `/embeddings`), failures mapped to `SourceError` naming the
  embeddings' variables, never the key.
- Migration `0038_item_embeddings` (`item_id` PK → items, cascade; `model`, `dims`, `vector`
  float32 BLOB at unit length, `text_hash`, `created_at`).
- `application/embeddings.py`: the text (title, creator, first year, the domain's new
  `RankingSpec.text_fields`), hashing, packing, `math.sumprod` cosine (no numpy); the
  `embed_items` job (32 a request, 8 requests a job, follow-ups, `embeddings` budget 1,000 a
  day); triggers after enrichment, after a suggestion's item is cached, a one-minute sweep for
  items with no current vector (new `JobRunner(sweeps=…)`), and the hourly hash pass.
- `application/library_source.py`: the `library` source, "From your library", declared last
  by every domain: the person's waiting entries (planned or `want_status`) nearest the seed.
  `from_library` keeps them through the store; `Candidate.item_id` stores them found; a seed
  not yet embedded is embedded for its round.
- The pile's `similarity` signal ("Close to what you scored 9: Rayuela") in `ranking.py`, read
  only with a configured model, passed by the pile route, Home and a goal's picks;
  `PileReason.signal` gained it.
- A round's found picks are read in order of likeness to the seed (`SuggestionStore(
  embedding_model=…)`).
- The sheet: *From your library* rows say "On your list", open the entry, offer *Not for me*
  only; "N on your list, nearest first". `from_library` on `/api/item-types`; OpenAPI and
  `schema.d.ts` regenerated.
- `scripts/record_embedding_fixtures.py`; fixtures `embeddings_*` (documented shapes,
  `"recorded": false` in `embedding_fixtures.json`, texts listed there).

Acceptance criteria:

1. *From your library* returns the nearest planned entries — `test_library_source.py`
   `test_from_your_library_returns_the_nearest_waiting_entries_to_the_seed` (Gemini and
   OpenAI-compatible fixtures: the order `NEAREST_TO_RAYUELA`, found, no provider asked, absent
   from Home's list), plus only this person's waiting entries, a seed embedded on demand, *Not
   for me* honoured. The 10,000-item budget: `test_a_ten_thousand_item_library_answers_under_300_ms`
   (about 120 ms at 768 dimensions).
2. Without configuration, Sprint 132's ranking unchanged — `test_ranking.py`
   `test_without_embeddings_the_order_is_sprint_132s_exactly` (identical output with vectors
   stored but no model, or another model) and `test_up_next_and_the_pile_route_read_the_configured_model`;
   `test_embeddings.py` and `test_library_source.py` for "nothing embedded, the source says how".
3. Changing an item's text re-embeds it once — `test_changing_an_items_text_re_embeds_it_once`
   (one request with that book's new text, then none), and a new model embeds all again.
4. Migration up/down — `test_0038_upgrades_and_downgrades_on_a_real_shaped_library` on real
   temporary SQLite files (columns, primary key, foreign key, cascade, downgrade, integrity).

Verification (DEC-167): `test_embeddings.py` 33, `test_library_source.py` 8, `test_ranking.py`
20; the touched-module backend set 544 passed; `npx vitest related` 41 files, 348 tests;
Playwright `more-like-this.spec.ts` (one new case) and `home.spec.ts` 25 passed; `make check`
green. Walkthrough: `scripts/walkthrough.py --replay` with a module answering Gemini's
`batchEmbedContents` from the texts' words (no model run; worklog has the details), 13 books
and 4 films seeded from live Open Library, Cinemeta and TMDB.

Deviations (DEC-191): `RankingSpec.text_fields` is where a domain declares its text; a
one-minute sweep and `JobRunner(sweeps=…)` beyond the sprint's two triggers (the walkthrough's
finding); *Want* on a held item records the answer rather than refusing; the library reason is
"Waiting since …"; numpy is not a dependency, so plain floats.

Commits: `eea2c12` embeddings, `2659c7f` the library source, `427c2fb` the similarity signal,
`4356fdf` the browser case, `44d51b4` the one-minute sweep, `8d32488` the reason's wording,
`b35b095` the docs.
