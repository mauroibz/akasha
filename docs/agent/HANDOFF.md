# Handoff — Sprint 050 is complete; Sprint 051 (verification-gate optimization) is ready

Sprint 050 shipped **TVmaze as the second series provider**. `docs/agent/state.json` names **051**
as active with status `ready` — but 051 is no longer the multi-domain import sprint. At plan
revision 28 (DEC-111) the owner directed TESTING.md's *Optimization backlog* to run as a sprint
first, and the import line renumbered: **052** multi-domain imports, **053** IMDb, **054** Trakt.
`make test` is 989 backend + 190 frontend, green; `make check` is green. Nothing is tagged,
released or pushed — the whole series/TVmaze line is local on this branch.

## What the next session is picking up

Sprint 051 implements the four items in `docs/agent/TESTING.md`'s *Optimization backlog* — read
`docs/sprints/051-verification-gate-optimization.md` first. The measured baseline:

- Playwright: 106 passed + 2 skipped in **49.4 s** at one worker. The two load-sensitive
  invariants are the 10,000-entry DOM-budget tests at `frontend/e2e/library.spec.ts:75` and
  `:125`; everything else should go parallel.
- Vitest: 190 passed in 23.3 s with **21** `Query data cannot be undefined` warnings on
  `["attachments",3]` from `DetailPage.test.tsx` fetch mocks. The `window.scrollTo` shim half of
  the item is already done (`frontend/src/test/setup.ts:30`).
- Walkthrough launcher: generalize `scripts/walkthrough_series.py` (the lifespan trap and the
  fresh-data-dir pattern are already solved there) into one tracked `scripts/walkthrough.py`.
- Timeouts: nothing has one — no `pytest-timeout`, no Vitest `testTimeout`, Playwright relies on
  the unstated default. Measure the slowest current tests before choosing bounds.

## Known and left, in the order they are likely to bite

- **One live series search is still owed.** Both Sprint 049's and Sprint 050's walkthroughs ran
  against **recorded** provider responses (DEC-108's substitution rule). What is not proven is
  that the adapters' request shape is still what live Wikidata and TVmaze answer today. When the
  network is healthy, run one live series search before Sprint 052's own walkthrough leans on
  the same assumption.
- **The intermittent 422 in the series walkthrough is a harness artifact, not a defect** — the
  designed `near_match_confirmation_required` guard (`application/add.py:197-202`) fires on a
  leftover row when two add-tests run back-to-back against a reused walkthrough data dir. Fresh
  data dir and it disappears. The new launcher makes the fresh dir the default; don't chase the
  422 as a bug.
- **The e2e dev server proxies `/api` to a backend that is not running.** The baseline
  Playwright run prints `ECONNREFUSED` proxy noise throughout while passing — the specs stub
  their own API. Recorded, not fixed; it is not one of the four backlog items.
- **Sprint 047 was verified at a reduced level by owner direction (DEC-102).** Nobody has seen
  the Letterboxd connector rendered on the Import page, nobody has approved a movie row through
  the Triage UI, and undo has no coverage in that sprint at any level. Sprint 053's walkthrough
  gate is where that debt is scheduled to be paid.
- Two recorded defects from Sprint 046 (DEC-100) are still open and neither is movie-specific:
  `_backfillable_items` counts a null `cover_path` or `year` as "worth a lookup" in every
  domain, regardless of `completeness_fields`; and `GET /api/search/resolve` maps every
  exception from `resolve_input` to a 502, so a typed `record_not_found` reads as a provider
  outage.

## Private data and operational constraints

- **`exports/` is the owner's private source archive and is gitignored as a whole directory.**
  It holds the Letterboxd ZIP, the MyAnimeList XML, two IMDb CSVs, a Trakt archive and a Spotify
  export, all carrying account ids, usernames, ratings, and in Trakt's case the owner's **email
  address**. Read-only walkthrough input. **No fixture may be cut from any of them** — every
  committed importer fixture is invented. Sprint 052's test connector and Sprint 053's IMDb
  reader both need invented fixtures, not slices of the real exports.
- Wikidata and TVmaze both need no key, only `USER_AGENT_CONTACT`. Stremio's poster host is
  already in `ALLOWED_COVER_HOSTS`.
- `frontend/e2e/scratchpad/` is gitignored; the series walkthrough specs there are local only.
