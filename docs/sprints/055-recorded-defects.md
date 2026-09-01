# Sprint 055 — The recorded defects, and the gates that stopped paying

**Status:** planned
**Depends on:** 054

**Roadmap revision:** 29

## Objective

Every defect the last nine sprints found, recorded and left, is either fixed or closed with a reason.
Nothing here is new product: it is the list the Outcomes have been accumulating, plus the three
places the verification gates now cost more than the evidence they buy — **measured**, not assumed.

The sprint is deliberately short and deliberately last. It runs after Sprint 054 so the release
decision is made on a library with no known open defects in it.

## Required context

- `docs/agent/TESTING.md` — the playbook whose cadence half of this sprint repairs, and its baseline
  table, which this sprint replaces with the measurements below.
- `docs/decisions.md`: DEC-100 (the two movie-line defects recorded and left), DEC-110 (the merge
  rule that produces the synopsis this fixes), DEC-084 and DEC-111 (the gate playbook, and the
  precedent for scheduling gate work as a sprint).
- Sprint 050's Outcome for the provider merge, Sprint 053's for the synopsis as it appears on a real
  record.
- `backend/src/book_tracker/domain/merge.py` and each series provider's `provider_order`.

## Current implementation baseline

Measured 2026-09-01 on this workstation, at Sprint 053's closure commit:

| Gate | Sprint 051 recorded | Measured now | Note |
|---|---:|---:|---|
| `make check` | ~10 s | 1.6 s | but **red** on a clean checkout with any local walkthrough spec present |
| backend pytest, as the gate runs it | ~62 s @ 989 | 67.5 s @ 1090 | coverage is in `addopts` |
| backend pytest, `--no-cov` | not measured | **41.8 s** | coverage costs **26 s, 61%**, on every run |
| frontend Vitest | ~23 s @ 190 | 23.7 s @ 194 | 10 stderr lines remain, all one notice |
| Playwright, parallel | 38.2 s, green | 38.4 s, **1–2 failed on 3 of 3 runs** | never green |
| Playwright, serial | 49.4 s | 101.7 s, green | the only trustworthy result |

Three of Sprint 051's four items held. The fourth did not, and the two largest costs in the table are
ones that sprint did not look at.

## Deliverables

### 1. A series gets the synopsis somebody would actually read

Observed live in Sprint 053: a real series enriched to `synopsis: "serie de televisión animada"` —
Wikidata's one-line *description*, where TVmaze had a full synopsis for the same show. Nothing is
broken. `wikidata-series` is first in `provider_order` and `fill_empty` fills only empty fields, so
the short text arrives first and the long one never gets a turn (DEC-110).

The rule is right for most fields and wrong for this one. **A longer answer for a long-text field is
not a conflict to be resolved by arrival order.** Decide and implement one of:

- a per-field merge preference, so a domain may say which of its fields prefer the fuller value; or
- `wikidata-series` not supplying `synopsis` at all, leaving that field to the provider that has one.

Prefer the first if it costs no more than the second: it is the general statement, and it is the same
shape as `completeness_fields` — a domain saying something about its own fields rather than a
provider being trimmed to fit. Record which was chosen and why.

**This must not become "the last provider wins".** The owner's own edits still beat every provider,
and a provider must never overwrite a field another provider filled with something equally good.

### 2. The two defects DEC-100 recorded and left

- **`_backfillable_items` treats a null `cover_path` or `year` as "worth a lookup" in every domain,
  regardless of `completeness_fields`.** A domain that legitimately has no cover, or rows with no
  year, is re-queued on every backfill for ever — the same shape as the `completeness_fields` defect
  DEC-067 row 3 already fixed one line above it. Either make both conditions part of the
  declaration, or state why they are universal and leave them.
- **`GET /api/search/resolve` maps every exception from `resolve_input` to a 502.** A typed
  `record_not_found` is an answer — "no series by that name" — and reads to the owner as a provider
  outage. Map a miss to a 4xx and keep 502 for a real failure. Sprint 049's walkthrough tolerated it
  and said so; it has been open since.

### 3. The parallel Playwright gate becomes usable, or is withdrawn

It has not passed once. Three runs on 2026-09-01: 2, 2 and 1 failures, always from
`accessibility.spec.ts:474` and `library.spec.ts:255`. Both pass serially every time, both are
rendering-timing assertions (an axe `color-contrast` sample and an animation crossfade), and both are
the same class of load-sensitive test Sprint 051 already moved into the serial `heavy-library`
project — it moved two and missed these two.

Move them, with their reason written beside the existing grep. Then the parallel gate is the gate:
about 40 s against 101.7 s serial, green.

**If they still fail after being moved, withdraw the parallel split.** A gate that is 63 s faster and
never green costs more than the one it replaced, because every session runs the serial one afterwards
anyway. That is the acceptance test, not the wall-clock number.

The underlying `color-contrast` finding is separate and is also this sprint's: the caption at
`frontend/src/features/library/VirtualLibrary.tsx:100` is `text-muted-foreground/80`, one class used
once. Computed statically it is 5.26:1 on the page background and 4.88:1 on a surface, both above the
4.5:1 that size needs — so the fault is that axe samples it mid-fade, not that the palette is wrong.
Either stop that caption fading, or drop the opacity and delete the class.

### 4. Coverage stops being charged to every run

`--cov=book_tracker --cov-report=term-missing` sits in `addopts`, so **every** backend run pays 26 s
and prints a 60-line table — including the focused single-file runs the playbook's first rung asks
for. That is the definition of paying for the same evidence repeatedly, which is the sentence
`TESTING.md` opens with.

Move it to its own target (`make coverage`), keep `--timeout=30` where it is, and say in
`TESTING.md` when coverage is actually required. `make test` and CI keep it if the owner wants a
number per commit; the TDD loop does not.

### 5. The shared gate stops policing files that are not in the repository

`frontend/e2e/scratchpad/` is gitignored on purpose — local walkthrough specs, owner paths, throwaway
flows. Prettier and ESLint both still read it, so **writing a walkthrough turns `make check` red**,
and the failure names a file that is not part of the project. It cost time in Sprint 053 and it will
cost time in every sprint with a walkthrough gate.

Add the directory to `.prettierignore` and to `eslint.config.js`'s `ignores`.

### 6. The last of the Vitest noise

Ten stderr lines survive Sprint 051's clean-up, and they are all one message: motion's
`You have Reduced Motion enabled on your device`. The suite sets reduced motion deliberately. Silence
it at the source the way `window.scrollTo` was silenced, so a green run is silent and a real
`console.error` is visible again.

## Acceptance criteria

1. A series whose providers offer a one-line description and a full synopsis stores the full
   synopsis, proved against recorded responses from both providers.
2. The owner's existing values and a provider's earlier non-empty answer are still never overwritten;
   a regression test says so.
3. `_backfillable_items` no longer re-queues a row for ever on a condition its domain did not
   declare — or the universality of `cover_path`/`year` is stated in the code and in DEC form.
4. A resolvable-looking link that names nothing returns a 4xx with a typed code, not a 502.
5. `npm run test:e2e` passes green, three runs in a row, at its default worker count — or the split
   is withdrawn and `TESTING.md` records why.
6. `frontend/src/features/library/VirtualLibrary.tsx:100` no longer produces an axe finding under
   load.
7. A focused backend run costs no coverage; `make coverage` produces the report on demand.
8. `make check` is green on a checkout that contains a local scratchpad walkthrough spec.
9. A green `npm test` prints no stderr.
10. `TESTING.md`'s baseline table carries the measurements from this sprint, not Sprint 051's.

## Required tests (TDD)

- Merge: a long-text field where an earlier provider supplied a short value and a later one a long
  value; and the negative — an earlier provider's good value is not replaced by a later one of
  similar length, and an owner edit is never touched.
- Backfill: a domain whose rows have no year is not re-queued indefinitely.
- `resolve`: a typed `record_not_found` becomes a 4xx; a transport failure stays 502.
- The Playwright criterion is three consecutive green runs, recorded in the Outcome with durations.

## Verification

```bash
cd backend && uv run pytest tests/test_enrichment.py tests/test_series_domain.py \
  tests/test_search_api.py -q
cd frontend && npm test
make check
make test
npm run test:e2e        # three times, all green, durations recorded
make coverage           # the new target, once
```

Then a walkthrough only if deliverable 1 changed what a person sees on a series detail page: enrich
one real series and read its synopsis.

## Explicit non-scope

- Any new product behaviour. This sprint fixes what is written down and nothing else.
- The IMDb list `Description` column, which is a **question for the owner** rather than a defect: it
  is deliberately dropped, and mapping it to entry notes is a product decision. Ask; do not implement
  it here unless the answer is yes.
- Re-litigating DEC-110's fill-empty rule beyond the one field class that needs it.
- Provider additions, new domains, or anything in the epics list.

## Commit checkpoints

1. `[FIX] Prefer the fuller answer for a long-text field`
2. `[FIX] The two defects the movie line recorded and left`
3. `[CHANGE] Make the parallel browser gate green, or withdraw it`
4. `[CHANGE] Stop charging coverage and lint to every run`
5. `[DOCS] Close sprint 055 and hand off`

## Risks and decisions to surface

- **Deliverable 1 changes a merge rule that four domains share.** The risk is not the series case; it
  is a rule that quietly starts overwriting somewhere else. The negative tests are the deliverable as
  much as the fix is.
- **Withdrawing the parallel split would undo the visible half of Sprint 051.** That is an acceptable
  outcome and should be recorded plainly if it happens: the sprint bought three things that held and
  one that did not, and saying so is worth more than defending it.
- Coverage moving out of `addopts` means a session that forgets `make coverage` sees no coverage
  number at all. That is the intended trade; name it in `TESTING.md` rather than leaving it to be
  discovered.

## Outcome

_Not started._
