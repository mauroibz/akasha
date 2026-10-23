# Sprint 111 — Where things are, and who has them: on screen

**Sprint:** 111
**Status:** ready
**Roadmap revision:** 49
**Depends on:** 110
**Owner:** Mauro

## Objective

The detail page says where a thing is and who has it, and lends or takes it back in a tap; a
quiet *Lent out* list answers "what's out?"; the library filters by location (DEC-176).

## Required context

- DEC-176; Sprint 110's Outcome (the API). `pages/DetailPage.tsx` (the personal region and
  `PropertyRow`), `features/detail/OpinionDialog.tsx`, `pages/HomePage.tsx` (filter chips),
  `components/AppShell.tsx` (navigation), the command bar (`features/command`).

## Deliverables

1. Detail page, personal region: a *Where* row (the location, or "Somewhere"; editable inline
   with the owner's earlier locations offered) and a *Lent* row ("Lent to Sofi on 2 Apr 2026" with
   *Back*; or *Lend…*, asking who and when, today by default). Past loans listed under it when
   there are any.
2. `/lent`: what is out, oldest first, cover, title, person, how long ("7 weeks"), *Back*. An
   empty state that says nothing is out. Reached from the command bar and from the Lent row, not
   from the main navigation.
3. The library filter gains *Location* (from `/api/locations`) and *Lent out*, as chips.
4. The command bar finds "where is…" by title and answers with the location.

## Acceptance criteria

1. Lend, return and set a location from the detail page; each is one request; tested in Vitest
   and the detail Playwright spec.
2. `/lent` lists open loans and *Back* removes the row.
3. Filters by location and lent narrow the library; chips clear them.
4. Accessibility spec passes on the detail page and `/lent`; 390px fits without sideways scroll.

## Verification

Per DEC-167: `vitest related`, `make check`, the detail and library Playwright specs plus a new
`e2e/lent.spec.ts`, and both screens in the running app at 390px and 1440px.

## Explicit non-scope

Reminders, loan due dates, borrowing from someone else.

## Outcome

_Not started._
