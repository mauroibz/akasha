# Handoff — the plan is complete (Sprint 083 closed 2026-09-14)

`docs/agent/state.json` reads `project_status: complete` with no active sprint:
**every planned sprint 001–083 is completed.** Sprint 083 — "A list you wrote
yourself", the hand-written-CSV search-then-confirm importer (DEC-156, plan
revision 41) — closed green: all acceptance criteria verified, the full gate
run on the final tree (backend 1569, Vitest 330, `make check`, Playwright
142+2 skips), and the AC8 walkthrough exercised live against Open Library and
Google Books on a fresh data dir. Detail lives in the sprint file's Outcome
and the 2026-09-14 worklog entry.

## What shipped this sprint (short version)

A `list` connector (book domain): column mapping auto-detected from headers
(accents folded) or picked on the screen; rows with no identity; a `matching`
batch state with one durable sequential `search_import_rows` job per preview
searching the row's own domain's providers, quota-aware, rate-limited; top-3
proposals per row in `import_proposals` (migration 0022); confirm re-stages the
row from the provider's full payload with the identity normalized the way the
add path does (canonical `isbn` — covers then arrive through the post-commit
enrichment backfill); discard keeps the row exactly as typed, including after a
confirm ("Undo my answer"); commit refused while `matching`.

## Known and left, in the order they are likely to bite

1. **The version surfaces all read `2.0.0`** (DEC-155). Sprint 083's work is in
   the tree, unpublished — the hotfixes (DEC-157), akasha-prune (DEC-158) and
   this sprint ship with the next image build. The release itself is
   owner-directed (the publishing-session shape, `references/publishing-a-
   release-session.md` in the seeds skill, is the precedent).
2. **DEC-154's residual proof** (the Tailscale tailnet walkthrough) is still
   owed by the owner, unrelated to this sprint.
3. **Contended insights at 10k entries** (DEC-155) remains unowned by a sprint —
   a fresh-scale finding, recorded in the decisions log for whoever plans the
   next line of work.
4. **The dev machine's standing `akasha-akasha-1` container and `local-081`
   image** are prunnable once the board is upgraded past 2.0.0 (owner action).

## If the owner directs more work

The state machine's rule (WORKFLOW.md): a regression discovered now belongs to
a newly planned remediation or extension sprint — the DEC-079 plan-extension
shape (state `complete → ready` with a new sprint file at `ready`, FINAL_SPRINT
moved, plan revision bumped, one `docs:` commit). Nothing in the roadmap's
"Not scheduled" list has changed.

## Session notes

- The interrupted frontend session left uncommitted residue with no worklog
  entry; this session audited it (commit `6f72992`'s message accounts for every
  file) and closed the sprint on top.
- Three defects found and fixed during closure are recorded in the Outcome
  with their TDD entry points: discard-after-confirm leaving provider data,
  the cross-domain row search, and the raw `isbn13` identifier key. The first
  two had shipped in D3/D4 believing the contract was met — the live
  walkthrough is what proved otherwise.
- `frontend/scripts/walkthrough-list.mjs` is the re-runnable AC8 script; it
  needs a fresh data dir per attempt (preview replays by fingerprint) —
  backend :8002, frontend dev :5175 with `AKASHA_E2E_BACKEND`.
