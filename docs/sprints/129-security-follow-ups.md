# Sprint 129 — Security follow-ups

**Sprint:** 129
**Status:** in_progress
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

## Verification

Per DEC-167: the tests for the changed code, `make check`, `make audit`. No screen changes.

## Outcome

_Not started._
