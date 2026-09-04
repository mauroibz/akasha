# Sprint 069 — A door out of the app

**Status:** ready
**Depends on:** 068
**Roadmap revision:** 37

> Planned from [`../export-proposal.md`](../export-proposal.md). **Accepted as DEC-135.**
> 068 closed 2026-09-04; this sprint is next.

## Objective

Make the export reachable by somebody who has never read the API documentation: a third
tab on `/import` that renders what Sprint 068 declared, says how many entries each file
would hold, tells the reader where the file goes at the other end, and downloads it.
After this sprint the feature is complete and usable for every domain.

## Required context

- [`../export-proposal.md`](../export-proposal.md) — §2.5 is this sprint's screen, §3 is
  the placement decision and the copy question, §5 is what it must not do.
- [`068-export-the-way-we-import.md`](068-export-the-way-we-import.md) — the declaration
  this screen renders. **Read the shipped `GET /api/exports` response, not the plan for
  it.**
- `docs/decisions.md` DEC-080 (the screen renders the declaration and never markdown),
  DEC-079 (why Triage became a tab instead of a sixth nav item), DEC-026 (tokens).
- Code, read fresh: `frontend/src/pages/ImportPage.tsx` — the `?tab=` URL contract at
  `:158-210`, the workflow strip at `:444`, the `Tabs` usage; the
  `/triage` → `?tab=triage` redirect route in `frontend/src/App.tsx:65-72`;
  `frontend/src/features/import/ConnectorGuide.tsx` — the declaration renderer this
  sprint reuses rather than copies; `frontend/src/components/AppShell.tsx:21-25` — the
  nav item whose label the copy decision touches; `frontend/src/api/imports.ts` for the
  shape an API module of declarations takes here.
- Tests: `frontend/src/pages/ImportPage.test.tsx`, `frontend/e2e/import.spec.ts`,
  `frontend/e2e/accessibility.spec.ts`, `frontend/e2e/insights.spec.ts` (the 390px
  measurement this sprint copies).

## Current implementation baseline

- `/import` is a two-tab screen with a numbered workflow strip (`grid-cols-2` at `:444`),
  and the URL is the tab.
- There is no `/export` route and no control anywhere that downloads anything.
- `ConnectorGuide` already renders ordered guide steps and a help URL from a declaration,
  as plain strings. The export declaration carries the same two fields by design.
- The nav item is labelled **Import**.

## Deliverables

1. **A third tab, unnumbered.** Import (1) and Triage (2) keep their numbers; Export joins
   without one, because it is not a step of importing. `?tab=export` is its address.
2. **`/export` is a real address** that lands on the tab, the way `/triage` lands on
   `?tab=triage`. Same redirect shape, same reason.
3. **A row per declared view**, rendered from `GET /api/exports` with no view named in any
   `.tsx` file: label, what it carries in words, the entry count it would write, and a
   download control.
4. **Guide steps reused, not re-implemented.** The steps that say where the file goes at
   the far end render through the same declaration renderer the import side uses.
5. **The download is honest about being a stream.** A large library takes time; the control
   reports in-progress, success and failure, and a failed download says what failed rather
   than silently doing nothing.
6. **Empty and near-empty states.** A domain with no entries shows the row with a count of
   zero and a disabled download that says why. A view carrying nothing for this library is
   not hidden.
7. **The lossless row is first and marked as such.** The JSON is the one file that loses
   nothing; the screen says so in a sentence rather than assuming a reader knows.
8. **The copy decision, applied.** The nav item becomes **Data** (or **Import & export**
   if the owner prefers the longer label) — one line, and the owner's call. Whichever is
   chosen, the screen heading and the nav label agree.

## Acceptance criteria

1. From a cold start, a person who has never seen the API can reach a file of their
   library in two clicks from the nav, for every domain.
2. Every row on the screen comes from the declaration: adding a view server-side makes a
   new row appear with no frontend change. Proven by a test that serves an extra,
   invented view and asserts it renders in full.
3. Guide steps render as an ordered list of plain text. Markdown in a step renders as the
   characters it is, not as markup.
4. A download reports failure visibly when the request fails, and the screen stays usable.
5. A domain with zero entries shows a zero and an explained disabled control, not an
   empty screen and not a hidden row.
6. `/export` and `?tab=export` land on the same tab, and the tab survives a reload and a
   pasted URL.
7. The screen holds at 390px with no horizontal body scroll and 44px targets, measured
   the way `e2e/insights.spec.ts` measures it.
8. Zero serious axe violations on the tab.
9. The existing import and triage component and e2e suites pass unchanged.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| A row renders entirely from the declaration, including an invented view | component | `ImportPage.test.tsx` |
| Guide steps render as text; markdown is not interpreted | component | `ImportPage.test.tsx` |
| A failed download surfaces an error and leaves the screen usable | component | `ImportPage.test.tsx` |
| Zero-entry domain: count of zero, disabled control, stated reason | component | `ImportPage.test.tsx` |
| `/export` and `?tab=export` reach the same tab | component | `ImportPage.test.tsx` |
| Downloading a file end to end from the running app | e2e | `frontend/e2e/import.spec.ts` |
| The tab at 390px does not scroll the body horizontally | e2e | `frontend/e2e/insights.spec.ts` pattern, in `import.spec.ts` |
| No serious accessibility violations on the export tab | e2e | `frontend/e2e/accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`
- `npx playwright test` — **owed**: a new screen, a new route and a download path.
- **Walkthrough (DEC-025):** open the tab in a real browser at 1280px and at 390px,
  download every view for every domain, open each downloaded file, and report what was in
  it. A download tested only through a mocked fetch does not discharge this.

## Explicit non-scope

- **New formats.** MyAnimeList, Letterboxd and the series decision are Sprint 070; if this
  screen needs changing to show them, deliverable 3 failed.
- Filtered export, scheduled export, share links, an `akasha` re-importer — proposal §5.
- Any change to the import or triage tabs beyond adding a third one.
- The cohesion primitives — Sprints 071/072. This tab uses what `/import` uses today.

## Commit checkpoints

1. `[ADD] Ask the server what can leave`
2. `[ADD] A third tab on the screen where data moves`
3. `[ADD] Say what each file holds and how much of it`
4. `[ADD] Hand over the file, and say so when it fails`
5. `[MOD] Name the screen after what it does in both directions`

## Risks and decisions to surface

- **The nav label is the owner's decision** and the only one that blocks nothing. Ship a
  recommendation, state it, and make it trivial to change.
- **A streamed download has no progress.** The server sends no length, so the control can
  report *working* honestly but cannot report *42%*. Do not invent a percentage.
- **A three-tab strip at 390px is where the workflow strip gets tight.** It is the same
  class of problem as DEC-134's domain strip; this sprint measures it rather than
  assuming, and if it needs the scrolling treatment it says so for Sprint 071.
- **Counts cost a query per view.** If `GET /api/exports` is slow on a real library,
  measure before adding a parameter — the precedent is DEC-133's answer to the same
  question.

## Outcome

_Not started._
