# Handoff

## Where the project stands

Sprint 086 ("drop ebook files") is **completed and closed**; the plan stands complete at 86/86.
v2.3.0's version surfaces and release notes are committed.

The last user-visible change: Add has an *Ebook files* drop zone. Dropped EPUBs open the import
preview already filled from each file's own metadata and cover; one click commits them into
Triage with the EPUB attached. Also on the Import strip as "Ebook files".

## Verified (final tree)

Backend 1617 · Vitest 345 · `make check` green · Playwright 146 + 2 skipped · smoke-container
green · live walkthrough clean (three real EPUBs, fresh data dir).

## Known and left

- Triage pre-selects the domain default ("Read") for dropped books; "To read" may suit better.
- ePubLibre files put the original publication year in `dc:date`, which lands as edition year.
- EPUBs without an ISBN are not enriched; edit-and-refresh is the path.
- Only EPUB is read; azw3/mobi/pdf are refused by the member pattern.

## Next session

If the release step did not complete: tag `v2.3.0`, watch the Release workflow, GitHub Release
from `docs/operations/release-notes-v2.3.md`. Board: `AKASHA_VERSION=2.3.0` in the board's
`.env`, `./render-compose.sh`, `docker compose pull && docker compose up -d`.
