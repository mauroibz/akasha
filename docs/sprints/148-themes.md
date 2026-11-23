# Sprint 148 — Themes

**Sprint:** 148
**Status:** completed
**Roadmap revision:** 56
**Depends on:** 147
**Owner:** Mauro

## Objective

Four theme presets join *Ink* and *Paper*, picked from Arrange and Settings.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 3.9 and the mockup.
- DEC-165 (*Ink* and *Paper*), DEC-026 (tokens; the score ramp), `docs/brand/BRAND.md` (the dot is amber).
- Frontend: `index.css`, `lib/theme.ts`, `lib/theme.test.ts`, `index.html` (the inline script), `pages/SettingsPage.tsx`, the Arrange panel.

## Current implementation baseline

Two themes as token sets under `[data-theme]`; the choice is stored in the browser and set before first paint; every text pair is held to AA by a test.

## Deliverables

1. **Presets.** *Moss*, *Claret*, *Dusk* (dark) and *Sakura* (light) as complete token sets from the mockup, adjusted until every pair passes AA.
2. **The picker.** Swatches in Settings and in Arrange; the choice applies at once and before first paint on the next load. The device preference still decides between *Ink* and *Paper* when nothing is chosen.
3. **What does not follow.** The score ramp keeps its meaning and stays legible on every preset; the mark's dot stays amber.

## Acceptance criteria

1. Each preset passes the contrast test for every pair the existing themes are held to.
2. Choosing a preset survives a reload with no flash of another theme.
3. The score colours on every preset pass AA against the surface they sit on.
4. The axe checks pass on the Library and the Journal in every preset.

## Required tests (TDD)

`lib/theme.test.ts` extended per preset; the picker (Vitest); `e2e/accessibility.spec.ts` per preset on two screens.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*. This sprint closes DEC-193's line: `make test` and the full Playwright suite are the release's.

## Explicit non-scope

Free colour pickers. Per-medium themes.

## Commit checkpoints

`[ADD]` four presets; `[ADD]` the picker; `[DOCS]` close.

## Risks and decisions to surface

- The presets' names and number are the owner's to change.

## Outcome

Completed 2026-11-23 (DEC-193). Commit: `fb6c231`. This closes the 4.0 line.

- **Presets.** *Moss*, *Claret*, *Dusk* (dark) and *Sakura* (light) as complete token sets in
  `index.css`. The dark ones carry *Ink*'s score ramp and *Sakura* carries *Paper*'s.
- **The picker.** `features/theme/ThemePicker.tsx`: swatches for *Match my device*, the two
  themes and the four presets, in Settings and (compact) while arranging the Library. A choice
  applies at once; `public/theme-init.js` knows the six names, so a preset is on the page
  before it paints.
- **What does not follow.** The score ramp and the mark's dot.

Acceptance: 1 and 3 by `lib/contrast.test.ts` (24 pairs for each of six themes, 144 checks);
2 by `lib/theme.test.ts` and `e2e/themes.spec.ts` (the theme at parse time, and a reload);
4 by `e2e/themes.spec.ts` (axe on the Library and the Journal in each preset).

Verification, this sprint: Vitest 760 passed; `e2e/themes.spec.ts` 5 passed; the Library in
each preset and Settings in *Dusk* looked at in the running app at 1440 and 390 px.

**The line's gates**, run on this tree because it is the last sprint: `make check`;
`make test`, backend 2,229 passed and Vitest 760 passed; every Playwright project (chromium,
heavy-library, production-bundle) 249 passed and 2 skipped by design; `make audit` clean.
`make smoke-container` was NOT RUN: it builds and runs the image, which is a release step and
no release was asked for.

Three defects the full suites found, fixed here, each one something a per-sprint run had not
covered:

- Migration 0040 froze the three ways a day is lit in a `CHECK` constraint; the project's
  rule is that the schema never freezes an application vocabulary
  (`test_migrations.py`). The constraint is removed and the words are checked where they are
  written. The migration had not been released.
- `test_tmdb_recommendations.py` read *More like this* from `/api/home` by default; since
  Sprint 141 it is a showcase the person places. The test places it.
- The production-bundle spec clicked the navigation's *Add* link, gone since Sprint 140. It
  opens the Journal, also a lazily loaded route.

Deviations: none in what was built. The presets' names and number are as the mockup drew
them; they are the owner's to change.

Impact on later sprints: none planned. The version surfaces still read 3.1.0: moving them
and writing release notes belong to the release.
