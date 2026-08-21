# Handoff — numbered plan complete through Sprint 035

Plan revision 17. **Sprint 035 closed on 2026-08-21 and the project state is `complete`.** Sprints
001–035 are in `completed_sprints`; active sprint fields are null; `FINAL_SPRINT` is 35. Nothing was
tagged, pushed, released or deployed.

## What now ships

The Calibre folder flow needs no mount, plans incrementally, and has an off-by-default **Also attach
the ebook files** toggle. With it enabled the browser selects one file per book in epub-first
preference order, names anything over the 25 MiB per-file cap, commits metadata first, then attaches
each wanted ebook in its own bounded request with visible progress. Re-sync sends no ebook already
held; deleting an attachment makes only that file return. Undo removes unchanged import-created
attachments and their unreferenced blobs before deleting their items, while preserving renamed,
replaced and hand-uploaded files.

The shared import layer does not branch on Calibre for that behavior: connectors declare bundle
member patterns and records declare their source files; inventory, route and ledger behavior are
generic. The file UI remains opaque and file-type agnostic—Akasha still has no ebook reader.

## Closure evidence

- `make check` passed all static, type, OpenAPI and project-validation gates.
- `make test`: 559 backend and 179 frontend tests passed.
- Full Playwright at `--workers=1`: 98 passed, 3 skipped. The third skip is the optional ignored
  real-library walkthrough when its environment paths are absent.
- Real-library walkthrough: 18 epubs / 95.4 MB attached and downloadable; unchanged re-sync sent
  zero ebooks; deleting one caused exactly one to return; UI undo left 0 entries, items,
  attachment rows and attachment blobs. Live `data/` was untouched.
- The worktree was clean after the final closure commit.

The reusable walkthrough is local at
`frontend/e2e/scratchpad/sprint35-walkthrough.spec.ts`; `frontend/e2e/scratchpad/` is gitignored.
It requires `AKASHA_WALKTHROUGH_LIBRARY`, `AKASHA_WALKTHROUGH_DATA_DIR`, and an isolated backend
using the same data directory. This keeps owner-specific paths and destructive test data out of Git
while avoiding a rewrite next time.

## Known and left

- `_bundle` still checks for a root `metadata.db` with connector-specific wording. Allowed bundle
  members are declarative now, but required root members are not. This was observed and left out of
  DEC-083 scope.
- The walkthrough logged one Open Library `provider_unreachable` after undo when asynchronous
  enrichment raced local-cover installation. Imported covers and attachment behavior were correct.
- The two heavy `library.spec.ts` cases remain load-sensitive with parallel Playwright workers;
  `--workers=1` is the established green gate. Do not loosen their DOM/keyboard invariants.
- `_DiskSpooledMultiPart.spool_max_size` must remain 1, not 0; zero means never roll to disk.
- The deployed bind-mount installation still needs
  `docker compose -f compose.yaml -f compose.bind-mounts.yaml up -d`.

## Next

No numbered sprint is active. A future session should first plan a new remediation sprint or choose
one of ROADMAP's unnumbered epics, update `FINAL_SPRINT`, and move state from `complete` according to
the normal planning protocol. Do not push, tag, deploy or release unless the owner asks.
