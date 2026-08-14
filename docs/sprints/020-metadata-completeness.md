# Sprint 020 — Metadata completeness: viability, then build

**Status:** completed
**Depends on:** 019
**Roadmap revision:** 8

## Objective

A measured verdict on whether cross-provider field completion and edition choice are affordable,
and then whatever that verdict — plus an explicit owner go-ahead — justifies building.

**This sprint is gated.** DEC-035 approves an *assessment*, not an implementation. An agent that
arrives here and starts building cross-provider merging because the feature is "approved" has
skipped the entire point. Phase A concluding that the feature is not worth its cost is a
legitimate, complete outcome.

## Required context

1. `AGENTS.md`
2. `docs/sprints/ROADMAP.md`, the Sprint 020 section — the gate and the owner's framing are stated
   there and this file does not replace them
3. `docs/specs/product-spec.md` section 4.3 (per-field completion) and section 5 (enrichment)
4. `docs/specs/technical-spec.md` section 6 (providers), section 7 (jobs), section 1 (budgets)
5. `docs/decisions.md` DEC-008 (enrichment fills empty fields only), DEC-025 (verification requires
   using the application; provider behaviour is proven against recorded responses), DEC-035 (the
   gate itself), DEC-036 (stored normalized projection), DEC-041 (a dev-server-only suite is not
   evidence about the shipped artifact)
6. Sprint 018 Outcome and `docs/agent/HANDOFF.md`
7. `backend/src/book_tracker/infrastructure/providers.py`, `application/enrichment.py`,
   `infrastructure/covers.py`, `infrastructure/jobs.py`, and
   `backend/tests/fixtures/providers/` with its README

## Current implementation baseline

Re-derive at activation. As of Sprint 018's close: enrichment tries Open Library and consults
Google Books only when Open Library fails or returns nothing usable, so a record that comes back
usable but incomplete is accepted as-is. One cover is stored per item at `data/covers/<item_id>.jpg`
and there is no notion of candidates. `RateLimiter` enforces a minimum interval per provider and
the 429/backoff path is tested at the HTTP boundary. `scripts/benchmark_library.py` measures list
latency at 10,000 entries, idle and with the job queue draining, and is the natural place to add
provider-request counting rather than starting a harness from nothing.

## Phase A — viability and impact assessment

No product change ships in this phase. The deliverable is a written verdict in `docs/decisions.md`
with measurements behind every claim, answering:

- What each provider's published and observed rate limits actually are, and what a 500-book and a
  5,000-book import would cost against them under per-field completion.
- Measured wall-clock impact on a realistic import, against current fallback-only behaviour as the
  baseline.
- Whether a fetched candidate can be **verified to be the same edition** before its fields are
  merged. The known sharp edge: `GoogleBooksProvider.fetch_by_isbn` takes the first hit of an
  `isbn:` search, which is not guaranteed to carry the requested ISBN13, so merging its publisher
  or page count risks attaching one edition's data to another. **Treat this as a live v1 defect,
  not only as a question.** It does not wait on the gate: the current fallback path already calls
  `fetch_by_isbn`, so a wrong edition's data can already be written today. If Phase A concludes
  against building the rest of the feature, repairing this still ships.
- What storing multiple cover candidates costs on disk, and whether they are fetched eagerly or on
  demand when a chooser is opened.
- How failure semantics change shape: one provider succeeding while another errors is a successful
  enrichment, not a failed job.
- Whether DEC-008's fill-empty-only invariant survives unchanged. It should, because merging
  happens before the write, but that must be demonstrated rather than assumed.
- **Whether a provider placeholder image can be detected at all, and by what** — byte-size
  heuristic, perceptual hash against known placeholders, or nothing. DEC-035 folded the
  "image not available" observation into this sprint on the reading that a second candidate gives
  that case a way out. That is true for a chooser the owner opens deliberately; it is not true for
  the automatic path, where a placeholder still resolves as the default cover and nothing notices.
  Answer both paths or say plainly that only one is addressed.

Two pieces of prior art belong in Phase A's reasoning rather than being rediscovered. Product spec
4.3 already specifies per-field completion at **search** time — "prefer Open Library's record and
Google Books' cover if OL has none" — and `_merge_group` in `domain/providers.py` implements it
there. So this sprint may be narrowing an inconsistency between search and enrichment rather than
inventing a behaviour, which lowers the complexity estimate and raises the argument for doing it.

Phase A may conclude a narrow slice — cover choice alone, on demand, with no change to automatic
enrichment — carries most of the value at a fraction of the risk. Report that plainly.

## Phase B — build what Phase A justified

Scope is set by Phase A's verdict and an explicit owner go-ahead, not by this document. Whatever is
built inherits the existing invariants without exception: imported user data is never overwritten,
network providers are never consulted while rendering cached library pages, and enrichment still
only fills empty fields.

## Acceptance criteria

1. Phase A's verdict is recorded in `docs/decisions.md` with the measurements that support it,
   **including the ones that argue against building**.
2. Edition verification is answered concretely: either a fetched candidate can be confirmed to be
   the requested edition, or the assessment says it cannot and what that rules out.
3. If Phase B proceeds: no regression in import throughput beyond the budget Phase A set, no
   provider blocking or rate-limit errors under a full-library run, and the fill-empty-only
   invariant proven intact.
4. If a cover chooser ships: reachable from the detail page, defaults to the current cover, never
   blocks the page it lives on, and passes the axe gate like every other surface.
5. The two long-standing observations folded into this sprint are addressed or explicitly deferred
   with a reason: a provider "image not available" placeholder stored as a real cover, and edition
   choice preferring a recent reprint over the original.

## Required tests (TDD)

- Provider behaviour against the recorded fixtures in `backend/tests/fixtures/providers/`, never
  against a mock of the method under test (DEC-025). **Never silently re-record a fixture** — it is
  a pinned observation of an external contract.
- Edition verification: a candidate whose returned identifiers do not include the requested ISBN13
  is rejected before any field is merged.
- DEC-008 intact: a merged record still never overwrites a field the user or an import supplied.
- If a chooser ships: unit coverage for candidate selection, an e2e path through the detail page,
  and an axe check on the open chooser.

## Verification

```bash
python scripts/validate_project.py
make format
make check
make test
cd frontend && npm run test:e2e
cd .. && make build
make smoke-container
git diff --check
```

Plus, recorded in the Outcome: the Phase A measurements in full, and a walkthrough against the
container (not `make dev`) if anything user-visible shipped.

## Explicit non-scope

- Authentication, public exposure, multi-user support.
- Rewriting the enrichment job runner. Extend it.
- Re-recording provider fixtures to make a test pass.

## Commit checkpoints

1. `feat: count provider requests per enrichment job in the benchmark`
2. `docs: record the Phase A metadata completeness verdict`
3. Phase B checkpoints, named once the verdict and the owner's go-ahead exist
4. final `docs(sprint-020): close sprint and hand off`

## Risks and decisions to surface

- The gate itself: do not start Phase B without an explicit owner go-ahead recorded in
  `docs/decisions.md`.
- Free-tier limits are the owner's exposure, not the agent's. Doubling traffic per book must not
  get the application rate-limited or blocked.
- This sprint sets the provider contract that Sprint 024's domain pilot inherits. Whatever Phase A
  concludes about verifying a candidate before merging its fields is the answer albums and games
  will be built against, so record the reasoning, not only the verdict.

## Outcome

**Phase A ran; Phase B did not start.** The owner set that shape at planning time: deliver the
measured verdict plus the ungated repair, then stop, so the Phase B decision is made with numbers in
hand. No go-ahead was given and none is recorded, which is the gate working as DEC-035 designed it.

### Delivered

| | |
|---|---|
| `4a08747` | provider-request counting in the benchmark, plus its own repair |
| `45bfabb` | live completeness harness, `classify_edition`, `ItemPayload.edition_match` |
| `0f579fd` | **DEC-044**, the Phase A verdict |
| `2e1f388` | edition verification enforced; placeholder-cover guard |
| `602afb8` | `strip_html` at the provider boundary; migration `0008` |

### Acceptance criteria

1. **Verdict recorded with measurements, including those arguing against building** — DEC-044.
   The numbers that argue against are the load-bearing ones: cross-provider completion buys a
   description in 22% of cases, a page count in 12%, and **0% for year, publisher, authors and
   cover**, while multiplying per-book traffic and breaching the Google free tier threefold on a
   5,000-book import.
2. **Edition verification answered concretely** — yes for Open Library (100% confirmed across 44
   answers, because `/isbn/` resolves authoritatively), and only sometimes for Google Books
   (80.4% confirmed, 19.6% unverifiable, 0% contradicted). What that rules out is stated: a volume
   that cannot be tied to the requested ISBN is not merged at all.
3. **Phase B did not proceed**, so its throughput and rate-limit criteria do not apply. The
   fill-empty-only invariant is nonetheless proven intact on the path that did change, by
   `test_a_verified_google_volume_still_only_fills_empty_fields`.
4. **No chooser shipped**, so its criteria do not apply. DEC-044 costs one out for the owner:
   candidates are free from the Open Library work record enrichment already fetches — 28 covers for
   Rayuela, 33 for the sampled *Cien años de soledad* — so discovery needs zero extra requests.
5. **Both folded observations addressed.** The placeholder cover is *fixed*, not merely described:
   it is detectable by geometry (Google's is 575x92, a 6.25:1 banner, against real covers at 0.66
   and 0.77) and `prepare_cover` now rejects it. The reprint-over-original ranking is *reproduced
   and explicitly deferred with a reason* — it is search ranking governed by product spec 4.3 and
   DEC-024, so changing it is user-visible product behaviour outside an assessment's remit.

### Verification, actual results

`python scripts/validate_project.py` passed. `make check` passed. `make test` backend **209** /
frontend **83**. `npm run test:e2e` **75 passed / 2 skipped** across both projects, matching the
Sprint 019 baseline. `make build` clean with no chunk-size warning. `make smoke-container` passed,
its verified restore reporting revision `0008_plain_text_descriptions`. `git diff --check` clean.

### Walkthrough

Ran against a container on a **copy** of the library, never the real one. The copy sat at revision
`0006`, so startup wrote `pre-migration-20260814T002018Z` and then applied both `0007` and `0008`
unattended — the DEC-039 path exercised for real rather than asserted. A three-row Goodreads import
whose ISBNs came from `/api/search` committed after resolving one genuine ambiguity (the library
already held two copies of *Cien años de soledad*), reporting `unsorted_entries: 2`.

Enrichment then exercised both sides of the repair. For `9788419233790` Open Library missed with
`edition_not_found` and the Google Books fallback **confirmed** the edition, so it was merged:
RM Verlag, 136 pages, 2024. For `9788437604572` Open Library hit and supplied Cátedra and **746**
pages — notably *not* the 762 the unverifiable Google volume would have written. Every stored cover
measured portrait (ratios 0.59–0.67); none was placeholder-shaped. Four detail pages were opened in
a real browser: no literal `<p>` or `<b>` anywhere, and no console errors in the whole run. The
*Escaping the Build Trap* description now reads as prose in paragraphs. `docker stop` logged
`Application shutdown complete` and exited **143**.

### Deviations

- **Commit order differs from the checkpoint list in this file.** The repair lands *after* the
  verdict rather than before, because the owner chose to let the measurement pick the policy for
  unverifiable candidates rather than fixing it in advance.
- **A prerequisite defect was repaired**, as `AGENTS.md` section 2 permits and requires recording:
  `scripts/benchmark_library.py` still emitted `normalize_text(...)` in `query_plans`, which DEC-036
  removed as a connection-level function, so every run of the script since had died with
  `no such function`. Phase A could not measure without it.
- **One fixture was added, none re-recorded.** `googlebooks_isbn_9780307474728.json` supplies the
  confirmed case so the repair can be shown to still admit a verified volume. The existing
  `googlebooks_isbn_9788437604572.json` turned out to *already* contain the defect, and a live check
  confirmed the same volume still comes back, so nothing was refreshed.
- **`ItemPayload` gained a field**, `edition_match`. Recorded because Sprint 024 inherits it.
- **Two existing tests changed meaning deliberately**, both named in DEC-044's reasoning:
  `test_open_library_miss_falls_back_to_google_books` now runs against the confirmed fixture, and
  the unverifiable case became its own test asserting the rejection.

### Impact on future sprints

- **021 (attachments), 022 (creator sort), 023 (export)** — unaffected.
- **024 (albums)** inherits the verification contract, which is why DEC-044 records reasoning rather
  than only a verdict: a provider fills fields only when its candidate can be tied to the identifier
  requested. MusicBrainz's release-versus-release-group split is the same problem.
- **A Phase B remains available and unstarted**: cover choice from Open Library work-record
  candidates, on demand. It needs an explicit owner go-ahead recorded in `docs/decisions.md`.
- **Three observations are unowned and recorded**: Open Library title mojibake, the 5-second search
  timeout that silently yields Google-only results, and the quoted publisher string.
