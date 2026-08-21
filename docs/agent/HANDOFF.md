# Handoff — Sprint 035 is planned and ready

Plan revision 17. **Sprint 034 closed on 2026-08-21; Sprint 035 is planned and `ready`, not
started.** `state.json` names `docs/sprints/035-ebook-attachments.md` with 001–034 in
`completed_sprints`; `FINAL_SPRINT` in `scripts/validate_project.py` is 35. Nothing has been tagged,
pushed, released or deployed.

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

## The next sprint

**Sprint 035 — Ebook attachments on a toggle**, planned in its own file and recorded as DEC-083.
Read the sprint file; the summary is that a Calibre import can bring the ebooks along on a toggle
that is off by default, one file per book, epub first.

Three things are settled and should not be re-litigated at execution time:

1. **The undo ledger is the real work.** `UndoService` retains any item that has an attachment
   (DEC-047), so an import that attaches files makes every imported book un-undoable unless a sixth
   `attachment` entity type lets the ledger tell an imported file from a hand-uploaded one. Take
   this before the toggle.
2. **One request per file, after the batch commits.** The bundle route's ceiling is per request, so
   folding ebooks into the preview bundle caps the feature at roughly forty books.
3. **`_bundle_member` has to become connector-declared.** It hardcodes the Calibre bundle shape in a
   shared route. Change the tail, keep the traversal guard.

The scope boundary is settled: **attaching files is a feature of the importer.** Akasha's own file
UI stays simple and file-type agnostic. Product spec §1's "not an ebook server" non-goal stands as
written.

One thing the owner should see before execution starts: the disk curve — 95 MB for this library,
roughly 3.2 GB for 600 books, and backups at ~1.0 effective copies only while `BACKUP_DIR` shares a
filesystem with the data directory. Note also that **calibre-web-automated is being retired**, so
Akasha's blob store becomes the only copy of these files that is backed up. Undo and restore are
load-bearing accordingly.

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
