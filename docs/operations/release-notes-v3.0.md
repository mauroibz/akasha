# Akasha v3.0.0 — release notes

A home screen, and suggestions. Sprints 130–136 (DEC-183 to DEC-191).

## What you will notice

- **Home.** Akasha now opens on a home screen at `/`; the library moved to `/library` (old
  links with library filters in them still land there). Home is a grid of small modules, all
  read from what is already stored, with no network calls:
  - **On now:** what you are reading or watching, with *+chapter*, *Finished* and *Set aside*.
  - **Up next:** five things from your pile, ranked, each with the reason it is there ("Next in
    Mistborn; you gave book 1 a 9", "You rate Stephen King 7.3 across 10", "Waiting since
    Sep 2026"). *Start* moves it to under way.
  - **The year:** this year's finishes as covers by month, and an empty slot for each thing your
    goal still needs.
  - **Lately:** finishes, score changes and additions, newest first.
  - **Your libraries:** one tile per library with its counts, scores and covers.
  - **Tidy up:** duplicate pairs, entries without a cover, finished entries without a score.
  - **One question**, **Shelves**, **Lent out**, and **More like this** (below).

  *Edit home* reorders, resizes (S/M/L) and hides modules; the layout is saved per person.
- **The ranked pile.** *Up next* on Home and a goal's picks in the Diary use one ranking,
  computed from your own library: the next in a series, creators and subjects you score above
  your own average, how long something has waited, a library short of its goal; something you
  set aside lately drops for a while.
- **More like this.** A button on a film's or a series' page (and its *On now* card) opens a
  side sheet of suggestions. With a TMDB token (`TMDB_READ_TOKEN`, free) TMDB picks twelve in
  one request and the first three are looked up in your usual providers; the rest are looked up
  when you press *Look up*. Each suggestion has *Want* (adds it to your list), *Not for me*
  (keeps it out of later rounds) and *Seen it*. Home's *More like this* shows the newest found
  picks. TMDB's suggestions carry its attribution and are deleted after six months.
- **Two more sources, off until you give them a key.**
  - **Model:** a hosted language model (Claude by default; Gemini or any OpenAI-compatible
    endpoint) suggests things for every library, and is the only source for books, anime and
    albums. A pick is shown only once your providers found it, so invented titles never appear.
    It is sent titles, creators, years and your scores in that library, nothing else.
  - **From your library:** with an embeddings endpoint (Gemini by default, or any
    OpenAI-compatible one; the Claude API has none), every item gets a vector of its stored text.
    The sheet then lists the things already on your list closest to the one you opened, *Up
    next* can say "Close to what you scored 9: …", and other sources' picks come in order of
    likeness. It is sent item text only, nothing about you, your scores or your notes.

  Without a key nothing changes; the sheet and **Settings → Suggestions** say how to turn each
  on and what is sent.

## New settings

All optional, all passed through by `compose.yaml` and described in `.env.example`.

| Setting | What it does |
|---|---|
| `TMDB_READ_TOKEN` | Already used for posters; now also turns on TMDB suggestions for films and series. |
| `AKASHA_RECOMMEND_DAILY_LIMITS` | Rounds a day per source, as JSON, e.g. `{"tmdb": 200, "model": 50}`. A round is one request. TMDB is unlimited unless set; the model defaults to 50. |
| `AKASHA_RECS_MODEL_PROVIDER` | `anthropic` (default), `gemini` or `openai`. |
| `AKASHA_RECS_MODEL` | Another model than the default (`claude-haiku-5-5`, `gemini-2.5-flash`, `gpt-5-mini`). |
| `AKASHA_RECS_MODEL_KEY` | The model's key; or `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY`. |
| `AKASHA_RECS_MODEL_URL` | Base URL of an OpenAI-compatible endpoint (default `https://api.openai.com/v1`). |
| `AKASHA_RECS_EMBEDDINGS_PROVIDER` | `gemini` (default) or `openai`. |
| `AKASHA_RECS_EMBEDDINGS_MODEL` | Another model than the default (`gemini-embedding-001`, `text-embedding-3-small`). |
| `AKASHA_RECS_EMBEDDINGS_KEY` | The embeddings key; or `GEMINI_API_KEY` / `OPENAI_API_KEY`. |
| `AKASHA_RECS_EMBEDDINGS_URL` | Base URL of an OpenAI-compatible `/embeddings` endpoint (Voyage: `https://api.voyageai.com/v1`). |

**The embeddings budget.** Embeddings are capped at 1,000 requests a day (32 items each). To
change that, set `AKASHA_PROVIDER_DAILY_LIMITS` with an `"embeddings"` entry, and keep the
Google Books entry in the same value: the setting replaces the whole default, so
`{"embeddings": 500}` alone would leave Google Books unmetered. Write
`{"googlebooks": 900, "embeddings": 500}`.

The first start with an embeddings key embeds the whole library over the following minutes; a
new item is embedded within a minute of being added.

## Upgrade

**Tagged `v3.0.0`.** Three migrations, all new tables, nothing existing is changed:

- `0036` — Home's layout, one per person.
- `0037` — suggestions and the rounds that chose them.
- `0038` — one stored vector per item for embeddings.

The application backs the database up before migrating. A copy of the live library (2.9.0,
revision 0035) was upgraded with this image under the read-only compose with authentication on:
the backup was written, the three migrations ran, integrity and foreign-key checks were clean,
and the counts were unchanged; a restart ran no migration.

```bash
git checkout v3.0.0            # if you run from a clone, for the new compose.yaml
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=3.0.0`. To use the new sources, add the
keys above to `.env` and recreate the container (`docker compose up -d`).

Bookmarks to `/` that meant the library now open Home; the library is one click away, or
bookmark `/library`.

## Still to check live (yours)

No model or embeddings key was available while this was built, so those two sources have never
answered a real request. Their test fixtures are written in each API's documented shape and
marked unrecorded. With keys, from `backend/`:

```bash
ANTHROPIC_API_KEY=… uv run python ../scripts/record_model_fixtures.py
GEMINI_API_KEY=… uv run python ../scripts/record_embedding_fixtures.py
```

then rerun `tests/test_model_recommendations.py`, `tests/test_embeddings.py` and
`tests/test_library_source.py` (a real reply may name or order things differently; update the
expectations in their own commit), and try one *Model* round and one *From your library* in the
app. The default Gemini and OpenAI model names were chosen without a live call; confirm them.
TMDB was exercised live, including against the copy of your library.
