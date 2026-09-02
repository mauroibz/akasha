# Handoff — Sprint 062 closed; v1.5.7 is prepared but **not published**

`docs/agent/state.json` reads `project_status: "complete"` with `active_sprint`,
`active_sprint_file` and `active_sprint_status` all `null`. Sprint 062 was the last one
(`FINAL_SPRINT = 62` in `scripts/validate_project.py`). **Do not assume there is a sprint to
resume** — read `docs/sprints/ROADMAP.md`'s "Future epics" and ask the owner what's next.

## The one thing that needs the owner

**Nothing in this repository is pushed.** `main` is ahead of `origin/main` by Sprint 061's
commit and all of Sprint 062's. `compose.yaml`'s default now names `1.5.7`, and **that tag does
not exist in the registry yet** — until it is published, a fresh `docker compose up` on a clean
host would fail to pull. Publishing is an owner action (`docs/operations/publishing-images.md`):

```bash
git push origin main
git tag v1.5.7 && git push origin v1.5.7   # then watch the Release run in Actions
```

Nothing else is outstanding. A rollback needs only `AKASHA_VERSION=1.5.6`.

## What Sprint 062 was, in one paragraph

The owner reported broad instability and asked whether it was the providers or something we
introduced. It was both, and the two are separable. **Three external providers were degraded at
once** — Wikidata's query-service replicas 15–17 s lagged, AniList's public API disabled upstream
(`403`), MusicBrainz throttling — and each one uncovered a defect of ours standing behind it.
Read **DEC-125** for the full account before touching any provider adapter; the sprint file
carries the per-criterion evidence.

The load-bearing one: a candidate's `language` was folded into the metadata patch for every
domain, but only `book` and `album` declare that field, so **every TVmaze-sourced series add had
been a 422 since Sprint 050** — invisible until Wikidata went down and TVmaze started answering
alone. `declares_field` now gates the fold in both `application/add.py` and `api/library.py`.

## Two lessons this sprint paid for, worth not re-learning

1. **The suite was green while anime search was broken in the running application.** The planned
   fix (raise `search_providers`' budget to 10 s) did not work, because the timeout actually
   cutting the request was the *shared client's* 5 s read timeout one layer down, and Kitsu
   spends 4–6 s before its first byte. Only the walkthrough found it. When a fix is about
   timeouts, check every layer that owns one.
2. **A test double that has drifted from the adapter it stands for hides defects exactly like a
   mock of the unit under test does.** `test_cached_add.py`'s TVmaze double reported
   `language=None` while the real adapter reported `"en"`, so the suite proved a payload the
   adapter never sends. That is DEC-025's failure mode by a different door.

## Current state, concretely

- **Backend:** 1,236 tests passing. **Frontend:** 197 passing. `make check` green.
  `make smoke-container` green (run twice — the second time after the version bump, which is
  deployment configuration and re-owes that gate).
- **`docs/decisions.md`** ends at **DEC-125**.
- **E2E was not run and is not owed** for Sprint 062: the diff touches zero files under
  `frontend/src/` and changes no request path. Note separately that Sprint 061's blocker is
  still present — `frontend/node_modules/.vite/deps` is owned by `root`, which stops Vite's dev
  server and therefore Playwright's `webServer` auto-launch. **Sprint 061's own E2E spec and
  walkthrough remain unexecuted**; that is still outstanding and is the first thing to run once
  someone has a working dev server.

## Known-degraded, deliberately not fixed (all in DEC-125)

- **Movie search rests on Wikidata alone** (DEC-098). Removing `maxlag` removed the
  self-inflicted half of the outage; a genuine Wikidata outage still takes the domain down.
- **AniList's API is disabled upstream** with no stated return date. The adapter stays: it fails
  fast, costs one wasted request, and Kitsu covers the domain. Re-check before building on it.
- **`/api/health/providers` reports configuration, not reachability.** It said `available: true`
  for AniList throughout an incident in which AniList returned `403` to every request.
- **Kitsu's latency tail** occasionally exceeds its budget; the anime search then returns `503`.
  The honest fix is a second working provider, not a longer wait for everyone.
- **`languages` mixes vocabularies** — Wikidata's localized labels (`español`) and TVmaze's
  English names (`Spanish`) land in the same field.

## Private data and operational constraints

Unchanged. `exports/` is the owner's private source archive, gitignored whole, read-only
walkthrough input. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only.

The owner's own instance runs on `127.0.0.1:8000`. Sprint 062's walkthrough deliberately ran a
separate container on an isolated volume at port 8062 and never wrote to theirs — do the same.
That container and its volume (`akasha-wt062`, `akasha-wt062-data`) were removed at closure.

Authorization does not carry forward: this session was asked to fix, test and cut a version, and
did exactly that locally. It does not extend to pushing, tagging on the remote, force-pushes or
history rewrites.
