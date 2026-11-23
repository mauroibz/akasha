# Sprint 149 — The Journal's two gaps

**Sprint:** 149
**Status:** ready
**Roadmap revision:** 57
**Depends on:** 148
**Owner:** Mauro

## Objective

A goal is set for a medium the person chooses, and a day can be lit for anything, found by search, new items included.

## Required context

- DEC-195 points 1 and 2; DEC-065 and technical spec 8 (when a provider may be asked).
- `features/goals/GoalWidget.tsx`, `GoalInvite.tsx`, `goals.ts`; `features/journal/EveryDay.tsx`; `api/add.ts` (`searchCandidates`, `createEntry`), `api/library.ts` (the library search).

## Current implementation baseline

The Goal widget invites a goal for the medium finished most this year and only *Another number* opens a dialog that can change it. The day's question offers what is under way, or says nothing is.

## Deliverables

1. **The goal's medium.** Above the invitation, the one medium chooser lists the media a goal can count, in the person's order; the invitation is for the one chosen.
2. **Something else.** In the day's question, *Something else* opens a search field. Typing lists matches from the library, each chosen with a tap. *Search the web* asks a provider for the typed text, only on that button; adding a result creates the entry with its medium's default status and chooses it.

## Acceptance criteria

1. With two media that can carry a goal, choosing the second and *Aim for 12* sets the goal for the second.
2. With nothing under way, a day is lit for an entry found by typing its title.
3. No provider request is made while typing; one is made per press of *Search the web*.
4. A web result added from the question exists in the library afterwards and the day is lit for it.

## Required tests (TDD)

`GoalWidget.test.tsx`, `EveryDay.test.tsx` (search, request counting, add), `e2e/every-day.spec.ts`.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px.

## Explicit non-scope

Personalize (150). Logging progress from the question.

## Commit checkpoints

One per deliverable, then `[DOCS]` close.

## Risks and decisions to surface

- Listed in the Outcome as they are met.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
