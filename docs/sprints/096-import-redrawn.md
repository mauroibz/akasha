# Sprint 096 — Import, redrawn

**Sprint:** 096
**Status:** ready
**Roadmap revision:** 45
**Depends on:** 095
**Owner:** Mauro

## Objective

Importing reads as one clear page: one nav entry, *Import*, carrying the Inbox count; a drop area
over a grid of source cards instead of a strip of nine tabs; a check step that shows covers and
titles, never an id; the Inbox as its own page and Export in Settings. Proposal I1–I4.

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.3 I1–I4, §5.1; DEC-165,
  DEC-167; Sprint 095's Outcome (the raw status words).
- `frontend/src/pages/ImportPage.tsx` and its test, `pages/TriagePage.tsx`,
  `features/export/ExportPanel.tsx`, `features/import/ConnectorGuide.tsx`,
  `components/AppShell.tsx`, `pages/SettingsPage.tsx`; backend `api/imports.py`
  (`ImportRecordResponse`, the ambiguity candidates).

## Current implementation baseline

`/import` stacks an Import/Triage/Export step strip over a scrolling strip of nine sources; the nav
says *Data*, the step *Triage*, its title *Inbox*, the library button *Inbox 0*. An ambiguous row
offers "Use existing item 42". The guide heading reads "How to get a Your list". Status
suggestions print as `to_read`.

## Deliverables

1. Names: the nav entry is *Import* with the Inbox count as a badge; the Inbox is `/inbox` (the
   Triage page, titled Inbox); Export is a *Your data* section of Settings. `/import?tab=triage`,
   `/triage` and `/import?tab=export` redirect.
2. Source step: with no source chosen, a drop area (detect and hand off, Sprint 095) above a grid
   of source cards (name, domain, one-line description); choosing one opens its form, and the
   choice is in the URL so Back returns to the grid.
3. Check step: an ambiguous row shows the existing item's cover and title beside the new record's;
   status suggestions use the domain's labels; the guide heading reads naturally.
4. The source grid, the check list and the step header move out of `ImportPage.tsx` into
   `features/import/`.

## Acceptance criteria

1. No visible text says *Data*, *Triage*, an item id, or a raw status value on these screens.
2. Every old URL lands somewhere sensible.
3. Every importer's preview and commit still works (the import spec and page tests).

## Verification

Per DEC-167: `vitest related`, `make check`, the import, triage, add-ebooks and command-bar specs,
the route-structure tests if a route changes, and screenshots of the grid, a check with an
ambiguity, the Inbox and Settings.

## Explicit non-scope

The arrivals strip and trust-stated-status (097).

## Outcome

_Not started._
