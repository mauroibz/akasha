# Handoff — the numbered plan is complete

Plan revision 15. **Sprint 033 closed on 2026-08-21 and no sprint is active.** `state.json` reads
`complete` with null active fields and 001–033 in `completed_sprints`; `FINAL_SPRINT` in
`scripts/validate_project.py` is 33. Nothing has been tagged, pushed, released or deployed.

## What the last two sprints changed

**032** folded Triage into `/import` as a tab and made a connector publish its own guidance, its own
error vocabulary and its own actionable failure sentences (DEC-080).

**033** removed the mount from the Calibre path (DEC-081). You choose your library folder, the
browser reads it, and the client uploads `metadata.db` plus the covers and nothing else — no
`CALIBRE_DIR`, no restart, and no handle held on a library calibre-web is already using. The mount
picker and the typed path survive as the connector's declared `alternate`, on the same tab, for
automation and for a library too large to upload.

## Where things stand

- Gates green at closure: validator, `make check`, `make test` (backend 522, frontend 171),
  `npx playwright test` (96 passed, 2 skipped), `git diff --check`.
- Both walkthrough arms passed against the owner's real library. Read that worklog entry before
  touching the import screen — it records four observations left deliberately unfixed.

## If you pick up the import boundary next

`docs/guides/adding-a-domain.md` is the instruction; technical spec §6.5 is the contract.

1. **`kind` is `upload | path | directory`.** All three are things the reader hands over. Spotify is
   an OAuth source and is none of them — that is the first design question the music epic hits.
2. **`alternate` is exactly one level deep.** A source with three ways in needs a different shape,
   not a longer chain. Conformance refuses nesting and a reused `field`.
3. **`accepts_files` is a promise about `read`**, not about the screen. `kind="directory"` without
   it is refused.
4. **A directory reader should point its ordinary adapter at `ImportSource.directory`.** The route
   has already streamed, validated and materialized the bundle at `<directory>/library`, so an
   uploaded source and a local one must normalize through the same code. `CalibreImporter.read` is
   the worked example, and it is nine lines.

## Known and left

- **`_DiskSpooledMultiPart.spool_max_size` is 1, and must not become 0.** `SpooledTemporaryFile`
  rolls over only when `max_size > 0`, so 0 means *never roll* — the opposite of what it looks like.
  Setting it to 0 would silently restore holding an entire library in memory. A test pins it.
- **The e2e suite proxies unstubbed `/api` calls to whatever is on :8000**, which on this machine is
  the running Compose container with the real library. Stub every route a spec touches, or set
  `BOOK_TRACKER_E2E_BACKEND`. `stubImporters` in `e2e/seed.ts` is the shared registry fixture.
- **This deployment runs on bind mounts, not named volumes.** Start it as
  `docker compose -f compose.yaml -f compose.bind-mounts.yaml up -d`. A plain `docker compose up -d`
  silently runs against the empty `akasha_data` volume and the library looks wiped while the real
  database sits untouched in `./data/books.db`.
- A fingerprint replay still reports "N entries added" when it added nothing. Pre-existing, cosmetic,
  and worth fixing if anyone edits that result panel.
