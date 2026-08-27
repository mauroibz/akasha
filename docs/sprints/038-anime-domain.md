# Sprint 038 — Anime: the third domain

**Status:** ready
**Depends on:** 037
**Roadmap revision:** 20

## Objective

A registered `anime` domain with two provider adapters, added and used through the existing screens,
with no migration and no screen written for it — and a recorded answer to whether
`docs/guides/adding-a-domain.md` is accurate.

## Required context

- `docs/guides/adding-a-domain.md` — the whole guide. **This sprint is also its test.**
- `docs/specs/technical-spec.md` §6.6 (the binding contract) and §6.2 (the provider boundary).
- `docs/decisions.md`: **DEC-088** (the providers, measured), **DEC-089** (why four sprints),
  DEC-052 (the six seams), DEC-051 (curated sort names), DEC-067 rows 3, 4 and 7,
  DEC-068 (the IGDB paper walk — the closest precedent for what this sprint does).
- Code to read before writing anything: `backend/src/book_tracker/domains/album/` end to end
  (about 120 lines, the shortest complete domain), `domain/spec.py`, `domain/registry.py`,
  `domain/providers.py`, `infrastructure/providers.py`, `infrastructure/covers.py`,
  `main.py` lifespan, `frontend/src/api/library.ts`.
- `backend/tests/test_domain_conformance.py` — the suite this domain passes by existing.

## Current implementation baseline

Observed on 2026-08-27 at `bcb11ca`:

- `DOMAINS` holds `book` and `album`. `IMPORTERS_BY_DOMAIN` maps `book` to Goodreads and Calibre,
  `album` to `()`.
- `EntryStatus` publishes eight values, `EntryFormat` five, `ItemTypeName` two. Their client mirrors
  are `entryStatuses` and `entryFormats` in `frontend/src/api/library.ts`.
- `ALLOWED_COVER_HOSTS` holds five hosts plus the `.archive.org` suffix rule.
- Migration head is `0014_status_is_the_domains`; `entries.status` has no CHECK, so a new
  vocabulary needs no migration.
- `main.py` lifespan constructs `OpenLibraryProvider`, `GoogleBooksProvider` and
  `MusicBrainzProvider` into `app.state.provider_catalog`.
- `DetailPage.tsx:368` renders the `reread_count` fact with the hardcoded label `Rereads`.

## Deliverables

### 1. The domain package — `backend/src/book_tracker/domains/anime/__init__.py`

```python
DOMAIN = Domain(
    item_type="anime",
    label="Anime",
    identity=ANIME_IDENTITY,
    fields=ANIME_FIELDS,
    statuses=ANIME_STATUSES,
    default_status="completed",
    entry_fields=frozenset({"date_started", "date_finished", "reread_count"}),
    formats=ANIME_FORMATS,
    entry_panel_label="Your watch data",
    enriches=False,            # until Sprint 039; see Explicit non-scope
    recognize=lambda value: recognize_anime_url(value),
    chooses_covers=False,
)
```

- **Fields.** `creators` (many, "Studios"), `english_title`, `japanese_title`, `kind` ("Type" —
  TV/Movie/ONA/OVA/Special), `episodes` (number, 1–10000), `episode_minutes` (number),
  `season`, `source` ("Adapted from"), `genres` (many), `airing_status` ("Airing"), `synopsis`
  (long_text).
  Two naming constraints, both deliberate: `kind` rather than `format`, so the release shape is not
  confusable with the entry-level format axis; and `airing_status` rather than `status`, so a
  metadata field never reads as an entry status. Neither shadows a reserved item column.
- **Statuses.** `unsorted` (`u`, not choosable), `watching` (`w`), `completed` (`c`),
  `on_hold` (`h`), `dropped` (`d`), `plan_to_watch` (`p`). This is MyAnimeList's own vocabulary
  because it is the vocabulary the owner's data is already in. `dropped` is a coincidence of
  spelling with the book vocabulary, not shared state.
- **`default_status="completed"`.** 74 of the owner's 81 rows are completed, and adding an anime by
  hand is overwhelmingly logging one you have watched. A one-line change if that reads wrong in use.
- **Formats.** `streaming`, `digital`, `bluray`. The conformance suite requires a non-empty
  vocabulary; these are how a copy is held, not how it was watched.
- **Identity.** `identity_key` returns `f"mal:{id}"` when the candidate carries a MyAnimeList
  mapping and `None` when it does not (DEC-088). `source_preference = ("anilist", "kitsu")`.
- **Recognizer.** `anilist.co/anime/<id>` → fetch on `anilist`; `myanimelist.net/anime/<id>` →
  fetch on `anilist` with the value `mal:<id>`; `kitsu.io/anime/<slug-or-id>` → fetch on `kitsu`.
  Parsed through `split_url`, never `urlsplit`.

### 2. The adapters — `backend/src/book_tracker/domains/anime/providers.py`

- `AniListProvider` (`name = "anilist"`). GraphQL POST to `https://graphql.anilist.co` through
  `bounded_json` with `INTERACTIVE_ATTEMPTS`. **A User-Agent is mandatory** — without one Cloudflare
  answers `error code: 1010` / HTTP 403 (DEC-088). `search` uses `Page(media(search:, type:ANIME,
  sort:SEARCH_MATCH))`; `fetch` takes either an AniList id or a `mal:`-prefixed id and queries
  `Media(id:)` or `Media(idMal:)` accordingly. Cover from `coverImage.extraLarge`. Studio from
  `studios(isMain:true)`, supplied unchanged as `creator_sort`.
- `KitsuProvider` (`name = "kitsu"`). `https://kitsu.io/api/edge`. `search` uses
  `filter[text]=` with `include=mappings`, which returns the `myanimelist/anime` external id on every
  row in the same request and is what makes the identity strategy work for this source. `fetch` uses
  `include=animeProductions.producer,categories,mappings` and selects the producer whose
  `animeProductions.role == "studio"`. Cover from `posterImage.large` — **not** `original`, which
  measured 980x1420 at 1.6 MiB.
- Neither adapter leaks a raw provider response above infrastructure. Pacing: AniList publishes
  `X-RateLimit-Limit: 30`, so the adapter respects it the way `MusicBrainzProvider` respects its
  documented ceiling.

### 3. Registration

- `domain/registry.py`: one import, `DOMAINS` gains `ANIME`, `IMPORTERS_BY_DOMAIN` gains
  `ANIME.item_type: ()`.
- Published unions: `EntryStatus` gains `WATCHING`, `COMPLETED`, `ON_HOLD`, `PLAN_TO_WATCH`
  (`dropped` already exists); `EntryFormat` gains `STREAMING`, `BLURAY` (`digital` already exists);
  `ItemTypeName` gains `ANIME`.
- `frontend/src/api/library.ts`: the same values in `entryStatuses` and `entryFormats`.
- `make openapi` so the checked-in schema carries them.
- `main.py` lifespan: construct both adapters into the provider catalog.
- `infrastructure/covers.py`: `s4.anilist.co` and `media.kitsu.app` in `ALLOWED_COVER_HOSTS`.

### 4. Recorded responses — `backend/tests/fixtures/providers/`

Real captured payloads for both adapters: an AniList search, an AniList fetch by id, an AniList fetch
by `idMal`, an AniList response with `idMal: null`, a Kitsu search with mappings, and a Kitsu fetch
with includes. Boundary behaviour is proven against these, never against a mock of the method under
test (DEC-025).

### 5. The one screen fix this domain exposes

`DetailPage.tsx` labels `reread_count` as `Rereads` for every domain. On an anime that is wrong copy,
and it is the entry panel's last hardcoded book word after `entry_panel_label` fixed the heading.
Give the three passage fields per-domain labels the way statuses and formats already have them, and
render the declaration. Small, and it belongs here because this is the sprint that makes it visible.

## Acceptance criteria

1. `anime` is registered and `GET /api/item-types` publishes its label, fields, statuses,
   `default_status`, `entry_fields`, formats, `entry_panel_label` and `chooses_covers`.
2. The whole conformance suite passes over three domains with **no test added to it**. If a check has
   to be edited to admit anime, that edit is a finding and is recorded, not quietly made.
3. Searching a title from the add box returns anime candidates from both providers, and two
   candidates naming the same MyAnimeList id merge into one row with `anilist` primary.
4. A candidate with no MAL mapping merges with nothing and still adds correctly.
5. Pasting `https://myanimelist.net/anime/22199`, `https://anilist.co/anime/20613` and a Kitsu anime
   URL each resolve to the right record. A malformed string (`http://[`) still lets every other
   domain take its turn.
6. Adding an anime stores its cover through the shared pipeline from an allowlisted host, at the
   pipeline's own bounds, with no relaxation of scheme, redirect or size rules.
7. The library tab strip offers Anime; its status chips, triage hotkeys, format picker, metadata
   dialog and detail layout all render from the registry with no branch on item type.
8. A status write outside anime's vocabulary is refused with 422 naming the domain; a
   `reread_count` write succeeds because anime declares it.
9. The entry panel names rewatches rather than rereads on an anime, and still names rereads on a book.
10. **No migration is added.** If one turns out to be necessary, stop and record why — that is the
    guide's central promise failing and is more valuable than the sprint.

## Required tests (TDD)

- `tests/test_anime.py` — the domain declaration: vocabulary, field spec, identity over recorded
  candidates including the `idMal: null` case, and the recognizer over the conformance probe set.
- `tests/test_anime_providers.py` — both adapters against recorded responses: search parsing, fetch
  parsing, the `mal:` fetch path, studio extraction from Kitsu's `role == "studio"`, cover URL
  selection, and the AniList missing-User-Agent failure surfacing as a provider error rather than an
  unhandled exception.
- `tests/test_domain_conformance.py` — runs over anime by parametrization. **Nothing is added.**
- `tests/test_item_types.py` — asserts against the registry, not a literal set. Confirm it still does.
- `frontend/src/api/library.test.ts` — the published unions pin to `openapi.json`.
- A frontend test that the entry panel's passage-field labels come from the domain.

## Verification

```bash
cd backend && uv run pytest tests/test_domain_conformance.py -q
cd backend && uv run pytest tests/test_anime.py tests/test_anime_providers.py -q
make check && make test
cd frontend && npm run test:e2e
```

Then the walkthrough gate, against the running application with real data: search an anime by title,
add it from each provider, paste all three URL forms, set every status from the detail page and from
triage, put one on a shelf, and confirm the cover renders. Record what was exercised, what was
observed, and anything that felt wrong including out-of-scope observations.

**Also record, explicitly, whether `docs/guides/adding-a-domain.md` was sufficient on its own** — what
was missing, what was wrong, and what had to be learned from reading another domain. That report is a
deliverable of this sprint, not a courtesy.

## Explicit non-scope

- **Enrichment.** `enriches=False` here, and Sprint 039 flips it. An added anime arrives complete
  from one fetch; only an *imported* one is thin, and there is no importer yet.
- **Progress.** No `entries.progress`, no watched-episode count. Sprint 040.
- **The importer.** Sprint 041. No parsing of the export in this sprint.
- **Manga.** A separate domain if it is ever wanted, not a mode of this one.
- **Jikan and MyAnimeList's official API.** Rejected and unmeasured respectively (DEC-088).
- **The `/books/:id` detail route.** Still cosmetically wrong for every domain (DEC-067 row 8).

## Commit checkpoints

1. `feat(sprint-038): declare the anime domain`
2. `feat(sprint-038): add the AniList adapter`
3. `feat(sprint-038): add the Kitsu adapter`
4. `feat(sprint-038): register anime and publish its vocabulary`
5. `fix(sprint-038): name the entry panel's passage fields per domain`
6. `docs(sprint-038): close sprint and hand off`

## Risks and decisions to surface

- **AniList's terms name this application's category.** Settled by the owner on 2026-08-27 and
  recorded in DEC-088. If that reading is revisited, Kitsu carries the domain alone and the change is
  configuration, not a sprint. Do not re-litigate it mid-sprint.
- **Two providers, one identity key** is new since books. If merging misbehaves against real
  candidates, the fallback is `identity_key` returning `None` — albums' complete answer — and that is
  a decision to record, not a heuristic to tune.
- **AniList tail latency.** One request measured 40.04s against a sub-second median. If that recurs,
  the interactive retry policy and its timeout are the thing to check, not the query.
- **`default_status="completed"`** is a judgement from the owner's data shape. Confirm it in the
  walkthrough.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, the guide-accuracy report, and impact on Sprints 039–041._
