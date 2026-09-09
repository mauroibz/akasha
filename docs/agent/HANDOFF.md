# Handoff — Sprint 078 awaits its real-phone walkthrough

`docs/agent/state.json` reads `project_status: "in_progress"`, `active_sprint: "078"`,
`active_sprint_file: "docs/sprints/078-the-way-in.md"`, `active_sprint_status: "in_progress"`,
`last_completed_sprint: "077"`, and `plan_revision: 40`. Keep it there: implementation and
automated verification are complete, but the sprint's only non-automatable acceptance criterion
has not been observed on the owner's device.

## Delivered and committed

- `12d5f82`: shared typed refusal handling across all six frontend API modules.
- `230464b`: standalone login form and password-manager HTML contract.
- `59fed62`: cached `/me` coordinator, outside-shell auth routes, safe return destination and
  mid-session refusal handling.
- `969e55f`: first-run setup that claims and immediately reveals the existing library.
- `c10a3e2`: desktop/mobile-header account control and sign-out with private-cache clearing.
- `71dc706`: concurrent refusals cannot overwrite the first requested destination.
- `afea4fb`: auth-on end-to-end flows, 390 px/keyboard/44 px coverage and login/setup axe checks.

Auth-off stays invisible through the default e2e fixture. Login and setup are lazy chunks outside
`AppShell`. Passwords remain local form state; session credentials remain only in the HttpOnly
cookie. No backend or OpenAPI contract changed. Review the final worklog entry for TDD detail and
the complete verification evidence.

## Green gates

- `make check`: passed.
- `make test`: 1,421 backend and 318 frontend tests passed outside the filesystem sandbox. The
  sandbox run showed its known FastAPI TestClient futex stall, not a test failure.
- `npx playwright test`: 134 passed, 2 configuration-dependent skips outside the sandbox. The
  sandbox cannot connect to its loopback webserver (`EPERM`).
- `npm run build`: passed; entry chunk 88.10 kB / 26.25 kB gzip, with separate login/setup chunks.
- Disposable-container walkthrough at 390 px: setup claimed a seeded *Rayuela*, sign-out/sign-in
  worked, and the same browser session survived a real container restart. Four taps excluding
  typing; scratchpad Playwright result 1 passed. All exact disposable container/image/volumes were
  removed, and read-only inventory showed no residue.

## Exact blocker and next action

The required walkthrough must still be performed on a real phone over Mauro's tailnet. In Chrome
and Firefox, confirm that the browser offers to save the password after successful login and to
fill it on the next visit. Leave that signed-in session overnight, then confirm the application
opens the next morning without another login. Record the browser names, save/fill observations,
next-morning result and total tap count.

If all observations pass, no product gate needs rerunning unless code/tests/configuration change:
update Sprint 078's Outcome, atomically mark 078 completed and 079 ready, append the closure
worklog/handoff, run `python scripts/validate_project.py` and `git diff --check`, and commit
`[DOCS] Close sprint 078 and hand off`. If the manual walkthrough finds a defect, resume TDD and
rerun every invalidated gate. Do not advance the sprint based on the disposable-container proxy.

The owner's standing development stack (`akasha-akasha-1`) was never stopped or changed. No
account, key, paid service, runtime data or irreversible owner decision was created.
