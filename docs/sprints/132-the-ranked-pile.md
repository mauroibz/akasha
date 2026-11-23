# Sprint 132 — The ranked pile

**Sprint:** 132
**Status:** in_progress
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

_Not started._
