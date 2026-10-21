# Sprint 105 — Shelves with opinions

**Sprint:** 105
**Status:** completed
**Roadmap revision:** 46
**Depends on:** 104
**Owner:** Mauro

## Objective

The shelves page is a room of shelves: each shelf's name large, a line of character beside it,
covers face-out on a ledge, the largest shelf drawn biggest. Hovering a cover opens it like a
book's front cover swinging back, showing its title, year and score inside. One shelf's own page
reads as a sentence, with covers that carry no chips. The owner: "too bland right now, it could
be more opinionated", and "a hover on a shelf should open the cover as an animation" (DEC-169).

## Required context

- DEC-169; DEC-167. The canvas: https://claude.ai/artifact/6vt1GZ5nBi5zYq67ibZh3c, board
  *Shelves — the room*.
- `pages/ShelvesPage.tsx`, `pages/ShelfPage.tsx`, `features/shelves/ShelfCard.tsx`, `ShelfRail.tsx`,
  `api/shelves.ts`, `application/library.py` (`list_shelves`), `api/library.py`.

## Current implementation baseline

A full-width *New shelf name* field and button, a domain strip, a sort control and a search
field, then a grid of identical cards with up to three thumbnail covers each. A shelf's page
draws the library's cards, with status and score chips over each cover; in a screenshot taken
while planning, three of four covers there rendered as dark gradients.

## Deliverables

1. `GET /api/shelves` adds, per shelf, a `preview` of up to eight members (entry id, title, year,
   score, cover URL; highest scored, then most recent), `finished_count` and `mean_score`.
2. The shelves page as a room: the page title large with one sentence ("Six shelves, 33 things on
   them. Your best-loved is *Rayuelas*."); per shelf a row with the domain, the name in a large
   serif (the largest shelf larger), a line ("12 books · 9 read · you rate them 8.6") and the
   covers standing on a ledge; "+N" for the rest; an empty shelf as a dashed place with a
   sentence. *New shelf* is a button that opens a small field; sort and the domain filter are
   text controls; the search field stays when there are more than eight shelves.
3. A cover on a ledge opens on hover and on keyboard focus: the front cover rotates back on its
   spine (a 3D turn, about 0.4s) to show an inside page with the title, year and score.
   `prefers-reduced-motion` and pointers without hover keep it closed; the cover still links to
   the entry.
4. One shelf's page: the name large and the shelf as a sentence; covers larger, in a grid without
   chips over them, the score shown under the title. Whatever made covers render as gradients
   there is found and fixed, or recorded.

## Acceptance criteria

1. The shelves response carries the preview and the two figures; tested.
2. The room renders every shelf as a ledge with its covers and line, in both themes and at 390px.
3. Hover and focus open a cover; reduced motion leaves it closed (a test emulates it).
4. A shelf's page draws covers without chips, and every cover loads.
5. The accessibility spec passes on both pages.

## Verification

Per DEC-167: the shelves backend tests, `vitest related`, `make check`, the shelves and
accessibility specs, and both pages in the running app in Paper, Ink and at 390px, with the
hover animation seen.

## Outcome

Delivered 2026-10-21. Verified per DEC-167: `test_shelf_room.py` and the shelf, library, export,
bulk and isolation suites (105), `vitest related` (140), `make check`, a new `shelves.spec.ts`
(hover and keyboard open a cover, reduced motion keeps it shut, nothing scrolls sideways at
390px) with the accessibility spec (32), and both pages in the running app on the copy of the
owner's library (eleven shelves) in Paper, Ink and at 390px, 640px, 800px, 1100px and 1440px,
with a cover caught open.

- **AC1.** `GET /api/shelves` adds `preview` (up to eight members, in the covers' order, those
  without art included), `finished_count` and `mean_score`; tested.
- **AC2.** The room: a sentence ("11 shelves, 33 things on them. Your best-loved is
  *ciencia-ficcion*."), then a row per shelf: its domains, its name in a 4–6rem serif (the
  largest shelf larger), its line ("11 books · 2 finished · you rate them 7.5"), and its covers
  on a wooden ledge (darker in Ink). Covers without art are typeset from the title. An empty
  shelf is a dashed place. *New shelf* is a button that opens a field; sort and domain are
  text controls; *Find a shelf* appears past eight shelves.
- **AC3.** `OpeningCover`: the front turns 115° on its spine in 0.4s on hover or keyboard focus,
  past upright so the whole inside page (title, year, score) shows and the cover's inner side
  hangs to the left; `prefers-reduced-motion` and pointers without hover keep it shut. Measured:
  `matrix3d(-0.42, …)` open, `none` under reduced motion.
- **AC4.** A shelf's page: the shelf as a sentence ("11 books, 2 finished. You rate them 7.5."),
  covers in a two- to five-column grid with a spine shadow, title, creator and score beneath
  and no chips over them; every cover loaded. The dark gradients seen while planning were the
  old grid's chip overlay over covers its virtualizer had not loaded yet.
- **AC5.** Axe passes on the room and on a shelf's page.

**Deviations.**
- The ledge does not scroll: a scrolling ledge clipped the opening cover, and the covers' 3D
  layers still widened the page past it (1837px at 1440px). Each ledge stands as many covers as
  fit its width (two on a phone, up to five large or six) and ends with *See all N*.
- The first open angle, 68°, left the swung cover over the left third of the inside page and
  cut the title; 115° shows it all.
- Editing status and score from a shelf's page moved to the entry's page with the chips, as
  the mock drew it.

Commit: `e4b81c9`, `5e37e44`.
