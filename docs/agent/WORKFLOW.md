# Autonomous sprint workflow

This document expands the mandatory protocol in `/AGENTS.md`. It is designed for a fresh agent with no conversational history and for recovery after interruption.

## State model

`docs/agent/state.json` is the only machine-readable sprint pointer.

Allowed project statuses:

- `ready`: active sprint may be claimed;
- `in_progress`: implementation started but is not complete;
- `blocked`: work cannot continue without external input or unavailable required infrastructure;
- `complete`: every planned v1 sprint is complete.

Sprint files separately use `planned`, `ready`, `in_progress`, `blocked`, or `completed`. Exactly one non-completed sprint may be `ready`, `in_progress`, or `blocked`, and it must be the active file in state. Future sprint summaries in `ROADMAP.md` remain `planned` until activated.

State transition:

```text
ready -> in_progress -> completed + next ready
                   \-> blocked -> in_progress
```

There is no `completed -> in_progress` transition. A regression discovered later belongs to the current sprint as prerequisite repair or to a newly planned remediation sprint, with a decision-log entry.

## Claiming work

No lock service is provided. The repository and worktree are the lock.

Before editing:

1. inspect branch, status, recent commits, state, active sprint, and handoff;
2. if another process/agent is working in this worktree, stop;
3. if the state says `in_progress`, treat it as interrupted work, not permission to restart;
4. inspect diffs and tests, then continue from evidence;
5. do not reset, clean, stash, amend, or discard unknown changes.

A dirty worktree with no handoff explanation is ambiguous. Ask the user before destructive recovery.

## Context budget

Read narrowly but completely:

- always read `AGENTS.md`, state, active sprint, workflow, handoff, the last worklog entry, and relevant decisions;
- read only product/technical sections named by the active sprint, then follow links needed to understand invariants;
- inspect actual implementation and focused tests before changing them;
- scan the roadmap after implementation, not every future detail before each small edit.

Summaries never override code inspection or canonical specs.

## TDD and implementation loop

For each acceptance behavior:

1. identify the cheapest authoritative test layer;
2. write a test that fails for the intended reason;
3. run it and preserve the failure output in working context (not documentation transcripts);
4. implement a small vertical behavior;
5. run the focused test, then neighboring tests;
6. refactor, format, and commit a coherent green slice;
7. update docs near the behavior while context is fresh.

Prefer behavior tests over mocks. Mock network, time, randomness, and host paths at boundaries. Never make normal tests depend on public services.

## Commit rules

- Conventional subjects: `feat:`, `fix:`, `test:`, `refactor:`, `build:`, `docs:`.
- Commit generated lockfiles and migrations with the code that requires them.
- Never commit secrets, runtime data, staged imports, covers, local DBs, or `.env`.
- Do not amend/rebase prior-agent commits or push unless explicitly asked.
- A sprint can contain several implementation commits and one final state/handoff commit.
- Commit hashes belong in the sprint Outcome because they are audit history, not persistent assistant memory.

## Session worklog

`docs/agent/worklog.md` is the append-only, one-entry-per-session memory layer between `docs/decisions.md` (durable architecture decisions) and the sprint `Outcome` (per-sprint delivered behavior). It exists so a session that resumes an in-progress sprint does not re-derive or silently redo what an earlier session already tried.

- Append an entry whenever a session ends — sprint complete, still in progress, interrupted, or blocked — using the format at the top of the file.
- Record what was actually verified and how, and every dead-end or workaround the next agent would otherwise rediscover. Terse and factual.
- Never edit or delete a prior entry; correct the record by appending a new one.
- This does not replace code inspection or the canonical specs; a worklog entry is evidence of what a session did, not authority over intended behavior.

## Clarification policy

Ask only when the answer materially changes:

- user-visible semantics;
- irreversible schema/data migration;
- data deletion or overwrite behavior;
- security/exposure boundary;
- paid/external service choice;
- a settled product decision.

For reversible implementation details, choose the simplest option consistent with the specs, test it, and log material reasoning. The four defaults in technical spec section 12 are authorized defaults, not blockers.

A clarification message must contain one focused question, the options, trade-offs, and a recommended default. Mark state `blocked` only if useful work cannot continue without the answer.

## Deviation policy

A deviation is any material difference in behavior, API, schema, dependency/architecture, operations, or sprint boundary.

- Correctness repair: update technical spec and decision log.
- Product behavior change: requires user approval unless already an explicit default.
- Work pulled forward/back: update active sprint Outcome and every affected future sprint.
- Failed planned approach: record evidence and replacement, not a defensive essay.
- Minor file-name/refactor differences need no decision entry if contracts are unchanged.

Never rewrite an old decision to hide that it changed. Append a superseding entry and cross-reference it.

## Verification evidence

The active sprint names required commands. Record concise actual results in its Outcome, for example test counts, build success, and smoke-check behavior. Do not paste huge logs. A command not run must be labeled `NOT RUN` with reason; required checks then prevent completion unless the user explicitly changes acceptance.

Visual behavior requires browser/Playwright execution. Container behavior requires a built/run image. Database migration behavior requires migrating real temporary SQLite files. A unit test is not a substitute for these checks.

## Blocked handoff

When blocked:

1. preserve all useful green work in commits;
2. set state and sprint to `blocked`;
3. append a `docs/agent/worklog.md` entry and write `HANDOFF.md` with exact blocker, reproduction command/output summary, attempted approaches, safe next action, and dirty files if any;
4. run all checks that remain meaningful;
5. commit documentation/state if the worktree can be left coherent;
6. ask the focused clarification.

Do not advance the sprint.

## Interrupted-work recovery

If the prior agent disappeared while `in_progress`:

1. inspect `git status`, `git diff`, recent commits, sprint Outcome, and handoff;
2. run focused tests for changed areas before editing;
3. distinguish uncommitted user work from documented agent work; never discard either;
4. complete or revert only changes you can attribute and understand, using normal commits;
5. update handoff after restoring a coherent state.

If tests and docs disagree, actual test output proves current behavior, while higher-authority specs determine intended behavior.

## Sprint closure checklist

- [ ] Every deliverable and acceptance criterion is implemented.
- [ ] Required negative/failure tests exist.
- [ ] Focused, regression, quality, UI/container checks all ran as required.
- [ ] `git diff --check` passes.
- [ ] Canonical docs/OpenAPI/examples match implementation.
- [ ] Decision log includes material deviations.
- [ ] All future sprints were impact-reviewed.
- [ ] Active Sprint Outcome contains concise evidence and commits.
- [ ] Next detailed sprint file is expanded from template and references actual paths.
- [ ] Worklog entry appended for this session.
- [ ] State and handoff point to that sprint.
- [ ] Project validator passes.
- [ ] Final closure commit exists.
- [ ] Worktree is clean.

## Final sprint

After the final planned sprint passes — Sprint 026 under roadmap revision 8 — set project state to `complete`, set `active_sprint` and `active_sprint_file` to `null`, preserve the completed list, and write a release-state handoff. Do not tag, publish, deploy, or push unless the user asks.
