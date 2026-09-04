# Sprint 070 — Their formats, not ours

**Status:** planned
**Depends on:** 069
**Roadmap revision:** 37

> Planned from [`../export-proposal.md`](../export-proposal.md) §2.3. **Accepted as
> DEC-135;** remains `planned` until 069 closes. Proposal §4: *if the release has to be cut,
> cut this sprint* — after 069 every domain can already leave in JSON and in a CSV, from a
> button.

## Objective

Add the spellings the other applications actually import — MyAnimeList for anime,
Letterboxd for film — and settle, with evidence, what series exports to. Each verified by
a round trip rather than by reading a specification. **No frontend file changes**: that is
the acceptance criterion that proves Sprint 068's declaration carries its weight.

## Required context

- [`../export-proposal.md`](../export-proposal.md) §2.3 (the formats and the confidence
  attached to each), §2.6 (round-trip verification), §6 (the risks, all four of which are
  this sprint's).
- [`068-export-the-way-we-import.md`](068-export-the-way-we-import.md) — the `ExportView`
  protocol and where a view lives. Read the shipped protocol.
- `docs/decisions.md` DEC-025 (a real parser, not a mock), DEC-088 and DEC-127 (this
  repository measures a third party's format instead of trusting its documentation —
  both times that mattered).
- Code, read fresh: `backend/src/book_tracker/domains/anime/myanimelist.py` — the reader
  of the exact XML this sprint writes, including what it does with `my_status`,
  `my_score`, `my_watched_episodes` and the gzip handling;
  `backend/src/book_tracker/domains/movie/letterboxd.py` — the reader of Letterboxd's
  *export archive*, which is **not** the shape their importer takes;
  `backend/src/book_tracker/domains/movie/imdb.py` — reads list CSVs and declares
  `("movie", "series")`, which makes it the candidate round-trip partner for series.
- Tests: `backend/tests/test_myanimelist_import.py`,
  `backend/tests/test_letterboxd_import.py`, `backend/tests/test_imdb_import.py`,
  `backend/tests/test_export.py`, and the fixtures under `backend/tests/fixtures`.

## Current implementation baseline

- Anime, movie and series can leave in JSON and in the `table` CSV, and in nothing an
  ecosystem service reads.
- `domains/anime/myanimelist.py` parses MyAnimeList's export XML, measured against the
  owner's real file. That parser is what a `myanimelist` view is proven against.
- `domains/movie/letterboxd.py` parses their five-table export archive. Letterboxd's
  **import** takes a different, simpler CSV, and this repository has never written one.
- Nothing in the repository reads or writes a Trakt-importable list.

## Deliverables

1. **The `myanimelist` view**, in `domains/anime/`, writing the export XML gzipped, with
   the status vocabulary, score scale and episode counts its own reader expects.
2. **The Letterboxd import CSV, confirmed before a line is written.** Their documented
   import columns, checked against their current documentation, with the date the check
   was made recorded in the view's own module the way every importer here records it. If
   the columns cannot be confirmed, the deliverable is the recorded finding, not a guess.
3. **The series answer, decided by evidence.** Either an `imdb`-shaped list CSV — which our
   own `domains/movie/imdb.py` reads for both movie and series, so it round-trips through
   a real parser — or the recorded conclusion that the `table` floor is the answer for
   series. Both are complete; guessing is not.
4. **CSV injection covered per view**, as a test per view rather than a shared assumption.
5. **The memory test extended** to the new views, for Sprint 068's reason.
6. **Zero frontend changes.** New rows appear on the export tab because the declarations
   appear. If a `.tsx` file has to change, that is a finding about Sprint 068 and is
   recorded as one.

## Acceptance criteria

1. An anime library exported through the `myanimelist` view and fed back through
   `domains/anime/myanimelist.py` returns the same titles, statuses, scores and episode
   counts, from the gzipped bytes as written.
2. The Letterboxd view's columns match the columns Letterboxd's own import documentation
   lists on the date recorded in the module, and the module records that date.
3. Whatever series resolves to, the outcome states the evidence for it. If it is a list
   CSV, it round-trips through `domains/movie/imdb.py`; if it is the `table` floor, the
   outcome says what was checked to reach that.
4. `git diff --stat` for this sprint touches no file under `frontend/`.
5. Every new view neutralizes a leading `=`, `+`, `-` or `@` in free text.
6. Peak memory is flat against library size for every new view.
7. The export tab shows the new views, with their guide steps and counts, without having
   been changed.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| MyAnimeList round trip through our own reader, gzipped | integration | `test_export.py` |
| MAL status/score/episode vocabulary matches what the reader expects | unit | `test_export.py` |
| Letterboxd view writes the documented import columns, in order | unit | `test_export.py` |
| Series: the round trip, or the recorded absence of one | integration | `test_export.py` |
| Formula prefixes neutralized in each new view | unit | `test_export.py` |
| Peak memory flat for each new view | integration | `test_export.py` |
| The new views appear in `GET /api/exports` with guide and count | api | `test_export.py` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`
- The exhaustive backend suite; `openapi.json` regenerated if the declaration list is in it.
- `npx playwright test` — the export tab must still pass with no change to it.
- **Walkthrough (DEC-025), and it is the point of this sprint:** export the owner's real
  anime library, import the file into MyAnimeList; export the film library, import it into
  Letterboxd. Report what the far end accepted, rejected or silently changed. **We cannot
  test somebody else's importer** (proposal §6) — this walkthrough is the only evidence
  that exists, and a sprint that skips it has verified nothing about the feature's purpose.

## Explicit non-scope

- Any frontend change — see deliverable 6.
- New readers. This sprint writes formats; it does not learn new ones.
- AniList, Kitsu, Trakt or Discogs as targets in their own right. If a MyAnimeList or IMDb
  file is accepted by one of them, that is a line in the guide steps, not a view.
- Everything in proposal §5.

## Commit checkpoints

1. `[ADD] Write the file MyAnimeList reads back`
2. `[ADD] Letterboxd's import columns, checked against their own page`
3. `[ADD] What a series exports to, and why` (or `[DOCS]` if the answer is the floor)

## Risks and decisions to surface

- **A target changes its columns and our view silently stops fitting.** Record the date of
  the check in the module, round-trip through our own reader where one exists, and let the
  walkthrough be the real test.
- **Letterboxd's import shape is the one thing here we have never parsed.** If their
  documentation is ambiguous, the honest deliverable is a recorded finding and the `table`
  floor for film, not a file that looks plausible.
- **Series may not have a target at all.** That is an acceptable outcome and it should be
  written down, so the question is not reopened from scratch in a year.
- **Gzip plus streaming is a real constraint.** The MAL file is compressed; compressing a
  stream is fine, buffering it to compress is not, and the memory test is what catches the
  difference.

## Outcome

_Not started._
