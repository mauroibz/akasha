# Handoff — the numbered plan is complete

Plan revision 16. **Sprint 034 closed on 2026-08-21 and no sprint is active.** `state.json` reads
`complete` with null active fields and 001–034 in `completed_sprints`; `FINAL_SPRINT` in
`scripts/validate_project.py` is 34. Nothing has been tagged, pushed, released or deployed.

## What the import flow looks like now

Triage is a tab on `/import` (032). Calibre needs no mount: you choose your library folder and the
browser reads it, sending `metadata.db` and the covers and nothing else (033). And a re-import sends
only what is missing, because the client asks the server what it already holds first (034) —
measured at 10.55 MB for a first import and 0.99 MB for an unchanged re-sync of an 18-book library.
The mount survives beneath it all as the connector's declared `alternate`.

## Where things stand

- Gates green at closure: validator, `make check`, `make test` (backend 531, frontend 176),
  `npx playwright test` (97 passed, 2 skipped at `--workers=1`), `git diff --check`.
- The walkthrough ran four phases against the owner's real library. Read that worklog entry before
  touching the import flow.

## The next thing the owner wants

**Sprint 035 — ebook attachments on a toggle.** Deliberately after 034, because with the plan step
in place, turning it on costs one large first sync and near-nothing after, instead of 163 MB every
time. What it needs:

1. **A sixth entity type in the undo ledger.** It currently knows `entry`, `entry_shelf`, `item`,
   `item_identifier`, `shelf` — no `attachment`. Without it, undoing an import would drop rows via
   `ON DELETE CASCADE`, leave the bytes for `reclaim`, and undercount what it reverted.
2. **A format decision.** 14 of the owner's books exist as both `.epub` and `.azw3` — 163 MB for
   both, 95 MB for epub only.
3. **Skip-and-report above the 25 MiB attachment cap**, rather than failing the whole import.

The scope boundary is settled: **attaching files is a feature of the importer.** Akasha's own file
UI stays simple and file-type agnostic rather than growing toward an ebook manager. Product spec §1's
"not an ebook server" non-goal stands as written.

## Known and left

- **Playwright reports a large multipart body as zero bytes.** `request.postDataBuffer()` and
  `request.sizes().requestBodySize` both return 0 for a 10 MB upload, which silently turns an upload
  measurement into "0.00 MB". `scratchpad/w34/counter.mjs` is a counting TCP proxy that works; start
  there if you need wire sizes.
- **Two heavy `library.spec.ts` specs flake under parallel workers** — the 10,000-row DOM budget and
  the keyboard guards. Which one fails varies per run and `--workers=1` is green. They guard real
  invariants; do not loosen them.
- **`_DiskSpooledMultiPart.spool_max_size` is 1 and must not become 0.** `SpooledTemporaryFile` rolls
  over only when `max_size > 0`, so 0 means *never roll* and would restore holding a whole library in
  memory. A test pins it.
- **An unchanged re-sync shows "Local cover staged" without uploading covers.** Correct — the
  fingerprint matches, so Sprint 031's replay returns the stored batch.
- **The e2e suite proxies unstubbed `/api` calls to whatever is on :8000**, which here is the running
  container with the real library. Stub every route a spec touches or set `BOOK_TRACKER_E2E_BACKEND`.
- **This deployment runs on bind mounts.** Start it as
  `docker compose -f compose.yaml -f compose.bind-mounts.yaml up -d`; a plain `docker compose up -d`
  runs against the empty named volume and the library looks wiped.
