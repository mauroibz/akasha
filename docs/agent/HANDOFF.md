# Handoff — Sprint 053 is complete; Sprint 054 (the Trakt import) is ready

The IMDb import ships, and it cost **one new module plus one line in the registry**. Sprint 052's
multi-domain seam held for a connector it was not built for, which is the only test of it that
counts. `docs/agent/state.json` names **054** as active with status `ready`. `make test` is 1090
backend + 194 frontend, green; `make check` is green; Playwright is 106 passed + 2 skipped serially.
Nothing is tagged, released or pushed — the whole series line is local on this branch.

**Sprint 047's debt is paid** (DEC-102): a movie has now been previewed on the Import screen,
approved through Triage and undone, in a browser, against real data.

## What Sprint 053 delivered, and the one thing it had to repair

`backend/src/book_tracker/domains/movie/imdb.py` reads both IMDb export shapes — a ratings CSV and a
list CSV — told apart by their headers. `Title Type` routes each row through a declared table whose
default is *skip and count*, so a title type IMDb has not published yet is a number on the preview
screen rather than a failed import. `application/imports.py`, `api/imports.py`, `ImportPage.tsx` and
`TriagePage.tsx` were not touched, and neither was any other frontend file.

**The repair, and it is a shared contract: DEC-113.** `EnrichmentSpec.identity_kind` is now
`identity_kinds`, an ordered tuple. The movie domain enriched on `letterboxd` alone, and an IMDb
export carries no Letterboxd URI — so every film imported from IMDb would have sat in the library for
ever with no poster, no genres and no runtime, and **nothing would have failed**. Movies declare
`("letterboxd", "imdb")`; every other domain declares a one-element tuple. The backfill runs one
statement per key in declaration order and queues an item once, under the first key it has.

The obligation that creates, which conformance cannot check for you: **every provider in a domain's
`provider_order` must answer every key it declares.**

## What the next session is picking up

Sprint 054 — the Trakt import. Read
`docs/sprints/054-trakt-import.md`; its baseline section was rewritten at this closure with what 053
established, and `domains/movie/imdb.py` is the nearest worked example to copy the shape from.

Three things it inherits rather than rebuilds:

- Rows a reader cannot target are an `ImportSnapshot.skipped` tally by reason, in the source's own
  word, reaching the preview as a count and never as a row error (DEC-112). Trakt's season and
  episode ratings map onto that the way IMDb's `Title Type` did.
- A row names its own domain through `NormalizedImportRecord.item_type`, and `match` must pass **that
  row's** type rather than the connector's first, or a near-match offer is scoped to the wrong
  library.
- Both target domains enrich on `imdb` and a Trakt archive carries IMDb ids, so nothing further is
  owed — but check it rather than assume it. Sprint 053 had to.

**Sprint 055 now follows it** (plan revision 29, DEC-114): the defects the movie and series lines
recorded and left, plus four gate repairs that measurement justified. The release decision therefore
comes after 055, on a library with no known open defects. Nothing is pushed unasked.

## The gates, as measured 2026-09-01

**Run Playwright serially until Sprint 055 lands.** The parallel split has not passed once — three
runs, 1 to 2 failures each, always `accessibility.spec.ts:474` and `library.spec.ts:255`, both green
on every serial run. `npm run test:e2e -- --workers=1` is 102 s and green; the parallel default is
38 s and never green, so running it costs you both. DEC-114 has the full assessment of Sprint 051.

Two other costs are scheduled for 055 and worth knowing today: coverage sits in `addopts` and adds
26 s plus a 60-line table to **every** backend run (`--no-cov` for a focused run during TDD), and the
lint gate reads the gitignored `frontend/e2e/scratchpad/`, so writing a walkthrough spec turns
`make check` red until you run `npm run format`.

## Running the walkthrough gate — read this before you spend an hour

`scripts/walkthrough.py` gives a fresh temporary data directory **per launch**, not per spec run.
Three Sprint 053 attempts failed on state carried between runs and every symptom looked like a
product bug: a committed batch replays by fingerprint, and rows already approved leave an empty
inbox. **One clean backend per attempt.** A short wrapper that kills the old one, starts a new one,
waits for the printed URL and runs the spec makes iteration cheap; write one before debugging.

```bash
cd backend && uv run python ../scripts/walkthrough.py     # add --replay <module> to stub providers
cd frontend && BOOK_TRACKER_INCLUDE_SCRATCHPAD=1 \
  BOOK_TRACKER_E2E_BACKEND=http://127.0.0.1:<printed port> \
  IMDB_RATINGS=… IMDB_LIST=… \
  npx playwright test --project=chromium --workers=1 e2e/scratchpad/<file>.spec.ts
```

`frontend/e2e/scratchpad/` is gitignored, so those specs are local only. Two are the working
references now: `sprint52-walkthrough.spec.ts` for target checkboxes and mixed-domain Triage, and
`sprint53-walkthrough.spec.ts` for a real export driven end to end.

Also: **enrichment is a background job, so a browser test races it.** Sprint 053 proved AC9 with a
short script that commits through the API and polls until the covers arrive — about six seconds. Do
the same rather than adding a sleep to a Playwright spec.

## Known and left

The first four are **scheduled as Sprint 055** and need no rediscovery; they are listed so a
session meeting one recognises it rather than chasing it.

- **A show's synopsis comes back as Wikidata's one-line description, not TVmaze's real synopsis.**
  Live, a series enriched to `synopsis: "serie de televisión animada"`. That is the designed rule
  working — `wikidata-series` is first in `provider_order` and the merge fills only empty fields, so
  TVmaze's fuller text never gets a turn (DEC-110). It is still a poor synopsis on a real record.
  **Sprint 055, deliverable 1.**
- **An intermittent accessibility failure under parallel Playwright, pre-existing and not from the
  import line.** Six workers make axe report `color-contrast [serious]` on
  `.text-muted-foreground/80` — one class, used once, at
  `frontend/src/features/library/VirtualLibrary.tsx:100`. Serial runs are green every time, and the
  failing spec moves between the two that render that caption. Computed statically it is 5.26:1 on
  the background and 4.88:1 on a surface, both above the 4.5:1 that size needs, so it reads as a
  sample taken mid-fade. Sprint 051's parallel split surfaced it. **Sprint 055, deliverable 3.**
- **The e2e dev server proxies `/api` to a backend that is not running** unless
  `BOOK_TRACKER_E2E_BACKEND` is set. The gate prints `ECONNREFUSED` noise throughout while passing —
  the specs stub their own API. Recorded, not fixed.
- **An IMDb list export carries a `Description` per row that the reader deliberately drops.** If the
  owner uses it as a note, it can be mapped. **Sprint 055 asks the owner**; it is a product question,
  not a defect, and is explicitly out of that sprint's scope unless the answer is yes.
- Two recorded defects from Sprint 046 (DEC-100) are still open and neither is domain-specific:
  `_backfillable_items` counts a null `cover_path` or `year` as "worth a lookup" in every domain,
  regardless of `completeness_fields`; and `GET /api/search/resolve` maps every exception from
  `resolve_input` to a 502, so a typed `record_not_found` reads as a provider outage. **Sprint 055,
  deliverable 2.**

## Private data and operational constraints

- **`exports/` is the owner's private source archive and is gitignored as a whole directory.** It
  holds the Letterboxd ZIP, the MyAnimeList XML, two IMDb CSVs, a Trakt archive and a Spotify
  export, all carrying account ids, usernames, ratings, and in Trakt's case the owner's **email
  address**. Read-only walkthrough input. **No fixture may be cut from any of them** — every
  committed importer fixture is invented, Sprint 053's included. Sprint 054 needs invented fixtures
  too, and two Trakt members must never be opened at all: `user-settings.json` and
  `user-profile.json` carry that email address, and a test should assert nothing reads them.
- Wikidata and TVmaze both need no key, only `USER_AGENT_CONTACT`. Stremio's poster host is already
  in `ALLOWED_COVER_HOSTS`.
