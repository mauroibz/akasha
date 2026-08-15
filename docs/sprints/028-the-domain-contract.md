# Sprint 028 — The domain contract

**Status:** ready
**Depends on:** 027
**Roadmap revision:** 11

## Objective

**A third domain is built by reading a contract, not by reading how albums were built.**
Phase A produces that contract — what a domain must supply, what it may never touch, where its code
lives — plus a conformance suite a domain must pass, run against books and albums first to prove it
describes reality rather than intentions. Phase B moves only what the suite proves is misplaced.

**Gated** (DEC-035, DEC-042): Phase A is a written verdict in `docs/decisions.md` and changes nothing
user-visible. Phase A concluding that little is misplaced is a complete, correct outcome, and Phase B
runs only on that verdict plus an explicit owner go-ahead.

This is the first of the two sprints DEC-058 makes the gate to further domains.

## Required context

1. `AGENTS.md`, `docs/agent/WORKFLOW.md`
2. `docs/decisions.md`: **DEC-052** (the six seams and the falsifiable prediction this sprint is
   here to test), **DEC-057** and **DEC-059** (what an entry is per domain), **DEC-060** (seam 5b as
   built — the single best statement of what `Domain` currently declares), **DEC-062** (the library
   shell's dependence on the registry, and the facet asymmetry the contract must state),
   DEC-058 (why the plan ends here)
3. `docs/sprints/025-second-domain-albums.md` and `026-statuses-formats-tracklists.md`, both
   Outcomes — the actual record of what a second domain cost
4. `backend/src/book_tracker/domain/domains.py` in full. `Domain` **is** the contract today, and it
   is undocumented outside the sprint files that grew it.
5. `docs/specs/technical-spec.md` sections 5.1, 7.1, 7.2, 8; `docs/specs/product-spec.md` sections
   3.2, 3.3, 7
6. `docs/agent/HANDOFF.md` and the last worklog entry

## Current implementation baseline

Observed 2026-08-15 at Sprint 027's close. **Re-derive at activation.**

- `Domain` (`domain/domains.py`) carries `item_type`, `label`, `identity`, `fields`, `enriches`,
  `recognize`, `statuses`, `default_status`, `entry_fields`, `formats`, `entry_panel_label`.
  `DOMAINS` is a dict keyed on `item_type`; `DEFAULT_DOMAIN` names books for every call site that
  predates the second domain.
- **Three published unions** — `EntryStatus`, `EntryFormat`, `ItemTypeName` — each spelled out for
  mypy and each pinned to the registry by an assertion in `backend/tests/test_domain.py`. That
  pattern is a contract rule, not a coincidence.
- `GET /api/item-types` publishes the whole of it, and no screen branches on the item type. The
  library shell (tabs, chips, format selector) renders from it entirely as of Sprint 027.
- Writes validate against the item's own domain in `LibraryService._validated`, refused with a 422
  naming the domain; a bulk write spanning domains is refused whole.
- **Known book-shaped things in shared layers**, to be measured rather than assumed: `domain/goodreads.py`
  and `domain/calibre.py` and `application/imports.py` are book-only throughout (Sprint 029's
  problem, but Phase A should say so); the cover chooser is Open Library's work-editions path and
  offers itself on an album where it can only say no; `entries.status` carries a CHECK constraint
  listing the union of every domain's statuses, which cannot express the real per-domain rule.

## Deliverables

### Phase A — the contract and the suite

1. **A written domain contract**, in `docs/specs/technical-spec.md` and referenced from
   `docs/decisions.md`: every field of `Domain` and what supplying it obliges; the adapter, field
   spec, status vocabulary, format vocabulary and URL recognizer a domain must provide; what a
   domain may never touch; and where its code lives.
2. **A conformance suite** — `backend/tests/test_domain_conformance.py` — parametrized over
   `DOMAINS`, so it runs against books and albums today and against a third domain by that domain
   existing. It must check at least: the three published unions cover this domain's values; every
   declared status has a label and a distinct triage key within its domain; `default_status` is one
   of the declared statuses; `entry_fields` is a subset of the passage fields; a field spec's
   `columns` is present exactly for `rows` fields; the identity rule rejects what it should; and the
   API refuses this domain's non-values with a 422.
3. **A measurement of what is misplaced** — book-shaped logic in shared layers, listed with its cost
   to move, not moved.
4. **A paper walk through IGDB against the suite**, which is where DEC-052's prediction that "games
   need no seam albums did not" is actually tested. Cheaper and more honest than another bespoke
   sprint.

### Phase B — only what the verdict justifies

5. Move what the suite proves is misplaced, one coherent slice per move, with the suite green
   before and after.

## Acceptance criteria

1. The contract document is sufficient to build a domain without reading Sprints 025–027.
2. The conformance suite runs against every registered domain by parametrization, not by a
   per-domain test, and both books and albums pass it.
3. The suite fails when a deliberately malformed domain is registered in a test — a status with no
   label, a `default_status` outside the vocabulary, a `rows` field with no columns.
4. The IGDB paper walk produces a written verdict naming every seam it would and would not need.
5. Phase A changes no user-visible behavior; the full suite and the e2e gate are green and unchanged.
6. Any Phase B move leaves every existing test green without weakening one, and is a separate commit.

## Required tests (TDD)

- The conformance suite itself, written against books and albums before any move.
- A malformed-domain fixture, registered only inside the test, that each conformance check rejects.
- For any Phase B move: the existing tests covering the moved behavior run unchanged against its new
  home before the old one is deleted.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && make build && make smoke-container
git diff --check
```

Phase A is documentation and tests, so the walkthrough gate is satisfied by demonstrating that the
suite fails against a malformed domain and passes against both real ones. **Any Phase B move
touching user-visible behavior re-arms the full walkthrough gate** against a library holding books
and albums.

## Explicit non-scope

- **Building a third domain.** That is an epic on top of this contract (DEC-058), and building one
  here would be the thing this sprint exists to make unnecessary.
- **Per-domain imports.** Sprint 029. Phase A may *name* the book-shaped import layer as misplaced;
  moving it is 029's whole outcome.
- **A plugin runtime.** Product spec section 2 has held the line since v1: the registry is code.
- Re-opening DEC-057, DEC-059 or DEC-062.

## Commit checkpoints

1. `test: hold every domain to the same contract` (the suite, against books and albums)
2. `docs: state what a domain must supply` (the contract, plus the IGDB verdict as a decision)
3. Phase B only, one per move, e.g. `refactor: move the suggestion map behind the domain`
4. final `docs(sprint-028): close sprint and hand off`

## Risks and decisions to surface

- **The gate is real.** Phase A concluding that almost nothing is misplaced is a correct outcome and
  must be reported as one, not padded into a refactor to justify the sprint.
- **A conformance suite that only restates the dataclass is worthless.** It has to be able to fail:
  the malformed-domain fixture is the acceptance criterion that keeps it honest.
- **Scope creep runs through "while we are here".** Every move Phase B makes must be one the suite
  proved, not one the reader noticed.
- The cover chooser on an album is a real defect and predates this sprint. Decide whether it is in
  scope or scheduled, rather than leaving it unmentioned a third time.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
