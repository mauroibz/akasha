# Sprint 132 — The ranked pile

**Sprint:** 132
**Status:** completed
**Roadmap revision:** 54
**Depends on:** 131
**Owner:** Mauro

## Objective

The pile is ranked by what the person is most likely to want next, each pick with a true,
specific reason, computed locally with no network. Home's *Up next* and the goal picks use it.

## Required context

- DEC-183 point 3; product spec §1 (non-goals) — this sprint removes *Recommendations* from it.
- `application/goals.py` (`picks`: favourite creator, longest waiting), `api/goals.py`,
  `application/home.py` (`next`; Home shows 3, 4 or 5 picks by *Up next*'s size, DEC-185),
  each domain's `FieldSpec`s (`series`, genres/subjects, creators) in `domains/*/__init__.py`,
  the score history tables (Sprint 114).

## Deliverables

1. `application/ranking.py`: `rank_pile(user, item_type | None, limit)` returns planned entries
   with a score and a reason built from signals the library already holds:
   - **next in a series** the person is reading or finished (book `series` field and position
     where present);
   - **creator affinity**: mean score and count for the creator;
   - **subject/genre affinity** from declared groupable fields, weighted by recent high scores;
   - **time waiting** (small, so the old pile surfaces slowly);
   - **goal pace**: domains behind their goal get a lift;
   - **recently dismissed or set aside** is pushed down.
   Weights are constants in one place; ties break on entry id so the order is stable.
2. Each reason is a short sentence naming its evidence ("Next in Mistborn; you gave book 1 a 9",
   "You rate Le Guin 8.4 across 5"). Only signals that fired appear.
3. `/api/home` `next` and `/goals/{type}/picks` use it; a `GET /api/pile?type=&limit=` exposes it.
4. Product spec §1: *Recommendations* leaves the non-goals; §-new describes the ranked pile.

## Acceptance criteria

1. On a fixture library each signal moves the expected entry up, and reasons cite real data
   (tested per signal).
2. The ranking makes no network calls and answers under 100 ms for a 2,000-entry pile.
3. *Up next* shows the reason under each pick.

## Required tests (TDD)

`tests/test_ranking.py` per signal and for stability; API test for `/api/pile`; frontend test for
reasons in *Up next*.

## Verification

Per DEC-167 and a walkthrough of *Up next* on a realistic library; record whether the order
feels right.

## Explicit non-scope

Any external source; embeddings (136 adds them as a signal).

## Outcome

Delivered 2026-11-23 (DEC-186).

- **Ranking** (`68f8b1e`, tuned in `5272c90`, `8da1fbd`): `application/ranking.py`
  `rank_pile(engine, user_id, item_type | None, limit)` scores every entry in a `planned`
  status from stored data — series, creator, affinity, waiting, goal, set aside — weights as
  constants at the top of the module, ties on entry id. Reasons are sentences citing the data
  ("Next in Mistborn; you gave book 1 a 9", "You rate Ursula K. Le Guin 8.7 across 3", "You rate
  Fantasy 9.0 across 3 anime", "Toward 24 books this year; 14 so far", "Started 1 Nov 2026, then
  set aside"), only signals that fired, strongest first. Domains declare what it reads:
  `Domain.ranking: RankingSpec` (books: `series`, Goodreads "(Series, #N)" titles, `subjects`;
  anime, films, series: `genres`), held by a conformance check (`05bdc34`).
- **Readers:** `GET /api/pile?type=&limit=` (new), Home's `next` (all libraries, five) and
  `/goals/{type}/picks` (one library) all answer `{entry, score, reasons}`; *Up next* shows the
  strongest reason under each pick, the Diary's picks the same as a sentence.
- **Product spec** §1: *Recommendations* left the non-goals; §7 *Home* describes the ranked
  pile. Technical spec: `/api/pile`, `next`, `?tz=`, `RankingSpec`.
- **Prerequisite repairs on Home, recorded:** the year no longer leaves its row's height empty
  beside Lately — the strip takes the module's height and each month's covers take the fewest
  columns that show the busiest month whole (`929fca4`; covers 53x79 px at 1440 against about
  25x37 before). *Lately* groups additions by the person's own day: the client sends its zone
  as `tz`, falling back to `TZ` then UTC, and the row's date is local (`b83f2c2`; DEC-185 point
  4 superseded).

Acceptance criteria:

1. Each signal moves the expected entry and its reason cites real data — `tests/test_ranking.py`,
   one test per signal plus series edge cases (no places, after a drop, a disliked series, one
   under way), subject ubiquity, stability, reason order, another person's library.
2. No network and under 100 ms on a 2,000-entry pile — the route test swaps the provider
   client for one that fails on any request (no calls); 26 ms median for 2,000 waiting among
   5,000. `/api/home` on 10,000 entries: 119 ms median (budget 150; 126–133 before).
3. *Up next* shows the reason under each pick — `UpNext.test.tsx`, and `home.spec.ts` *Start
   moves a pile entry under way* checks the reason in the browser.

Verification (DEC-167): backend `test_ranking`, `test_goals`, `test_home_api`,
`test_home_layout`, `test_isolation`, `test_app_shape`, `test_domain`, `test_domain_conformance`
— 341 passed (then the conformance file again after the move: 249 passed); `npx vitest related`
on the changed files — 49 passed; `make check` green; Playwright `home.spec.ts` and
`diary-goal.spec.ts` — 18 passed. Walkthrough on `scripts/walkthrough.py --keep` with a
realistic seeded library (worklog). Commits also `0993d52` (e2e reason check), `375d4fe` (docs).

Deviations: *dismissed* has no stored source (nothing dismisses a pile entry), so the push-down
reads only *set aside* — an entry back on the pile with a `date_started` (DEC-186 point 5). The
goal signal applies only across libraries (point 4). Calibre's `series_index` is not imported,
so Calibre series rank without places.
