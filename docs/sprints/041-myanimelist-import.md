# Sprint 041 — The MyAnimeList import

**Status:** planned
**Depends on:** 039, 040

**Roadmap revision:** 20

## Objective

The owner's MyAnimeList export lands in Triage complete — status, score, dates, rewatches,
watched-episode count, tags — and enriches into full records, without a line changing in the shared
import pipeline or the import screen.

## Required context

- `docs/guides/adding-a-domain.md`, the optional importer step in full. **This sprint is also the
  test of the connector half of that guide**, the way Sprint 038 tests the domain half.
- `docs/decisions.md`: DEC-076 and **DEC-078** (importers normalize once; the shared pipeline
  validates and commits), **DEC-080** (a connector guides its own users), DEC-082 (why a source with
  no durable identity should not claim `incremental`), DEC-083 (source files and the ledger),
  DEC-085 and DEC-087 (the two-step import and staged triage), DEC-088, DEC-089.
- `docs/specs/technical-spec.md` §6.5 and §6.6.
- Code: `domain/importers.py` in full, `domains/book/goodreads.py` as the worked upload connector,
  `application/imports.py`, `api/imports.py`, `frontend/src/pages/ImportPage.tsx` and `TriagePage.tsx`
  **to read, not to edit**.
- Tests: `tests/test_goodreads_import.py`, `tests/test_generic_imports.py`,
  `tests/test_domain_conformance.py` (parametrized over registered importers).

## Current implementation baseline

Observed on 2026-08-27 at `bcb11ca`:

- `IMPORTERS_BY_DOMAIN` maps `book` to `(GOODREADS_IMPORTER, CALIBRE_IMPORTER)` and `album` to `()`.
- The shared route serves `POST /api/import/<name>/preview` and `/commit` for any registered
  connector, publishes tabs through `GET /api/importers`, and owns durable preview, ambiguity,
  fingerprint replay, one bounded commit, `unsorted` triage, the 24-hour undo window and post-commit
  source files.
- The conformance suite is parametrized over registered importers and refuses a missing protocol
  member, an unknown target domain, empty identity kinds, a malformed guide, a non-https `help_url`
  and an empty or shouted error vocabulary.

### The source, as measured

The owner's export — `animelist_1787838698_-_13950540.xml.gz`, 3,102 bytes gzipped, 81 entries —
was parsed on 2026-08-27. Every claim here is from that file, not from MyAnimeList's documentation:

- Gzipped XML. Root `myanimelist`, one `myinfo` element and one `anime` element per row.
- `myinfo.user_export_type` is `1`. **`2` is a manga export** and must be refused with an actionable
  message rather than silently producing nothing.
- `series_animedb_id` is present and distinct on all 81 rows. It is the MyAnimeList id, so it is
  exactly the `mal` identity Sprint 038's domain and Sprint 039's enrichment are keyed on.
- `my_status` takes `Completed` (74), `Dropped` (6), `Plan to Watch` (1). The full MyAnimeList
  vocabulary also has `Watching` and `On-Hold`; both are mapped even though this file has neither.
- `my_score` is 0 on 3 rows and 4–10 on the rest. **0 means unrated**, not a score of zero.
  MyAnimeList's scale is already 1–10, so scores map straight across and are **not** provisional —
  unlike Goodreads, whose 5-star rating is doubled and marked (DEC product spec 5.1).
- `my_start_date` is `0000-00-00` on all 81 rows; `my_finish_date` is `0000-00-00` on 76 and a real
  ISO date on 5. **`0000-00-00` is absent, not a date.**
- `my_watched_episodes` differs from `series_episodes` on the partial rows — `Black Clover` is 20 of
  170, dropped. This is the field Sprint 040 exists for.
- `my_times_watched`, `my_tags` and `my_comments` are empty throughout this particular file. All
  three are still mapped, because the next export will not be.
- `series_type` is `TV` (60), `Movie` (18), `ONA` (3). `series_episodes` is present on every row.

## Deliverables

### 1. The connector — `backend/src/book_tracker/domains/anime/myanimelist.py`

```python
class MyAnimeListImporter:
    name = "myanimelist"
    label = "MyAnimeList"
    item_type = DOMAIN.item_type
    input = ImportInputSpec(kind="upload", label="MyAnimeList export", field="file", ...)
    identity_kinds = frozenset({"mal"})
    error_codes = frozenset({
        "invalid_xml", "not_an_anime_export", "missing_series_id", "export_too_large",
    })
```

- **`read` accepts gzip and plain XML**, sniffing the magic bytes rather than trusting the filename,
  because MyAnimeList serves the export gzipped and a reader may or may not have unpacked it.
- **A decompression bound.** A 3 KB gzip is not the worst case a LAN with no auth can post. Cap the
  decompressed size explicitly and raise `export_too_large` rather than streaming it into memory.
  Declare `max_bytes` on the input honestly.
- XML parsed defensively: no external entity resolution, no DTD.
- `user_export_type == 2` raises `not_an_anime_export` with an `action` naming the next move —
  DEC-080's point is that `action` is the only part a person can act on.
- Normalization, per row:

  | Source | Lands as |
  |---|---|
  | `series_animedb_id` | `identifiers["mal"]`, and `source_fields` |
  | `series_title` | `ImportItem.title` |
  | `series_type` | `metadata["kind"]` |
  | `series_episodes` | `metadata["episodes"]` |
  | `my_status` | `ImportEntry.suggested_status` via the map below |
  | `my_score` | `score`, with `0` → `None`, no provisional flag |
  | `my_start_date` / `my_finish_date` | `values["date_started"]` / `["date_finished"]`, `0000-00-00` → `None` |
  | `my_times_watched` | `values["reread_count"]` |
  | `my_watched_episodes` | `progress` (Sprint 040) |
  | `my_comments` | `notes` |
  | `my_tags` | `shelves`, comma-split and slugged |

- The status map is stated against `DOMAIN` and asserted over `DOMAIN.status(...)` in the tests, the
  way Goodreads' is, so a renamed status fails a test rather than silently suggesting nothing:
  `Watching → watching`, `Completed → completed`, `On-Hold → on_hold`, `Dropped → dropped`,
  `Plan to Watch → plan_to_watch`.
- `match` normalizes only `mal` identifiers and calls `matcher.match(...)`. It never queries storage.
- `stage` archives the source and strips raw bytes from the snapshot.
- `incremental=False`. The source is one small file with nothing to plan the upload of; DEC-082 says
  declare false rather than guess.
- `browsable=False`, `accepts_files=False`, no `alternate`.

### 2. The guidance it publishes

Ordered steps, no markdown, rendered by the shared screen without knowing who wrote them: where the
export lives on myanimelist.net, that the file arrives gzipped and may be uploaded as-is, that this
is a snapshot rather than a sync, that scores transfer 1:1 unlike Goodreads', that watched-episode
counts come across, and that everything lands in Triage. `empty_state` and an https `help_url`.

### 3. Registration

`IMPORTERS_BY_DOMAIN[ANIME.item_type] = (MYANIMELIST_IMPORTER,)`. One tuple entry. **Nothing else.**

### 4. Enrichment on commit

An imported row is a title, a type, an episode count and a `mal` id. Sprint 039's backfill picks it up
because anime declares its enrichment spec, so covers, studios, year, season, genres and synopsis
arrive afterwards without the connector fetching anything. Measured cost for this export: AniList
resolved all 81 ids in 2 requests and 54 KiB (DEC-088), though the backfill's shape is one job per
item rather than a batch, which is a thing to observe rather than assume.

### 5. Fixtures, and the owner's file

- A trimmed, anonymised fixture at `backend/tests/fixtures/imports/myanimelist_sample.xml.gz`:
  eight rows covering every status in the map, a `0` score, an all-zero date, a real finish date, a
  partial watch count, a row with tags, and a row with a comment. `myinfo` stripped of `user_id` and
  `user_name`.
- A second fixture that is a manga export, for the refusal path.
- **The owner's real export is not committed.** `AGENTS.md` forbids committing uploaded imports, and
  the file at the repository root carries a user id and a username. Sprint 038 gitignores it; this
  sprint uses it for the walkthrough only.

## Acceptance criteria

1. `GET /api/importers` publishes a MyAnimeList tab under Anime with its guide, empty state and help
   link, rendered by the shared screen with no edit to `ImportPage.tsx`.
2. Preview of the owner's real 81-row export produces 81 records, no row errors, and the counts match
   the measurements above: 74/6/1 across the three statuses present, 3 rows with no score, 5 rows
   with a finish date, 0 rows with a start date.
3. Commit lands 81 items and 81 `unsorted` entries; the library's default view hides them until
   triaged; Triage offers anime's own hotkeys.
4. `Black Clover` reads as dropped at 20 of 170 episodes after commit.
5. Re-previewing the same file replays the fingerprint rather than duplicating; undo within 24 hours
   reverses everything the batch did, including enrichment effects.
6. A manga export is refused with `not_an_anime_export`, a user message and an imperative `action`;
   nothing is written.
7. Malformed XML, a truncated gzip and an oversized decompression are each refused under a declared
   code, and no undeclared code ever reaches the client.
8. Enrichment fills the imported items from AniList without overwriting anything the owner edited in
   Triage first.
9. **No change to `application/imports.py`, `api/imports.py`, `ImportPage.tsx` or `TriagePage.tsx`.**
   If one is needed, that is the connector boundary failing and is the sprint's most valuable finding
   — record it rather than patching quietly.

## Required tests (TDD)

- `tests/test_myanimelist_import.py` — the parser against both fixtures: every field mapping, the
  `0000-00-00` rule, the `0` score rule, the status map asserted over `DOMAIN.status(...)`, tags to
  shelves, gzip and plain input, the manga refusal, the decompression bound.
- `tests/test_generic_imports.py` — a route round-trip for this connector through the shared
  preview/commit/undo pipeline, added the way the existing connectors are.
- `tests/test_domain_conformance.py` — runs over this importer by parametrization. **Nothing added.**

## Verification

```bash
cd backend && uv run pytest tests/test_myanimelist_import.py tests/test_generic_imports.py \
  tests/test_domain_conformance.py -q
make check && make test
cd frontend && npm run test:e2e
```

Walkthrough, against the running application and **the owner's real export**: upload it, read the
preview, commit, work down Triage using anime hotkeys, set a few statuses and scores, confirm the
watched-episode counts survived, let enrichment run and watch covers and studios arrive, then undo a
second test batch and confirm it reverses cleanly. Record row counts observed, not summarised.

## Explicit non-scope

- **Manga.** Refused with a clear message, not supported. A manga domain is a separate decision.
- **Two-way sync with MyAnimeList.** This is a snapshot, as every connector here is.
- **`incremental`.** Nothing to plan for a single small file.
- **AniList's own list export**, or importing from Kitsu. Named as obvious future connectors — each
  is another object in this directory plus one tuple entry — and not built.
- **Editing the shared import or triage screens.** Doing so would falsify acceptance criterion 9.

## Commit checkpoints

1. `feat(sprint-041): read a MyAnimeList export`
2. `feat(sprint-041): normalize a MyAnimeList row onto the anime domain`
3. `feat(sprint-041): register the MyAnimeList connector`
4. `docs(sprint-041): close sprint and hand off`

## Risks and decisions to surface

- **Criterion 9 is the real subject of this sprint.** Sprint 032 made connectors self-describing so
  that adding one is a package rather than a package plus a patch. Whether that held for a connector
  written by somebody who did not write the pipeline is the finding either way.
- **A gzip upload is a decompression bomb surface** on an application with no auth. Bound it
  explicitly; do not rely on the route's byte cap, which measures the compressed size.
- **Enrichment volume.** 81 items is 81 jobs against a provider publishing `X-RateLimit-Limit: 30`.
  If the backfill's one-job-per-item shape is wrong at this size, that is a Sprint 039 finding
  arriving late, and it is a decision to record rather than a batch to smuggle into the connector.
- **The owner's export is live personal data.** Walk through against a disposable database and leave
  `data/` untouched, as Sprint 037 did.

## Outcome

_Not started._
