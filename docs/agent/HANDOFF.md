# Handoff — Sprint 054 is complete; Sprint 055 (the recorded defects) is ready

The Trakt import ships, and it cost **one new module plus one line in the registry** — the third
connector in a row to prove Sprint 052's seam with no shared change at all.
`docs/agent/state.json` names **055** as active with status `ready`. `make test` is 1172 backend +
194 frontend, green; `make check` is green; serial Playwright 106 passed + 2 skipped. Nothing is
tagged, released or pushed — the whole series line is local on this branch.

## What Sprint 054 delivered

`backend/src/book_tracker/domains/movie/trakt.py` reads a Trakt archive (a ZIP of verbatim API
responses) into both libraries. The roll-up is the point: `watched-history.json` is the only
member with episode detail, and distinct `(show, season, number)` events excluding season 0 become
the entry's `progress`, against `aired_episodes` as the `episodes` total at export time. On the
owner's real archive that produced exactly 76 and 38, matching `plays` — the fallback exists for
archives whose history is truncated, and a row that used it carries the fact in its entry notes
(a row *error* would block a healthy commit; the shared entry-value allowlist refuses unknown
`values` names, so the machine marker rides `source_fields["plays_used"]`).

Four members are never opened: `user-settings.json` and `user-profile.json` (the owner's email
address — the malformed-member test proves nothing reads them), plus `user-last-activities.json`
and `user-stats.json` (account telemetry, same treatment). Season and episode ratings are counted
and reported, never scored.

## What the next session is picking up

Sprint 055 — **the last planned sprint**: every defect the movie and series lines recorded and
left, plus the three gate repairs measurement justified. Read
`docs/sprints/055-recorded-defects.md`; the list is already gathered there and needs no
rediscovery — the synopsis defect, the two DEC-100 defects, the parallel-Playwright split, the
coverage cost in `addopts`, and the lint gate reading the gitignored scratchpad.

Closing 055 means the release decision reaches the owner: `v1.5.0`, release notes, and whether
v1.4.0 gets tagged first. Sprint 018's procedure is unchanged; nothing is pushed without being
asked.

## The gates, as measured at this closure

Same as Sprint 053's: **run Playwright serially** (`--workers=1`, about 102 s, green every time)
until 055 settles the split — the parallel default is faster and has never passed. Coverage sits
in `addopts` and costs 26 s per backend run (`--no-cov` for focused TDD runs). A local scratchpad
spec turns `make check` red until `npm run format` runs.

## Running the walkthrough gate

`scripts/walkthrough.py` gives a fresh data directory **per launch**, not per spec run — one
clean backend per attempt, or a committed batch replays by fingerprint and approved rows leave an
empty inbox. Two new references now exist for this sprint:

- `scripts/walkthrough_trakt_054.py` — the API flow, 27 checks (env: `BOOK_TRACKER_BASE_URL`,
  `TRAKT_ARCHIVE`, `IMDB_RATINGS`). Undo is **terminal** for a fingerprint: the IMDb overlap check
  must run against the committed library, undo last.
- `frontend/e2e/scratchpad/sprint54-walkthrough.spec.ts` — the browser flow, 8.9 s (env:
  `BOOK_TRACKER_E2E_BACKEND`, `TRAKT_ARCHIVE`, `IMDB_RATINGS`).

Three idioms the spec ran into, so the next one does not rediscover them: the two IMDb CSVs are
swapped easily (`Const,...` is the *ratings* export and the overlapping one; `Position,...` is a
*list* export); the Library grid's rows are `button "Open <title>"`, not links; and the Library
is domain-scoped via `/?type=series`. The Import preview screen renders suggested statuses but
not entry values — progress is proven on the Detail page (`[data-fact='progress'] dd` reads
"76 / 76 episodes").

## Known and left

Unchanged from Sprint 053's closure — **all scheduled as Sprint 055**:

- A series' synopsis comes back as Wikidata's one-line description rather than TVmaze's real one
  (DEC-110's fill-empty rule working as designed; a poor synopsis on a real record).
- The intermittent parallel-Playwright `color-contrast` finding on `VirtualLibrary.tsx:100`.
- The two DEC-100 defects: `_backfillable_items` counting null covers/years as "worth a lookup",
  and `/api/search/resolve` mapping a typed `record_not_found` to a 502.
- The e2e dev server proxies `/api` to a backend that is not running unless
  `BOOK_TRACKER_E2E_BACKEND` is set — gate noise, recorded not fixed.
- The IMDb list export's `Description` per row — **055 asks the owner**; it is a product question.

## Private data and operational constraints

- `exports/` is the owner's private source archive, gitignored as a whole. Read-only walkthrough
  input. **No fixture may be cut from any of them**; every Trakt fixture is invented. The two
  email-carrying members are never opened by the reader, and a test asserts it.
- Wikidata and TVmaze need no key, only `USER_AGENT_CONTACT`. Stremio's poster host is already
  in `ALLOWED_COVER_HOSTS`.
- Process note: the plan-revision-29 session never appended its worklog entry; Sprint 054's entry
  covers both. Do not re-derive what revision 29 changed — it is in the worklog and DEC-114.
