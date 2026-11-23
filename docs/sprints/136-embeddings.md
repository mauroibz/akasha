# Sprint 136 — Embeddings

**Sprint:** 136
**Status:** ready
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

_Not started._
