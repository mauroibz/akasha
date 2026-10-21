# Sprint 104 — Goals on the Diary

**Sprint:** 104
**Status:** in_progress
**Roadmap revision:** 46
**Depends on:** 103
**Owner:** Mauro

## Objective

The Diary carries a gentle goal: a band with the year so far and the calendar of lights, a
dialog to set or change the goal, and a few picks from what is waiting. Encouraging, never pushy:
no streaks, no reminders, no red, nothing that says behind (DEC-169).

## Required context

- DEC-169; DEC-167. The canvas: https://claude.ai/artifact/6vt1GZ5nBi5zYq67ibZh3c, boards
  *Diary with a gentle goal*, *Setting a goal*, *Fill A — calendar of lights* and the phone board.
- Sprint 103's API; `pages/DiaryPage.tsx`; `api/library.ts` (`patchEntry`); the item-type
  `statuses` (`in_progress`, `planned`).

## Current implementation baseline

The Diary lists finished entries by month for a chosen year. Goals exist in the API only.

## Deliverables

1. On the Diary, per domain with a goal: a band with the year's total in a large serif numeral,
   one sentence ("Two a month, at your own pace. October has one so far."), and the calendar of
   lights: twelve columns, a lit place per finished entry, unlit places for the goal's months,
   dashed places for months still ahead, nothing red. *Change goal* and *Hide goal*.
2. The goal dialog: domain chips (only domains that record a finish date), a stepper with the
   count drawn large, *a month* or *a year*, the picks switch, a sentence saying months count
   together.
3. Picks for the current month when the goal suggests: large tilted covers, title, creator, the
   reason in a sentence; *Start* sets the domain's `in_progress` status (hidden where the domain
   has none) and *Something else* shows the next pick.
4. No goal yet: one quiet invitation on the Diary, never a nag.
5. Phone layout: the band and calendar fit 390px; picks scroll sideways.

## Acceptance criteria

1. Setting a goal in the dialog draws the band; changing and hiding it work.
2. The calendar lights one place per finished entry in its month; months ahead are dashed.
3. *Start* moves a pick to the in-progress status; *Something else* replaces it.
4. The accessibility spec passes on the Diary with a goal, in both themes.

## Verification

Per DEC-167: `vitest related`, `make check`, a Diary spec with the goal, and the screen in the
running app in Paper, Ink and at 390px.

## Outcome

Not started.
