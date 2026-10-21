# Sprint 090 — Two themes

**Sprint:** 090
**Status:** completed
**Roadmap revision:** 45
**Depends on:** 089
**Owner:** Mauro

## Objective

Akasha has two designed themes, *Ink* (today's dark, warmed) and *Paper* (warm light), chosen in
Settings and defaulting to the device's preference, with a display serif for titles. This is the
look the owner approved in the design mock (DEC-165).

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.1 (D1, D2), §3.
- The design mock: https://claude.ai/artifact/KRWdo67P7QfirBsBK4mdRa (Library, Detail and
  Appearance boards, both themes).
- [`../brand/BRAND.md`](../brand/BRAND.md) and [`../brand/brand-handoff.md`](../brand/brand-handoff.md)
  ("dark only", amended by DEC-165 point 1).
- `frontend/src/index.css` (the DEC-026 HSL tokens), `frontend/tailwind.config.ts`,
  `frontend/index.html`, the account/settings surface (`components/AccountSection.tsx`).

## Current implementation baseline

- One dark token set on `:root`, `color-scheme: dark`. Components use the tokens; the only
  hard-coded palette is the acting-as banner in `AppShell.tsx:143`.
- Inter only, bundled through `@fontsource-variable/inter` (no third-party font host: DEC-026).

## Deliverables

1. Token sets for *Ink* and *Paper* under `[data-theme]`, from the mock's values, each checked for
   WCAG AA contrast (text 4.5:1, large text and UI 3:1) by a test that computes the ratios.
2. A theme setting (*Match my device*, *Paper*, *Ink*) stored per browser and applied before first
   paint by an inline script in `index.html`, so no flash.
3. Newsreader, bundled through `@fontsource-variable/newsreader`, as `--font-display` for page
   titles, item titles and the detail page heading; a type scale in the Tailwind config.
4. The brand documents amended: two themes, amber stays the one accent, the score ramp unchanged
   in meaning; colours tuned per theme for contrast.

## Acceptance criteria

1. Every token pair used for text meets AA in both themes; the test fails if one does not.
2. Choosing a theme changes the page at once and survives reload; *Match my device* follows the
   OS setting live.
3. No flash of the wrong theme on load.
4. Titles render in Newsreader; body text stays Inter.

## Verification

Per DEC-167: the contrast test, `vitest related`, `make check`, the accessibility and library
browser specs, and screenshots of Library and Detail in both themes.

## Explicit non-scope

- New components, motion, and the detail page as property rows (091, 092).
- Storing the theme on the server account (a per-browser setting is enough for now).

## Outcome

Delivered 2026-10-21. Verified per DEC-167: `contrast.test.ts` (48 checks, both themes),
`theme.test.ts`, `SettingsPage.test.tsx`, `vitest related` on every touched file (93, then 164),
`make check`, the accessibility, library and editorial browser specs (63; Playwright's default
device preference is light, so these ran on Paper), and screenshots of Library, Detail and
Settings in both themes against a copy of the owner's data.

- **AC1.** Ink and Paper token sets under `[data-theme]`, from the mock. `--primary-text`
  separates amber that is read (Paper `#9A4A07`) from the amber fill (`#E9A23B`); Tailwind's
  `text-primary`, `border-primary` and `ring-primary` map to it, so no component changed class.
  Paper's score ramp is darker so a filled chip's page-coloured number reads at 4.5:1.
- **AC2.** `/settings` (Appearance: Match my device, Paper, Ink), linked from the desktop nav;
  per-browser, live with the OS while following it.
- **AC3.** An inline script in `index.html` sets the theme before first paint.
- **AC4.** Newsreader (bundled, optical size) on page titles, the detail title, Insights, Export,
  sign-in and the library lockup.

Found while looking: the long-running Vite dev server had not reloaded the Tailwind config, so the
first screenshots showed no serif; a production build proved the classes were generated, and a
restart fixed the dev server. An always-on phone header for the Settings link pushed the first
cover from under 300px to 351px at 390px (the library spec caught it); the phone header stays
auth-only and the phone's Settings entry is 093's. For a signed-in non-admin, the account menu's
old "Settings" entry (which opened `/people`) is now "Account".

Commit: `049603f`.
