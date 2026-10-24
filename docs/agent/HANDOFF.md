# Handoff

## Where the project stands

**2026-10-23:** the owner sorted a brainstorm after 2.7.0 (DEC-176) and approved two of four
resurfacing mockups (DEC-178). Sprints 109–121 are completed and committed on `main`,
**unreleased on top of 2.7.0**. **2026-10-24:** the owner's first look planned 122–127 (DEC-179);
Sprint 122 is ready.
Migrations 0028–0032 are new (location and loans, duplicate dismissals, score events with
triggers, score ranks, shelf-suggestion dismissals).

What the line added, by screen:

- **Library card:** *Undo* after a status or score change. Filters for place and *Lent out*.
- **Detail page:** *Where* and *Lent* rows; *Over time* (how the score changed, and why);
  *Start again*; *Still an 8?* when a scored entry is finished again; Edition facts show only
  what they have and offer *Fill from provider*.
- **`/lent`**, **`/deck`** (chores: the inbox, *Still want this?*, *Find a cover*,
  *Look at old scores again*, *Put your scores in order*, *Duplicates*), **`/rank`**,
  **`/tiers`**.
- **Diary:** *All years* (one timeline with score changes), and *Your 2025 in review*.
- **Shelves:** a *Suggested* ledge (a creator, a series, one work across libraries).
- **Insights:** *Put your 8s in order* and *See them as tiers*.

Waiting on the owner:

- **DEC-178's reading of the mockup note.** The owner wrote that 02 might not be opened unless
  prompted; that describes 03 (the revisit deck), which was built. If 03 was meant, Sprint 121
  is one commit (`8b61b07`) to revert.
- A 2.8 release (version surfaces, release notes, `make smoke-container`, tag) when asked.
- Still open from before: trust-stated-status on import (DEC-165 point 3); real Hardcover,
  Simkl and StoryGraph exports (Sprint 099).
- Homelab sync is GitHub issue #31; the commonplace book is a v3 candidate (DEC-176).

## Verified

- Per sprint, as DEC-167 asks: the tests for the changed code, `make check`, the Playwright
  specs for each changed screen, and a walkthrough on a fresh `scripts/walkthrough.py`
  backend with live providers for every sprint that changed a screen (recorded per sprint).
- Once for the whole line, on 2026-10-23: `make test` — backend 1787 passed, Vitest 524
  passed; full Playwright — 200 passed, 2 skipped (live metadata, by design); `make check`.
  The first full run found two things outside the sprints' per-change sets, both fixed: the
  pinned route list (`1345575`) and the Settings *Chores* link's touch target (`d507930`).
  `rescore.spec.ts` failed once under full parallel load and passed alone and in the next
  full run; timing-sensitive, recorded, not marked flaky.
- Not run: `make smoke-container` (owed before a release).

## Known and left

- After the last light of a reread the status stays *Reading* (DEC-175 by design).
- At 390px the detail page's personal-region dates wrap ("2026-10-" / "23"): each row keeps
  room for its hidden *Change* button.
- The rank page's back link says *Library* even when opened from Insights.
- *Find a cover*: an installed cover is not taken back by *Undo* (no remove-cover endpoint).
- Triage pre-selects the domain default ("Read") for dropped books; "To read" may suit better.
- EPUBs without an ISBN are not enriched; only EPUB is read.
- Re-file records no undo effect (DEC-168).
- `test_events.py::test_the_stream_carries_each_change_to_a_job` is timing-sensitive.

## Next session

No sprint is planned. Run checks under `set -o pipefail`: `make check | tail` hides a failure
from `&&` (it happened twice this line). Walkthroughs: `uv run python ../scripts/walkthrough.py`
from `backend/`, vite on 5180 with `AKASHA_E2E_BACKEND`; start a fresh backend after backend
changes (it does not reload); stop servers by port (`fuser -k`), since `pkill -f` matches the
calling shell. The board runs 2.7.0; its upgrade is the owner's.
