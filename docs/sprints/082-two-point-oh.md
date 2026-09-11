# Sprint 082 — Two point oh

**Status:** in_progress
**Depends on:** 081
**Roadmap revision:** 40

> Planned from [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §3 and §4.
> **Accepted by the owner as DEC-146.**

## Objective

Close the plan and ship it. Every document that says Akasha has no authentication is rewritten to
say what is now true, the exposure rule becomes narrower rather than deleted, the container smoke
test's existing both-mode coverage is reconfirmed against the release image, and the version
surfaces read `2.0.0` together.

## Required context

- [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §4 (what this plan
  deliberately does not do — the boundary this sprint has to write down accurately).
- `docs/decisions.md` **DEC-145** (the release procedure never published a GitHub Release, and the
  version surfaces had no cheap gate — both are this sprint's to fix or to restate), **DEC-146**.
- Outcomes of Sprints 075–081, all seven, read in full. This sprint documents what was *built*,
  not what was planned, and the two will differ.
- Every document that currently asserts there is no authentication — find them by search rather
  than from this list, but at least:
  - `/AGENTS.md` — the invariant *"v1 has no auth and must remain LAN-only"*.
  - `docs/specs/product-spec.md` §9 (the v2 deferrals), §10 row 7 (the settled decision), §11.
  - `docs/specs/technical-spec.md` §9 (*"No auth means no public exposure"*), §12.
  - `docs/operations/runbook.md` — reverse-proxy guidance.
  - `docs/operations/publishing-images.md` — the release procedure.
  - `README.md`, `.env.example` line 1, `compose.yaml`'s warning comment, `SECURITY.md`.
  - `docs/sprints/ROADMAP.md` — the "Not scheduled" entries for auth and multiuser.
- `scripts/smoke_container.sh` — AC4 and the version comparison DEC-145 rebuilt; Sprint 077's
  both-mode login/restart/logout coverage is the baseline to audit and rerun.
- `scripts/validate_project.py` — `FINAL_SPRINT`, and the place DEC-145 said a cheap
  version-surface check belongs.

## Current implementation baseline

To be re-read at activation. Expected: everything in §2 of the proposal built and passing;
`AKASHA_AUTH` defaulting to `off`; documentation across at least nine files still telling a reader
there is no authentication and must never be exposed. Sprint 077 already extended the container
smoke gate across auth off and auth on because that was required to prove its shipped boundary.

## Deliverables

1. **The exposure rule becomes narrower, not absent.** Everywhere the current rule appears, it is
   replaced by one sentence with the same force: *no internet-reachable proxy, DNS or port forward
   unless `AKASHA_AUTH=on`, TLS terminates in front, and the session cookie is `Secure`.* The
   `AGENTS.md` invariant is rewritten in place — it is an invariant a future agent will be held to
   and it must be true, not deleted.
2. **Product spec §9, §10 and §11 are rewritten.** The auth and multiuser deferrals become
   descriptions of what is built. Sharing, Calibre write-back and OPDS **stay** deferred and stay
   accurate. §10's settled-decisions row 7 gains its resolution the way row 6 did when export
   shipped.
3. **Technical spec §5.1, §7.1, §9 and §12** describe `users`, `sessions`, the two new columns on
   the import ledger and jobs, the auth routes, the cookie policy, the trusted-header mechanism
   and its peer allowlist, and the shared-versus-private table from the proposal's §2.4 as a
   canonical contract rather than a proposal's claim.
4. **The runbook gains an auth section**: turning it on for an existing install, first-run setup,
   creating the second user, what to do when a password is lost, what to do when a proxy
   misconfiguration locks everyone out, and how to run behind `tailscale serve`. Written for an
   operator at 1am, which is the standard the existing runbook already sets.
5. **`.env.example` carries every new setting** with its default and, for the trusted-proxy
   header, the warning beside the setting rather than in a document.
6. **The existing both-mode smoke test is a release gate.** Audit Sprint 077's
   `scripts/smoke_container.sh` coverage against the final user/session surface, extend it only
   where the later sprints require it, and rerun: `AKASHA_AUTH=off`, refusal before auth-on login,
   permission after login, survival across restart, and refusal after logout.
7. **The cheap version check DEC-145 asked for.** `scripts/validate_project.py` compares
   `backend/pyproject.toml`, `frontend/package.json`, `main.py`'s FastAPI `version=` and
   `frontend/openapi.json` and fails when they disagree, so `make check` catches in one second
   what only a minutes-long container test caught before.
8. **The version bump to `2.0.0`** across all four surfaces, with `frontend/openapi.json`
   regenerated.
9. **`docs/operations/release-notes-v2.0.md`**, in the shape of the existing eight: what changed,
   what migrates, what an existing install has to do (nothing, unless they want auth), and the
   upgrade path for someone turning auth on for the first time.
10. **The release procedure gains its missing step.** `docs/operations/publishing-images.md`'s
    end-to-end list gets "publish a GitHub Release from the release-notes file", which DEC-145
    recorded as missing and which is why seven releases had tags and no Release.

## Acceptance criteria

1. No document in the repository asserts that Akasha has no authentication. Verified by search for
   the phrases, not by memory.
2. The exposure rule appears in `AGENTS.md`, both specs, the runbook, `README.md`, `.env.example`
   and `compose.yaml`, and says the same thing in each — a rule with two versions is a rule nobody
   follows.
3. Product spec §9 still defers sharing, Calibre write-back and OPDS, and says nothing about them
   that Sprints 075–081 made untrue.
4. Technical spec §5.1 lists all fifteen tables; §7.1 lists every route including the auth and user
   routes; §9's security section describes the cookie policy and the trusted-header mechanism.
5. An operator can turn auth on for an existing single-user install by following the runbook alone,
   with no reference to a sprint file or a decision entry. Verified by doing it.
6. `make smoke-container` passes and exercises both modes.
7. `python scripts/validate_project.py` fails when any one of the four version surfaces is edited
   to disagree, and passes when they agree.
8. All four surfaces read `2.0.0` and `frontend/openapi.json` is regenerated and committed.
9. The release notes describe what was built, including anything the seven Outcomes recorded as a
   deviation from this plan.
10. `FINAL_SPRINT` in `scripts/validate_project.py` is `82`, and the state file closes the plan
    per `WORKFLOW.md`'s final-sprint rule.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Version surfaces agreeing passes; any one disagreeing fails | unit | `test_validate_project.py` (new, or the script's own self-check) |
| Every documented route exists on the router | api | `test_library_api.py` |
| Every setting named in `.env.example` is accepted by `Settings` | unit | `test_settings.py` |
| No setting accepted by `Settings` is missing from `.env.example` | unit | `test_settings.py` |
| Both modes, against the built image | container | `scripts/smoke_container.sh` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `python scripts/export_openapi.py`; `npm run api:check`.
- `npx playwright test`.
- `make smoke-container` — both modes, and the gate that matters most for a release.
- **Walkthrough (DEC-025):** the upgrade rehearsal. Take a copy of a real v1.8.0 database, start
  `2.0.0` against it with no configuration change at all, and confirm the library is exactly as it
  was. Then turn `AKASHA_AUTH=on` following **only** the runbook, complete setup, create the second
  user, and sign in as both. Report every place the runbook was wrong or incomplete, and fix it
  before closing — an operations document that has never been followed is a draft.

## Explicit non-scope

- **Tagging, pushing or publishing anything.** `WORKFLOW.md`'s final-sprint rule: do not tag,
  publish, deploy or push unless the owner asks. This sprint prepares the release; the owner
  makes it.
- **Sharing, public links, Calibre write-back, OPDS, passkeys.** All still deferred, all still
  accurately described as deferred.
- **New product behaviour of any kind.** If this sprint needs a feature, a previous sprint was not
  finished.
- Backfilling GitHub Releases for the four v1.5.x tags. DEC-145 records the gap; the owner chose
  the three that were published.

## Commit checkpoints

1. `[DOCS] Say what the exposure rule is now, everywhere it is written`
2. `[DOCS] Describe auth and multiuser in both specs`
3. `[DOCS] Teach the runbook how to turn auth on`
4. `[BUILD] Reconfirm both-mode smoke coverage against the release image`
5. `[BUILD] Fail make check when the version surfaces disagree`
6. `[DOCS] Release notes for v2.0.0`

## Risks and decisions to surface

- **Documentation-only sprints are where accuracy quietly dies.** The mitigation is criterion 5
  and the walkthrough: the runbook is *followed*, not reviewed. Every previous release's operations
  guidance in this project was written by someone who had just done the thing; this one must be
  too.
- **Rewriting the `AGENTS.md` invariant is the most consequential edit in the sprint.** A future
  agent is bound by it. Getting it wrong in the permissive direction is how an unauthenticated
  install ends up on the internet. Write the narrower rule; do not delete the line.
- **The seven Outcomes will disagree with this plan somewhere.** They are the authority
  (`AGENTS.md` §4). Document what was built. Do not edit a sprint's Outcome to match a document.
- **The version bump is a breaking-sounding number for a non-breaking release.** Nothing migrates
  destructively and an existing install upgrades with no action. Say that in the first paragraph of
  the release notes, the way v1.5's did.

## Outcome

**Implementation complete and gates green 2026-09-11; closure pending one owner approval — the
`AGENTS.md` invariant rewrite (deliverable 1), blocked by the agent platform's write protection
on that file until the owner consents. Everything else below is done, committed and verified.**

The plan DEC-146 opened is otherwise closed; `2.0.0` is prepared and the sprint deliberately did
not tag, push or publish anything (the owner makes the release).

- **The exposure rule is narrower, not deleted, and identical everywhere it appears:** no
  internet-reachable proxy, DNS or port forward unless `AKASHA_AUTH=on`, TLS terminates in front,
  and the session cookie is `Secure`. Written into both specs, the runbook, `README.md`,
  `.env.example`, `compose.yaml` (header comment and `security-boundary` label) and
  `SECURITY.md`, whose threat model now describes both modes and puts authentication and
  cross-user isolation in scope when auth is on. **The `AGENTS.md` invariant rewrite is the one
  piece not landed: the platform blocks agent writes to that file without owner consent, and the
  consent request timed out twice. The exact replacement is recorded in the HANDOFF; the sprint
  closes the moment it lands.**
- **Both specs are canonical for what Sprints 075–081 built.** Product spec §9's auth/multiuser
  deferrals became a Delivered paragraph; sharing, Calibre write-back and OPDS stay deferred and
  accurate; §10 row 7 resolved as delivered; §6's route block lists the auth/user routes and the
  previously missing application routes (item-types, insights, cover-candidates, exports,
  importers, health/live+ready). Technical spec §5.1 now lists all fifteen real tables
  (`provider_usage` was missing; `schema_probe` is Sprint-001 scaffolding, not a contract table),
  the `sessions` table description carries DEC-153's sliding horizon, §9's security section owns
  the cookie policy, trusted-header mechanism, peer allowlist and exposure rule, and §12 marks
  auth/multiuser delivered.
- **The runbook teaches auth.** A new "Turning authentication on" section covers the env flip,
  the setup screen (which claims the existing library for the admin), creating the second person,
  password loss, proxy lockout recovery (auth-off is reversible; password login never dies), the
  sessions screen, and a "Running behind `tailscale serve`" subsection with the three settings,
  the loopback-bind rule and the header-name-is-their-contract note. Verified by *doing* it — see
  the walkthrough below.
- **`.env.example` carries every setting** and is now pinned by two tests: every name it documents
  is accepted by `Settings` (commented or not), and every `Settings` variable is documented in it
  (image-fixed paths excepted). The sweep found and documented one real gap:
  `AKASHA_PROVIDER_DAILY_LIMITS` (DEC-045) was never in the file.
- **The version-surface gate (DEC-145's ask) ships in `scripts/validate_project.py`:** the four
  surfaces are compared on every `make check`, pyproject the source of truth.
  `backend/tests/test_validate_project.py` proves each single-surface disagreement fails and
  agreement passes; the live failure was demonstrated (package.json at `9.9.9` → validator red
  naming the file). The smoke test's four-surfaces assertion remains the container-side proof.
- **The version surfaces read `2.0.0`** and `frontend/openapi.json` is regenerated (version-only
  diff); the export and `npm run api:check` pass.
- **The both-mode smoke gate covers the final surface.** Audited Sprint 077's block (login,
  restart survival, logout, cookie shape) and Sprint 081's trusted-header block; extended with
  one block proving Sprint 081's session surface: two fresh device logins, the list naming both
  with exactly one current and a user agent, revoking the other ending only it.
- **Release notes and procedure.** `docs/operations/release-notes-v2.0.md` written in the house
  shape (versioning note first: 2.0.0 is a major number for a non-breaking release), including
  both recorded deviations — DEC-154's waived tailnet walkthrough and the
  contended-insights-at-10k numbers. `publishing-images.md`'s end-to-end list gains the missing
  "publish a GitHub Release from the release-notes file" step, with DEC-145 named as why.
- **Required tests (TDD).** `test_validate_project.py` (new, 7 tests: RED on the missing
  `version_surfaces`, GREEN after implementation, parametrized per-surface failures);
  `test_settings.py` (+2: `.env.example`↔`Settings` both directions, RED on the commented-name
  parser and on the provider-limits gap); `test_library_api.py` (+1: the documented route set
  equals the served router in both auth modes); `scripts/smoke_container.sh` (the release gate).
  Commits: `f42236d` (version check), `f9fb396` (bump), `7cf0739` (exposure rule + specs),
  `a849ddf` (smoke coverage), `c12b2a7` (release notes), `5ce4c32` (smoke-block fix),
  `c3f0a1e` (runbook addition), plus closure.
- **Exhaustive gate, frozen tree:** `make check` green; backend **1,483 passed** (1,473 + 10 new)
  at 90% coverage, frontend **325 passed**; full Playwright **138 passed, 2 configuration-dependent
  skips**; OpenAPI export and consumer check green; `make smoke-container` green end to end
  (after the in-gate smoke-block fix and full rerun), building the image from the frozen tree and
  cleaning its own disposable volumes.
- **Walkthrough (DEC-025), the upgrade rehearsal — done against real data.** A copy of the
  ZimaBoard's live production database (82 entries, migration stamp `0016`, no users table) was
  seeded into a throwaway compose project. 2.0.0 started, took the pre-migration backup, ran
  migrations 0017–0021, and served the library unchanged: all 82 entries present, every row
  owned by the seeded user, `PRAGMA foreign_key_check` clean, the source DB on the board
  untouched at `0016`. Then, following only the runbook: the setup screen created the admin
  (all 82 entries became theirs — verified in the database), the second user was created through
  the documented route, both signed in, the second user's library was empty, the admin's was
  intact, a cross-user entry id answered `404`, and the sessions list showed the current device.
  Two findings became runbook additions before closure: the unsorted-hidden-by-default
  expectation (a never-triaged library looks nearly empty on `/` after upgrade — the filter, not
  data loss), and a note that a source-checkout operator's plain `docker compose up` inherits the
  checkout's own `.env`. Rehearsal volumes, containers and temp files were all removed.
- **Deviations.** The smoke script's first sessions block failed its own first run by reading the
  sessions list with a cookie the Sprint 077 block had already logged out — a test-sequencing
  defect, fixed with fresh device logins and the full gate rerun; recorded as DEC-155. No product
  behavior changed in this sprint: the runtime diff is one comment in `config.py`, the version
  literal, and the validator's new check.
- **Future-sprint review.** There are none — this is `FINAL_SPRINT`; the plan is complete. The
  two open observations for whoever reopens it are recorded in DEC-154 (the waived tailnet
  walkthrough's residual proof) and DEC-155 (contended insights at 10k entries).
