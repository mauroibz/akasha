# Agent entrypoint

This is the single entrypoint for any coding agent working in this repository. A user instruction of `work` means: execute exactly one active sprint using this protocol, stopping only when it is complete or genuinely blocked.

This protocol follows the [Seeds](https://github.com/mauroibz/seeds) methodology for agentic development.

## 1. Establish context

From the repository root:

1. Run `git status --short --branch` and `python scripts/validate_project.py`.
2. Read, in order:
   - this file;
   - `docs/README.md` — the documentation map, which says of every document whether it is
     canonical, historical or a proposal. A dated path inside a closed sprint is not an instruction;
   - `docs/agent/state.json`;
   - the active sprint file named by `active_sprint_file`;
   - every document listed in that sprint's `Required context` section;
   - `docs/agent/WORKFLOW.md`;
   - `docs/agent/TESTING.md`;
   - the last entry of `docs/agent/worklog.md`: where the previous session stopped, what it verified, and any warning it left;
   - `docs/decisions.md` entries referenced by the sprint.
3. Inspect existing code and tests named by the sprint. Never infer their content from an earlier agent's summary.
4. Confirm that the active sprint status is `ready` or `in_progress`, all `depends_on` sprints are completed, and the worktree is clean except for changes explicitly described in `docs/agent/HANDOFF.md`.

If state is inconsistent, repair documentation-only inconsistencies when the intended state is unambiguous; otherwise stop and ask one focused clarification.

## 2. Execute one sprint

1. Change both `project_status` and `active_sprint_status` in `docs/agent/state.json` to `in_progress`, set `started_at` if it is empty, and change the active sprint file's `Status` to `in_progress`. Commit these state changes only with the first meaningful implementation slice; do not make a bookkeeping-only commit.
2. Implement acceptance criteria in listed order using test-driven development:
   - add or change a test and observe the expected failure;
   - implement the smallest coherent behavior;
   - run the focused test and relevant regression tests;
   - refactor only while tests remain green.
3. Make small conventional commits at coherent checkpoints. Do not rewrite or squash commits made before this session.
4. Stay inside sprint scope. A prerequisite defect may be fixed if necessary; record it. Future-sprint work is forbidden unless the active sprint explicitly pulls it forward.
5. Never weaken, delete, skip, or mark flaky a test merely to get green. Never fabricate command output.
6. Whenever a session ends without closing the sprint — out of budget, interrupted, or blocked — append a `docs/agent/worklog.md` entry before stopping, so the next session resumes from recorded evidence rather than re-deriving it.

## 3. Verify

Follow `docs/agent/TESTING.md`'s verification ladder. After implementation and tests are frozen, run
each distinct command in the sprint's `Verification` section once, plus `make check` and `make test`
if those targets exist and the sprint did not already name them. For UI behavior, execute the
specified browser or Playwright checks rather than relying only on unit tests. For deployment work,
build and exercise the container.

Do not rerun an exhaustive product suite merely because the only subsequent changes are sprint
Outcome, roadmap, worklog, handoff, or state documentation. Classify the post-gate diff using the
playbook and run its required closure checks. Any later change to runtime code, tests, migrations,
dependencies, build/test configuration, or generated contracts invalidates the relevant gate and
must be verified again.

A sprint is not complete if required verification is skipped. If the environment makes a check impossible, leave the sprint `in_progress`, document the exact blocker and command output in `docs/agent/HANDOFF.md`, and do not claim completion.

### Walkthrough gate

A sprint touching user-visible behavior is not complete until you have run the application against realistic data, performed the sprint's user flow end to end, and recorded in `docs/agent/worklog.md` what you exercised, what you observed, and anything that felt wrong. Passing tests are not evidence that a flow works.

This gate exists because thirteen sprints closed with green gates on a product whose entire feedback layer was invisible and whose enrichment pipeline had never once succeeded (DEC-025). Two rules follow from that failure:

- A test that substitutes a mock for the unit under test does not satisfy a correctness acceptance criterion. Behavior at an external boundary is proven against recorded real responses.
- Report what you saw, including what looked wrong but was out of scope. A defect noticed and left unrecorded is the failure mode this gate is meant to prevent.

## 4. Reconcile plan and implementation

Before the completion commit:

1. Update canonical docs for any implemented contract that differs from plan.
2. Append material decisions or deviations to `docs/decisions.md`; never silently edit history.
3. Update the active sprint's `Outcome` section with delivered behavior, tests run, commit references, and deviations.
4. Review every not-yet-completed sprint in `docs/sprints/ROADMAP.md`. Update affected acceptance criteria, dependencies, risks, or context links.
5. Keep `README.md`, examples, API contracts, migrations, and operational docs synchronized with actual behavior.

Document observed reality. Do not change the product spec merely to excuse an incomplete implementation.

## 5. Close and hand off atomically

Only after all acceptance criteria and verification pass:

1. Mark the active sprint `completed` in its file.
2. In `docs/agent/state.json`, append it to `completed_sprints` and set `last_completed_sprint`. If another sprint remains, select it and set both `project_status` and `active_sprint_status` to `ready`; if the final planned sprint just closed, follow `WORKFLOW.md`'s final-sprint rule and set the project complete with null active fields. Clear `started_at` and update `updated_at`.
3. Append a `docs/agent/worklog.md` entry for this session (done, verified-and-how, deviations, next), then rewrite `docs/agent/HANDOFF.md` for the next agent as concise current reality, not a transcript.
4. Classify every change made after the exhaustive gate using `docs/agent/TESTING.md`. For the
   normal documentation/state-only closure, run `python scripts/validate_project.py` and
   `git diff --check`; run documentation formatting or link checks when applicable. If a post-gate
   change invalidated a product gate, rerun that gate before closing.
5. Create the final documentation/state commit: `docs(sprint-NNN): close sprint and hand off`.
6. Confirm `git status --short` is empty, then write the completion report for the owner (Mauro, not a frontend developer): in plain language, the sprint that was completed, one line per acceptance criterion and how it was verified, any deviations, anything that needs the owner (accounts, keys, money, irreversible choices), and one sentence on what the next sprint delivers. Keep audit detail — commit hashes, full command output — in the sprint `Outcome` and worklog, not the report.

The active sprint pointer must never advance before the implementation is tested and committed.

## Authority and conflicts

Order of authority:

1. The user's current instruction.
2. `docs/specs/product-spec.md` for product behavior and scope.
3. `docs/specs/technical-spec.md` for implementation contracts.
4. The active sprint file for sequencing and acceptance criteria.
5. `docs/sprints/ROADMAP.md` for future intent.
6. Existing code and tests as evidence of implemented reality, not permission to contradict higher-level specs.

When documents conflict, do not guess. If the product intent is clear, reconcile lower-level documents and record the decision. Ask only when alternatives materially change user-visible behavior, data safety, security, or irreversible architecture.

## Non-negotiable invariants

- Exactly one sprint is active.
- Exactly one agent owns an active sprint; do not run concurrent implementation agents in the same worktree.
- One sprint ends with a clean worktree and all commits local on the current branch; never push unless asked.
- SQLite foreign keys are enabled on every connection; migrations are the only schema-change path.
- Imported user data is never overwritten by synchronization; explicit refresh is the only overwrite path.
- Network providers are never consulted while rendering cached library pages.
- Calibre is opened read-only.
- v1 has no auth and must remain LAN-only.
- A domain is a package under `backend/src/book_tracker/domains/`, and the shared layers never branch on which one they are holding. `if item_type == "book"` above the registry is a defect, not a shortcut — technical spec 6.6 is the contract and `docs/guides/adding-a-domain.md` is how to satisfy it.
- Internal names are permanent: the code package stays `book_tracker` and the core entities stay `items`/`entries` regardless of product branding. No session renames them to match a brand; user-facing copy is the only thing that follows the brand.
- Secrets, databases, uploaded imports, and covers are never committed.
