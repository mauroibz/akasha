# Handoff

## Where the project stands

On 2026-10-21 the owner accepted `docs/production-grade-proposal.md` (DEC-165) and the plan
reopened as Sprints 087–101. **Sprint 087 — Jobs that keep their word** is completed (no
user-visible change; background work and the request path are sturdier, see DEC-166).
**Sprint 088 — One contract, generated** is `ready`.

The last user-visible change: Add has an *Ebook files* drop zone. Dropped EPUBs open the import
preview already filled from each file's own metadata and cover; one click commits them into
Triage with the EPUB attached. Also on the Import strip as "Ebook files".

## Verified (final tree)

Backend 1630 · Vitest 345 · `make check` green · Playwright 146 + 2 skipped · live walkthrough
clean (220-row Goodreads import, 220/220 enrichments on first attempt). smoke-container last ran
for v2.3.0; 087 changed no deployment files.

## Known and left

- Triage pre-selects the domain default ("Read") for dropped books; "To read" may suit better.
- ePubLibre files put the original publication year in `dc:date`, which lands as edition year.
- EPUBs without an ISBN are not enriched; edit-and-refresh is the path.
- Only EPUB is read; azw3/mobi/pdf are refused by the member pattern.

## Next session

Run Sprint 088 (`docs/sprints/088-one-contract-generated.md`). The design mock the owner
approved is the canvas artifact https://claude.ai/artifact/KRWdo67P7QfirBsBK4mdRa; Sprints
090–093 build from it.

If the v2.3.0 release step did not complete: tag `v2.3.0`, watch the Release workflow, GitHub Release
from `docs/operations/release-notes-v2.3.md`. Board: `AKASHA_VERSION=2.3.0` in the board's
`.env`, `./render-compose.sh`, `docker compose pull && docker compose up -d`.
