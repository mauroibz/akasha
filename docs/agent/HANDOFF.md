# Handoff — Sprints 063 and the anime/albums question both closed, on their own branch

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "064"`, pointing
at `docs/sprints/064-spotify-album-import.md` (renamed from `065-` — see DEC-127) —
a **real, fully written plan**, ready to claim. Nothing is blocking it; its dependencies
(025, 026, 031, 052, 061, 062) are all complete.

The anime/albums placeholder Sprint 063's own closure created is **gone**, not blocked:
the owner asked directly whether a third anime provider was viable, Jikan was
re-measured live and reproduced the identical failure DEC-088 recorded a week earlier,
and anime turned out to have never been single-provider in the first place (AniList +
Kitsu since Sprint 038). See **DEC-127** for the full account, including why albums'
half of that question moved to the roadmap's "Not scheduled" section instead of staying
a numbered sprint with nothing to do until the owner revisits DEC-052.

## This work is on its own branch, not main

The owner asked to "branch and work on the next sprint." All five of Sprint 063's
commits are on `sprint-063-cinemeta-second-source`, branched from `main` at `344b94d`.
`main` itself is untouched. **Nothing has been merged, pushed, or opened as a PR** —
that is the owner's call (a fast-forward merge is clean; `main` has not moved since the
branch point). Confirm with the owner before merging.

## What Sprint 063 was, in one paragraph

Sprint 062 (DEC-125) removed the self-inflicted half of the movie domain's single-adapter
outage risk; it left the domain resting on one adapter. This sprint measured Cinemeta
(Stremio's keyless, IMDb-keyed metadata service — already a de facto dependency through
every poster this build renders) at 15/15 films and 10/10 series, parity with Wikidata's
own filter, and shipped it as a second source for movies and a third for series. The
identity change that made this possible: `MOVIE_IDENTITY` moved from the Wikidata `Q` id
to the IMDb id, mirroring the series domain, since a second provider makes a real
cross-provider merge possible where one adapter could not. See **DEC-126** for the full
account; the sprint file carries the per-criterion evidence.

Verified live, not just in unit tests: built the image, ran it on an isolated volume and
port, searched and added in both domains with everything healthy, then rebuilt it with
Wikidata's two hostnames resolved to an unreachable address and repeated both — both
domains' search and add survived on Cinemeta (and, for series, TVmaze) alone, each add
installing a real cover.

## One lesson worth not re-learning

**`getent hosts` inside a container can report the real DNS answer even when
`/etc/hosts` and `--add-host` are correctly applied.** `getent ahosts` (or an actual
connection attempt) is what proves an override took effect — the first check here
looked like the override had silently failed; it had not.

## Current state, concretely

- **Backend:** 1,252 tests passing (1,236 at Sprint 062's close + 16 new). **Frontend:**
  197 passing, unchanged. `make check` green (ruff, mypy, ESLint, Prettier, tsc, the
  OpenAPI contract check — untouched, since no route or schema changed). `make
  smoke-container` green, built from this branch.
- **`docs/decisions.md`** ends at **DEC-127**.
- **E2E was not run and is not owed**: the diff touches zero files under `frontend/src/`
  and changes no request path (`test_a_movie_search_survives_wikidata_raising`, the
  merge tests and the health-endpoint proof are all backend-only; the frontend already
  renders provider-degradation banners generically per Sprint 062). Sprint 061's
  pre-existing blocker (`frontend/node_modules/.vite/deps` owned by `root`, stopping
  Vite's dev server and Playwright's `webServer` auto-launch) is unrelated to this
  sprint and was not touched.
- New adapters registered in `main.state.provider_catalog`: `cinemeta` (movie),
  `cinemeta-series` (series). Neither needs a credential.

## Known-degraded, deliberately not fixed (carried from DEC-125, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies (Wikidata's localized labels vs. TVmaze's English
  names) — Cinemeta does not add a third vocabulary here, since it emits no
  `languages` value for either domain (measured absence, not an oversight).

**AniList has recovered** — DEC-125 recorded it `403`-disabled upstream on 2026-09-02;
measured live again on 2026-09-03 (DEC-127) it answered 12/12 searches, fast. Nothing
about the adapter changed; the upstream outage that prompted DEC-125's note appears to
have resolved on its own.

## New, from this sprint, deliberately not fixed

- **Two Cinemeta-sourced titles measured with no metahub poster** (`tt32142616`,
  `tt0470183` and `tt0794240` — a clean 404 each, confirmed with a direct request).
  Not a bug: DEC-103 already established a poster is a nicety on a complete record, and
  the same "some titles have none" shape was already recorded for TVmaze in Sprint
  062's worklog.
- **`/api/health/providers` reporting configuration, not reachability** still means the
  endpoint said `available: true` for `wikidata`/`wikidata-series` throughout the
  forced-outage half of this sprint's own walkthrough. Still worth fixing, still not
  here (DEC-125 already named this; this sprint just re-confirmed it applies here too).

## Private data and operational constraints

Unchanged. `exports/` is the owner's private source archive, gitignored whole,
read-only walkthrough input. Secrets, databases, uploaded imports and covers are never
committed. v1 has no auth and stays LAN-only; Calibre is opened read-only.

The owner's own instance runs on `127.0.0.1:8000` (or `4441` published). This sprint's
walkthrough ran two throwaway containers in turn, on an isolated Docker volume set and
non-default host ports (18063, then 18064), and never touched the owner's own. Both
containers, their volumes, and the local `akasha-wt063:latest` image were removed at
closure — `docker ps -a` / `docker volume ls` / `docker images` all confirmed clean.

Authorization does not carry forward: this session was asked to branch and implement a
sprint, and did exactly that locally. It does not extend to merging into `main`,
pushing, or any remote action.
