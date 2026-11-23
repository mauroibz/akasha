# Sprint 146 — Journal

**Sprint:** 146
**Status:** ready
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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
