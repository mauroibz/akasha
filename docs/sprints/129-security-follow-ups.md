# Sprint 129 — Security follow-ups

**Sprint:** 129
**Status:** completed
**Roadmap revision:** 53
**Depends on:** 128
**Owner:** Mauro

## Objective

The repository-side follow-ups the owner approved after Sprint 128 (DEC-181): refusals at the
boundary are visible in the log, known-vulnerable dependencies fail CI, the last quadratic
title regex is linear, and the public overlay signs idle devices out after a month.

## Required context

- DEC-180, DEC-181; `docs/sprints/128-public-exposure-hardening.md` (Outcome: "Not fixed,
  recorded").
- `backend/src/book_tracker/api/auth.py`, `app/middleware.py`, `domain/normalization.py`,
  `application/library.py`, `compose.public.yaml`, `.github/workflows/ci.yml`, `Makefile`.

## Deliverables

1. `api/security_log.py`: one JSON line with `category: "security"` per failed, limited and
   successful login, setup-code guess, password-change guess and cross-site refusal.
2. `_EDITION_NOTE` excludes brackets inside the note (linear).
3. `compose.public.yaml` sets `AKASHA_SESSION_DAYS` to 30 by default.
4. `make audit` (pip-audit on production requirements, `npm audit --omit=dev`) and a CI job
   running it.
5. The runbook's *Watching for attacks*.

## Acceptance criteria

1. Each refusal leaves its line with the client and username, never the password (tested).
2. `work_key` on 200,000 unclosed brackets finishes in under a second (tested).
3. The overlay contract test names the 30-day default.
4. `make audit` passes on the current lockfiles.

## Scope added during the sprint (DEC-182)

6. Robustness: transactional upgrades, digest-checked pre-migration backup reuse, prompt
   shutdown with open event streams, best-effort response cache, resumable import installs,
   fsynced and self-repairing blobs, final job cancellation and dead-lettering, a runner that
   stays stopped.
7. Performance: batched entry hydration, chunked exports, first-page-only totals and facets,
   memoized text folding, `synchronous=NORMAL`, join indexes (migration 0035), a one-column
   cover check, immutable hashed assets with 304s, gzip, calmer React Query defaults, and a
   lighter first load.

## Verification

Per DEC-167: the tests for the changed code, `make check`, `make audit`. No screen changes.

## Outcome

Delivered 2026-11-21 on branch `ccr-61c66a6d-g1wptf`, after Sprint 128 merged (#38).

**Security follow-ups** (`c9d9cca`, `d104edd`, `79dffa0`, `21a6fc5`, `a2ed1f1`): the
`category: "security"` log lines; the linear edition-note regex (200,000 unclosed brackets in
under a second); 30-day sessions on the public overlay; `make audit` and its CI job (pip-audit:
no known vulnerabilities; npm: 0); the runbook's *Watching for attacks*.

**Robustness** (two read-only audits, then fixes, each with a test that failed first):

- One transaction per upgrade (`b170087`, `c5753e5`): 0034 failing after its `CREATE TABLE`
  leaves the database at 0033 and a retry succeeds.
- Pre-migration backups reused only while their content digest matches the live library
  (`21afdaf`).
- Shutdown with an open `/api/events`: 0.13 s after SIGTERM, measured with a real uvicorn
  (was more than the 20 s grace period, then SIGKILL) (`34b402b`).
- A locked response cache no longer fails a provider that answered (`5903895`).
- Blobs fsynced before their rows commit; a damaged blob is replaced on re-upload
  (`4e1a9f4`).
- Import installs resume after a crash, and staging is kept until installed (`36f3ee3`,
  `d988b3c`); a kept batch is retried hourly, not every idle second (`e5408fa`).
- Cancelled jobs stay cancelled; jobs whose lease keeps expiring are dead-lettered
  (`5a560d1`); enrichment re-checks an undone batch inside its write (`af46656`);
  import search resumes after answered rows (`779b58b`).
- A runner told to stop before its first step stays stopped (`ea188e6`), which was the cause
  of `test_the_stream_carries_each_change_to_a_job` failing about one run in five; the test
  now holds the job in `running` across a poll (`7bde257`, 8 of 8 green).

**Performance** (measured on a 10,000-entry library, same machine, medians):

| Path | Before | After |
|---|---|---|
| Library page of 100 | 183 ms, 705 queries | 40 ms, 11 queries |
| Diary (1,666 entries) | 2.8 s, 13,330 queries | 116 ms, 30 queries |
| Gaps / timeline / now | 326 / 87 / 49 ms | 37 / 13 / 15 ms |
| JSON export over HTTP | 7.1 s | 1.6 s |
| Insights creators / publisher | 344 / 279 ms | 231 / 113 ms |
| First-load JS on the wire | 929 KB | 228 KB |
| Library page JSON | 89.6 KB | 4.3 KB (gzip) |
| Revalidating assets | full bodies | 0 bytes (immutable, 304) |

Commits `75ef98a`, `93f7140`, `9454688`, `f72b609`, `0db66fb`, `355c88f`, `56d6a2f`,
`7e22e8b`, `f141875`, `f8f299b`, contract `2c183c3`. Migration `0035_join_indexes`.

**Found in the walkthrough and fixed** (`GoalInvite`): with the year's count arriving after the
first render, the Diary's invitation offered "Aim for 12" beside picks of 24, 36 and 52, none
selected; the choice is now a position among the picks (test first).

**Verification:** `make check`; `make audit`; Vitest 557 passed; Playwright `diary-goal`, `auth`,
`library`, `add-detail` (41 passed); backend suite 2003 passed, 1 failed (the
root-only `test_prune_items` case, green in CI). Walkthrough on a seeded
10,000-entry library with auth on: library, Diary, detail, Insights, Shelves, Import load with no
console errors apart from the fixture's missing cover files; refocusing the window made zero API
requests; `/api/entries` is gzip and `no-store`; hashed assets are `immutable`.

**Deviations:** FastAPI's cursor pages now return `null` total and facets (contract change);
React Query no longer refetches on focus, so another device's change shows after 30 s on the next
navigation (DEC-182 point 6).
