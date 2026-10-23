# Sprint 111 — Where things are, and who has them: on screen

**Sprint:** 111
**Status:** completed
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

Delivered 2026-10-23 in `39356d9`, with `fca2bb8` fixing a recorded defect the walkthrough met.
Verified per DEC-167: `vitest related` (27 files, 271 tests), `make check`, Playwright `lent`
(new), `accessibility` (two new checks, light and dark: the lend form, the lent row, `/lent`),
`progress-marks`, `add-detail`, `library`, `command-bar`, `editorial` (85 passed). Walkthrough
against a fresh backend with live Open Library: Solaris and Rayuela from search, an album by
hand, at 1280 (Paper) and 390 (Ink).

1. *Where* and *Lent* on the detail page; each change one request (Vitest; walkthrough: "Living
   room, shelf 2", lent to Sofi on 30 Aug, "7 weeks").
2. `/lent` lists open loans longest out first; *It's back* removes the row (Vitest, Playwright).
3. The library's Filters gain *Anywhere / a place* (shown once a place exists) and *Lent out*;
   chips clear them (Vitest; walkthrough: two cards under the place).
4. Accessibility passes on the detail page rows and `/lent`; 390px fits (Playwright).
5. The command bar shows "Julio Cortázar · Living room, shelf 2 · Lent to Sofi" on a library hit,
   and *Lent out* goes to `/lent`.

Found during the walkthrough and fixed (`fca2bb8`): the phone detail page scrolled sideways
(13px on Rayuela; the 19px recorded in 2.7). The single grid column sized to its content, and
a description ending in a Wikipedia URL set it. The column is `minmax(0, 1fr)` and long words
wrap; the lent spec's stub carries such a URL and failed without the fix.

Deviations and notes:

- TDD order: the `/lent` page and its test were written together; the test was then run green.
  The others were observed failing first.
- The command bar shows the place on a library hit; it does not search places themselves
  ("hall" finds nothing unless a title matches). Searching locations would mean adding them to
  the FTS index; not done.
- A test that holds every unknown request open learned the new `/api/locations` request.
