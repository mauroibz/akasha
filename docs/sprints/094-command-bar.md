# Sprint 094 — The command bar

**Sprint:** 094
**Status:** completed
**Roadmap revision:** 45
**Depends on:** 093
**Owner:** Mauro

## Objective

One place takes anything you can type: `⌘K`/`Ctrl+K`, `/` or the search control opens a command
bar that finds in your library (ranked), searches the web per domain with an explicit Add,
resolves a pasted link or ISBN to one confirm card, and runs actions (go to a page, import, switch
theme, new shelf). Adding moves out of the library filter box, so the three doors to "add" become
one (A1, A2, A5).

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.2 A1, A2, A5 and §4.1,
  §4.4; DEC-165, DEC-166 (ranked search deferred here from 089), DEC-167.
- `frontend/src/components/ui/command.tsx` (cmdk, unused), `api/add.ts` (`searchCandidates`,
  `resolveCandidate`), `features/add/AddForm.tsx`, `pages/HomePage.tsx` (`searchTheWeb`, the web
  results region), `pages/AddPage.tsx`; backend `application/library.py` (`_search_expression`),
  `api/providers.py`.

## Current implementation baseline

The library search box filters the library and, on Enter or *Search*, searches providers into a
web-results region beside the feed; a link or ISBN typed there resolves. `/add` is the manual form
plus ebook drop. `CommandDialog` exists and is unused. No ranked library search.

## Deliverables

1. `GET /api/search/library?q=` — FTS5 ranked (bm25, title weighted), ten results, the current
   person's entries only.
2. `CommandBar` (cmdk in a dialog; a bottom sheet on phones): sections *In your library*, *On the
   web* (per domain, results show cover, title, creator, year and an *Add* button with the
   domain's default status), *Go to* and *Do*. A link or ISBN shows one resolved confirm card.
3. Opened by `⌘K`/`Ctrl+K` anywhere, `/` outside a field, the header's search control, and the
   phone's bottom-bar search.
4. The library header keeps its filter box for filtering only; its *Search* web half and the
   web-results region move into the bar. `/add`'s lede points at the bar.

## Acceptance criteria

1. Typing a title from your library shows it first under *In your library*; Enter opens it.
2. Typing a new title shows web results; *Add* adds it with the domain's default status and says
   so, without leaving the page.
3. Pasting an IMDb, Open Library or MusicBrainz link shows one confirm card; Enter adds.
4. Every action is reachable by keyboard; the bar has a dialog role and a labelled input.

## Verification

Per DEC-167: backend tests for the ranked endpoint, `vitest related`, `make check`, the library
and add-detail browser specs plus a new command-bar spec, and screenshots of the bar in both
themes.

## Explicit non-scope

Global paste and drop (095); new link recognisers (095).

## Outcome

Delivered 2026-10-21. Verified per DEC-167: ranked-search backend tests (2 new), the backend suite
once (1646; see below), `vitest related` (227), `make check`, the library, add/detail,
accessibility and auth specs plus a new `command-bar.spec.ts`, and screenshots of the bar in both
themes against live Open Library.

- **AC1.** `GET /api/search/library` (bm25, title 10, creators 6, series 4, subjects 2, note 1;
  Inbox included; title fragments by substring after the ranked rows) feeds *In your library*.
- **AC2.** Web results per domain with an explicit Add; no status is sent, so the server applies
  the domain default; *already in your library* and near matches are said in a toast with Open
  or Add anyway; the row becomes *Added · Open*.
- **AC3.** Links and ISBNs resolve to *From that link*.
- **AC4.** cmdk combobox named "Search or add"; Cmd/Ctrl+K anywhere; the spec drives it entirely
  by keyboard.

**Deviation.** The library box keeps its web half and confirm form (edition choice, near-match
confirmation, highlight in place): it is mature and tested, and the bar is the one door that is
always there. The header's Add opens the bar. `/` still focuses the library's filter box.
**Found:** results of the previous text stayed listed for the debounce, so Enter opened a stale
result (the spec caught it; they are hidden while typing settles). The nav's new door overflowed
tablet width; it is an icon below 1024px. And the route-documentation and isolation-policy tests
had failed since 089 (not in that sprint's covering set): fixed here, and the backend suite run
once to look for anything else hidden (none).
