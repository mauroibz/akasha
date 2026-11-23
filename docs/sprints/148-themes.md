# Sprint 148 — Themes

**Sprint:** 148
**Status:** ready
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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
