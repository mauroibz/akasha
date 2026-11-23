# Sprint 146 — Journal

**Sprint:** 146
**Status:** completed
**Roadmap revision:** 56
**Depends on:** 145
**Owner:** Mauro

## Objective

Diary, Insights and the games become one screen, the Journal, which opens on something to do. The navigation is *Library* and *Journal*.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 2.3, 3.6 and 3.7 and the mockup.
- DEC-132 (Insights), DEC-169 (goals), DEC-178 (year in review), DEC-179 (Play).
- Frontend: `pages/InsightsPage.tsx`, `features/insights/`, `pages/DiaryPage.tsx`, `features/diary/Timeline.tsx`, `features/goals/`, `features/play/PlaySection.tsx`, `pages/ChoresPage.tsx`, `features/home/` (tidy, question), `components/AppShell.tsx`.
- `e2e/insights.spec.ts`, `e2e/diary-*.spec.ts`, `e2e/play.spec.ts`, `e2e/chores.spec.ts`.

## Current implementation baseline

Observed 2026-11-23 while writing the proposal (section 2); re-observe at activation. Insights opens with four games and then numbered sections per medium; the Diary shows goals and months per year, with the year in review beneath it; `/deck` lists the chores.

## Deliverables

1. **The screen.** `/journal`: the header sentence, the widget, **Timeline** (the Diary's months and year choice, the year in review link), **Patterns** (the Insights sections per medium). `/insights` and `/diary` redirect to it and its anchors; `/diary/:year/review` stays.
2. **The widget.** One at a time, switched by tabs, the last used remembered per browser: **Play** (the games and decks as cards, from `PlaySection`, tidy up and `/deck`) and **Goal** (the goal band and invitation per medium). The slot is built to take a third widget (147).
3. **Navigation.** *Library* and *Journal*, on desktop and on the phone's tab bar with the bar's button between them.

## Acceptance criteria

1. `/journal` shows the widget, the timeline and the patterns; switching the widget does not reload the page and is remembered.
2. Every game reachable from Insights, Home or `/deck` before is reachable from the Play widget.
3. `/insights?…` and `/diary` land on the Journal at the matching section.
4. No serious axe violation or overflow at 390 and 1440 px.

## Required tests (TDD)

The Journal page, the widget switcher (Vitest); `e2e/insights.spec.ts`, `e2e/diary-goal.spec.ts`, `e2e/diary-timeline.spec.ts`, `e2e/play.spec.ts` against `/journal`.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*.

## Explicit non-scope

The *Every day* widget (147).

## Commit checkpoints

`[ADD]` the Journal and its widget slot; `[MOD]` Play and Goal as widgets; `[MOD]` navigation and redirects; `[DOCS]` close.

## Risks and decisions to surface

- Insights' "only what the library is filtered to" depends on the Library's remembered filters; it stays.

## Outcome

Completed 2026-11-23 (DEC-193). Commit: `27a30f0`.

- **`/journal`.** `pages/JournalPage.tsx`: the header, the widget, *Timeline*, *Patterns*.
  `DiaryPage` and `InsightsPage` take `embedded` and are drawn inside it without their frame,
  title, goal block and games. `/diary` and `/insights` redirect to `/journal#timeline` and
  `/journal#patterns`, which take the focus; `/diary/:year/review` is unchanged.
- **The widget** (`features/journal/JournalWidgets.tsx`): tabs with arrow keys, one widget
  mounted at a time, the last used remembered in the browser. *Play*: the games, plus links to
  *Tidy up*, the rank list and tiers. *Goal*: this year's goal bands, or the invitation. A
  third widget is one more entry in the page's list.
- **Navigation.** Library and Journal; on a phone Library, the bar's button, Journal. The
  games, the decks, the showcases and the command bar point at the Journal.

Acceptance: 1 and 3 by `JournalPage.test.tsx` and the redirected e2e specs; 2 by the Play
widget's test and `e2e/play.spec.ts`; 4 by `e2e/accessibility.spec.ts`.

Verification: Vitest 653 passed; Playwright chromium and heavy-library, full run 224 passed
with 15 expecting the old screens, then 239 passed and 2 skipped by design; `make check`.
Looked at on a copy of the development library at 1440 and 390 px in *Paper* and at 1440 px
in *Ink*: four games in Play, the year's two finishes in the timeline, the patterns below;
`/diary` landed on the timeline. No overflow, no console errors.

Deviations:

- The header is the title "Journal" with one line under it, not a sentence about the person's
  data: the Patterns part already opens with that sentence, and two would repeat.
- The widget does not remember across devices (the browser's storage, as the theme is).
- Play asks its questions of the first medium in the person's order, as Insights asked them of
  the medium its tabs showed.
- One e2e wait changed: the goal dialog's accessibility test waited for every animation on
  the page to end; it now waits for the dialog's own, because a part of the Journal that spec
  does not stub keeps a loading skeleton pulsing.

Observed, left: the Journal is long (the full Insights page is its last part). *Timeline*
shows one year at a time with the year chooser at the right of its heading.

Impact on later sprints: 147 adds *Every day* as the first widget in `JournalPage.tsx`.
