# Handoff — Sprint 083 (ready): a list you wrote yourself

`docs/agent/state.json` reads `project_status: ready` with **Sprint 083 active**
(`docs/sprints/083-a-list-you-wrote.md`, `Status: ready`, plan revision 41, DEC-156). The plan
reopened on 2026-09-13 at the owner's request: an importer for a hand-written CSV/TXT —
`exports/Libros.csv`, 104 rows, title/author columns, **no identifiers** — unlike every existing
connector, which reads platform exports whose IDs made bulk matching trivial.

**Before this sprint starts: two hotfixes landed in the tree (DEC-157, worklog 2026-09-13).**
Triage's selection bar now has the red Discard action (confirm dialog, one `DELETE
/api/entries/bulk` request over the shared selection shape), and a detail page opened from a
triage row shows "← Triage" instead of "← Library". Verified through the full gate plus a live
walkthrough; `frontend/openapi.json` was regenerated for the new route. Nothing in Sprint 083's
contract is affected — but its e2e stubs route `**/api/entries/bulk` by method now, which the
discard specs in `frontend/e2e/triage.spec.ts` show the pattern for.

## What Sprint 083 delivers (read the sprint file for the contract)

A `list` connector (book domain) with a screen-pickable column mapping (auto-detect by header,
first-two-columns fallback); a new `matching` batch state with one durable `search_import_rows`
job per preview that searches the domain's providers **sequentially, one row at a time**
(rate-limited, quota-aware, resumable), storing top-3 merged proposals per row in a new
`import_proposals` table (migration 0022); confirm re-stages the row from the provider's full
payload, discard keeps the typed row; commit is refused while `matching`. The three owner
decisions (background matching before commit, full payload on confirm, title/author only —
extra columns deliberately unmapped, "queda a futuro") are recorded in the sprint file and
DEC-156.

## Where the research left the ground truth

Measured 2026-09-13, file:line in the sprint file's Required context and baseline sections:

- `Importer.match` is a local-library seam only; provider search lives in
  `application/providers.py:search_providers` (concurrent, 10 s bound, `merge_and_rank`).
- `ImportService._validate` (`application/imports.py:190`) refuses undeclared identifier kinds —
  the new connector declares `identity_kinds = frozenset()` and emits none.
- The job system is general (`infrastructure/jobs.py`, `JobRunner` in `main.py:292`'s handler
  table, `RateLimiter(0.5)` at `main.py:275`, `ProviderQuota` blocking for background work);
  `GET /api/import/jobs/{id}` already exists (`api/imports.py:771`).
- `import_batches.state` is free text (no CHECK — migration 0016 constrained only `kind`), so
  `matching` needs no migration on that table; only the proposals table is new.
- The CSV's traps are enumerated in the sprint baseline: trailing-space header `Editorial `,
  transposed `Homero,Iliada` row, collection volumes (`Duma key 2`), typos, two quoted titles,
  two dictionary rows, `et al` author. It stays in the git-ignored `exports/` — never committed;
  tests use a synthetic fixture shaped like it.
- Google Books is keyed and enabled in this checkout's `.env`; Open Library is keyless.

## Known and left, in the order they are likely to bite

1. **The version surfaces all read `2.0.0`** and the validator gates them (DEC-155). Sprint 083
   adds no release; do not bump them.
2. **DEC-154's residual proof** (Tailscale tailnet walkthrough) is still owed by the owner,
   unrelated to this sprint.
3. **Contended insights at 10k entries** (DEC-155) remains unowned by a sprint.
4. **The dev machine's standing `akasha-akasha-1`** container and `local-081` image are prunable
   once the board is upgraded to 2.0.0 (owner action).
5. **Sprint 083's walkthrough** must prove the proposal pipeline against recorded real Open
   Library responses (DEC-025), not mocks; capture the fixtures early in the sprint — if Open
   Library is shedding (the DEC-108 maxlag incident class), the capture script needs patience
   and the fixtures README records observed throttling.

## Protocol notes for whoever executes

- This was a docs-only planning session: no state flipped beyond the plan revision itself, no
  code changed, `make test` not owed (no application code changed). Claim the sprint with
  `python scripts/sync_sprint_state.py --sprint 083 in_progress` when starting.
- The sprint file's Commit checkpoints, Verification section and explicit non-scope are binding.
  The "Not scheduled" section of the ROADMAP is untouched by this reopening.
