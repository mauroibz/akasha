# Handoff — Sprint 049 is complete; Sprint 050 (TVmaze) is ready

Sprint 049 shipped **series as the fifth domain** on keyless Wikidata, with a working poster and a
working episode-progress control from the first commit. `docs/agent/state.json` names **050** as
active with status `ready`. No runtime code for TVmaze exists yet.

The series domain is registered, its provider is constructed into the catalog as `wikidata-series`,
and every screen renders it from `GET /api/item-types` with no frontend change. `make test` is 967
backend + 189 frontend, green; `make check` is green. Nothing is tagged, released or pushed — the
whole series line is local on this branch.

## What the next session is picking up

Sprint 050 adds **TVmaze** as the second series provider: a real synopsis (the sprint's `synopsis`
field currently holds Wikidata's one-line description, named for its purpose now), a real airing
status, and the shows Wikidata's search misses. Read `docs/sprints/050-tvmaze-provider.md` first.

The seam is already in place, deliberately:

- The series identity strategy declares `("wikidata", "tvmaze")` **now**, so 050 adds an adapter,
  not a declaration. DEC-109 records why the conformance check lets a domain name a provider the
  registry does not yet hold: `source_preference` is a ranking, `enrichment.provider_order` is strict.
- `EnrichmentSpec.provider_order` for series is `("wikidata",)`; 050 extends it.
- TVmaze needs no key, only `USER_AGENT_CONTACT`. Its published rate limit is at least 20 calls per
  10 seconds per IP, with HTTP 429 on breach.

## The walkthrough pattern, proven this sprint

Sprint 049's walkthrough ran against **recorded** Wikidata because the replicas were maxlag-shedding
all day and the adapter's contractual `maxlag=5` refuses every live search. DEC-108 records the
substitution rule: replay the provider half at the transport seam, leave the cover pipeline live,
and record explicitly what is and is not proven. `scripts/walkthrough_series.py` is the reusable
harness. Two runner traps cost time and are now documented in the worklog: uvicorn's own lifespan
pass re-runs and undoes a seam installed inside the lifespan (drive it yourself, `lifespan="off"`),
and the add path fetches the chosen entity alone rather than as the search batch (the replay needs
single-entity routes, derivable from the batch fixtures).

**One live search is still owed.** The recorded walkthrough proves the rendered flow, the poster
pipeline and the progress control; it does not prove the adapter's request shape is still what live
Wikidata answers today. When the replicas recover, run one live series search before Sprint 050's
own walkthrough leans on the same assumption.

## Still true from before, and still not repaired

Sprint 047 was verified at a reduced level by owner direction (DEC-102): nobody has seen the
Letterboxd connector rendered on the Import page, nobody has approved a movie row through the Triage
UI, and **undo has no coverage in that sprint at any level**. Sprint 052's walkthrough gate is where
that debt is scheduled to be paid.

Two recorded defects from Sprint 046 (DEC-100) are still open and neither is movie-specific:

- `_backfillable_items` counts a null `cover_path` or `year` as "worth a lookup" in every domain,
  regardless of that domain's `completeness_fields`.
- `GET /api/search/resolve` maps every exception from `resolve_input` to HTTP 502 `provider_failure`,
  so a typed `record_not_found` is reported as an outage. The walkthrough re-confirmed this: a link
  naming no series still reads as a provider outage rather than a clean "no series by that name".

## Private data and operational constraints

- **`exports/` is the owner's private source archive and is gitignored as a whole directory.** It
  holds the Letterboxd ZIP, the MyAnimeList XML, two IMDb CSVs, a Trakt archive and a Spotify export.
  Every one carries account ids, usernames or ratings; the Trakt archive carries the owner's **email
  address** in `user-settings.json` and `user-profile.json`. These are read-only walkthrough input.
  **No fixture may be cut from any of them** — every committed importer fixture is invented.
- Wikidata and TVmaze both need no key, only `USER_AGENT_CONTACT`. Stremio's poster host is already
  in `ALLOWED_COVER_HOSTS`; series need no allowlist change.
- `frontend/e2e/scratchpad/` is gitignored; the series walkthrough spec there is local only.
