# Sprint 028 — The domain contract

**Status:** ready
**Depends on:** 027
**Roadmap revision:** 11
**Branch:** `sprint-025-albums`, continuing DEC-053/DEC-061/DEC-063. The owner settled this at
planning time: sprints 025–027 stay unmerged and 028 runs beside them, so the contract is written
against a codebase that actually holds two domains.

## Objective

**A third domain must be an epic somebody else can build in parallel — not a patch to files every
other domain lives in.**

That is the epic this sprint gates (DEC-058): each domain encapsulated enough that
`calibre → books`, `spotify → music` and `steam → games` can be built by different hands without
touching each other or the core. Sprint 025 proved the seams exist. What does not exist is a
**contract** — a new domain is currently built by reading how albums were built and inferring the
rules — and, more sharply, **a domain is not yet a unit of code**: it is a set of edits distributed
across nine shared files, one of them a migration on the `entries` table.

Phase A produces that contract, plus a conformance suite a domain must pass, plus a measurement of
what a third domain would still have to touch. Phase B moves what the measurement proves.

**Sprint 029 rebuilds the main screen right after this one** (DEC-065), so the contract's account of
what a *screen* renders from the registry is the part most likely to need revising. Write it against
the registry rather than against today's layout, and expect 029's close to amend the screen-facing
section — the backend contract and the conformance suite are unaffected by that sprint.

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

**Re-derived 2026-08-15 by reading the code, not the previous sprint's summary.** Re-derive again at
activation; the file references below are the ones that were true on that date.

### What is already neutral, and must not be re-litigated

- `Domain` (`domain/domains.py`) carries `item_type`, `label`, `identity`, `fields`, `enriches`,
  `recognize`, `statuses`, `default_status`, `entry_fields`, `formats`, `entry_panel_label`.
  `DOMAINS` is a dict keyed on `item_type`; `DEFAULT_DOMAIN` names books for every call site that
  predates the second domain.
- `GET /api/item-types` (`api/library.py:478`) publishes all of it, and the library shell, triage,
  detail page and status controls render from it. **There is no `type === "album"` branch anywhere.**
- Writes validate against the item's own domain in `LibraryService._validated`, refused with a 422
  naming the domain; a bulk write spanning domains is refused whole.
- **A partial conformance suite already exists**: `backend/tests/test_domain.py:140-179` parametrizes
  over `DOMAINS` and checks the status vocabulary, the hotkey bindings and the format vocabulary.
  The new suite absorbs it rather than duplicating it.
- **Three published unions** — `EntryStatus`, `EntryFormat`, `ItemTypeName` — each spelled out for
  mypy and each pinned to the registry by an assertion in `test_domain.py`. That pattern is a
  contract rule, not a coincidence.

### What a third domain must edit today — the measurement Phase A starts from

A domain is not a unit of code. Adding `game` means editing files that books and albums live in:

| Shared file | What a third domain changes there |
|---|---|
| `domain/domains.py` | its fields, statuses, formats, its `Domain`, the `DOMAINS` tuple, **all three published unions**, its URL recognizer and host regexes — all beside books' and albums' |
| `domain/providers.py` | its `IdentityStrategy` constant |
| `main.py` | provider construction and registration, **and `provider_health` (`main.py:259-270`), which names `openlibrary`/`musicbrainz`/`googlebooks` as literals** |
| `config.py` | credentials — IGDB needs Twitch OAuth, where every provider so far needed at most a static key |
| `infrastructure/covers.py:25-36` | its art host in the shared allowlist |
| `alembic/versions/` | a migration rebuilding the shared `entries` table (below) |
| `frontend/src/api/library.ts:6-24` | `entryStatuses` / `entryFormats`, hand-mirrored from the backend enums |
| `frontend/src/features/library/labels.ts` | the fallback vocabulary, which is the book vocabulary |
| `frontend/src/pages/AddPage.tsx:112,250,299` | three live `itemType === "book"` branches — search label, placeholder, manual-fallback copy |

Two of those are worse than a file to edit, and are the findings Phase A must cost:

- **`entries.ck_entries_status` is a frozen list.** `alembic/versions/0013_entry_formats.py:66`
  renders the CHECK from `ALL_STATUSES` **at migration-write time**, so the live database holds
  `('unsorted','read','reading','to_read','wishlist','dropped','pending','owned')`. A third domain
  declaring `playing` passes `validate_status` and is then refused by SQLite. **A new domain
  currently requires a schema migration on a shared table** — the sharpest contradiction of the epic
  goal in the repository. The owner's instruction is that this is measured and costed here, with
  alternatives, and decided at the gate; it is **not** pre-authorized work.
- **Enrichment is book-shaped below the seam.** `_backfillable_items`
  (`application/enrichment.py:341+`) correctly filters on `domain.enriches`, but its SQL joins
  `item_identifiers.kind = 'isbn'` and tests `publisher`/`page_count`/`description`; `PROVIDER_ORDER`
  (`enrichment.py:33`) is `("openlibrary","googlebooks")` and `_fetch` takes an ISBN. Albums only
  avoid all of this by declaring `enriches=False`, so **the second domain never tested this seam.**
  A third domain that enriches on a non-ISBN key finds nothing behind the flag.

### Known book-shaped things in shared layers, to be measured rather than assumed

- The **manual add path** (`application/add.py:129-148`) is a book form hard-wired to
  `DEFAULT_DOMAIN`: ISBN, publisher, language, and a `frontend/src/features/detail/schemas.ts`
  validator that says "A book needs a title".
- **`cover_candidates` (`application/providers.py`) takes an Open Library provider as an argument.**
  That is why "Choose a cover" appears on an album and can only say no — a defect that predates this
  sprint and has now been left unmentioned three times. **Decide it here: in scope, or scheduled.**
- The detail route is **`/books/:id` for every domain** (`VirtualLibrary.tsx:267,285`,
  `TriagePage.tsx:358,745`, `AddPage.tsx:209,631`).
- The whole **import layer is book-only** — `domain/goodreads.py`, `domain/calibre.py`,
  `application/imports.py`, and `api/imports.py` whose preview rows carry `goodreads_book_id`,
  `calibre_book_id`, `calibre_uuid` and `isbn`. That is **Sprint 030's** outcome; Phase A names its
  cost and moves none of it.
- `domain/goodreads.py` and `domain/calibre.py` sit in `domain/` beside the shared domain model,
  which is the clearest symptom of there being no per-domain code home at all.

## Deliverables

### Phase A — the contract, the suite, the measurement

1. **A written domain contract**, in `docs/specs/technical-spec.md` and referenced from
   `docs/decisions.md`: every field of `Domain` and what supplying it obliges; the adapter, field
   spec, status vocabulary, format vocabulary, identity strategy and URL recognizer a domain must
   provide; what a domain may never touch; and — the owner's decision at planning time —
   **where its code lives, prescriptively**: a per-domain package holding all of the above, with the
   registration points that stay shared named exhaustively (`DOMAINS`, provider wiring in `main.py`,
   migrations). The layout section is a prescription, and Phase B moves books and albums into it.
2. **A conformance suite** — `backend/tests/test_domain_conformance.py` — parametrized over
   `DOMAINS`, so it runs against books and albums today and against a third domain by that domain
   existing. It absorbs `test_domain.py:140-179` rather than duplicating it, and checks at least:
   the three published unions cover this domain's values; every declared status has a label and a
   distinct triage key within its domain; `default_status` is one of the declared statuses;
   `entry_fields` is a subset of the passage fields; a field spec's `columns` is present exactly for
   `rows` fields; a metadata field never shadows a `RESERVED_FIELD_NAMES` column; the identity rule
   rejects what it should; and the API refuses this domain's non-values with a 422. Plus two the
   measurement forces:
   - **every value a domain declares is accepted by the database, not only by the API** — the check
     that fails today for a hypothetical third domain and makes the CHECK-constraint finding a test
     result rather than an opinion;
   - **the frontend's `entryStatuses` / `entryFormats` agree with the registry**, so the hand-mirrored
     TypeScript unions cannot drift the way a hand-maintained label map would.
3. **A measurement of what is misplaced, as a costed table of alternatives — not one path.** One row
   per finding: what it is, which domains it blocks, the options with their cost, and a
   recommendation. The two named findings above and the cover chooser are its minimum contents.
4. **A paper walk through IGDB against the suite**, which is where DEC-052's prediction that "games
   need no seam albums did not" is actually tested. It must also answer the question the epic asks:
   **which shared files would an IGDB team edit, and would a Spotify team editing them the same week
   collide?** That is the falsifiable form of "developed in parallel without interfering". Cheaper
   and more honest than another bespoke sprint.

### Phase B — only what the verdict justifies

5. **Move books and albums into per-domain packages**, one coherent slice per move, with the suite
   green before and after — the demonstration that the contract's layout section describes something
   that exists.
6. Move anything else the suite proves is misplaced, on the same terms.

## Acceptance criteria

1. The contract document is sufficient to build a domain without reading Sprints 025–027, and states
   where that domain's code lives.
2. The conformance suite runs against every registered domain by parametrization, not by a
   per-domain test, and both books and albums pass it.
3. The suite fails when a deliberately malformed domain is registered in a test — a status with no
   label, a `default_status` outside the vocabulary, a `rows` field with no columns, **and a status
   value the database's CHECK constraint would refuse**.
4. The measurement is a costed table with alternatives per finding, and covers the CHECK constraint,
   the enrichment key, and the cover chooser.
5. The IGDB paper walk produces a written verdict naming every seam it would and would not need, and
   the shared files two parallel domain teams would contend over.
6. Phase A changes no user-visible behavior; the full suite and the e2e gate are green and unchanged.
7. Any Phase B move leaves every existing test green without weakening one, and is a separate commit.
   The per-domain package move is either delivered or explicitly deferred with the owner's recorded
   go-ahead — not left ambiguous.

## Required tests (TDD)

- The conformance suite itself, written against books and albums before any move.
- A malformed-domain fixture, registered only inside the test, that each conformance check rejects.
- The database-acceptance check written against a fixture domain whose status the current constraint
  refuses, so the finding is reproducible rather than argued.
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
suite fails against a malformed domain and passes against both real ones. **Phase B's package move
re-arms the full walkthrough gate** against a library holding books and albums: nothing user-visible
should change, and that has to be seen rather than asserted.

## Explicit non-scope

- **Building a third domain.** That is an epic on top of this contract (DEC-058), and building one
  here would be the thing this sprint exists to make unnecessary.
- **Per-domain imports.** Sprint 030. Phase A *names* the book-shaped import layer as misplaced and
  costs it; moving it is 030's whole outcome.
- **The one search bar.** Sprint 029 (DEC-065).
- **A plugin runtime.** Product spec section 2 has held the line since v1: the registry is code.
- Re-opening DEC-057, DEC-059 or DEC-062.

## Commit checkpoints

1. `test: hold every domain to the same contract` (the suite, against books and albums)
2. `docs: state what a domain must supply` (the contract, plus the IGDB verdict as a decision)
3. Phase B only, one per move, e.g. `refactor: give each domain its own package`
4. final `docs(sprint-028): close sprint and hand off`

## Risks and decisions to surface

- **The gate is real.** Phase A concluding that almost nothing is misplaced is a correct outcome and
  must be reported as one, not padded into a refactor to justify the sprint. The measurement above
  makes that unlikely, which is a reason to trust the measurement rather than to widen the sprint.
- **A conformance suite that only restates the dataclass is worthless.** It has to be able to fail:
  the malformed-domain fixture is the acceptance criterion that keeps it honest.
- **Scope creep runs through "while we are here".** Every move Phase B makes must be one the suite
  or the measurement proved, not one the reader noticed.
- **The per-domain package move touches import paths across the backend and is the largest thing in
  this sprint.** If it runs long, it is the slice to hand to the first domain epic with the contract
  already written — not the slice to rush. Say so in the handoff rather than half-finishing it.
- The cover chooser on an album is a real defect and predates this sprint. Decide whether it is in
  scope or scheduled, rather than leaving it unmentioned a fourth time.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
