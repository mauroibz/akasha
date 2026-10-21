# Handoff

## Where the project stands

v2.4.0 shipped on 2026-10-21 (Sprints 087–101) and runs on the owner's ZimaBoard. The owner then
asked for a 2.5 release: Insights redrawn, gentle goals on the Diary, and Shelves redrawn. A design
canvas was reviewed and accepted as **DEC-169**: https://claude.ai/artifact/6vt1GZ5nBi5zYq67ibZh3c.
The plan reopens as Sprints 102–105. **All four are completed and the project state is `complete`.** 2.5.0 passed the full release gate and the version is bumped locally; nothing is pushed, tagged or deployed. The owner asked for the work
to be built; release, push and deploy wait for them to ask.

Waiting on the owner:

- Trust-stated-status on import (DEC-165 point 3).
- A real Hardcover export and a real Simkl export (Sprint 099).
- A real StoryGraph export, to confirm the connector built in 099.

## What changed in the last two sprints

- **Sprint 100.**
  - The library's filter chips end in *Save view*, and saved views appear in the command bar.
  - The Detail page has *Move to another library…*, which re-files an entry into another domain
    through that domain's own record (DEC-168).
- **Sprint 101.**
  - Provider health reports `working`, `degraded` or `down` from real calls, and the Add page's
    notice names a provider that has stopped answering.
  - Searches are cached for 24 hours.
  - `AKASHA_METRICS=on` serves `/metrics`.

## Verified (v2.4.0)

- `make test`: backend 1686 passed, Vitest 423 passed.
- Playwright: 147 passed, 2 skipped (the live-metadata specs, by design).
- `make check` and `make smoke-container` pass.

## Known and left

- Triage pre-selects the domain default ("Read") for dropped books; "To read" may suit better.
- ePubLibre files put the original publication year in `dc:date`, which lands as edition year.
- EPUBs without an ISBN are not enriched; edit-and-refresh is the path.
- Only EPUB is read; azw3, mobi and pdf are refused by the member pattern.
- Re-file records no undo effect; moving back is a second re-file (DEC-168).
- `test_events.py::test_the_stream_carries_each_change_to_a_job` failed once in a full run under
  load and passed in the rerun. It is timing-sensitive and recorded, not marked flaky.
- Walkthrough scripts must wait on `load`, not `networkidle`: the events stream never idles.

## Next session

No sprint is planned. 2.5.0 is ready: the gate passed (backend 1699, Vitest 425, Playwright 152 +
2 skipped, container smoke), the version surfaces say 2.5.0 and the notes are written. Pushing,
tagging, the GitHub Release and the board upgrade wait for the owner (migration 0026 runs on the
board with its pre-migration backup). Walkthroughs can use the copy of the owner's
library in the session scratchpad (`data102/`), taken from the board's 2026-10-21 nightly backup;
it is never committed. The 2.5 canvas is https://claude.ai/artifact/6vt1GZ5nBi5zYq67ibZh3c; the
2.4 mock was https://claude.ai/artifact/KRWdo67P7QfirBsBK4mdRa.
