# Project assessment — 2026-08-08

**Status:** historical. An audit of the repository as it stood after Sprint 013, kept because the
diagnosis and the gates it produced are still load-bearing — every verification rule in
`CONTRIBUTING.md` traces to it. **File paths below describe the code on that date** and several have
moved since; the current layout is in technical spec §2.

---

**Author:** audit session preceding roadmap revision 6
**Trigger:** after Sprint 013 the owner reported the product as a candidate failure — clunky UI,
incomplete flows, searched books not found, books added without metadata, missing polish — and
asked whether the cause was the stack, over-specification, problem difficulty, or execution.
**Verdict:** execution, in one bounded and identifiable way. Do not rebuild.
**Recorded as:** DEC-024, DEC-025, DEC-026.

---

## 1. Summary

Thirteen sprints closed with green gates — 122 backend tests, 38 frontend tests, 86% coverage,
`scripts/validate_project.py` passing — on a product that does not work. All of those gates
passed honestly. None of them could observe the failures.

Of the four hypotheses the owner raised, three are wrong:

- **Bad stack.** No. The specified stack is appropriate. It was also never installed — see
  section 2. The product was judged on a stack it never received.
- **Over-specification.** No. `docs/specs/product-spec.md` anticipated Excel-armoured Goodreads
  ISBNs, Calibre's directly-mappable 0–10 rating scale, provisional score handling, keyset
  versus offset pagination, and the conflict between layout animation and virtualization. It is
  not the problem.
- **Problem too hard.** No. The backend demonstrates otherwise: roughly 4,900 lines with a clean
  domain/application/infrastructure split, Alembic migrations, ISBN-10/13 conversion-equivalent
  identity, typed identity conflicts that refuse to auto-merge, keyset pagination with NULL-last
  ordering, a leased job runner that survives restart, and an import ledger with 24-hour undo.
- **Bad execution.** Yes — concentrated in roughly 2,600 non-test lines of frontend, plus four
  backend defects, plus a protocol that could not detect any of them.

---

## 2. Three required libraries were never installed

`docs/specs/technical-spec.md` section 8 requires "React Hook Form with schema validation,
shadcn/ui primitives, Tailwind tokens, and Motion." Three of those are absent from the running
project.

| Required | State | Evidence |
|---|---|---|
| shadcn/ui | never installed | `frontend/components.json` is configured (new-york, zinc, `cssVariables: true`) but `frontend/src/components/ui/` does not exist and the lockfile contains zero Radix packages |
| Motion | installed, never used | `motion` is in `package.json`; imported in zero files |
| React Hook Form + zod | never installed | absent from `package.json`; ~18 fields in `DetailPage.tsx` are uncontrolled and read via `FormData` |

Consequences that follow directly:

- `tailwind.config.ts` is `theme: { extend: {} }` with no plugins, and `index.css` defines no CSS
  variables despite `components.json` declaring `cssVariables: true`. **There is no design
  system** — colour is inline `zinc-*` and `fuchsia-*` literals.
- `index.css` names Inter but never loads it. The application has been rendering in `system-ui`.
- Every status, sort, and filter control is a native `<select>`, which cannot be styled and
  renders as an operating-system widget inside a dark interface. This is the single largest
  contributor to the reported clunkiness.
- The five navigation icons in `AppShell.tsx` are hand-drawn SVG paths in which `LibraryIcon` and
  `ShelfIcon` are the same three horizontal lines.
- Every microinteraction in product-spec section 7 — score-picker springs, sort crossfade,
  add-flow stagger, optimistic rollback feedback, cover blur-up — does not exist. The
  `prefers-reduced-motion` block in `index.css` guards animations that were never written.

Product-spec section 7 chose this stack with an explicit rationale: "highest polish-per-unit-effort
for someone without frontend experience," and rejected Jinja+HTMX specifically to avoid
"hand-designed markup." What was built is hand-designed markup with the polish mechanism removed.

---

## 3. Four defects verified against live systems

### 3.1 Background enrichment has never succeeded

`OpenLibraryProvider.fetch_by_isbn` in `backend/src/book_tracker/infrastructure/providers.py`
delegates to `self.fetch(isbn)`, which requests `https://openlibrary.org/books/{isbn}.json`. That
endpoint accepts an OLID, not an ISBN. Product-spec section 4.2 already specifies the correct
`/isbn/{isbn}.json` form.

Measured live on 2026-08-08:

```
GET https://openlibrary.org/books/9780441013593.json  → 404   (what the code requests)
GET https://openlibrary.org/isbn/9780441013593.json   → 302   (what the spec specifies)
```

Every enrichment job raises, is caught by a bare `except Exception` in
`backend/src/book_tracker/application/enrichment.py`, and is recorded as an opaque failure. There
is no fallback to Google Books. **This is why imported books have no covers and no metadata.**

The correct fix requires two changes, not one: the URL, and `follow_redirects=True` on the shared
`httpx.AsyncClient` in `main.py`, which is not currently set. A 302 passes `raise_for_status()`
and would then fail JSON parsing.

**Why no test caught it:** all five occurrences of `fetch_by_isbn` in
`backend/tests/test_jobs.py` replace the method with an `AsyncMock`. The real implementation has
never executed in CI. The tests prove the job runner calls a method; they prove nothing about
what that method does.

### 3.2 Search ranking discards provider relevance

`merge_and_rank` in `backend/src/book_tracker/domain/providers.py` sorts merged candidates by:

```
(title != query, language not in {es, en}, cover is None, normalize_text(title), source, source_id)
```

The fourth key is alphabetical by title. Both providers return results in relevance order; this
re-sorts them A–Z. A search whose target does not match the query string exactly lands wherever
the alphabet places it.

Product-spec section 4.3 describes the ranking as "deliberately dumb," meaning do not
over-engineer it. Discarding the ordering the providers already computed is not that.

### 3.3 Google Books never registers

`main.py` appends the provider only when `google.enabled`, which requires a non-empty
`GOOGLE_BOOKS_API_KEY`. There is no `.env` file, so search has been running on Open Library alone
— weakest precisely on the Spanish-language and small-press editions the product targets.
Product-spec section 2 selected Google Books for exactly that coverage. The degradation is
silent: no warning at startup, no indication in the interface.

### 3.4 Every toast is invisible

`"Already in your library"`, `"Book added"`, and `"Book removed from your library"` are written to
`sessionStorage` under `akasha.toast` by `AddPage.tsx` and `DetailPage.tsx`, read by the
destination route, and rendered into:

```jsx
<p className="sr-only" aria-live="assertive">{announcement}</p>
```

in `HomePage.tsx` and `TriagePage.tsx`. `sr-only` is visually hidden. **The application's entire
feedback layer is screen-reader-only.** Adding a book, deleting a book, and hitting a duplicate
all complete in visual silence. Product-spec section 4.3 explicitly requires a visible toast on
duplicate add.

The e2e suite passes because Playwright reads visually hidden text as readily as visible text.

### 3.5 Smaller defects, same root

- Search results 2 through 20 never resolve an edition year. The work-resolution loop in
  `OpenLibraryProvider.search` is gated on `and not enriched`, true only on the first iteration.
- The shelf filter on `/` is built from `entries.flatMap(entry => entry.shelves)` — only the
  pages loaded so far — while `GET /api/shelves` exists and is used correctly by `ShelvesPage`,
  `DetailPage`, and `AddPage`. The filter list is incomplete and changes as the user scrolls.

---

## 4. Why the protocol did not detect any of this

`AGENTS.md` section 3 defined verification as the sprint's own commands, plus `make check`,
`make test`, and "the specified browser or Playwright checks." Every sprint satisfied that
honestly.

Three structural gaps made the gate blind:

1. **Nothing required using the application.** No step asked an agent to open the app, add a
   book, and look at what happened. An invisible confirmation and a blank imported library are
   both invisible to a command runner.
2. **Playwright never ran in CI.** `.github/workflows/ci.yml` ran `make check`, `make test`, and
   `make build`; `make test` runs pytest and vitest only. The eight Sprint 013 layout
   regressions — the only guardrail on the grid contract — were local-only.
3. **Mocking the unit under test counted as testing it.** The enrichment defect survived thirteen
   sprints behind an `AsyncMock` of the exact method that was broken.

The result is legible in the sprint history. Sprint 013 spent a full cycle on grid-cell overlap
geometry — real, careful work, correctly executed — while adding a book produced no visible
confirmation and importing a library produced blank rows. Nothing in the loop could see the
difference in priority, because nothing in the loop had seen the product.

This is a process defect, not a capability defect. It is addressed by DEC-025.

---

## 5. Disposition

**Keep the backend.** It is an asset. Rebuilding it would cost weeks and would likely produce
something worse.

**Rebuild the frontend on the specified stack.** At roughly 2,600 non-test lines it is small
enough to redo deliberately rather than patch incrementally, and patching it would preserve the
hand-rolled substrate that is the actual problem.

**Fix the protocol first-class**, not as a footnote. The same discipline that produced thirteen
green sprints will produce good work once it is pointed at the product rather than at the test
suite.

Roadmap revision 6 sequences this as: Sprint 014 correctness (backend only, so real metadata and
covers exist before the interface that displays them is judged), Sprint 015 design system and
components, Sprint 016 motion and interaction polish, Sprint 017 hardening, Sprint 018 release.

## 6. Owner actions required

- Provision a Google Books API key and place it in `.env` as `GOOGLE_BOOKS_API_KEY`. Free tier,
  roughly 1,000 requests per day, no billing account. Sprint 014 cannot be fully verified without
  it.
