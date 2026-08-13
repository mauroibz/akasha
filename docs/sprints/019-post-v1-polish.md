# Sprint 019 — Post-v1 polish and ledger clearing

**Status:** in_progress
**Depends on:** 018
**Roadmap revision:** 8

## Objective

Clear the three small user-visible defects that survived v1, so the months of architectural work
that follow are not walked through against known cosmetic noise.

This sprint is deliberately small. Every item is independent of every other sprint on the roadmap;
nothing here blocks or is blocked by Sprint 020. If an item turns out to be larger than a day, that
is the finding — record it and stop, rather than growing this sprint to fit.

## Required context

1. `AGENTS.md` and `docs/agent/WORKFLOW.md`
2. `docs/specs/product-spec.md` section 7 (microinteractions, screens, interaction notes — the
   `s` shortcut is specified there) and section 5.1 (Goodreads import lands rows `unsorted`)
3. `docs/decisions.md` DEC-026 (the score ramp and the bespoke score picker), DEC-028 (one visible
   feedback surface), DEC-033 (a reduced-motion assertion is only meaningful in a pair), DEC-041
   (a dev-server-only suite is not evidence about the shipped artifact)
4. `frontend/src/lib/score.ts`, `frontend/src/components/ScorePicker.tsx` and its test
5. `frontend/src/pages/TriagePage.tsx` — the existing keyboard map and its input guards
6. `frontend/src/pages/ImportPage.tsx` — the commit result panel
7. `docs/agent/HANDOFF.md`, "Gotchas that will cost you an hour each"

## Current implementation baseline

Re-derive at activation. As of Sprint 018's close:

- The collapsed score trigger in `ScorePicker.tsx` renders a bordered transparent box with the
  score in ramp colour, via `scoreTextClass`. The filled treatment — ramp colour as background,
  numeral in `--background` — already exists as `scoreFillClass` in `lib/score.ts` and is used for
  the selected segment of the open picker. A provisional score is marked by a dashed border plus a
  dot, asserted through `data-provisional` in the e2e suite.
- `/triage` implements `j`/`k`, status, score, shelf, and commit/advance shortcuts with input
  guards. `s` is listed in product spec section 7 as shelf-autocomplete and does nothing.
- Goodreads and Calibre commits land new rows `unsorted`, which the default library view excludes.
  The import result panel reports counts but does not point anywhere.

## Deliverables

### 1. High-contrast score chip

Swap the collapsed `ScorePicker` trigger from `scoreTextClass` to the existing `scoreFillClass`, so
a scored item reads as a solid ramp-coloured chip with the numeral knocked out in `--background`
rather than as a colour-on-dark numeral. This is reuse of the treatment the open picker already
uses for its selected segment, not a new design — do not introduce a new token or a new colour.

Two things to get right rather than assume:

- The provisional affordance was tuned against a transparent trigger. A dashed `border-primary/60`
  and a `bg-primary` dot behave differently on a filled chip, and both carry assertions. Re-judge
  them visually; if the dot stops being legible, the fix is the dot, not the fill.
- The unscored state (`—`, `text-muted-foreground`) stays as it is. Only a real score fills.

Surfaces to check for consistency once it changes: library cards, `/triage` score cells
(`TriagePage.tsx:628`), and the detail page (`DetailPage.tsx:196`), which use `scoreTextClass`
directly rather than through the picker. Decide deliberately whether those follow the chip or stay
as text, and record which in the Outcome — the DEC-026 rule is that the colour means the same thing
wherever the eye lands.

### 2. `s` on `/triage`

Product spec section 7 lists `s` as the shelf-autocomplete shortcut. Every other triage key works.
Either implement it against the existing shelf assignment path, or record a decision that the spec
was aspirational and remove it from section 7.

**The sprint is not complete while it is still merely noticed.** It has been carried in
`HANDOFF.md` as noticed-and-left across three sprints; the point of this sprint is that it stops
being carried.

### 3. Post-import affordance

After a commit, the import result panel reports created counts, but the rows land `unsorted` and
the default library excludes them, so the library looks as though the import did nothing. Point at
Triage from the result panel with the unsorted count, using the existing feedback surface rather
than a new one (DEC-028).

## Acceptance criteria

1. A scored library card renders the score as a filled ramp-coloured chip with the numeral in the
   background colour; the ramp band boundaries of DEC-026 are unchanged.
2. An unscored entry still renders `—` in muted colour, and a provisional score is still
   distinguishable from a confirmed one both visually and through `data-provisional`.
3. Either `s` on `/triage` opens shelf autocomplete and obeys the same input-focus guards as every
   other triage shortcut, or product spec section 7 no longer lists it and `docs/decisions.md`
   records why.
4. After committing an import, the result surface names how many rows are waiting in Triage and
   offers a way to get there.
5. The axe gate and both DEC-023 mounted-DOM bounds still pass; a fill is a paint change and must
   not have become a layout change.

## Required tests (TDD)

- `ScorePicker.test.tsx`: a scored trigger carries the fill class for its band; an unscored trigger
  does not; a provisional score remains identifiable.
- Triage keyboard test for `s`, including the input-focus guard, if it is implemented.
- Import commit test asserting the result surface names the unsorted count.
- Existing accessibility spec re-run over the library and triage screens.

## Verification

```bash
python scripts/validate_project.py
make format
make check
make test
cd frontend && npm run test:e2e
cd .. && make build
git diff --check
```

`npm run test:e2e` means both Playwright projects, not `--project=chromium` (DEC-041). Everything
in this sprint is user-visible, so the walkthrough gate applies: run the container, look at a
scored library, import something, and record what you saw.

`docs/brand/screenshots/library.png` and `detail.png` show the old score treatment. Recapture them.

## Explicit non-scope

- Placeholder-cover detection and reprint-over-original search ranking — Sprint 020.
- The `GoogleBooksProvider.fetch_by_isbn` first-hit defect — Sprint 020, where edition verification
  is already an acceptance criterion.
- Author sort — Sprint 022. It looks small and is not: Spanish double surnames make the
  last-space heuristic wrong for this library, so it needs a stored sort name and a migration.
- Export — Sprint 023.
- Any change to the score ramp itself, the token set, or the picker's open panel.

## Commit checkpoints

1. `fix: fill the score chip so the ramp reads at a glance`
2. `feat: open shelf autocomplete from the triage keyboard` (or `docs: retire the unimplemented
   triage shelf shortcut`)
3. `feat: send a finished import to the rows it left unsorted`
4. `docs(sprint-019): close sprint and hand off`

## Risks and decisions to surface

- Whether the detail page and triage score cells follow the chip or stay as coloured text. Pick one
  and record it; do not leave the three surfaces disagreeing.
- **No v1 tag exists.** The owner declined it in Sprint 018 and the one-line command is in
  `docs/operations/release-notes-v1.md`. Ask once; do not tag unasked.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
