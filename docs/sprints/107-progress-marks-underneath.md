# Sprint 107 — Episodes and chapters, underneath

**Sprint:** 107
**Status:** completed
**Roadmap revision:** 48
**Depends on:** 106
**Owner:** Mauro

## Objective

An entry can record which episodes or chapters were finished, per part (a series' season), as an
optional set of marks that drives the existing progress count. A series knows its seasons from
TVmaze, a book its chapter count from the owner or Open Library. This sprint builds the model
and the API; Sprint 108 builds the tracker on the detail page (DEC-171).

## Required context

- DEC-171; DEC-077 (why marks are not child entities); DEC-092 (the total is never a bound);
  DEC-167.
- `domain/spec.py` (`ProgressSpec`, `validate_progress`, `validate_entry_values`, `FieldSpec`
  `rows` and `ColumnSpec`); `domains/series/__init__.py`, `domains/series/tvmaze.py`,
  `domains/anime/__init__.py`, `domains/book/__init__.py`, `domains/book/providers.py` (the Open
  Library edition fetch); `api/library.py` (`ProgressSpecResponse`, entry `PATCH`);
  `application/export.py` (the lossless JSON round trip); migration 0026 as the latest.
- `docs/guides/adding-a-domain.md` and technical spec §6.6: the outline is a declaration.

## Current implementation baseline

Series and anime declare `ProgressSpec("Episodes watched", "episode", total_field="episodes")`;
an entry holds one `progress` integer. Books declare no progress. TVmaze's adapter fetches
`/shows/<id>` without episodes. Nothing records which episodes.

## Deliverables

1. `ProgressSpec.parts_field`: the name of a `rows` metadata field whose rows are a part's
   number and its size. Published on `/api/item-types`. The conformance suite checks that a
   declared `parts_field` is a `rows` field with those two number columns.
2. Series: a `season_episodes` rows field (*Season*, *Episodes*), filled by TVmaze through
   `?embed=episodes` (specials excluded), with a recorded real response as the fixture. Not a
   completeness field (DEC-171 point 5).
3. Books: a `chapters` number field (1–2,000), filled from Open Library's edition
   `table_of_contents` row count when present, editable in the metadata dialog;
   `ProgressSpec("Chapters read", "chapter", total_field="chapters")`.
4. Migration 0027: `entries.progress_marks`, nullable JSON text. Shape: `{"<part>": [n, ...]}`,
   numbers sorted and unique, each ≥ 1; at most 10,000 marks.
5. Entry `PATCH` accepts `progress_marks`. Writing marks sets `progress` to their count in the
   same transaction; writing `progress` alone clears marks; writing both is refused with 422.
   A domain without progress refuses marks, as it refuses `progress`.
6. The item detail response carries the resolved outline: `parts_field` rows when present, else
   one part of `total_field`, else none.
7. `POST /api/items/{id}/outline`: fetch the outline for an item that has none (a series added
   before 2.7) through the domain's providers and store it. An explicit action, never called
   while rendering; a provider failure answers 502 and changes nothing.
8. Lossless JSON export and restore carry `progress_marks`.

## Acceptance criteria

1. Marks round-trip through `PATCH` and set `progress` to their count; a typed count clears
   them; both at once is 422; a film refuses marks.
2. A series added from a recorded TVmaze response has `season_episodes` matching it, specials
   excluded.
3. A book whose Open Library edition has a table of contents gets `chapters`; one without does
   not, and enrichment does not re-queue it.
4. The outline endpoint fills a series that had none, and a recorded provider failure leaves the
   item unchanged.
5. Marks outside the outline are kept and counted.
6. No shared layer names an item type: the outline comes from `ProgressSpec` declarations.
7. Export then restore preserves marks.

## Required tests (TDD)

Spec validation (marks shape, limits, the mutual exclusion), the series and book field
mappings from recorded responses, migration up and down, the entry `PATCH` paths, the outline
endpoint with success and failure recordings, conformance, export round trip.

## Verification

Per DEC-167: the test files covering the changed modules, migration up and down, `make check`
(including the OpenAPI check), and the endpoints against a copy of the owner's library from the
nightly backup, kept in the scratchpad: a series' outline loaded, marks written, the count read
back.

## Explicit non-scope

- Any screen (Sprint 108).
- Episode titles, air dates, or anything per part beyond checked or not. No ratings per part.
- Marks for albums or films.
- A backfill job over existing series.

## Commit checkpoints

1. `[ADD]` `ProgressSpec.parts_field`, the fields, migration 0027 and the `PATCH` contract.
2. `[ADD]` TVmaze and Open Library outlines, and the outline endpoint.

## Risks and decisions to surface

- TVmaze numbers some long-running shows by year as the season (`2019`, `2020`). Stored as
  given; the screen labels it as TVmaze does.
- A refresh that changes the outline under existing marks is the DEC-092 case: marks stay.

## Outcome

Delivered 2026-10-22 in `8c108ed`.

- **AC1.** `PATCH /api/entries/{id}` takes `progress_marks`; marks set `progress` to their
  count, a typed count clears them, both together is 422, a film refuses marks
  (`invalid_progress`). An empty set stores `NULL` and records `progress` 0.
- **AC2.** TVmaze's fetch and IMDb lookup add `season_episodes` from
  `/shows/<id>/episodes` (recorded: Breaking Bad 7/13/13/13/16, The Mandalorian 8/8/8,
  Samantha Oups 29/2). A failed episode list leaves the rest of the record.
- **AC3.** Open Library gives `chapters` from the numbered rows of an edition's contents
  (*Thinking, Fast and Slow*: 38 of 50 rows); Rayuela's edition has none and gets none.
  Neither `chapters` nor `season_episodes` is a completeness field.
- **AC4.** `POST /api/items/{id}/outline` fills a series from TVmaze (200), answers 502
  `provider_failure` on a recorded 503 with the item unchanged, 422 `outline_unavailable`
  for a miss or a film, and returns an item that already has the field untouched.
- **AC5.** Marks beyond the outline are kept and counted.
- **AC6.** Conformance checks `parts_field` (a `rows` field with two numbered columns) and
  `abandoned` (only where progress is declared); three new malformed fixtures fail it.
- **AC7.** The JSON export carries `progress_marks`.

**Verified.** 788 backend tests across the 26 files covering the changed modules (one
pre-existing zipfile warning in the Trakt refusal test), `make check` (with regenerated
`openapi.json` and `schema.d.ts`), migration 0026 → 0027 → 0026 in
`test_progress_marks.py`. Live, on a scratchpad copy of the local dev library (17 entries,
migrated with its pre-migration backup): Breaking Bad resolved from its IMDb URL through
Wikidata had no seasons, the outline action fetched five from TVmaze, ten marks gave
`progress` 10, a typed 4 cleared them; *Thinking, Fast and Slow* added from Open Library
arrived with 38 chapters; the export carried the marks.

**Deviations (DEC-172).**
- The owner asked mid-sprint that dropping an entry ask how far it got. The declaration
  (`StatusSpec.abandoned`, on book, anime and series `dropped`) is here; the question is
  Sprint 108's.
- TVmaze's episode list is a second request: the lookup's 301 drops `?embed=episodes`.
- Only numbered contents rows count as chapters.
- There is no JSON restore in the application; the export carries marks and the database
  backup is the restore path.
- Six existing tests that used a book as the domain without progress now use a film.
