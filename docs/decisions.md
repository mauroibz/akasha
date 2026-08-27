# Decisions and deviations

Append-only record of material architecture choices, product-default resolutions, and differences between plans and implementation. Later decisions supersede earlier ones by reference; do not rewrite history.

## DEC-001 — Canonical document hierarchy

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** The source product draft mixed product intent with implementation sketches and had no deterministic agent handoff.
- **Decision:** Product behavior is canonical in `docs/specs/product-spec.md`; implementation contracts are canonical in `docs/specs/technical-spec.md`; the active sprint controls sequence. `AGENTS.md` defines conflict precedence.
- **Consequence:** Agents may refine implementation details without re-litigating product scope, but must record material deviations and cannot edit product intent to excuse incomplete work.

## DEC-002 — Import provenance uses a ledger

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** The source draft referenced an undefined `items.import_source` and proposed undo by `entries.import_batch`, which could delete pre-existing records or lose fill-empty history.
- **Decision:** Use `import_batches` plus `import_batch_entries` with created flags and before-values. Undo only effects proven to belong to that batch.
- **Consequence:** Import and undo are auditable and idempotent at the cost of two explicit tables.

## DEC-003 — Preserve merged provider identities

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** Search merging must retain Open Library and Google Books IDs, but one `items.source/source_id` pair cannot represent both or enforce secondary-source dedupe.
- **Decision:** Add `item_sources`; retain `items.source/source_id` as the preferred refresh source.
- **Consequence:** Exact dedupe works for any known provider identity without introducing a plugin registry.

## DEC-004 — Durable in-process job queue

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** Import enrichment must run for minutes outside requests and survive restart, while deployment remains one container/process.
- **Decision:** Persist jobs and leases in SQLite and run one cooperative poller in FastAPI lifespan. Handlers are idempotent; expired jobs are reclaimed.
- **Consequence:** No Redis/Celery dependency. Multiple Uvicorn workers are unsupported in v1 and must be prevented/documented.

## DEC-005 — Opaque, versioned keyset cursors and exact counts

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** The comma cursor in the draft is ambiguous for text/null values, and a count cache has difficult invalidation before profiling establishes a need.
- **Decision:** Use base64url versioned JSON cursors bound to sort/filter identity, explicit null buckets, and exact counts initially.
- **Consequence:** Cursor behavior is testable and evolvable. Count caching is deferred until measured.

## DEC-006 — Authorized defaults for four open product questions

- **Date:** 2026-07-21
- **Status:** accepted pending owner override
- **Context:** Four nonblocking questions remained in the source product draft.
- **Decision:** Unsorted is searchable but hidden by default; entry deletion retains items/covers; one row remains one edition with lossy rereads; series remains free text.
- **Consequence:** Agents do not stop for these questions. Any owner change updates product/technical specs and downstream sprints.

## DEC-007 — Network/file work outside SQLite write locks

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** The one-call add requirement described remote fetch, cover handling, and relational creation as atomic, but holding a SQLite write transaction across network calls would block local writes.
- **Decision:** Fetch and prepare cover to a temporary file first; perform dedupe, item/entry writes, and atomic file placement in a short transaction with compensating file cleanup.
- **Consequence:** The client still makes one request and relational state remains atomic; file side effects have explicit cleanup semantics.

## DEC-008 — Existing personal values outrank imports

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** The source draft both said Calibre re-sync never touches entries and suggested that higher-confidence Calibre values win import collisions.
- **Decision:** Source confidence chooses among rows only while creating a new entry in one commit. Once an item or entry exists, imports fill empty fields and record conflicting alternatives; they never replace non-empty personal values.
- **Consequence:** Calibre's native score can seed a new entry but cannot erase a provisional or manually edited score. Triage exposes the alternative for explicit choice.

## DEC-009 — Persist import plans and ordered effects

- **Date:** 2026-07-21
- **Status:** accepted; supersedes DEC-002's `import_batch_entries` shape
- **Context:** Commit must apply exactly what preview showed, Calibre can change between requests, and safe undo needs per-effect before/after evidence.
- **Decision:** Persist normalized `import_records` and explicit ambiguity decisions during preview. Commit records ordered `import_effects`; undo reverses only effects whose current values still equal the imported after-values and neutralizes batch jobs.
- **Consequence:** Preview creates audit/staging rows but no library entities. Commit is deterministic, and undo cannot overwrite later user edits.

## DEC-010 — Relational authoritative identity and edition-safe matching

- **Date:** 2026-07-21
- **Status:** accepted; supersedes DEC-003's preferred-source fields
- **Context:** JSON identifiers and check-then-insert cannot enforce concurrent dedupe, while title/author matching can collapse distinct editions.
- **Decision:** Store canonical ISBN/Calibre identities in uniquely constrained `item_identifiers` and provider records in `item_sources`, with one primary refresh source. Title/author is ambiguity evidence only and never auto-merges.
- **Consequence:** ISBN-10/13 equivalents and provider duplicates collide safely; translations/reprints remain separate unless explicitly resolved.

## DEC-011 — Cover installation follows relational commit

- **Date:** 2026-07-21
- **Status:** accepted; supersedes DEC-007's in-transaction file placement
- **Context:** Filesystem and SQLite commits cannot be atomic, and the product requires cover failure not to roll back a valid entry.
- **Decision:** Prepare a temporary cover before the write transaction, commit relational item/entry creation without `cover_path`, then install/update the cover in a second short transaction or idempotent job.
- **Consequence:** One HTTP request still creates the entry; cover state is explicitly eventual and non-fatal.

## DEC-012 — Work URLs require edition choice

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** Open Library work records and `first_publish_year` are not edition metadata, and silently choosing a first edition violates the edition-level model.
- **Decision:** A work URL resolves to ranked edition candidates for user selection. Work-level first publication year may populate `original_year`, never edition `year`.
- **Consequence:** URL add takes one extra selection for work links but does not cache false edition metadata.

## DEC-013 — Import conflicts remain audit data

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** Storing incoming conflicts on an existing entry would violate the rule that imports never modify existing personal records, while conflicting exact identifiers can point at different editions.
- **Decision:** Keep alternatives in durable `import_records`, not `entries`. If exact identities resolve to different items, quarantine the row as `identity_conflict` and require explicit resolution; never select or merge a winner automatically.
- **Consequence:** Triage joins audit conflicts for display, existing entries remain untouched, and contradictory identifiers cannot silently corrupt edition identity.

## DEC-014 — Reproducible dependency locks use uv and npm

- **Date:** 2026-07-21
- **Status:** accepted
- **Context:** Python and Node dependencies must resolve identically in local development, CI, and the multi-stage image without shipping build tools in the runtime.
- **Decision:** Commit `backend/uv.lock` and install it with `uv sync --frozen`; commit `frontend/package-lock.json` and install it with `npm ci`. The runtime copies a non-editable Python virtual environment built at its final absolute path, and copies only Vite output from the Node stage.
- **Consequence:** Builds are reproducible and the final image has one Python process with no Node executable. Dependency upgrades are explicit lockfile changes.

## DEC-015 — SQLite text normalization is deterministic at the connection boundary

- **Date:** 2026-07-22
- **Status:** accepted
- **Context:** Keyset text ordering, accent-insensitive search, and cursor values must use identical semantics, while SQLite's built-in `NOCASE` collation is ASCII-only and cannot implement the settled Unicode normalization rule.
- **Decision:** Register a deterministic `normalize_text` SQLite function on every application connection and use it for title/first-author search, ordering, and cursor values. Keep composite indexes for the common entry status/date/score paths; reassess a stored normalized projection only if Sprint 011 measurement shows text sorting needs it.
- **Consequence:** Text behavior is consistent without duplicating normalized user-visible values. Alembic remains independent of application-defined functions, and text-sort index optimization stays an explicit measured hardening task.

## DEC-016 — Shared edition metadata boundary precedes imports and enrichment

- **Date:** 2026-07-22
- **Status:** accepted
- **Context:** Interactive add, Calibre, Goodreads enrichment, refresh, and manual correction need one stable interpretation of edition metadata and cached covers. Building Calibre first would duplicate or prematurely settle that boundary.
- **Decision:** Insert Sprint 008 for working book metadata/covers and shift Calibre through release to Sprints 009–013. Open Library remains the primary refresh identity; optional Google Books may fill only absent fields for the same canonical ISBN. Persist cover paths internally and expose controlled versioned API URLs.
- **Consequence:** All later ingestion paths reuse typed metadata, edition/original-year separation, secure cached covers, and preservation semantics. Final-project validation now closes after Sprint 013.

## DEC-017 — Editorial UI completion follows Calibre

- **Date:** 2026-07-22
- **Status:** accepted; supersedes DEC-016 only for downstream sprint numbering
- **Context:** The implemented APIs and screens cover core workflows but omit planned navigation,
  entry deletion, shelf management, complete modal behavior, and a coherent responsive visual system.
  Calibre remains the next source boundary and its actual UI must exist before import screens are
  redesigned together.
- **Decision:** Keep Calibre as Sprint 009, insert a dedicated editorial UI redesign/completion Sprint
  010, and shift jobs, triage, hardening, and release to Sprints 011–014. Permit only small typed API
  additions directly required by a specified screen; retain full triage as its own sprint.
- **Consequence:** Sprint 010 can redesign the real Goodreads/Calibre experience and close current
  product-spec UI gaps without simulating jobs or triage. Final-project validation closes after
  Sprint 014.

## DEC-018 -- Shelf response gains entry_count

- **Date:** 2026-07-22
- **Status:** accepted
- **Context:** Sprint 010 requires shelf entry counts in the `/shelves` management UI, but the
  existing `ShelfResponse` only carried id, name, and slug.
- **Decision:** Extend `ShelfResponse` with `entry_count: int = 0` via a `func.count` subquery join
  on `entry_shelves` in `list_shelves`. No schema change is needed; the count is derived at query
  time. OpenAPI and typed frontend clients were regenerated.
- **Consequence:** Shelf management can display counts and update them after mutations without a
  separate API call. The count is always fresh from the database.

## DEC-018 — Job runner shares the FastAPI event loop

- **Date:** 2026-07-22
- **Status:** accepted
- **Context:** Sprint 011 needs a durable background job runner for enrichment tasks. The
  sprint risk notes asked whether a separate process is needed or the runner can share the
  FastAPI event loop.
- **Decision:** The `JobRunner` runs as a cooperative poller within the FastAPI lifespan.
  It uses `UPDATE … LIMIT 1` to atomically claim jobs without a separate worker process.
  Rate limiting and retry caps are clock-injected for deterministic testing. On startup,
  `reclaim_expired` returns crashed running jobs to `queued`.
- **Consequence:** No additional process management is needed for v1 LAN-only deployment.
  The runner is testable without subprocess orchestration. If throughput demands a separate
  worker later, the `JobRepository` API already supports external claiming.

## DEC-019 — Undo field-matching semantics

- **Date:** 2026-07-22
- **Status:** accepted
- **Context:** Sprint 011's safe undo must not remove later user edits. The spec requires
  reverting a field only if the current value still matches the recorded imported value.
- **Decision:** `UndoService` records `before_values` and `after_values` in
  `import_effects`. On undo, a `fill_empty` field is reverted to `before_values[field]`
  only when `_values_equal(current, after_values[field])` returns true. If the current
  value differs (user edited after import), the field is retained and counted as
  `retained`. Items with any retained field are added to a `modified_items` set that
  prevents their `create` effect from deleting the item. Created entries are deleted only
  if `after_values` contains `{"created": true}`. Created items are deleted only if no
  other entries reference them (shared-item safety).
- **Consequence:** Undo is safe to run at any time within the 24-hour window. Partial
  retention is reported in the API response and UI. Repeated undo is a no-op.

## DEC-020 — Triage page uses existing bulk API

- **Date:** 2026-07-22
- **Status:** accepted
- **Context:** Sprint 012 needed a bulk-first triage page. The backend bulk
  update API (`PATCH /api/entries/bulk`) and accept-suggested endpoint
  (`POST /api/entries/accept-suggested`) were already implemented in Sprint 010
  with server-side select-all and exclusions support.
- **Decision:** Build only the frontend triage page that exercises the existing
  API. No backend changes needed.
- **Consequences:** The triage page sends `filter` + `excluded_entry_ids` for
  select-all-with-exclusions, and `entry_ids` for explicit selection. The API
  contract is unchanged.

## DEC-021 — Inbox button navigates to /triage

- **Date:** 2026-07-22
- **Status:** accepted
- **Context:** The HomePage Inbox button previously toggled the `status=unsorted`
  filter on the library page. Sprint 012 introduces a dedicated triage page that
  is better suited for bulk processing of unsorted entries.
- **Decision:** The Inbox button now navigates to `/triage` instead of toggling
  the filter. The library page still supports status filtering via the status
  filter chips.
- **Consequences:** Users who previously used the Inbox button to filter the
  library now land on the triage page. The library page status chips remain
  available for filtering.

## DEC-022 — Repair the library grid before product hardening

- **Date:** 2026-07-23
- **Status:** accepted; supersedes DEC-017 only for downstream sprint numbering
- **Context:** After Sprint 012, the owner reported overlapping elements in the library grid. Code
  inspection found a structural layout defect: a two-column `128px 1fr` article receives a combined
  cover/metadata child plus a non-wrapping controls child, expanded score controls exceed available
  width, and fixed 310px virtual rows cannot absorb overflow. Existing browser tests do not assert
  spatial separation or responsive grid behavior.
- **Decision:** Insert a focused Sprint 013 to encode the failure, repair the responsive virtualized
  grid, and preserve table/keyboard/editing/pagination behavior. Shift hardening and release to
  Sprints 014 and 015. This planning change does not authorize implementation during the planning
  session.
- **Consequence:** The visible regression is repaired before broad accessibility/performance E2E
  hardening, and Sprint 014 inherits explicit responsive layout coverage. Final-project validation
  closes after Sprint 015.

## DEC-023 — The library grid virtualizes rows of cards

- **Date:** 2026-07-23
- **Status:** accepted
- **Context:** Sprint 013 confirmed the reported overlap by measurement: in grid mode the cover
  collapsed to the 32px placeholder glyph because it shared a 128px grid column with the metadata
  block, and the expanded score picker (ten 32px buttons in a non-wrapping row) escaped its
  fixed-height 310px full-width row at 375px. The mode called "Grid" was a single full-width column
  at every width.
- **Decision:** Grid mode virtualizes rows of cards. `gridColumnCount` derives the column count from
  the measured scroll-container width (1/2/4 columns at 375/768/1440), a virtual row is one
  fixed-height band of that many fixed-height 280px cards, and each card holds a fixed 128x192 cover,
  clamped metadata, and a non-wrapping control row. The compact score picker expands into an overlay
  anchored above its trigger inside the card instead of expanding in flow.
- **Consequences:** Fixed-size virtualization is preserved, so the technical-spec virtualization
  contract still holds. The mounted-DOM budget is now two bounds rather than one: mounted virtual
  rows stay under 20 as before, and mounted cards stay under 48 (rows x columns, with a smaller grid
  overscan of 2). Sprint 014's performance work inherits the per-card bound. Sprint 004's original
  "fewer than 20 mounted entries" phrasing applies to table mode and to rows, not to grid cards.

## DEC-024 — Insert correctness and UI-foundation sprints before hardening

- **Date:** 2026-08-08
- **Status:** accepted; supersedes DEC-022 only for downstream sprint numbering
- **Context:** After Sprint 013 the owner reported the product as a candidate failure: clunky UI,
  incomplete flows, searched books not found, books added without metadata, missing polish. An
  end-to-end audit found the cause is neither the stack, the specs, nor problem difficulty. Three
  libraries required by technical-spec section 8 — shadcn/ui, Motion, and React Hook Form with
  schema validation — were never installed, so there is no component library, no design tokens,
  and no microinteractions. Four defects were confirmed against live systems: Open Library ISBN
  enrichment requests `/books/{isbn}` (measured 404) instead of `/isbn/{isbn}` (measured 302) and
  has therefore always failed silently; `merge_and_rank` re-sorts merged results alphabetically
  and discards provider relevance; Google Books never registers because no key is configured; and
  every toast is rendered `sr-only` and is invisible. All 160 tests pass, because the enrichment
  method is replaced by an `AsyncMock` in all five of its tests and Playwright reads hidden text.
- **Decision:** Insert three sprints. Sprint 014 repairs metadata correctness and search
  relevance, backend only. Sprint 015 installs the specified component library, design tokens, and
  form stack, and makes feedback visible. Sprint 016 implements the product-spec section 7
  microinteractions. Hardening moves to Sprint 017 and release to Sprint 018. The backend is kept:
  its layering, migrations, keyset pagination, leased job runner, and import ledger are sound. The
  frontend is rebuilt on the specified stack rather than patched, with no compatibility shims. This
  planning change does not authorize implementation during the planning session.
- **Consequences:** Correctness precedes presentation, so Sprints 015 and 016 are judged against
  real covers and metadata rather than blank rows. Sprint 017 hardens a working product. The
  Sprint 013 grid contract (DEC-023) constrains Sprint 015 rather than being reopened by it.
  Final-project validation closes after Sprint 018, and the `range(1, 13)` bound in
  `scripts/validate_project.py` — already stale at plan revision 5 — is corrected to match.

## DEC-025 — Verification requires using the application, and E2E runs in CI

- **Date:** 2026-08-08
- **Status:** accepted
- **Context:** Thirteen sprints closed green while the product did not work. `AGENTS.md` section 3
  defined verification as the sprint's commands plus `make check`, `make test`, and Playwright.
  Every gate passed honestly every time. Nothing in the protocol required opening the application
  and using it, so an invisible feedback layer and a wholly dead enrichment pipeline survived
  thirteen closures. Playwright is additionally not part of CI at all: `.github/workflows/ci.yml`
  runs `make check`, `make test`, and `make build`, and `make test` runs pytest and vitest only.
  The eight Sprint 013 layout regressions — the only guardrail on the grid contract — have never
  run in CI.
- **Decision:** `AGENTS.md` section 3 gains a mandatory walkthrough gate: a sprint touching
  user-visible behavior is not complete until the agent has run the application against realistic
  data, performed the sprint's user flow end to end, and recorded in the worklog what was
  exercised, what was observed, and anything that felt wrong. Passing tests are not evidence that
  a flow works. A `playwright` job is added to CI. Tests that substitute a mock for the unit under
  test do not satisfy a correctness criterion; provider-boundary behavior is proven against
  recorded real responses.
- **Consequences:** Every UI-touching sprint costs a manual pass and produces a qualitative
  worklog record alongside command output. CI runtime grows by the Chromium suite. Sprints 014
  through 017 carry the walkthrough in their Verification sections explicitly.

## DEC-026 — Design direction, component library, and the bespoke score picker

- **Date:** 2026-08-08
- **Status:** accepted
- **Context:** Product spec section 7 asked for a real design direction rather than a default, and
  technical-spec section 8 required "a deliberate non-default saturated accent" without naming
  one. The implementation used ad-hoc `fuchsia-*` and `zinc-*` literals with an empty Tailwind
  theme and no CSS variables, and named Inter without ever loading it. Separately, converting the
  score picker to a portalled primitive would break a real invariant rather than a cosmetic one.
- **Decision:** The owner selected a warm amber direction. Tokens: zinc-950 background, zinc-900
  surface, zinc-800 border, zinc-50 text, zinc-400 muted, amber-400 accent on a zinc-950
  foreground, and a score ramp of red-400 (1–3), amber-400 (4–6), lime-400 (7–8), emerald-400
  (9–10). Inter is self-hosted and bundled. shadcn/ui, `react-hook-form` with `zod`, and
  `lucide-react` are installed and used for every control, with two documented exceptions:
  `ScorePicker` and the library card box remain bespoke. `ScorePicker` must not become a Radix
  `Popover` — Radix portals to `document.body`, and the expanded panel is required to stay
  geometrically inside its card (DEC-023, and the exact defect Sprint 013 repaired). The library
  card must not become a shadcn `Card` because `gridLayout.cardHeight` is pinned at 280px for
  fixed-size virtualization and `gridColumnCount` subtracts a hard-coded 32px padding matched to
  the row.
- **Consequences:** Colour, radius, spacing, and typography become tokens, so later theme changes
  are one edit rather than a sweep. Adopting Radix changes DOM shape, so `selectOption()` and
  `input[type="checkbox"]` selectors across three e2e specs must be rewritten in Sprint 015. The
  two bespoke components are now explicitly documented as intentional, so a future agent does not
  "finish the migration" and reintroduce the Sprint 013 defect.

## DEC-027 — The enrichment queue had no producer and no consumer

- **Date:** 2026-08-09
- **Status:** accepted
- **Context:** Sprint 014 was planned around one enrichment defect: `fetch_by_isbn` requested
  `/books/{isbn}.json`, which answers 404 for an ISBN. Implementing the fix exposed that the
  broken URL was never reached. `JobRepository.enqueue` was called from no production code path —
  neither importer enqueued anything on commit — and `JobRunner.tick` was called from no
  production code path either, only from tests. The runner was constructed in the lifespan and
  then never driven. DEC-025 recorded that the enrichment pipeline "had never once succeeded";
  the truth is stronger, in that it had never once started. Sprint 011 shipped a durable job
  queue, retries, leasing, and crash recovery, all of it correct and all of it unreachable,
  because its tests exercised `JobRepository` and `JobRunner` directly.
- **Decision:** Repair the pipeline as prerequisite work inside Sprint 014, since AC2, AC6, and
  the sprint's own walkthrough are unverifiable without it. Committing either importer enqueues
  `enrich_item` for the rows that batch created or matched. The lifespan starts a background task
  that drains the queue and cancels it on shutdown. Enrichment installs a missing cover after its
  metadata transaction commits. `POST /api/enrichment/backfill` and
  `GET /api/health/providers` are added to the API surface, and `jobs.error_code` is added by
  migration `0006` so a failure carries a stable type next to its human-readable sentence.
- **Consequences:** Enrichment now performs real network work in the background of a running
  application, rate-limited to ~2 req/s by the existing limiter. Two endpoints exist that the
  product spec's API list did not name; both are recorded there now. The backfill endpoint is the
  owner's path to repairing libraries imported while the pipeline was dead — it is explicitly
  operator-triggered rather than automatic, because it re-queries providers for every item that
  is still missing a field, including items no provider will ever have data for.
- **Also recorded:** a test that drives a queue's internals is not evidence that anything fills
  that queue. The gap here was not a wrong assertion but an absent one, and no coverage number
  would have shown it: every line of `jobs.py` was covered.

## DEC-028 — One visible feedback surface, one live region

- **Date:** 2026-08-11
- **Status:** accepted
- **Context:** Sprint 015 replaced the invisible feedback layer described in DEC-024. The sprint
  contract asked for visible toasts via Sonner while retaining the existing `aria-live`
  announcement paragraphs, on the reasoning that the defect was that they were the *only* channel
  rather than that they existed. Implementing it showed the two cannot coexist as written: Sonner
  wraps its toasts in its own `<section aria-live="polite" aria-relevant="additions text">`, so a
  retained paragraph carrying the same sentence announces every confirmation twice. Separately,
  Sonner v2 does not put `role="status"` on each toast; the polite region is on the container.
- **Decision:** There is exactly one confirmation channel. Sonner is mounted once in `AppShell`,
  every confirmation and every failed-write error goes through it, and the `sr-only`
  `aria-live="assertive"` paragraphs in `HomePage` and `TriagePage` are deleted rather than
  retained. The sprint's "toast surfaces keep `role='status'`" requirement is met by Sonner's
  container region rather than per toast. Visible loading and error states that are not
  confirmations — `role="status"` on "Loading your library…", `role="alert"` on a failed load —
  stay where they are.
- **Consequences:** A confirmation is announced once and seen once. The toast surface sits
  bottom-right rather than top-centre, because every screen puts its primary controls in the
  header and a toast there covers the control the reader just used. `e2e/feedback.spec.ts` asserts
  rendered geometry — width, height, and resting position inside the viewport — because
  Playwright's `toBeVisible()` accepts an `sr-only` element, which is exactly how DEC-024 went
  unnoticed for thirteen sprints. A test that queries a confirmation by role or text alone is not
  evidence that anyone saw it.

## DEC-029 — Portalled primitives inside the virtualized library

- **Date:** 2026-08-11
- **Status:** accepted
- **Context:** Sprint 015 flagged as a risk that a Radix `Select` inside a virtualized row portals
  its listbox to `document.body` while the row that owns the trigger can unmount on scroll, and
  required the answer to be measured rather than assumed. It also flagged that
  `isEditableTarget` guarded global keyboard shortcuts with a tag-name check plus a
  `[role="dialog"]` ancestor.
- **Decision:** Measured: while a Radix Select listbox is open the rest of the document is inert —
  pointer events are blocked and scrolling is locked — so a wheel gesture cannot move the
  virtualizer underneath it and the owning row cannot be recycled. A portalled Select is therefore
  safe inside a fixed-size virtual row, and `e2e/library.spec.ts` asserts it. Two consequences are
  recorded rather than worked around: the `feed` role is `aria-hidden` while a listbox is open, so
  tests that address the scroll container during that window must use a class rather than a role;
  and a page-level error rendered behind an open modal is unreachable, so a failed delete reports
  inside its own dialog. `isEditableTarget` now guards on the `dialog`, `alertdialog`, `combobox`,
  `listbox`, and `menu` roles, because Radix renders a Select trigger as a `button` and a tag-name
  check would let `7` set a score while a status dropdown had focus.
- **Consequences:** The DEC-026 exception list is unchanged — `ScorePicker` and the library card
  box stay bespoke — but for a narrower reason than "portals are unsafe here". Portalling is fine;
  what `ScorePicker` cannot do is portal *and* satisfy the DEC-023 requirement that its expanded
  panel stay geometrically inside its card. Sprint 016 may animate portalled content without
  re-litigating this, provided both mounted-DOM bounds still hold.

## DEC-030 — The Motion feature set is the guardrail, not the rule

- **Date:** 2026-08-11
- **Status:** accepted
- **Context:** Technical spec section 8 and DEC-023 forbid layout animations on virtualized rows,
  for a reason with history: rows unmount as they scroll out and would re-animate on every return.
  Until Sprint 016 that prohibition was a sentence in a document. Motion's `layout` and `layoutId`
  props are one word each, and nothing in the codebase would have stopped a future agent adding
  one to a card while implementing something else.
- **Decision:** `AppShell` mounts `<LazyMotion features={domAnimation} strict>` and components
  import `m` from `motion/react`. `domAnimation` deliberately omits Motion's projection features,
  so `layout` and `layoutId` do nothing anywhere in the application — the prohibition is
  structural, and violating it now requires changing the provider. `strict` turns an accidental
  eager `motion.*` into a runtime error rather than a silent full-feature bundle. Two
  `no-restricted-imports` rules back it up: the eager `motion` factory is banned everywhere, and
  Motion is banned outright inside `VirtualLibrary.tsx`. Every timing lives in
  `src/lib/motion.ts`; a `transition` literal in a component is a defect. Radix dialogs stay
  CSS-animated rather than being converted, because Radix gates unmount on `animationend` and a
  Motion version needs `forceMount` plus a hand-rolled presence bridge, putting focus trapping and
  Escape handling at risk for no visible gain.
- **Consequences:** Shared-layout transitions are unavailable application-wide. That is what ruled
  out morphing the selected add-flow card into the form; it ships as a carried-identity enter
  instead, which is also robust to the cover image not having loaded when the morph would have
  measured it. A future sprint wanting a shared-layout transition must justify `domMax` and accept
  that it re-arms the DEC-023 hazard.

## DEC-031 — The library crossfade waits, and resets scroll

- **Date:** 2026-08-11
- **Status:** accepted
- **Context:** Technical spec section 8 requires that sort and filter changes crossfade the
  container while rows do not animate. The container's children are absolutely positioned inside a
  spacer sized to the virtualizer's total height, which makes a naive crossfade of two lists a
  geometry problem rather than an opacity one.
- **Decision:** `AnimatePresence mode="wait"`, keyed on `libraryMotionKey(filters)` — every
  server-side filter and sort value and nothing else, so page appends and optimistic cache patches
  never re-key. `mode="wait"` is load-bearing rather than stylistic: moving to a filter TanStack
  already has cached resolves synchronously, and under the default mode both lists mount in the
  same commit, producing two scroll containers and two total-size spacers, doubling both the
  mounted-card count and the page height. `popLayout` was rejected because it requires the
  projection features DEC-030 removes. The pending state now holds the list's height so the page
  does not collapse between two lists.
- **Consequences:** Scroll position resets to the top of the list on a sort or filter change. That
  was already the behavior via the pending state, and preserving it is not meaningful anyway: the
  offset referred to data the new query key discards. Measured at the peak of a crossfade against
  the 5,000-entry fixture: 4 mounted rows, 16 mounted cards, exactly one container.

## DEC-032 — A rolled-back write is visual state, not a second announcement

- **Date:** 2026-08-11
- **Status:** accepted
- **Context:** Product spec section 7 asks a failed optimistic write to "roll back with a shake".
  DEC-028 established that there is exactly one confirmation channel and that a second live region
  announcing the same sentence is a defect. Whether a shake reopens that is a real question, and
  the honest answer decides where the treatment can live.
- **Decision:** The failing row carries a `data-rollback` marker and a CSS-keyframe shake. It has
  no text, no role and no live region, so the toast remains the only announcement; what the shake
  adds is *which* row, which a bottom-right toast naming no book cannot convey. CSS keyframes
  rather than Motion, for three reasons that all bite: the failing row may be scrolled out and
  remounted, so the treatment must derive from a prop rather than be held against a node; jsdom has
  no Web Animations API, so a Motion shake would be unassertable at the unit layer; and the
  `prefers-reduced-motion` block in `index.css` already covers a CSS animation. Scope is inline
  single-entry writes on `/` — the only optimistic writes in the application, covering both the
  pointer and number-key paths. `DetailPage` and `TriagePage` keep their existing error surfaces; a
  failed bulk write would shake N rows, and the object that failed is the selection, not a row.
- **Consequences:** Prerequisite repair, found by writing the test first: the rollback restored its
  snapshot into `["library", filters]` read from the render in scope when the write *failed*, not
  the key the snapshot was taken from, so changing sort while a PATCH was in flight and having it
  fail wrote one sort's list into another sort's cache. The key now travels in the mutation
  context. Also found: `tailwindcss-animate` redefines the `duration-*` utilities to set
  `animation-duration`, later in the cascade, so an element carrying both a `duration-*` transition
  and an `animate-*` keyframe runs the keyframe at the transition's duration.

## DEC-033 — A reduced-motion assertion is only meaningful in a pair

- **Date:** 2026-08-11
- **Status:** accepted
- **Context:** `e2e/library.spec.ts` had asserted since Sprint 004 that a card's computed
  transition duration is effectively zero under `prefers-reduced-motion`. The card carried no
  transition at all, so the assertion was true of a page containing no animation — it passed
  vacuously for eleven sprints, the same shape of failure as DEC-024.
- **Decision:** Reduced motion is proven on both sides. One test asserts that every animated
  surface — card, container, cover, score trigger, expanded score panel, and a status listbox Radix
  portals out of the card — reports zero transition *and* animation duration under the preference;
  a paired test asserts the same surfaces report a non-zero duration without it. A third watches
  every animation the browser starts across a sort change and a score commit under the preference,
  because the `*` block in `index.css` cannot touch Motion, which drives the Web Animations API and
  inline styles. Separately, the unit suite installs a controllable `matchMedia` and defaults every
  test to `reduce`; tests needing the animated path opt out explicitly.
- **Consequences:** Deleting the animation layer now fails the suite rather than passing it. The
  unit-suite default has a second effect worth more than the first: all sixty-eight tests are a
  standing proof that add, score, delete, triage and import remain fully usable with motion
  disabled, at no authoring cost.

## DEC-034 — The cover treatment is a decode-reveal, not a blur-up

- **Date:** 2026-08-11
- **Status:** accepted
- **Context:** Product spec section 7 asks for "blur-up or skeleton, never layout shift" on cover
  load. A blur-up shows a tiny low-resolution image immediately and swaps in the full one; it
  requires the server to supply that placeholder.
- **Decision:** The API exposes no LQIP or blurhash, and adding one is backend work outside a
  frontend sprint, so what ships is a decode-reveal: the skeleton stays, and the real asset arrives
  blurred and sharpens. This is named honestly in the component, here, and in the sprint Outcome
  rather than being filed as "blur-up done". The no-layout-shift half was already structurally
  guaranteed — the wrapper carries the caller's box and exists before a byte of the image does — so
  it is now asserted rather than rebuilt, against a cover deliberately held back 700ms.
- **Consequences:** If a real blur-up is wanted, it starts at the metadata boundary with a stored
  placeholder, not in `CoverImage.tsx`. `loading="lazy"` was deliberately not added: the
  virtualizer already bounds how many covers are mounted, and lazy loading would delay them during
  a fast scroll, which is the pop-in this treatment exists to remove.

## DEC-035 — Metadata completeness is wanted, but must prove it is affordable first

- **Date:** 2026-08-11
- **Status:** accepted
- **Context:** OQ-001 has been open since the Sprint 014 walkthrough: enrichment consults Google
  Books only when Open Library fails outright, so a record that comes back usable but missing a
  cover keeps the gap. The Sprint 016 walkthrough added a second symptom of the same shape — a
  provider "image not available" placeholder JPEG stored as a real cover, with no second candidate
  to fall back to. The owner was asked to decide and did.
- **Decision:** The feature is wanted. The owner's stated goal is metadata entries that build
  towards completeness from whichever provider has the missing piece, and specifically the ability
  to **choose a cover from the editions that were actually fetched** rather than accepting whatever
  the default resolved to. What the owner explicitly declined to decide is whether this is
  affordable, naming three unknowns: implementation complexity, performance under a large import,
  and the risk of exhausting or being blocked by free-tier provider limits — plus a fourth
  judgement, whether it improves or degrades the feel of the system. Therefore this becomes
  **Sprint 019, structured as a gate**: Phase A measures viability and impact and produces a
  written verdict with numbers, changing nothing user-visible; Phase B builds only what Phase A
  justifies, and only with an explicit go-ahead. Placed after the v1 release sprint, because it is
  additive and carries third-party unknowns that should not hold a working release hostage. The
  owner also directed that no assessment be performed at the time of this decision, so none was:
  this entry records intent and structure only.
- **Consequences:** OQ-001 closes as resolved-into-Sprint-019 rather than remaining an open
  question. The placeholder-cover observation is folded into it rather than tracked separately, on
  the owner's reading that cross-provider cover completion would give that case a way out; if
  Phase A concludes the feature is not worth building, that observation resurfaces on its own and
  needs its own answer. Sprint 019 becomes the final planned sprint, so the release-state rule in
  `WORKFLOW.md`, the closure step in `AGENTS.md`, and the completeness bound in
  `scripts/validate_project.py` all move from 018 to 019. Plan revision is now 7. **Phase A is
  permitted to conclude that the feature is not worth its cost**, and that outcome must be reported
  plainly rather than softened into a partial implementation.

## DEC-036 — Text sorting uses a stored normalized projection

- **Date:** 2026-08-12
- **Status:** accepted; supersedes the deferral in DEC-015
- **Context:** DEC-015 registered a deterministic `normalize_text` SQLite function on every
  connection and used it for title/first-author ordering, search, and cursor values, explicitly
  deferring a stored projection "only if measurement shows text sorting needs it". Sprint 017
  measured it. `scripts/benchmark_library.py` at 10,000 entries, on a developer workstation
  considerably faster than the target ZimaBoard: first page by `title` 73.8 ms p50 idle against
  39.4 ms for an indexed column, and **312 ms p95** with the job queue draining; `sort_author` at
  page 26 reached **627 ms p95** and the text filter **988 ms p95**, against a documented budget of
  500 ms (technical-spec section 1). The cause is not the plan but the call count: the UDF is a
  Python function invoked once per candidate row, so a 10,000-row scan is 10,000 interpreter
  round-trips inside SQLite.
- **Decision:** Store the projection. Migration `0007_normalized_sort_projection` adds
  `items.title_normalized` and `items.sort_author_normalized`, backfilled in Python with the domain
  function so Alembic still depends on no application-registered SQLite function. The columns are
  maintained by a mapper-level `before_insert`/`before_update` event in
  `infrastructure/models.py` rather than at each call site, so a future write path cannot forget
  them; `sort_author` is a generated column with no pre-flush value, so the event reads the author
  from the same `$.authors[0]` JSON path the generated column uses. Ordering, the `q` filter, and
  the cursor value all read the columns, the last of these by reading the stored value back rather
  than recomputing it, because a divergence between cursor and column would silently skip or repeat
  a page. The connection-level `normalize_text` registration is removed, having no remaining caller.
- **Consequences:** Every scenario is inside budget: `title` first page 82 ms p95 contended
  (was 312), `sort_author` page 26 78 ms (was 627), text filter 10 ms (was 988). **No index
  accompanies the columns, and that is measured rather than forgotten**: the list query drives from
  `entries` and reaches `items` by rowid, so SQLite builds a temp B-tree for the ORDER BY with or
  without the leading null-bucket CASE, verified by `EXPLAIN QUERY PLAN` both ways. The entire win
  is deleting per-row UDF calls. The projection's contents are pinned to `normalize_text`'s current
  behaviour; changing that function requires a new migration to re-backfill, and
  `test_persistence.py` fails if the two ever disagree.

## DEC-037 — Route-level code splitting, and a lowered chunk warning

- **Date:** 2026-08-12
- **Status:** accepted
- **Context:** Sprint 016 closed with a single 696.24 kB JavaScript bundle (219.66 kB gzip), up
  86 kB on Sprint 015 and roughly double the Sprint 013 baseline, with Rollup's chunk-size warning
  emitted on every build. Sprint 017 was handed the decision with the number attached: split, or
  raise the limit and say why. The deployment target is a ZimaBoard on a LAN with a documented
  first-library-page budget of 500 ms, and every cold load was parsing all 696 kB before rendering
  a screen that uses a fraction of it.
- **Decision:** Split, and lower the warning rather than raise it. `/` stays in the entry chunk
  because it is the screen the application opens on; `/add`, `/books/:id`, `/import`, `/shelves`,
  and `/triage` are `React.lazy` and arrive on navigation, behind a `role="status"` fallback so the
  wait is announced rather than silent. Vendor code is chunked by change rate rather than by size —
  `react`, `query`, `motion`, `forms` — so a deploy touching only application code leaves a cached
  browser's framework chunks valid. `build.chunkSizeWarningLimit` drops to 300 kB.
- **Consequences:** Eager JavaScript for the first paint falls from 696.24 kB to **510.96 kB**
  across four chunks (entry 188.54, react 169.02, motion 80.03, query 73.37), the largest single
  chunk is 193 kB, and the build emits no warning. The 104 kB form stack — `react-hook-form`, its
  zod resolver, and zod — no longer loads for a user who only browses their library. The lowered
  limit is the regression guard: raising it to accommodate the next 696 kB bundle would be a
  visible, arguable act rather than a silent one. Route transitions can now show a brief loading
  state, so E2E navigation assertions must address content rather than assume synchronous mounts.

## DEC-038 — Both list surfaces are feeds of articles, not ARIA tables

- **Date:** 2026-08-12
- **Status:** accepted
- **Context:** Sprint 017 added `@axe-core/playwright` checks to the Chromium suite and they failed
  immediately on three screens. The library in compact view declared `role="table"` over
  `role="row"` elements containing no cells, and `/triage` did the same; axe reports that as a
  **critical** `aria-required-children` failure, and a screen reader given a table it cannot
  navigate is worse off than one given a list. The cover placeholder carried `aria-label` on a bare
  `<div>` (`aria-prohibited-attr`, serious): ARIA ignores the attribute on a generic element, so
  "No cover" was written but never announced. The import page rendered `TabsList` with no
  `TabsContent` at all, so every tab's `aria-controls` pointed at an element that did not exist
  (`aria-valid-attr-value`, critical) and the fields a tab switched to were associated with
  nothing.
- **Decision:** Neither list was ever tabular — no column headers, no cells, a checkbox and a
  cover and a control row. Both become `role="feed"` with `article` children, which is the role
  ARIA defines for a scrollable, virtualized, incrementally-loaded list. Each article carries
  `aria-posinset` and `aria-setsize` from the server-side total, so a mounted window of 28 cards
  out of 10,000 announces where it sits instead of announcing nothing; the feed carries
  `aria-busy` while a page is in flight. The cover placeholder takes `role="img"`, making its
  label legal and audible. The import tabs get real `TabsContent` panels inside the form, one per
  source.
- **Consequences:** Twelve axe checks gate CI alongside the layout regressions — library grid,
  library compact, the score-picker overlay open inside its card, triage, triage with a selection,
  detail, the opinion dialog, add, the manual form, the degraded-provider notice, import, and
  shelves — asserting zero `serious` or `critical` violations under WCAG 2.0/2.1 A and AA. Lesser
  impacts are printed rather than failed, so a severity change in a future axe release cannot break
  an unrelated change; at adoption there were none of those either. Tests that addressed
  `role="table"` now address `role="feed"`. axe covers only what is computable from the rendered
  tree, so the keyboard and focus half of the acceptance criterion stays a hand-walked checklist
  recorded in the worklog.

## DEC-039 — Migrations run automatically, guarded by a pre-migration backup

- **Date:** 2026-08-13
- **Status:** accepted
- **Context:** Migrations have run inside the application lifespan since Sprint 001, which was
  unremarkable while every migration was a schema change on an empty or small table. Migration
  `0007` is different: it rewrites every row in `items` to backfill the normalized projection
  (DEC-036). On the ZimaBoard nobody watches a restart, so a migration that dies halfway leaves a
  partially rewritten table and no way back — Alembic here is forward-only and there was no backup
  of any kind. The alternative considered was an explicit deploy step, with the container refusing
  to serve until an operator ran the upgrade; `/api/health/ready` already returns 503
  `schema_not_current`, so it would have worked. The owner chose automatic, on the grounds that a
  single-user home server should come back by itself after a power cut.
- **Decision:** Startup keeps migrating automatically, but takes an online backup first whenever
  `pending_revisions` is non-empty and the database already carries an `alembic_version`. If that
  backup cannot be written, startup fails rather than migrating unprotected. A fresh database is
  skipped: there is nothing to lose, and a first start should not pay for a backup of an empty
  schema.
- **Consequences:** Every upgrade of an existing library leaves a labelled rollback point in
  `BACKUP_DIR`, which nightly retention never prunes. The backup is taken once per revision, not
  once per attempt: `restart: unless-stopped` plus a failing migration is a loop, and the first
  version of this wrote ten copies of the same database in ninety seconds during the Sprint 018
  upgrade drill. The rollback procedure is a restore plus an older image, and it is written down in
  `docs/operations/runbook.md`.

## DEC-040 — Backups live outside the data volume, seven nightly

- **Date:** 2026-08-13
- **Status:** accepted
- **Context:** Product spec section 8 sketches `sqlite3 books.db ".backup /data/backups/..."`, and
  `main.py` had been creating an unused `data/backups` directory since Sprint 001. Writing backups
  inside the volume they back up protects against the owner's mistakes and against nothing else: a
  deleted or corrupted volume takes every copy with it, and that is the failure a backup exists
  for.
- **Decision:** A separate `${BACKUP_DIR:-./backups}:/backups` mount, with `backup_dir` derived as
  a sibling of `data_dir` rather than a child, so the container's `/data` and `/backups` and a
  developer's `./data` and `./backups` both fall out of the same rule. Retention keeps seven
  nightly backups, the owner's choice. Retention is scoped by label, so nightly housekeeping cannot
  delete a pre-migration rollback point, and it only ever deletes directories carrying an Akasha
  manifest — a routine that globs an operator-supplied path and removes what it finds is a footgun.
- **Consequences:** `BACKUP_DIR` can point at a NAS share. The mount must be owned by uid 10001 or
  the nightly cron fails silently at 3am, which the runbook says in the install section rather than
  in a troubleshooting appendix. `data/backups` is no longer created. The backup itself is a Python
  module in the package rather than a shell script, so it ships in the image, runs under mypy and
  ruff, and is covered by unit tests that restore and read values back.

## DEC-041 — Vendor chunks are assigned by resolved package, and a build is tested

- **Date:** 2026-08-13
- **Status:** accepted
- **Context:** Sprint 018's walkthrough loaded the containerised application and got a blank page
  and `Cannot read properties of undefined (reading 'createContext')`. DEC-037's `manualChunks`
  used Rollup's object form, which assigns only the exact entry modules named — `react`,
  `react-dom` — and leaves their transitive runtime (`scheduler`, `jsx-runtime`,
  `use-sync-external-store`) unassigned to fall wherever Rollup puts it. React ended up spread
  across chunks that imported one another, and the entry evaluated before React existed. Every gate
  was green: unit tests run in jsdom, and Playwright runs against the Vite dev server, which serves
  unbundled modules and cannot express this failure at all. The production bundle had never been
  loaded by anything.
- **Decision:** `manualChunks` is a function that resolves each module to its package name and
  matches on that, with a fall-through to a single `vendor` chunk so no module can be left
  unassigned. Matching by package also catches the transitive members of a group — `motion` has to
  mean `framer-motion`, `motion-dom` and `motion-utils`, and the first attempt at this fix missed
  `framer-motion` and produced a different cycle. A second Playwright project,
  `production-bundle`, builds the application and loads it through `vite preview`, asserting that
  the entry renders and that a lazily loaded route chunk initialises after it.
- **Consequences:** Six chunks, entry down to 36 kB from 194 kB, no chunk-size warning. CI runs
  both Playwright projects; `--project=chromium` still gives the fast loop. The cost is a build
  inside the e2e job. The wider lesson is recorded here rather than in a commit message: a test
  suite that only ever exercises the dev server is not evidence about the artifact that ships.

## DEC-042 — Post-v1 roadmap: sequence, and assess-then-build as the default shape

- **Date:** 2026-08-13
- **Status:** accepted; extends DEC-035, which is not superseded
- **Context:** v1 shipped at Sprint 018 and the plan had exactly one sprint left on it, written as
  though the project ended there — the release-state rule in `WORKFLOW.md`, the closure step in
  `AGENTS.md`, and the completeness bound in `scripts/validate_project.py` all named Sprint 019 as
  the last. The owner then named four further directions: a score-contrast fix, arbitrary file
  attachments (epubs) kept inside the metadata-first framing, additional domains (albums, games,
  series) informed by `docs/domain_metadata_roadmap_report.md`, and whatever deferred work had gone
  unrecorded. The owner asked for a sequenced plan, with the large items scoped as *assess
  viability and impact first, then decide*.
- **Decision:** Roadmap revision 8 runs 019 post-v1 polish, 020 metadata completeness, then 021
  attachments, 022 creator sort names, 023 export, and 024–026 the domain line beginning with
  albums. Four ordering claims carry it. **Metadata precedes domains** because Phase A settles how
  a candidate is verified before its fields are merged, and that is the provider contract every
  later domain inherits; answering it once against books — where recorded fixtures and a working
  baseline exist — beats answering it retrofitted across N domains. **Creator sort precedes
  domains** because the repair generalizes from author to creator and N domains should not inherit
  a broken projection. **Albums is the pilot domain** among the three named: MusicBrainz needs no
  OAuth, release-group versus release maps onto the work-versus-edition problem already solved, and
  Cover Art Archive exercises the separate-image-provider case metadata completeness will have just
  settled. **Series is last** because it is gated on a product decision rather than an integration:
  the entry model is one score, one status, one `reread_count` per item, and a season is not
  expressible in it without giving entries hierarchy.
  The gate structure DEC-035 invented for a single sprint is adopted as the **default shape for any
  item whose cost is unknown** — 021, 024 and 026 are all Phase A / Phase B, and Phase A concluding
  *no* remains a complete outcome in each.
  Sprint 024's Phase A is specified as **a build rather than a document**: implement one domain end
  to end on a branch, and the deliverable is the list of everything touched that was not the
  provider adapter. The provider research already exists and repeating it as prose would produce a
  confident answer about this codebase that the research cannot support.
  Auth stays unscheduled at the owner's direction, remaining a product spec section 9 deferral and
  the gate on any exposure beyond LAN. Export moves from deferred to Sprint 023, constrained to the
  entity shape so a second domain does not force a v2 format.
- **Consequences:** The metadata sprint is **renumbered 019 → 020** and its file renamed, because
  `scripts/validate_project.py` requires `active_sprint == len(completed_sprints) + 1` and permits
  exactly one non-completed sprint file; putting polish first therefore forces the renumber rather
  than being a stylistic choice. Sprint 018's Outcome keeps its "Impact on Sprint 019" text as
  written, with a bracketed pointer, because a completed sprint's Outcome is audit history.
  The final-sprint bound moves from 019 to 026 in `WORKFLOW.md`, `AGENTS.md`, and
  `validate_project.py`, where the literal is now the named `FINAL_SPRINT` constant; it stays
  hardcoded rather than derived from files on disk, because its purpose is to stop a session
  declaring the plan finished early.
  `ROADMAP.md` drops the duplicated contract blocks for sprints 002–018 — every one of those
  sprints has its own file carrying the same Deliverables and Acceptance criteria, and nothing
  anchor-links into a roadmap section — taking it from 408 lines to 241 while covering eight more
  sprints. OQ-001 is deleted rather than kept as a resolved open question restated in three places;
  its one live paragraph, that product spec 4.3 already specifies per-field completion at *search*
  time and `_merge_group` implements it there, moves into the Sprint 020 file.
  One item is promoted out of the gate: `GoogleBooksProvider.fetch_by_isbn` taking the first hit of
  an `isbn:` search is recorded as a **live v1 defect** repaired whatever Phase A concludes, not
  only as a question the assessment asks.
  The proposal to rename the `book_tracker` package to match the Akasha brand was raised during this
  re-plan and **rejected on the existing invariant** in `AGENTS.md`: internal names are permanent
  and only user-facing copy follows the brand. Multi-domain content in a package named
  `book_tracker` is accepted as a cosmetic cost. Plan revision is now 8.

## DEC-043 — The triage shelf shortcut is retired unbuilt, not implemented

- **Date:** 2026-08-13
- **Status:** accepted
- **Context:** Product spec section 7 listed `s` on `/triage` as opening shelf autocomplete. Every
  other key in that list works — `j`/`k`, the digits, the status letters, `Enter`, `Escape` — and
  `s` never did. Sprint 017 looked at it and recorded it as feature work rather than a shortcut;
  Sprint 018 carried it again; the release notes shipped it as a known issue. Sprint 019 exists so
  that it stops being carried, and its acceptance criterion 3 allowed either branch: implement it,
  or remove it from the spec and record why.
  What `s` actually needs is not a key binding. `/triage` has no shelf surface at all — the bulk
  action bar offers status, score, clear-provisional and clear-selection, and nothing shelves. So
  the work is an autocomplete panel with filter-as-you-type over existing shelves, create-on-miss,
  focused-row versus whole-selection semantics, and the same input-focus guards as every other
  triage key. The API is ready — `add_shelves` and `remove_shelves` already exist on the bulk
  endpoint's `set` — but the surface is a feature.
- **Decision:** Retire it. `s` is removed from product spec section 7, which now says explicitly
  that shelving is not in the triage keyboard flow and that shelves are assigned from a book's
  detail page. The owner chose this over implementing it when the alternative was presented, on the
  reasoning that Sprint 019 is deliberately small and a shelf-autocomplete surface is not polish.
- **Consequences:** Shelf assignment stays where it already works: the `Edit opinion` dialog on a
  book's detail page, one entry at a time, plus whatever shelves an import carries. Triaging several
  hundred books cannot shelve them in bulk.
  **Section 7's action-bar line still promises *Add shelves*, and that is still unbuilt.** It is
  named here and in `HANDOFF.md` so it is not mistaken for delivered, and it is deliberately left
  unowned rather than assigned a sprint number the owner has not scheduled. If it is ever scheduled,
  it and `s` are the same feature seen from two angles and should be built together — one
  autocomplete surface, reachable from the action bar and from the keyboard.
  A spec line was deleted rather than an implementation added, which `AGENTS.md` permits only when
  product intent is clear and the decision is recorded. The intent here is the owner's explicit
  choice, not an excuse for an incomplete implementation, and this entry is the record.

## DEC-044 — Metadata completeness measured: the second provider adds almost nothing, and unverifiable candidates are rejected

- **Date:** 2026-08-13
- **Status:** accepted
- **Context:** DEC-035 approved an assessment, not an implementation, and DEC-042 made
  assess-then-build the default shape. Sprint 020's Phase A asked whether cross-provider field
  completion and edition choice are affordable. Everything below was measured, not estimated.
  Two instruments produced it: `scripts/assess_provider_completeness.py` against the live APIs on
  2026-08-13 with a 60-ISBN sample harvested from provider search, and the new provider-request
  counting in `scripts/benchmark_library.py` against the committed recordings.

  **Request cost per enrichment.** One enrichment is not one request. An Open Library hit costs
  **four** metadata requests plus one cover — the `/isbn/` redirect, the edition, each author, and
  the work — where the Google Books fallback costs **two** plus a cover. `RateLimiter` gates the
  whole queue at one job per 0.5 s, so a 5,000-book import has a **41.7-minute floor** before a
  single byte crosses the network; at the measured latencies its network time is hours, and the two
  do not overlap because jobs run one at a time.

  **Observed latency and availability**, 60 ISBNs, both providers:

  | | answered | p50 | p95 | max |
  |---|---|---|---|---|
  | Open Library | 44/60 | 1412 ms | 3957 ms | 6055 ms |
  | Google Books | 56/60 | 1057 ms | 1153 ms | 1410 ms |

  Open Library is the slower and less complete of the two by availability, failing
  `edition_not_found` for 16 of 60, and its p95 nearly reaches the 5 s client timeout.
  An **anonymous** Google Books request is answered **429 immediately**; with the owner's key the
  same request answers 200. The free tier is ~1000 requests/day, so a 5,000-book import under
  per-field completion would need ~15,000 Google requests and **exceed the daily quota threefold**.

  **Edition verification is a tri-state, and the middle case is empty.** Of Google Books answers:
  **80.4% confirmed, 19.6% unverifiable, 0% contradicted**. Open Library was **100% confirmed**
  across all 44 answers, because it reaches an edition through the authoritative `/isbn/` redirect
  rather than a search. So the risk is not that a provider returns a demonstrably wrong ISBN; it is
  that Google Books frequently returns a scanned library volume exposing only a barcode
  (`OTHER: UOM:39015008575477`) and no ISBN at all, which neither confirms nor denies anything.

  **The defect is real and was observed in the wild.** For ISBN `9789583007828`, Open Library
  returns *Crónica de una muerte anunciada* and Google Books returns ***Las venas abiertas de
  América Latina*** — a different book by a different author, and unverifiable. Had Open Library
  failed for that ISBN, today's code would have written Galeano's publisher, page count, year and
  description onto García Márquez's book. The committed recording
  `googlebooks_isbn_9788437604572.json` is a second instance and needed no re-recording.

  **What the second provider would actually add**, over the 41 ISBNs where both answered:

  | field | | | field | | |
  |---|---|---|---|---|---|
  | year | 0.0% | [edition] | description | 22.0% | [work] |
  | publisher | 0.0% | [edition] | subjects | 7.3% | [work] |
  | page_count | 12.2% | [edition] | authors | 0.0% | [work] |
  | cover | **0.0%** | [edition] | language | 2.4% | [work] |

- **Decision, and it is mostly a decision not to build.**

  1. **Cross-provider field completion is not worth its cost.** It would multiply provider traffic
     per book, breach the Google free tier on a large import, and buy a description in 22% of cases,
     a page count in 12%, and nothing at all for year, publisher, authors or cover. This is the
     outcome DEC-035 explicitly permitted and it is reported plainly rather than softened into a
     partial implementation.
  2. **The owner's stated headline want — choosing a cover from the editions actually fetched —
     gains nothing from a second provider.** Open Library carried a cover for **100%** of the
     editions it answered for, and Google Books added a cover in **0%** of cases. Cover *choice* is
     nonetheless cheap from a source nobody had costed: the Open Library **work record already
     fetched during every enrichment** lists **28 covers** for Rayuela and **33** for the sampled
     *Cien años de soledad*. Candidate discovery therefore costs **zero additional provider
     requests**; only the thumbnails a chooser displays cost anything, and only when it is opened.
     At the measured mean stored cover size of **38.8 KB**, five candidates for 5,000 books is
     ~947 MB eagerly and ~0 on demand, so **on demand** is the only defensible fetch strategy.
     **This is the narrow slice Sprint 020's Phase A was allowed to identify, and it is offered to
     the owner as a Phase B candidate. It is not started here: Phase B needs an explicit
     go-ahead and does not have one.**
  3. **An unverifiable candidate is rejected outright**, and this ships now as the repair of the
     live defect DEC-042 promoted. The alternative considered was merging only work-level fields
     (description, subjects) while dropping edition-specific ones — that option is **refuted by the
     measurement**: the observed failure was not a right-book/wrong-printing mismatch but an
     entirely different work, where the description is exactly as wrong as the page count.
     Splitting by field would have preserved the worst error. The cost is explicit: **19.6% of
     Google Books fallback answers are now discarded**, and for a book where Open Library also
     failed that means no enrichment at all. Absent metadata is preferable to confidently wrong
     metadata, which is the same reasoning DEC-008 applies to user data.
  4. **DEC-008 survives unchanged**, demonstrated rather than assumed: merging happens in the
     provider before the write, and `EnrichmentHandler.process` still fills only fields that are
     empty. A test pins it.
  5. **Failure semantics keep their current shape.** One provider erring while another answers is
     already a successful enrichment — `_fetch` returns the first usable payload and only reports
     failure when every provider is exhausted — so no change is needed and none is made.

- **Consequences and the two folded observations (Sprint 020 AC5).**

  **The placeholder cover is solved, and the answer is geometry, not bytes or hashes.** Google
  Books' "image not available" image is **575×92** — an aspect ratio of 6.25:1 — at 316–1631 bytes,
  where real covers measured 575×750 and 575×887, ratios of 0.66 and 0.77. A book cover is taller
  than it is wide; the placeholder is a thin banner. `prepare_cover` rejects only images under
  10px per side, so a placeholder passes today and is installed as a real cover. A ratio guard
  ships with this sprint's repair, because a placeholder stored as a real cover is a defect in the
  cover write path rather than a feature awaiting the gate. Open Library needs no such guard: its
  URLs are already built with `?default=false`, which answers **404** instead of a placeholder —
  verified, against **200 and 43 bytes** without the parameter. This answers both paths DEC-035
  asked about: the automatic path is guarded by geometry, and a chooser, if one is ever built,
  inherits the same guard.

  **Edition choice preferring a reprint over the original is reproduced and deferred with a
  reason.** For *Pedro Páramo*, `merge_and_rank` today returns a **1969** printing at rank 0
  (`original_year` 1955) and a **2024** Google Books edition at rank 1; the 1955 original is not in
  the top eight. This is search *ranking*, not enrichment, and it is governed by product spec 4.3's
  deliberately dumb ranking plus DEC-024's rule that provider relevance is not to be discarded.
  Changing it means changing what the picker offers, which is user-visible product behaviour and
  outside an assessment's remit. It is **explicitly deferred**, unowned, and recorded here so it is
  not mistaken for unnoticed.

  **Two smaller observations, recorded because DEC-025 asks for what looked wrong.** Open Library
  returns mojibake for some titles — `Cc3mo Leer a Garcc-A Mc!Rquez` for *Cómo leer a García
  Márquez* — which is upstream data corruption this project cannot fix but could detect. And
  `search_providers` runs against a client whose timeout is a hard **5 s** while Open Library's
  search plus its year-resolution fan-out routinely exceeds it; the handoff's "provider search takes
  about five seconds" is that, and it means a slow search silently returns Google-only results.

  **Sprint 024 inherits the verification contract**, which is the reason this entry records
  reasoning and not only a verdict: a domain provider is trusted to fill fields only when the
  candidate it returns can be tied to the identifier that was requested, and a provider that cannot
  prove that is not merged. MusicBrainz's release-versus-release-group distinction is the same
  problem in the shape DEC-042 already predicted.

## DEC-045 — Phase B is authorized: cover choice only, Open Library stays first, and quota becomes a provider-agnostic guard

- **Date:** 2026-08-13
- **Status:** accepted; the go-ahead DEC-035 and DEC-044 both required
- **Context:** DEC-044 recorded Sprint 020's Phase A verdict and offered the owner one narrow slice
  against a larger refusal. The owner read it and decided. This entry records that decision, because
  DEC-035 requires Phase B to rest on an explicit go-ahead rather than an agent's reading of a
  verdict.
- **Decision, in four parts.**

  1. **Cross-provider metadata completion is abandoned**, confirming DEC-044's recommendation rather
     than revisiting it. It is not deferred, not partially built, and not to be revived without new
     evidence.
  2. **The cover selector is authorized and built now**, as Sprint 020's Phase B. Its affordability
     rests entirely on DEC-044's measurement that candidates are already in hand: the Open Library
     work record enrichment fetches for every book lists 28 editions for Rayuela and 33 for the
     sampled *Cien años de soledad*, so discovery costs no additional provider request. Candidates
     are fetched on demand when the chooser opens, never eagerly, which is what keeps the disk cost
     at ~0 against the ~947 MB an eager five-candidate cache would cost at 5,000 books.
  3. **Provider order does not change: Open Library first, Google Books as the fallback.** The owner
     raised the alternative — Google as a high tier until its daily quota is spent, then Open
     Library — and it was measured rather than argued:

     | per 5,000-book import | Google Books calls | |
     |---|---|---|
     | Open Library first (kept) | **1,333** | Google consulted only where Open Library missed |
     | Google Books first | 5,000 | five times the free tier |

     Correctness and cost point the same way. Open Library reaches an edition through an
     authoritative `/isbn/` redirect and was verifiable in **100%** of its 44 answers, where Google
     Books was verifiable in **80.4%**; putting the less verifiable source first would also mean
     rejecting more of its answers under DEC-044's rule. Google answers faster (1.06 s against
     1.41 s p50) but enrichment is background work behind a 0.5 s per-job limiter, so latency is not
     the binding constraint. Google is genuinely needed for the ~25% of books Open Library cannot
     answer at all, and spending quota there is spending it where it is the only option.
  4. **A daily quota guard ships with this sprint**, because the owner's instinct that the 1,000/day
     limit needs designing around is correct even after (3): 1,333 > 1,000, so a single 5,000-book
     import exhausts the free tier today and silently loses enrichment on the remainder.

- **The guard is provider-agnostic by construction, at the owner's direction.** Google Books is the
  only metered provider today and it will not be the last — DEC-042 puts MusicBrainz, IGDB and TMDB
  on the roadmap and singles out IGDB as the one needing real credential machinery. So the mechanism
  names no provider: a `provider_usage` table keyed by `(provider, day)`, a `ProviderQuota` that
  answers `record` and `allows` for any name, and limits supplied as configuration
  (`provider_daily_limits`, default `{"googlebooks": 900}`) rather than written into code. Adding a
  metered provider later is a config entry. Three consequences worth stating:

  - **Unmetered providers are counted anyway.** Open Library has no cap and is never blocked, but
    recording its traffic means a future limit can be set against observed history rather than a
    guess, and the next domain sprint inherits the measurement Phase A had to write a script for.
  - **Exhaustion defers, it does not fail.** A capped provider's job has its `available_at` moved to
    the next day boundary **without incrementing `attempts`**, because the existing `fail` path
    dead-letters at a retry ceiling and a large import would otherwise destroy its own backlog. A
    genuine provider miss still fails exactly as before; deferral is reserved for quota.
  - **Interactive search is counted but never blocked.** Spending the last of a day's quota on a
    search the owner is waiting for is a good use of it; spending it on background enrichment is
    not. The cap therefore guards enrichment only.

  The default of 900 against a real limit of 1,000 is deliberate headroom: Google resets quota on
  Pacific time while the counter uses UTC, so the guard is conservative rather than exact.

- **Consequences.** **Sprint 020 is reopened rather than superseded by a new sprint.** Its file
  already carries a `Phase B — build what Phase A justified` section written to await this
  go-ahead, so reopening is what the gate structure anticipated: the sprint returns to
  `in_progress`, `021-attachments.md` returns to `planned` while it waits, and the Outcome is
  **appended to, never rewritten**. The alternative considered was a new Sprint 021 with attachments
  shifting to 022 and the domain line to 025–027; it was rejected because this file is append-only
  history that already refers to Sprints 021, 024 and 026 by number, and renumbering would silently
  falsify those references while `validate_project.py`'s sequential-numbering rule forced the whole
  cascade. Nothing about the later roadmap changes.
  DEC-044's placeholder-cover guard now protects the chooser too: a candidate that is a provider
  banner is rejected on the same geometry rule, so choosing one cannot install a placeholder.

## DEC-046 — Surviving a sick provider: patience in the background, fast failure in front of a person

- **Date:** 2026-08-13
- **Status:** accepted
- **Context:** Sprint 020's walkthrough ran into Open Library's JSON API answering **503** under
  load, repeatedly and for minutes at a time, while their website stayed up. The owner asked whether
  retries were the answer. Reading the code first found something worse than the outage itself:
  `JobRepository.fail` scheduled its retry for **now**, so an enrichment job spent all three of its
  attempts within a few seconds of an outage starting and then dead-lettered permanently. A
  five-minute wobble meant those books were never enriched again, and no amount of in-request
  retrying would have fixed that, because the damage happened above it.
- **Decision.** Two layers, split by whether anyone is waiting — the owner's stated principle, that a
  batch import may take as long as it needs while the moment-to-moment experience must not pay for a
  provider's bad day.

  **In-request retries**, bounded and deliberately small. Only transport failures and
  `{429, 500, 502, 503, 504}` are retried; a 404 is an answer, not an outage. Delays are exponential
  with jitter, `Retry-After` is honoured up to a five-second cap, and the attempt count is a
  parameter rather than a constant so each caller says how patient it is allowed to be:

  | path | attempts | why |
  |---|---|---|
  | enrichment (`fetch_by_isbn`) | 3 | nobody is watching; the whole point is to finish eventually |
  | cover chooser | 2, 10s each, 15s overall | a dialog someone opened; it may wait a little, not a lot |
  | search | **1 — no retry** | already on a 5s budget, and the other provider's results still render |

  Search is the sharpest case and the reasoning is worth keeping: a retry there returns nothing
  sooner and nothing better, it only spends a budget the reader is already waiting through. For
  Google Books it would also spend metered quota that enrichment will want later (DEC-045).

  **Job-level backoff**, which is the repair that actually matters. A failed job's retry is scheduled
  into the future — 30s, then 60s, then 120s, jittered, capped at ten minutes — so three attempts
  span minutes instead of seconds and a large import fails as a herd but does not resume as one. The
  dead-letter bound is unchanged, so a genuinely broken job still gives up.
- **Consequences.** Retries cost nothing when a provider is healthy: measured after the change with
  Open Library recovered, the chooser returned 14 candidates in 1.9s and 12 in 0.9s, and a search
  answered in 3.6s. Three existing tests are ~1.5s slower because they genuinely exercise the retry
  path now, which is real behaviour rather than overhead to be optimised away.
  **What this does not fix** is stated plainly, because the walkthrough's lesson was that unrecorded
  observations rot: a provider that is down for longer than the backoff window still exhausts a
  job's attempts and dead-letters it. The next step, if outages prove longer than minutes, is to
  treat sustained unavailability the way DEC-045 treats an exhausted quota — defer without spending
  an attempt — which the `JobRepository.defer` primitive already supports. That is deliberately not
  built now: it needs a deferral bound so a permanently dead provider cannot make a job immortal,
  and that is a schema change nobody has yet shown to be necessary.
  This work was done at the owner's direct instruction between sprints, with Sprint 021 left `ready`
  and untouched. Recorded here rather than in a sprint Outcome so it is not lost.

## DEC-047 — Attachments measured: the naive design costs 68x the current backup, and four cheaper shapes exist

- **Date:** 2026-08-14
- **Status:** accepted as a Phase A verdict; **Phase B is not authorized by this entry**
- **Context:** DEC-042 made assess-then-build the default shape for any item whose cost is unknown,
  and Sprint 021 is one. The owner wants to attach arbitrary files to items — epubs for books —
  inside the metadata-first framing. DEC-040 makes that a backup question before it is anything
  else: `ARCHIVED_DIRECTORIES = ("covers", "imports")` tars everything into every backup, seven
  nightly deep. The owner directed that Phase A **measure and report rather than pronounce**, since
  no disk budget is recorded anywhere in this repository, and that the Calibre zero-copy alternative
  be assessed alongside uploaded copies. Everything below was measured by
  `scripts/assess_attachment_cost.py` on 2026-08-14, on an NVMe workstation considerably faster than
  the target ZimaBoard, against a corpus of incompressible ZIP files standing in for epubs.

  **Backup growth, seven-night retention window.** "x today" is against the same library's current
  backup — database plus covers plus imports, no attachments.

  | | 100 files (250 MB) | 300 files (750 MB) | 500 files (1.25 GB) | vs today |
  |---|---|---|---|---|
  | today, no attachments | 26.3 MB | 78.6 MB | 130.9 MB | 1x |
  | **A** in the tar, every night | 1.73 GB | 5.20 GB | **8.68 GB** | **67.9x** |
  | **B** size cap only | 1.73 GB | 5.20 GB | 8.68 GB | 67.9x |
  | **C** separate label, keep 2 | 526 MB | 1.54 GB | 2.57 GB | 20.1x |
  | **D** weekly cadence | 276 MB | 829 MB | 1.35 GB | 10.6x |
  | **E** loose store, deduplicated | 276 MB | 829 MB | 1.35 GB | 10.5x |
  | **F** excluded, manifest only | 26.3 MB | 78.6 MB | 130.9 MB | 1.0x |
  | **G** Calibre reference | 26.3 MB | 78.6 MB | 130.9 MB | 1.0x |

  The multipliers are **independent of corpus size** — 67.9x, 20.1x, 10.5x, 1.0x hold at all three
  scales — so they are properties of the strategy, not of the sample.

  **Compression buys nothing, and costs.** The measured gzip ratio on the attachment corpus is
  **1.0003**: the `tar.gz` is fractionally *larger* than the raw bytes, because an epub is already a
  ZIP and all gzip adds is tar headers. It is not free: at 500 files a gzipping backup takes
  **20.4 s** against **2.0 s** for the loose store, a **10x** difference on hardware much faster than
  the ZimaBoard. The compression the current design pays CPU for is also precisely what makes
  deduplication impossible, since a tar shares no bytes with the tar written the night before.

  **Deduplication is the whole of E's advantage, and it was measured rather than assumed.** Disk
  accounting counts unique inodes; the second nightly backup's real incremental was measured and
  found to be the database and covers only, giving 1.00 effective copies of the attachment corpus
  against A's 7.00. E needs one filesystem, so it degrades to full copies — B's numbers — when
  `BACKUP_DIR` points at a NAS share, which DEC-040 explicitly allows.

  **Restore round-trips under every strategy**, verified in `backend/tests/test_attachment_cost.py`:
  scores, notes and shelves come back in all seven, and the five that carry attachment bytes return
  them byte-identical. F and G restore the database and **name every attachment they could not
  bring back**, which is the only honest form those two can take.

- **Where an attachment hangs: item, with one consequence that must be handled.** Item matches the
  metadata-first framing and survives import merges — a re-import that resolves to `reuse_item`
  finds the attachment already there. The consequence is in undo. `UndoService` deletes an item a
  batch created when no other entry references it, guarded only by `modified_items` for fill-empty
  fields. **An item carrying a hand-uploaded attachment must join that guard**, or undoing an import
  destroys a file the owner deliberately attached — exactly the class of loss the ledger exists to
  prevent. Separately, **no cover file is ever unlinked today**, so a deleted item leaks its image;
  product spec open question 2 accepts that explicitly on the grounds that "covers are ~50KB each."
  Attachments invalidate that premise at 2.5 MB per orphan, so whoever builds this owes either a
  delete path or a prune action.

- **Threat model, LAN-only and unauthenticated (product spec section 9).** Today every byte the
  application serves has been through `prepare_cover` / `prepare_uploaded_cover` and re-encoded to
  JPEG, and `get_cover` answers with a fixed `media_type="image/jpeg"`. Safety comes from that
  normalization, not from headers — the codebase sets no `Content-Security-Policy`, no
  `X-Content-Type-Options`, and no `Content-Disposition` anywhere. An opaque attachment is the first
  user-controlled content type to reach a browser, and it is served from the same origin as the SPA.
  So: **stored XSS is the real risk** — an uploaded HTML or SVG opened inline can script the
  application against its own API — and `Content-Disposition: attachment`, `nosniff` and a fixed
  `application/octet-stream` become load-bearing rather than optional. Filenames must be stored as
  metadata with server-generated paths, so a name is never a path component. And with no auth,
  anyone on the LAN can fill the disk: a per-file cap is not a total cap.

- **The Calibre alternative is viable with no schema change.** `calibre_uuid` is already persisted as
  an item identifier by the import path, and Calibre's `books` table carries `uuid` and `path` in the
  same row, so a Calibre-sourced item can re-derive its file location at serve time from the
  read-only mount. That is strategy G: zero disk, zero backup growth, and no new storage to secure.
  Its limits are real — it covers only books already in Calibre, it breaks if the library moves, and
  it is a different feature from attaching an arbitrary file to an arbitrary item.

- **Decision.** The measurement is recorded; the choice is the owner's, and it is **two choices**:
  whether attachments are built at all, and which strategy they get. The strategy question must not
  be settled quietly by an implementer, because it changes what a restore promises. **A and B are not
  recommended**: 68x, and B's cap bounds the worst file while leaving the total unbounded.
  **E is the recommended row if attachments are stored at all** — full fidelity, 10.5x, and the
  fastest backup of any strategy because it stops gzipping what does not compress. **F is the
  recommended row if the 10.5x is unwelcome**, and it is more defensible than it looks: an epub
  usually still exists wherever it came from, which a score and a note never do.
- **Consequences.** No product change ships in Phase A. Sprint 021 stays `in_progress` pending the
  owner's go-ahead, which DEC-035 requires to be explicit and recorded here rather than inferred from
  this verdict. `scripts/assess_attachment_cost.py` and its tests are committed so any future
  revisit re-measures rather than re-argues. If Phase B proceeds, the undo guard, the orphan-file
  question and the three response headers are requirements it inherits from this entry, not
  refinements to be discovered later.

## DEC-048 — Phase B authorized: attachments are content-addressed, and the backup shares blobs rather than copying them

- **Date:** 2026-08-14
- **Status:** accepted; the go-ahead DEC-035 and DEC-047 both required
- **Context:** DEC-047 measured seven strategies and handed the owner two choices — whether to build
  attachments at all, and which storage strategy. The owner read it and asked a question that
  exposed a gap: DEC-047 costed *backup* layouts and left the live store as "files in a directory".
  Since nothing was built yet, the owner directed that both be designed together and that the result
  be scalable. This entry records the decision, because DEC-035 requires Phase B to rest on an
  explicit go-ahead rather than an agent's reading of a verdict.
- **Decision.** Attachments are built, as the narrow slice Sprint 021 scopes: one or more opaque
  files per item, uploaded manually, size-capped, listed with filename and size, downloadable from
  the detail page. No format parsing, no reader, no reading progress, no device sync.

  **The live store is content-addressed**: `data/attachments/{sha256[:2]}/{sha256}`, with the
  original filename held in the database as metadata rather than on disk. One choice pays four ways.
  The same file attached to several items is stored once. **Path traversal becomes impossible by
  construction** rather than by validation, because a user-supplied name is never a path component —
  the traversal test Sprint 021 requires is satisfied by the design instead of by a filter.
  Integrity is free, since the path is the digest. And a blob that can never change makes the backup
  correct by definition rather than by an assumption about immutability.

  **The backup shares blobs instead of copying them** — strategy E in DEC-047. Database, covers and
  imports keep exactly today's behaviour: seven full nightly copies, unchanged, because they change
  constantly and are small. The attachment payload is hardlinked **from the live store**, which is
  O(1), always finds the blob, and keeps a deleted attachment alive for as long as a backup that
  carries it still exists. Where `BACKUP_DIR` is on another filesystem — DEC-040 explicitly allows a
  NAS — the link falls back to a copy and the cost degrades to DEC-047's strategy B.

  **Deletion is refcounted**: a blob goes when no attachment row references it. That mechanism also
  answers the orphaned-cover leak DEC-047 found, rather than repeating it at 2.5 MB per orphan.

  **Marginal cost per attached file is 2x its size** — one copy live, one shared across every backup
  — against 8x for the naive design. It is linear in the corpus with no multiplier, and a store keyed
  by digest does not care whether the bytes are an epub or, under sprints 024-026, a FLAC.

- **Verification stays cheap on purpose.** The backup manifest records each blob's name and size, and
  `verify_backup` checks those rather than rehashing. The name *is* the digest, so a deep check is
  always available, but rehashing 1.25 GB nightly would dominate a backup that DEC-047 measured at
  about two seconds. Recorded as a trade-off rather than left implicit.
- **Consequences.** A new migration adds the `attachments` table, so the head moves off
  `0009_provider_usage` and the three tests that pin it by literal must be updated. `UndoService`
  gains an attachment guard, per DEC-047: an item carrying a hand-uploaded file is retained rather
  than deleted when a batch is undone. Downloads carry `Content-Disposition: attachment`,
  `X-Content-Type-Options: nosniff` and a fixed `application/octet-stream`, which are load-bearing
  here because today's safety comes from the cover pipeline re-encoding everything to JPEG and this
  is the first user-controlled content type the application serves. Sprint 023 (export) inherits an
  open question this entry does not answer: whether an export carries attachment bytes, references,
  or neither.

## DEC-049 — Attachment lifecycle reviewed: one real hole, several thin edges, scheduled as Sprint 022

- **Date:** 2026-08-14
- **Status:** accepted
- **Context:** With Sprint 021 closed and pushed, the owner asked for an assessment of whether the
  attachment feature covers its bases — delete, replace, rename, and whether the flows are clean and
  leak-free — explicitly without feature creep, and with any resulting work scheduled ahead of the
  existing plan. Everything below was read out of the shipped code, not inferred.
- **Findings.**

  **The one genuine hole is reclamation.** `delete_blob_if_unreferenced` has exactly one caller,
  `LibraryService.delete_attachment`. Three routes therefore produce a blob nothing points at and
  nothing can find: `attachments.item_id` is `ON DELETE CASCADE`, so deleting an item drops the rows
  and leaks the bytes; `store_blob` deliberately writes before the row is inserted, so a crash
  between them leaves an orphan; and deleting an entry leaves its item, and so its attachments, in
  place by design. The undo guard from DEC-047 makes the first route unreachable *today*, which is a
  guard rather than a fix. At 2.5 MB per file this is a materially different problem from the 39 KB
  orphaned cover that product spec open question 2 waved through.

  **Missing operations.** No rename, although the filename is already only metadata and renaming is a
  single database write. No replace. Whether replace is a real operation once rename exists is a
  product question and is left open rather than answered by building it.

  **Convention violated.** Removing an attachment has no confirmation, while the product spec's
  interaction notes state that confirmation dialogs are limited to delete and provider refresh, and
  *Delete entry* on the same page has one. Removing a file is irreversible once it is the last
  reference.

  **Memory.** Upload does `await file.read(cap + 1)` and download does `target.read_bytes()`, so a
  25 MiB file is a 25 MiB allocation per concurrent request. The cover endpoints do the same, but a
  cover is 39 KB. Not a leak — nothing accumulates — but a sharp edge on a ZimaBoard.

  **No frontend leak was found.** There is no `createObjectURL` anywhere in the codebase, so the
  classic blob-URL leak does not exist here; the React Query cache is keyed per item and bounded; the
  file input is reset after each pick. Two minor warts: `disabled={remove.isPending}` is on every
  Remove button, so removing one file disables all of them, and the `sr-only` file input is focusable
  and shares its accessible name with the visible button, giving two tab stops for one action.

  **One caching wrinkle.** The download carries `Cache-Control: immutable` for a year with no
  validator, while the row's `filename` is mutable — a re-upload of identical bytes under a new name
  renames the row. A file already downloaded therefore keeps its old name. Small, but real, and it
  makes rename and caching a single question rather than two.

- **Decision.** Scheduled as **Sprint 022, ahead of the existing plan** at the owner's direction,
  covering reclamation, rename, the remove confirmation, streaming, and the two UI corrections.
  Multiple-file selection, drag-and-drop and upload progress bars are named as **explicit non-scope**:
  they are real improvements but they are additive polish, not lifecycle correctness, and the owner
  asked for no feature creep. The scope line from DEC-047 is restated in the sprint file: an
  attachment is an opaque file, or it is a reader.
- **Consequences.** Plan revision goes to **9** and the tail of the roadmap renumbers: creator sort
  names 022 → 023, export 023 → 024, and the domain line 024-026 → 025-027. This is the same forced
  renumber DEC-042 hit, and for the same reason — `scripts/validate_project.py` requires
  `active_sprint == len(completed_sprints) + 1` and permits exactly one non-completed sprint file. The
  final-sprint bound moves from 026 to 027 in `WORKFLOW.md` and `validate_project.py`. Sprint 021's
  Outcome keeps its "Impact on future sprints" text as written, because a completed sprint's Outcome
  is audit history; its numbering is superseded by this entry rather than edited.
  **Reclamation is the dangerous deliverable** and the sprint file says so: it deletes data by
  inference, the refcount is authoritative where the filesystem is not, and a sweep must be reasoned
  about against an upload that has written its blob but not yet committed its row.

## DEC-050 — Attachment lifecycle: reclamation is a command, replace is not a feature, and `immutable` was wrong

- **Date:** 2026-08-14
- **Status:** accepted
- **Context:** Sprint 022 closed the lifecycle DEC-049 found open. Two of its
  questions were the owner's rather than the implementer's, and both were put to
  the owner at activation rather than settled quietly.
- **Decisions.**

  **Reclamation is an operator command, dry-run by default.** `akasha-attachments
  reclaim` reports what it would remove and removes nothing until `--apply`. Not
  a background sweep and not scheduled: this is the only routine in the codebase
  that deletes data by inference, and `enforce_retention` already sets the
  precedent that such a routine acts only on what it can prove is ours. Files
  under `attachments/` that we did not write are reported and left alone.

  **Two independent protections cover the concurrent upload**, which is the
  failure the sprint named as this deliverable's real risk. The sweep reads the
  filesystem *before* it reads the database, so a row committed between the two
  reads makes its blob read as referenced rather than orphaned — the reverse
  order deletes a file that was attached seconds earlier. And a blob whose mtime
  is inside a one-hour grace period is never a candidate at all, which covers the
  same window for an upload still in flight during both reads. The read ordering
  is pinned by a test that fails when the two are swapped.

  **A blob a backup holds is safe by construction, and this was checked rather
  than assumed.** The backup hardlinks blobs out of the live store (DEC-048), so
  the backup directory holds its own entry against the same inode; unlinking the
  live path decrements a link count and cannot reach the bytes. Verified in the
  container: the reclaimed blob was byte-identical in the backup afterwards and
  the backup still verified.

  **Item deletion defers to the sweep rather than reclaiming inline.** The only
  path that deletes an item is undo, and undo retains an item carrying an
  attachment (DEC-047), so an inline reclaim there would be unreachable code
  guarding an unreachable case. The deferral is proved from both ends by test:
  undo retains, and a blob orphaned by an item deleted any other way is found and
  reclaimed. Note that `entries.item_id` has no `ON DELETE CASCADE`, so an item
  cannot be deleted while an entry references it — found during the walkthrough,
  which had to delete the entry first to produce the orphan at all.

  **Replace is not built.** Once rename exists, replace is remove plus attach:
  the owner chose to skip it rather than add an endpoint, a second confirmation
  and a question about what a row's identity and `created_at` mean when its bytes
  change underneath. Recorded here so it reads as answered rather than forgotten.

  **`Cache-Control: immutable` was wrong and is gone.** The blob genuinely never
  changes, but the *response* is not the blob — it carries the filename, and the
  filename is editable. A year of `immutable` with no validator meant an
  already-downloaded file kept saving under a name the owner had since corrected.
  Replaced with `max-age=0, must-revalidate` and an ETag over digest **and** name
  together, so an untouched file still costs a 304 with no body while a renamed
  one cannot match and is refetched under its new name. Weakening the cache was
  the cheaper fix than removing the name from the response, because the name is
  the entire point of `Content-Disposition`.

- **Consequences.** `akasha-attachments` is a second console script alongside
  `akasha-backup`, documented in the runbook; it is not wired into cron and
  deliberately does not run itself. Uploads and downloads stream, measured at
  +29.9 MiB → +2.6 MiB peak RSS on upload and +24.9 MiB → +0.0 MiB on download
  for a 25 MiB file, which also makes the cap an as-it-arrives check rather than
  a buffer-then-refuse one. The orphaned cover from product spec open question 2
  is still not collected: the reclaim is scoped to the attachment store and does
  not generalize to covers, which are re-fetchable cache. Sprint 023 is unaffected
  and remains the creator sort names work.

## DEC-051 — The creator sort name is stored, seeded from Calibre where it exists, and correctable

- **Date:** 2026-08-14
- **Status:** accepted
- **Context:** `items.sort_author` is `json_extract(metadata, '$.authors[0]')` verbatim, and the
  library's "Author" sort ordered by its normalized form. That filed "Gabriel García Márquez" under
  G and "Adolfo Bioy Casares" under A, which for a Spanish-language library makes the sort
  unusable. The roadmap named the trap the obvious repair falls into: splitting on the last space
  yields *Márquez* and *Llosa*, both wrong, and *Rulfo*, right. Spanish double surnames carry no
  reliable signal, so no heuristic closes this.
- **Decision:** Store the sort name rather than compute it on read. Migration
  `0011_creator_sort_names` adds three columns to `items`: `creator_sort_override`, the only one
  that is not derived, and `creator_sort` / `creator_sort_normalized`, both computed as
  `override or creator_sort_name(first_author)` by the same `before_insert`/`before_update` mapper
  event DEC-036 introduced, so no write path can leave the sort key stale. Backfilled in Python
  with the domain function, following `0007`, so Alembic depends on nothing the application
  registers. Ordering and the keyset cursor move to `creator_sort_normalized`; **the `q` filter
  deliberately does not**, and stays on `sort_author_normalized`, because search matches the name
  as written and "gabriel garcia" must keep finding a row that sorts as "garcia marquez gabriel".
  Three consequences of that split are load-bearing: the API returns the display name and the sort
  name as separate fields, the detail page and grid keep showing the name as written, and
  duplicate-matching in `DomainRepository.match` still compares display names.

  **The heuristic is biased towards the Spanish double surname on purpose.** The first token is the
  given name, an initial stays with it, everything after is the surname, and a name already
  carrying a comma is left alone. It gets all three roadmap cases right and gets
  "John Ronald Reuel Tolkien" wrong. Measured on a walkthrough library of 16 authored items: **14
  right, 2 wrong**, both failures of the same kind — two given names and no initials
  ("Jorge Luis Borges" → "Luis Borges, Jorge"). Tuning it further was rejected: the edit surface is
  the answer to a wrong name, which is why the sprint treated it as the feature rather than the
  polish.

  **Calibre's `authors.sort` seeds the override, as owner data rather than cache.** A real Calibre
  database carries a hand-curated sort name per author, and this library came from Calibre, so the
  seed is curated truth on exactly the names the heuristic has no signal for. The column is
  optional — `REQUIRED_TABLES` guarantees the `authors` table, not its columns — so the reader
  checks and falls back. Storing it as the override rather than as the derived value is what stops
  a later refresh or re-import recomputing over it. Undo learned the field in the same change: the
  import fills it, so undo must be able to unfill it, while retaining a value the owner corrected
  afterwards.

  **`CursorState.v` goes to 2.** A cursor issued before the migration holds "gabriel" where the
  column now holds "garcia marquez gabriel"; comparing them would silently skip or repeat a page.
  The version bump makes it a `400 invalid_cursor` the library page already renders. This
  establishes the rule recorded in the technical spec: bump the version whenever a stored
  projection a cursor compares against changes meaning.
- **Consequences:** The migration head is `0011_creator_sort_names`. `sort_author` keeps its name
  and its display role; renaming it to a creator-shaped name was considered and deferred to Sprint
  025, which changes the metadata key from `authors` to `creators` and can do both in one pass —
  doing it here would have touched three components, seven e2e seeds, the benchmark and several
  backend tests inside the sprint whose own risk note is that pagination breaks in ways unit tests
  miss. No index accompanies the new columns, for the reason DEC-036 measured and re-verified here:
  `sort_author` at page 26 contended is **78.7 ms p95**, against the 78 ms DEC-036 recorded, and
  the text filter 10.4 ms against 10 ms. Sprint 024 (export) inherits a third owner-edited field
  after the attachment filename (DEC-050): an export that reconstructs sort names from authors
  loses a correction, exactly as one that reconstructs filenames from digests does.

## DEC-052 — Domains attach at six seams; the core is already neutral

- **Date:** 2026-08-14
- **Status:** accepted
- **Context:** Sprint 025 was planned as an unstructured pilot whose deliverable was a list of
  everything the second domain had to touch. Before activating it the owner asked the framing
  question directly — are domains cast into the book shape, or is the book shape generalized first
  — and asked that the album mapping be validated against the live API rather than reasoned about.
  Both were done; `docs/domain-architecture-proposal.md` is the result and is accepted in full.
- **Decision.**

  **The framing was wrong in a useful way.** `items` has been a neutral shell since Sprint 002 —
  `type`, `title`, `subtitle`, `year`, `cover_path`, `identifiers`, opaque `metadata`. The core does
  not need generalizing. What is book-shaped is every layer above it, so the work is lifting
  book-specific logic out of the shared layers into a per-domain plugin. **Strategy D** of the
  proposal: neutral core, seam-by-seam extraction, six seams, everything else untouched until a
  domain proves it must move. Strategy A (cast albums into book fields) was rejected on evidence,
  not taste; Strategy B (generalize everything first) was rejected because it designs the
  abstraction from one real domain.

  **Two measured facts decided it, both from live MusicBrainz probes on 2026-08-14.**

  *MusicBrainz ships a curated sort name and only inverts people.* `Miles Davis` is type `Person`
  and sorts `Davis, Miles`; `Daft Punk` is type `Group` and sorts `Daft Punk`; `Various Artists` is
  type `Other` and is left alone. DEC-051's `creator_sort_name` assumes a person's name, which is
  safe for books and false for a large share of album creators — it would produce `Punk, Daft` and
  `Floyd, Pink`. Casting an album into `metadata.authors` discards knowledge the provider already
  had and then manufactures the hand-correction work DEC-051 defines as owner data. This
  generalizes the Calibre seed into a rule: **a source that knows the sort name seeds the override;
  the heuristic runs only when nothing knew.**

  *Barcode is not a unique edition key.* `888837168625` appears on three distinct *Random Access
  Memories* releases and twice more with a leading zero, while a 1959 release carries none. ISBN's
  global uniqueness is the only reason `merge_and_rank` can group candidates across providers by it.
  Albums are therefore not "books with a different identifier field" — cross-provider identity does
  not exist for them, and the seam must be a strategy (`identity_key(candidate) -> str | None`,
  where `None` means never merge) rather than a configurable field name. This lives in
  `domain/providers.py`, which the earlier plan's touched-list did not anticipate.

  **The owner's four open questions are answered:** Strategy D accepted; albums perform no
  background enrichment (one release fetch returns everything, to be confirmed in the pilot, not
  bolted on later); Sprint 024 runs first and is confirmed rather than threatened by seam 3; and the
  status vocabulary splits, below.

  **Seam 5 splits, because six seams in one sprint is over-specified.** The owner raised this and it
  is correct. Splitting *before* albums would revert to Strategy B — a seam cannot be validated with
  only one domain present — so albums stay whole in Sprint 025 and the split runs through seam 5
  instead:

  - **5a, in Sprint 025:** per-domain status *labels* over the existing status values. `read`
    renders as "Listened" for an album. No schema change, no validation change, no hotkey change,
    and squarely inside the standing invariant that internal names are permanent while user-facing
    copy is free to move. The duplicate `statusLabels` in `pages/TriagePage.tsx:42` is collapsed
    into `features/library/labels.ts` first, since a per-domain label map against a duplicated
    table is how the book vocabulary silently survives on one screen.
  - **5b, in Sprint 026:** per-domain status *vocabularies* — different sets, validation moving off
    the global `EntryStatus` StrEnum, filter chips, triage hotkeys — plus the product question of
    whether `reread_count` and `date_finished` mean anything for an album. Deliberately decided with
    two domains in hand rather than one.

- **Consequences.** Roadmap moves to plan revision 10 and gains a sprint: 025 albums (seams 1–4, 5a,
  6), **026 status vocabulary (seam 5b)**, 027 games, 028 series. `FINAL_SPRINT` in
  `scripts/validate_project.py` moves from 27 to 28. Sprint 024 gains one paragraph framing the
  Goodreads CSV as one domain's export view rather than the export's only shape; its format bet —
  entity-shaped, opaque `metadata` — is confirmed by seam 3 and needs no redesign. Sprints 027 and
  028 gain a falsifiable prediction: games should need no seam that albums did not, and if it needs
  a seventh the abstraction was wrong. Three concrete cover-pipeline facts are recorded for seam 4:
  Cover Art Archive serves `http://` URLs while `validate_url` requires https, its final redirect
  host is `dn710907.ca.archive.org` — matched by neither the `archive.org` literal nor the
  `.us.archive.org` suffix, and checked on every hop at `covers.py:117` — and full-size art is
  811 KiB against 244 KiB at 1200px, which matters because `MAX_COVER_EDGE` is 600 and the
  difference is downscaled away.

## DEC-053 — Domain-line sprints run on a branch; the rest stay on `main`

- **Date:** 2026-08-14
- **Status:** accepted
- **Context:** Sprint 025's risk section flagged an apparent conflict: the roadmap says the second
  domain is implemented "on a branch", while `AGENTS.md` says a sprint ends with a clean worktree and
  all commits local on the current branch. The owner settled it at planning time rather than leaving
  it to be re-litigated mid-sprint.
- **Decision:** **The conflict was overstated and there is nothing to reconcile.** The invariant
  reads "local on *the current branch*", not "on `main`" — it forbids pushing, not branching. A
  sprint may therefore run on a branch and still satisfy every invariant, provided it ends clean and
  unpushed.

  What needed deciding is which sprints use one, and the rule is the risk, not the sprint number:
  **a sprint whose architecture could fail spectacularly runs on a branch; a sprint whose design is
  already confirmed stays on `main`.**

  - **Sprint 024 (export) stays on `main`.** It carries no architectural risk — DEC-052's seam 3
    confirmed its entity-shaped, opaque-`metadata` format bet rather than threatening it — and it
    depends on 020, not on the domain line. Isolating it would quarantine work nobody doubts.
  - **Sprint 025 (albums) and the domain line after it run on a branch**, cut from `main` when 025
    is activated. Its least-proven seam is identity (DEC-052 seam 2), derived from measurement
    rather than from a walk through the code, and the sprint already names two conditions under
    which it should stop and re-plan rather than push through.

  A branched sprint follows the ordinary protocol in every other respect: state and handoff advance
  as usual, the worktree ends clean, and nothing is pushed. Merging the branch back is an owner
  decision at the sprint's close, not an automatic step — that is the entire point of cutting it.
- **Consequences:** Sprint 025's "Risks and decisions to surface" no longer carries this as an open
  question. A later agent finding domain work on a branch should read that as intended state and not
  as an inconsistency to repair under `AGENTS.md` §1. `main` continues to hold every completed sprint
  and remains the branch a failed domain experiment is abandoned *back* to.

## DEC-054 — The export carries attachment references and their digest, not their bytes

- **Date:** 2026-08-14
- **Status:** accepted
- **Context:** DEC-048 built attachments and explicitly left one question for the export sprint:
  whether an export carries attachment bytes, references, or neither. Sprint 024 put it to the owner
  at activation, as Sprints 021 and 022 did with theirs.
- **Decision:** **References, with the digest.** Each item's export payload carries every attachment's
  `filename`, `byte_size`, `sha256`, `created_at` and API `path`. No bytes.

  "Neither" was never actually available, and noticing that narrowed the fork before it reached the
  owner: the sprint's first acceptance criterion requires every field the owner typed to survive, and
  DEC-050 made the attachment filename exactly that. An export omitting attachments would fail its
  own criterion.

  Bytes were rejected because the blob is **already held twice** — once live and once hardlinked into
  every nightly backup (DEC-048), where DEC-050 verified a backup's copy survives a live reclaim
  byte-identically. A third copy would convert an artifact you can open, read and mail into a
  multi-gigabyte archive, which is the fork the roadmap warned changes what the feature *is*.

  **The digest is what makes a reference more than a note.** The blob's path under
  `data/attachments/{sha256[:2]}/{sha256}` *is* its digest, so a reference resolves against any
  backup by name alone, with no running instance and no index. That is the property that makes
  omitting the bytes safe rather than merely cheap.
- **Consequences.** The export is a file rather than an archive, so it streams as JSON with no
  container format and no second code path. A restore story that needs bytes uses a backup, which is
  what backups are for (DEC-039, DEC-040). Should a future sprint want a self-contained archive, it
  is an additive `?include=attachments` variant rather than a format change, because the reference
  block already names every blob it would need to carry.

## DEC-055 — Every seam was cut where section 4 said, and the two that moved are named

- **Date:** 2026-08-14
- **Status:** accepted
- **Context:** Sprint 025's eleventh acceptance criterion requires that a seam cut somewhere other
  than `docs/domain-architecture-proposal.md` section 4 describes is written up — **and that a clean
  run reports that too, because silence is not evidence.** This is that entry.
- **Decision:** **The six seams landed where section 4 put them.** Albums are searched, added,
  covered, listed, opened and edited beside books with no book vocabulary anywhere in the path, and
  none of the three tripwires fired:

  - `identity_key` lifted out of `merge_and_rank` without dragging the ranking signals with it. What
    it needed beside it was the **source preference**: `_merge_group` picked the `openlibrary` row as
    a group's primary by name, which is the same question — who wins a merge — and belongs to the
    same strategy. That is a refinement of seam 2, not a relocation.
  - **Keyset pagination, `CursorState`, the job runner, the import ledger, undo, backup, attachments
    and shelves needed no change at all**, exactly as section 4 predicted. A mixed library was walked
    one row at a time past page 1 on four sorts to prove it. The one adjacent question — a stale
    `sort=sort_author` cursor after the rename — needed no version bump either, because
    `decode_cursor` already rejects a cursor whose sort key does not match the query.
  - No seventh seam was needed.

  **Two things sat slightly wide of where section 4 drew them, and both are recorded here rather
  than smoothed over:**

  1. **Seam 4 reaches one hop further than "upgrade the scheme before validating".** The Cover Art
     Archive answers `http://` in its JSON *and* in every redirect hop — measured live on
     2026-08-14: `coverartarchive.org` 307s to an `http://archive.org` URL, which 302s to an
     `http://dn710907.ca.archive.org` URL. Upgrading only the URL the JSON supplies fails on the
     second hop, so the upgrade is applied at every hop, and the allowlist gained a `.archive.org`
     subdomain rule rather than another literal host.
  2. **Seam 3 reaches the detail page and the export, not only the dialog.** Section 4 said the field
     spec drives "the metadata dialog, the detail page's display order, and the export's
     human-readable half", and the walkthrough proved the last part is load-bearing: with two domains
     present the Goodreads CSV was emitting albums as books. The CSV is one domain's export view and
     is now restricted to it; the entity-shaped JSON beside it still carries every type.
- **Consequences.** Sprint 027's falsifiable prediction stands: games should need no seam albums did
  not. The seam model is now proved by two domains rather than argued from one, and the parts of it
  that turned out to be under-specified were both *narrower* than expected rather than wider — which
  is the failure direction DEC-052 chose deliberately when it rejected Strategy B.

## DEC-056 — Metadata responses stopped inventing empty defaults

- **Date:** 2026-08-14
- **Status:** accepted
- **Context:** `ItemResponse.metadata` was a Pydantic model with `default_factory=list` on its list
  fields, so an item with no subjects was served `"subjects": []` whether or not the row held one.
  Seam 3 replaced that model with the opaque object the row actually stores.
- **Decision:** **The API serves the metadata that exists and nothing else.** An absent field is
  absent, not an empty list. Clients treat a missing key and an empty value the same way, which the
  frontend already did.
- **Consequences.** This matches the rule Sprint 024 set for the export — `metadata` passes through
  untransformed — so the two surfaces no longer disagree about what an item holds. A client that
  relied on the defaults would see a shape change; the only client is this repository's frontend, and
  a test pins the behaviour.

## DEC-057 — An album's status records possession, not consumption

- **Date:** 2026-08-14
- **Status:** accepted
- **Context:** Sprint 026's first deliverable is the product question DEC-052 deferred until two
  domains existed: whether `reread_count` and `date_finished` mean anything for an album. The owner
  answered it while trying Sprint 025's albums in the running application, before the sprint was
  activated.
- **Decision, in the owner's words:** album statuses should be **wishlist / pending / owned** rather
  than read/reading/read, and **a relisten counter makes no sense**.

  This is a larger answer than the question asked, and worth naming as such: it says an album's
  status is not a *consumption* state at all. A book moves to-read → reading → read, and that
  progression is the thing being tracked. An album is played hundreds of times or twice, and the
  interesting fact is whether you have it. So **status is a per-domain concept, not merely a
  per-domain vocabulary** — which is what seam 5b was always for, and confirms the split DEC-052
  made rather than complicating it.

  Consequences that follow directly:

  - `reread_count` is not shown or stored for albums, and `date_started` / `date_finished` go with
    it: they date a passage through a book that an album does not have.
  - The **score and the note carry the opinion** for an album, which they already do for books. The
    entry model does not need a new field to express "I have listened to this and I think it is
    an 8".
  - `unsorted` stays universal, because imports land there whatever the domain.
- **Open, and for Sprint 026 to settle with the owner rather than to assume:** the owner also wants
  **format tags — CD / Digital / Vinyl for albums, physical / borrowed / digital for books.** Those
  overlap with `owned`: a record of "I have this on vinyl" already asserts possession. Either
  - **(a)** status is possession (`wishlist` / `pending` / `owned`) and format is a property of the
    copy, which double-encodes ownership in two places that can disagree; or
  - **(b)** format tags *are* the possession record — having one means you own it — and status keeps
    a lighter consumption shape (`pending` / `listened`), which is fewer concepts but makes
    "wishlist" mean "no format tag yet", an absence rather than a state.

  **(a) is the recommendation**, because a status that can only be inferred from the absence of a tag
  is not legible on a card, and the walkthrough showed the status control is the thing the eye lands
  on. But this is a product judgement and the sprint must put it to the owner before building either.
- **Consequences.** Sprint 026's deliverable 1 changes from *ask the question* to *settle the
  ownership/format overlap*, which is a smaller and better-posed question. Books are untouched: their
  statuses, rereads and dates keep their present meaning, and no existing entry is remapped.

## DEC-058 — This plan line ends at the domain contract; further domains are epics

- **Date:** 2026-08-14
- **Status:** accepted
- **Supersedes:** the sprint 027/028 assignments in DEC-052, which put games and series inside this
  plan. It does not disturb DEC-052's architecture, which was validated exactly as intended.
- **Context:** Sprint 025 existed to find out whether a second domain was affordable. It was: all six
  seams landed where they were drawn and no tripwire fired (DEC-055). The owner's conclusion from
  running it is that **the experiment answered its question, and the plan should now finish music,
  polish what exists, and stop** — rather than spending its remaining sprints proving the same point
  twice more with games and series.
- **Decision.** **Plan revision 11.** The line ends with four sprints:

  | Sprint | What it closes |
  |---|---|
  | 026 | Statuses, formats and tracklists — music finished as a domain |
  | 027 | Library shell and shelves — the polish pass on the screen the owner actually uses |
  | 028 | The domain contract: what a domain must supply, and a conformance suite that proves it |
  | 029 | Per-domain imports: the pipeline stops being book-only |

  **Sprints 028 and 029 are the gate.** Their purpose is that a third domain becomes an *epic on top
  of a contract* rather than a sprint inside this plan: each domain encapsulated enough that
  `calibre → books`, `spotify → music` and `steam → games` can be built in parallel by different
  hands without touching each other or the core. `FINAL_SPRINT` moves 28 → 29 in
  `scripts/validate_project.py`.

  **Games and series leave the numbered plan** and become future epics. DEC-052's falsifiable
  prediction — that games need no seam albums did not — is not abandoned; it becomes the first thing
  the conformance suite in 028 is written to check, which is a better test of it than another
  bespoke sprint would have been.
- **Consequences.** The project reaches `complete` at the end of 029 rather than 028. Auth is
  unaffected and remains unscheduled (product spec section 9): it gates *exposure*, not domains, and
  nothing here changes that. A domain epic started after 029 inherits a written contract and a test
  suite it must pass, instead of six seams it must infer from how albums happened to be built.

## DEC-059 — Ownership is an entry-level format tag, not a status and not a shelf

- **Date:** 2026-08-14
- **Status:** accepted
- **Answers:** the question DEC-057 left open.
- **Context:** DEC-057 settled that an album's status records possession, and named one unresolved
  overlap: if a record is tagged `Vinyl`, the tag has already asserted ownership. The owner wants
  **both** readings supported: *"I can sort by owned and see where/how I own it"*, and *"mark
  something as wishlist → vinyl, so I can schedule my next purchase."* They also drew a boundary
  around shelves: those are **a higher tier of organization — "work", "fiction"** — and formats are
  not that.
- **Decision.** **Status and format are independent axes, and a format is a property of your copy.**

  A wishlist entry can carry `Vinyl` — the format you *intend* to buy — and an owned entry carries
  the format you actually have. Neither implies the other, so nothing is double-encoded and
  "wishlist → vinyl" is expressible, which option (b) in DEC-057 could not do.

  **It hangs on the entry, not the item.** An album's `format` from MusicBrainz describes *a release*
  — that Kind of Blue was pressed on 12" vinyl in 1959. Your copy might be a reissue, a CD or a
  stream. Those are different facts and the existing model already separates them: items hold shared
  edition facts, entries hold what is true for you.

  **Multi-valued**, because owning a record on vinyl *and* digital is ordinary — vinyl frequently
  ships with a download code — and because turning one value into many later is a migration.

  Costed against the alternatives:

  | | Shape | For | Against | Verdict |
  |---|---|---|---|---|
  | **A** | A `format` column on `entries` | One migration, trivial to sort and filter | Single-valued; vinyl-plus-digital needs a migration later | Rejected — the limitation is the common case |
  | **B** | Reuse shelves with a naming convention | No new machinery at all | Collapses the owner's explicit distinction: shelves are "work"/"fiction", not "vinyl" | Rejected on the owner's boundary |
  | **C** | JSON array on the entry | No new table | Filtering and counting need a projection; the same problem `metadata` already has | Rejected |
  | **D** | An `entry_formats` join table, vocabulary per domain from the registry | Multi-valued; filter and facet reuse the shelf query patterns exactly; the vocabulary is a domain's to declare, like its statuses | One migration and one new table | **Accepted** |

  **Shelves' mechanism is reused; shelves' meaning is not.** The join, the slug, the facet count and
  the bulk-assign path are proven and get copied. The control is its own, the vocabulary is closed
  and per-domain (`Vinyl`/`CD`/`Digital` for albums, `Physical`/`Borrowed`/`Digital` for books)
  rather than free text, and nothing renders a format as a shelf.
- **Consequences.** Sprint 026 carries this. "Sort by owned and see how" is a status filter plus the
  format on the card; "schedule my next purchase" is filtering `wishlist` by format. The closed
  vocabulary lives on `Domain` beside `fields` and the statuses, so a future domain declares its own
  — and the conformance suite in Sprint 028 gains one more thing to check.

## DEC-060 — Seam 5b, as built: what a domain declares about its entries

- **Date:** 2026-08-15
- **Status:** accepted
- **Implements:** DEC-057 and DEC-059. Records the three judgements Sprint 026 was told to surface
  rather than settle silently, and the two things the build found that the plan did not.
- **Decision.** `Domain` now declares what an *entry* on it can be, not only what an item is: an
  ordered status vocabulary carrying its own labels and triage keys, the default a newly added entry
  takes, which of `date_started` / `date_finished` / `reread_count` exist, its formats, and the
  heading over the personal region of the detail page. `status_labels` is gone — a label lives on the
  status it names.

  The three open judgements, answered by the owner on 2026-08-15:

  1. **Filter chips are one row per domain**, each under that domain's name, rather than a single
     union row. A library holding books and records has no one status vocabulary, and "Read" beside
     "Owned" with nothing saying which is which reads as one confused list. This survives Sprint
     027's domain tabs, which scope the rows to one at a time.
  2. **No status migration.** The album domain has never left this branch, so the only album entries
     that existed were three walkthrough rows in the dev library. They were deleted and re-added
     rather than remapped, and a test seeds one entry per book status *before* the change and reads
     all six back (Sprint 026 AC3).
  3. **A field a domain does not have is refused on write with a 422**, not merely hidden. Hiding
     leaves the API, the importers and the export able to store a reread count on a record — a value
     nothing can ever mean.

- **What the build found that the plan did not:**

  - **`entries` carried the six book statuses as a CHECK constraint.** Seam 5b was book-shaped one
    layer *below* the API as well. Migration `0013_entry_formats` rebuilds the table with the
    constraint widened to the union of every domain's vocabulary. It still catches a typo; it cannot
    express the real rule, which depends on the joined item's type. SQLite cannot alter a CHECK in
    place, and SQLAlchemy does not reflect SQLite CHECK constraints at all, so the rebuild spells the
    table out rather than relying on reflection — a reflected rebuild would have silently dropped
    every check.
  - **The add path had one default status for every domain.** It asks the domain now: a book is
    added `read`, a record `owned`.
  - **A track carries two numbers.** `position` is the sequential index and `number` is what is
    printed — `A1`, `A2` on a record. They are different strings in the same response, and the
    printed one is what a person reads off the sleeve, so it is what is stored.
  - **The walkthrough found two defects the suite could not**, which is the gate working as intended:
    a status two domains share was counted once and shown in both rows, and `digital` — declared by
    books and records both — appeared twice in the format filter under one value. `status_counts` is
    now split by item type beside the whole-library total, and the format list is flat.

- **Deliberately not built.** A `rows` field is not editable by hand: correcting a tracklist is a
  table editor, and `Refresh from provider` is the repair path until somebody needs more. Sprint 028
  inherits the `rows` field type as one more thing its conformance suite must describe.
- **Consequences.** A third domain now declares its statuses, its default, its formats, its entry
  fields and its panel copy, and no screen branches on which domain it is holding. `EntryStatus` and
  `EntryFormat` remain published unions for the parameters that legitimately span domains — a filter,
  a facet — and a test pins them to the registry so a domain cannot add a value the API surface
  forgets.

## DEC-061 — Sprint 026 ran on the Sprint 025 branch

- **Date:** 2026-08-15
- **Status:** accepted
- **Amends:** DEC-053 for this sprint only.
- **Context:** DEC-053 says a domain-line sprint cuts its branch from `main`. Sprint 025 closed on
  `sprint-025-albums` and has not been merged, because merging is the owner's decision and the branch
  exists precisely so that it is one.
- **Decision.** The owner directed Sprint 026 to run on `sprint-025-albums`. Cutting from `main`
  would have produced a branch with no album domain in it, and every acceptance criterion of this
  sprint is about albums.
- **Consequences.** Both sprints' work is on one branch and still unpushed. The merge decision is
  unchanged and still the owner's; it now covers 025 and 026 together.

## DEC-062 — The library selects a domain, and the tab remembers

- **Date:** 2026-08-15
- **Status:** accepted
- **Answers:** the question Sprint 027 was told to put to the owner rather than settle silently,
  plus the facet rule the build found underneath it.
- **Context:** Sprint 025 left `GET /api/entries` with no `type` filter on purpose — its AC4 asked
  only that a mixed library paginate correctly, which it does. The owner then reported the other
  half from the running application: *"the main library should really have a tab selector to choose
  between domains, there is no point in showing books and albums combined."* What needed deciding
  was only the default: every domain, or the last one used.
- **Decision.** **The last domain used**, remembered in `localStorage` under
  `akasha.library.domain` beside the existing grid/table preference, starting at "All" until a tab
  is chosen. The value is written into the URL once on mount and read from the URL from then on, so
  the choice is an ordinary filter for every purpose after that: a reload, a return from a detail
  page and a shared link all behave without the preference being consulted again, and an explicit
  `?type=` beats what was remembered.

  "All" was the alternative and it is not wrong — it keeps today's behaviour and makes the tabs
  optional. It was rejected because a person with four hundred books and thirty records is
  overwhelmingly in one of them at a time, and the cost of the wrong default is one click on every
  visit forever.

  **The strip renders from `GET /api/item-types`**, like every other domain-shaped control since
  DEC-052 seam 3, and only when the build has more than one domain — a book-only build has no tab
  strip rather than a strip with one tab.

  **The chips keep DEC-060 judgement 1.** Under "All" they stay one row per domain under that
  domain's name. With a tab chosen there is one row and the tab already carries the name, so the
  heading comes off rather than being said twice. Switching tabs drops statuses the new domain has
  no vocabulary for, which would otherwise leave the list filtered by a value none of the visible
  chips can clear — a library that reads as empty for no reason the screen can explain.

- **The facets treat `type` asymmetrically, and that is deliberate.** The existing rule is that each
  facet clears its own dimension. `type` is not one dimension:

  - `status_counts` and `status_counts_by_type` **clear** it. `status_counts` is the whole-library
    total the inbox badge counts, and narrowing it would make the badge disagree with `/triage`,
    which is domain-agnostic. `status_counts_by_type` is already split by type (DEC-060), so
    clearing the filter is what lets a tab that is *not* selected still have a live count.
  - `format_counts` **applies** it. That selector sits under the tab, so offering "Physical 312"
    while the library is showing records is an answer to a question nobody asked.

- **Consequences.** `type` is in `_filter_key`, so a cursor cut under one domain is refused under
  another instead of silently skipping or repeating a page. `ItemTypeName` joins `EntryStatus` and
  `EntryFormat` as a published union spelled out for the type checker and pinned to the registry by
  a test. Sprint 028's conformance suite gains one more thing a domain gets for free by existing:
  a tab, its chips, its formats and its counts.

## DEC-063 — Sprint 027 ran on the Sprint 025 branch

- **Date:** 2026-08-15
- **Status:** accepted
- **Amends:** DEC-053 for this sprint, as DEC-061 did for Sprint 026.
- **Context:** DEC-053 says a domain-line sprint cuts its branch from `main`. Sprints 025 and 026
  both closed on `sprint-025-albums` and neither has been merged, because merging is the owner's
  decision and the branch exists precisely so that it is one.
- **Decision.** The owner directed Sprint 027 to run on `sprint-025-albums`. A branch cut from
  `main` would have no album domain in it, and a domain tab strip over one domain is not this
  sprint.
- **Consequences.** Three sprints' work is on one branch and still unpushed. The merge decision is
  unchanged and still the owner's; it now covers 025, 026 and 027 together.

## DEC-064 — The add screen shows what is already known, and asks before fetching more

- **Date:** 2026-08-15
- **Status:** accepted
- **Extends:** DEC-045 (the provider quota and the rule that search is recorded but never blocked),
  DEC-052 seam 3 (a screen renders from the field spec), DEC-059 (a format is not a shelf).
- **Context:** the owner tried the closed Sprint 027 and reported the add flow: *"the search page,
  after you clicked on an item, feels empty. If we have the data, we could show the metadata there
  before confirming."* The question in it — *do we already have the data?* — was measured before
  anything was designed, and the answer is **partly**, which is what shaped the decision.

  A `SearchCandidate` carries `title`, `subtitle`, `creators`, `credit`, `year`, `original_year`,
  `language`, `identifiers` and `cover_url`. The confirm screen rendered the cover, the title and
  the credit, and discarded the rest. It does **not** carry `publisher`, `page_count`, `description`
  or `subjects` for a book, or `label`, `catalog_number`, `format` or `tracklist` for a record:
  those come from `provider.fetch`, which ran only at add time. There is no provider response cache
  — Sprint 005's "cached add" caches the resulting *item*, not the HTTP call — so previewing them
  costs one live request per candidate clicked.

- **Decision.** **Free data immediately, the full record on demand.**

  Everything the search already returned renders the instant a result is clicked, at no cost and
  with nothing to wait for, from the domain's field spec rather than a book-shaped list.
  `GET /api/search/preview` fetches one candidate's complete payload, writes nothing, and is reached
  by a button rather than an effect — because it is a request, and a reader comparing four editions
  should spend four requests only if they meant to.

  Costed against the alternatives:

  | | Shape | For | Against | Verdict |
  |---|---|---|---|---|
  | **A** | Free data only | No endpoint, no cost, no waiting | The description and the tracklist stay invisible until the thing is already in the library, which is the half of the complaint that motivated it | Rejected — solves the symptom, not the ask |
  | **B** | Fetch the full record on every click | Richest possible screen | Browsing a result list spends a request per click against a rate-limited free API; MusicBrainz adds 1.1 s of pacing to each | Rejected — makes browsing expensive |
  | **C** | Free data now, full record on a button | Instant by default, complete when asked, and the cost is visible and chosen | One more endpoint and one more piece of state | **Accepted** |

  **The preview follows search's quota rule, not enrichment's.** The spend is recorded and never
  blocked, because somebody is waiting for this one — the same reasoning DEC-045 applied to search:
  the last request of a day belongs to a person, not to background work that can defer to tomorrow.

- **And the opinion is set while adding.** `POST /api/entries` accepts `notes`, `formats`,
  `date_started`, `date_finished` and `reread_count`, each validated against the item's own domain
  and refused with a 422 naming it — the same rule `PATCH` follows (DEC-060 judgement 3), applied on
  the way in and **before the write**, so a refusal leaves no half-added row. Adding a book you just
  finished was previously an add followed immediately by an edit.

- **One control per concept, shared across screens.** The create-on-type shelf control moved to
  `features/shelves` and is used by the detail page and the add screen. Formats became one closed
  multi-select control used by the add screen and the opinion dialog, replacing two checkbox rows.
  **The two controls stay distinct, and that is DEC-059 and not styling**: the shelf control has a
  text input and offers to create, because a shelf is a tier you invent; the format control has
  neither, because a format is a closed vocabulary the domain declares. A single widget doing both
  would erase the distinction the owner drew.

- **Consequences.** The library and the add screen now render every domain-shaped thing from
  `GET /api/item-types`, so Sprint 028's conformance suite covers one more surface a domain gets for
  free. Two defects the suite could not see were found by the walkthrough and the axe gate
  respectively: a fact declared both as a candidate column and as a domain field was named twice,
  and the first pass's domain strip was a Radix `Tabs` whose triggers pointed `aria-controls` at a
  panel that was never rendered — it is a radio group now, the pattern the add screen already used
  for the same choice.

## DEC-065 — One search bar on `/`, and the library always names a domain

- **Date:** 2026-08-15
- **Status:** accepted by the owner
- **Accepts:** `docs/unified-search-proposal.md`, with two amendments the owner made to it.
- **Context:** after Sprint 027's second pass the owner asked for the main page to carry both
  jobs — *"1 large searchbar up top for both,"* with the domain selector to its left and an **Add**
  button to its right, a local search that consults no provider when it hits, and a web search
  below when it misses. The proposal measured the two searches before designing anything, because
  they are not the same kind of thing: one is SQL and free, the other is up to 5 s per provider and
  counted against a daily budget of 900 (DEC-045).

- **Decision.** The proposal is accepted, with the owner's amendments:

  1. **A web search fires on settled-and-empty, or on the button.** Not on every local miss. The
     literal rule fires once per keystroke while typing any title not already owned — which is
     every add — so `Kind of Blue` would cost twelve provider searches at a 5 s timeout each, and a
     session of adding would breach the free tier that DEC-044 already measured and rejected for
     enrichment. A search fires when the query has been still for ~800 ms, is at least 3 characters,
     and returned **zero** library rows, and never twice for the same string. **Add** forces one at
     any time.

  2. **"All" is removed as a filter** — *the owner's amendment, overriding the proposal's
     recommendation.* The proposal kept "All" and had the **Add** button ask which domain to search;
     the owner chose to drop it instead. The tab strip now always names exactly one domain, which is
     what makes one bar able to mean both things at once: the same choice picks the rows you filter
     and the providers you would search, with nothing left to disambiguate at the moment of pressing
     a button.

     This overrides DEC-062's "starting at All until one is picked". The remembered-domain rule
     survives unchanged; what changes is that the fallback when nothing is remembered is the first
     declared domain rather than everything. The whole-library view is not lost — `/triage` and the
     export both still span domains, and `status_counts_by_type` still carries a live count for the
     tab you are not on, which is now the only way to see that the other domain has anything.

  3. **The confirm step is a dialog over `/`** — accepted *"as long as we don't lose any
     functionality"*, which the sprint turns into an enumerated acceptance criterion rather than an
     intention. Eleven behaviours are listed there, and the near-match confirmation and the manual
     fallback are the two most likely to be dropped by accident.

- **`/add` survives** as the manual-entry route and a deep-link target. It is lazy-loaded, so
  keeping it costs nothing in the bundle, and moving manual entry inline as well is what would push
  this past one sprint.

- **Consequences.** This is **Sprint 029, and it runs after Sprint 028** — reversing the proposal's
  recommendation, which was written before the constraint was checked. The proposal argued this
  should go first so the domain contract describes a settled shell, and treated the sprint numbers
  as identities rather than a schedule. They are not: `scripts/validate_project.py` requires the
  active sprint to be `len(completed) + 1`, so in this project the number *is* the order. Running
  this first would therefore require renumbering, and renumbering would rewrite forward references
  inside closed sprints' Outcome sections and inside accepted decisions (DEC-052, DEC-058, DEC-060,
  DEC-062, DEC-064) — which `AGENTS.md` forbids and which is a much larger cost than the one being
  avoided.

  **What the original concern is worth, now that it is priced:** 028's conformance suite and its
  account of the backend registry are untouched by this sprint. Only its description of what a
  *screen* renders is exposed, and that is one section, which 029's close amends. 028's file now
  says so. `FINAL_SPRINT` moves from 29 to 30 and per-domain imports becomes Sprint 030.

## DEC-066 — Sprint 028's baseline, re-derived: a domain is not yet a unit of code

- **Date:** 2026-08-15
- **Status:** accepted
- **Context:** Sprint 028's file carried a baseline written at Sprint 027's close and marked
  *"Re-derive at activation."* The owner asked for the next sprint to be planned with the state of
  the repository stated explicitly against the epic goal — **each domain independent enough that
  separate teams can add one, with its own imports and features, without breaking another** — so it
  was re-derived from the code on 2026-08-15 rather than from the previous sprint's summary.
- **What the measurement found.** The registry half of DEC-052 is real and holds: `Domain` carries
  the whole per-domain contract, `GET /api/item-types` publishes it, every screen renders from it,
  writes validate against the item's own domain, and there is no `type === "album"` branch anywhere.
  `backend/tests/test_domain.py:140-179` already parametrizes over `DOMAINS`, so part of the
  conformance suite exists.

  **What does not hold is that a domain is a unit of code.** Adding a third one edits nine files that
  books and albums live in — `domain/domains.py` (fields, statuses, formats, the registry and all
  three published unions), `domain/providers.py`, `main.py` (including a `provider_health` that names
  three providers as literals), `config.py`, `infrastructure/covers.py`, a migration,
  `frontend/src/api/library.ts`, `features/library/labels.ts`, and three surviving
  `itemType === "book"` branches in `pages/AddPage.tsx`. Two are worse than a file to edit:

  - **`entries.ck_entries_status` is frozen.** `alembic/versions/0013_entry_formats.py:66` renders
    the CHECK from `ALL_STATUSES` at migration-write time, so a domain declaring a status books and
    albums lack passes `validate_status` and is refused by SQLite. **A new domain currently requires
    a schema migration on a shared table** — the sharpest contradiction of the epic goal in the
    repository.
  - **Enrichment is book-shaped below its seam.** `_backfillable_items` filters on `domain.enriches`
    correctly, but its SQL joins `item_identifiers.kind = 'isbn'` and `_fetch` takes an ISBN against
    a hardcoded `PROVIDER_ORDER`. Albums declare `enriches=False`, so the second domain never tested
    it.

  Also recorded rather than rediscovered: the manual add path is a book form bound to
  `DEFAULT_DOMAIN`; `cover_candidates` takes an Open Library provider as an argument, which is why
  the cover chooser offers itself on an album and can only say no; the detail route is `/books/:id`
  for every domain; and the import layer is book-only end to end, which is Sprint 030's outcome.
- **Decision.** Three answers from the owner, so the executing agent does not re-litigate them:

  1. **Sprint 028 runs on `sprint-025-albums`**, continuing DEC-053, DEC-061 and DEC-063. Sprints
     025–027 stay unmerged; the contract is written against a codebase that holds two domains.
  2. **The CHECK-constraint blocker is a Phase A finding with costed alternatives**, decided at the
     gate — not pre-authorized Phase B work. The gate stays a gate.
  3. **The contract prescribes a per-domain code home, and Phase B moves books and albums into it.**
     A contract that only documented today's shared-file layout would describe the very thing the
     epic exists to remove, and one that prescribed a layout no domain demonstrates would not be
     evidence of anything.
- **Consequences.** Sprint 028's baseline, deliverables and acceptance criteria are rewritten around
  this: the conformance suite gains a check that every declared value is accepted by *the database*
  and not only by the API, and a check that the frontend's hand-mirrored unions agree with the
  registry; the measurement is delivered as a costed table of alternatives per finding rather than
  one recommended path; and the IGDB paper walk additionally answers which shared files two parallel
  domain teams would contend over, which is the falsifiable form of "developed in parallel". The
  per-domain package move is named as the largest thing in the sprint and as the slice to hand
  forward with the contract written, rather than to rush. Two documentation inconsistencies found
  while planning are repaired under `AGENTS.md` §1: `ROADMAP.md` still headed the per-domain-imports
  contract "Sprint 029" after DEC-065 renumbered it to 030, and `HANDOFF.md`'s "no `type === "album"`
  branch anywhere" was true of albums and silent about books.

## DEC-067 — What the conformance suite measured, and what each coupling costs to remove

- **Date:** 2026-08-15
- **Status:** accepted (the measurement); the Phase B selection below awaits the owner's go-ahead
- **Context:** Sprint 028 Phase A deliverable 3. DEC-066 listed what a third domain must edit; this
  prices each one. Every row is a fork with its options and costs rather than a single recommended
  path, because a gate whose measurement recommends work in every row is not a gate. **Four of the
  ten rows recommend doing nothing**, and that is the honest outcome rather than a smaller sprint.
- **What the suite proved, before any of this was costed.** The conformance suite
  (`backend/tests/test_domain_conformance.py`) is parametrized over `DOMAINS` and splits its checks
  in two. A fixture domain that is registered nowhere satisfies **every** check about a domain's own
  consistency — its vocabularies, fields, identity rule and recognizer. Give it a status of its own
  and it fails both checks about whether the core can host it. **That is the finding in one
  sentence: a domain can be written against the contract today, and cannot be added without editing
  the core.**

  The suite also found a live defect on its first run, which is repaired in this sprint rather than
  costed: `urlsplit` raises on a malformed authority (`http://[`), `resolve_input` asks each
  registered domain in turn, and the first recognizer to raise **denied every domain after it its
  turn**. One domain breaking another's add box is precisely the failure mode this epic exists to
  prevent, and it was reachable from the add box by pasting a typo. Both recognizers now parse
  through a shared `split_url`, and the loop isolates a raising recognizer regardless.

| # | Coupling | Options | Cost | Recommendation |
|---|---|---|---|---|
| 1 | `entries.ck_entries_status` is a list frozen at migration-write time, so a new domain's status passes the API and is refused by SQLite | (a) migration per domain; (b) drop the CHECK and let `validate_status` be the authority; (c) a `domain_statuses` table and a trigger | (a) a batch rebuild of `entries` per domain **and an alembic head collision between two teams**; (b) one batch rebuild, once, and the loss of a defence-in-depth the application is the only writer behind; (c) makes the registry partly data, contradicting "the registry is code" | **(b)**, as the one schema change that removes a per-domain migration forever. Owner's call at the gate |
| 2 | The published unions `EntryStatus` / `EntryFormat` / `ItemTypeName` are spelled out by hand | (a) keep; (b) build the `StrEnum` from the registry; (c) generate the source | (a) three lines per domain, type-safe, and a test fails when it is forgotten; (b) opaque to mypy and loses the literal types in the API models — the reason it was written this way; (c) a build step for three lines | **(a) keep. Do nothing.** The coupling is real and cheaper than any of its removals |
| 3 | Enrichment is keyed on ISBN below the `enriches` flag (`_backfillable_items`, `_fetch`, `PROVIDER_ORDER`) | (a) leave and document what the flag means; (b) declare an enrichment key and an incompleteness rule per domain; (c) move enrichment behind the adapter | (a) nothing now; a domain wanting enrichment discovers the gap late; (b) rewrite of one SQL query and the fetch loop, ~half a sprint; (c) reaches the job payload and the ledger | **(a) for now.** No domain needs it: albums declare `enriches=False`, and a game record arrives complete in one query. Build (b) when a domain actually asks |
| 4 | The cover host allowlist is central | (a) keep; (b) let a domain declare its own hosts | (a) one line per domain; (b) a domain could widen the allowlist from its own package, which is what an allowlist exists to prevent | **(a) keep. Do nothing.** This one is central on purpose |
| 5 | `provider_health` names `openlibrary` / `musicbrainz` / `googlebooks` as literals | (a) derive the rows from the registered providers; (b) leave | (a) ~15 lines, and the response gains a row per provider automatically; (b) a domain's provider is invisible to the health endpoint until someone remembers | **(a)**, in Phase B. Cheap, and shared infrastructure should not name a provider |
| 6 | The manual add path is a book form bound to `DEFAULT_DOMAIN` | (a) leave; (b) render it from the field spec | (a) a new domain has no manual path — which matches the product decision that manual entry is a book fallback; (b) medium frontend work on the exact screen Sprint 029 rebuilds | **(a) now, named for Sprint 029.** Building it here would be built twice |
| 7 | The cover chooser offers itself on an album and can only say no (`cover_candidates` takes an Open Library provider) | (a) hide it unless the domain declares it can choose covers; (b) a per-domain cover-candidate strategy; (c) leave a fourth time | (a) one declaration plus one condition, and it is user-visible so it re-arms the walkthrough; (b) a seam nothing needs yet; (c) the reader keeps meeting a control that cannot work | **(a)**, in Phase B. The sprint required this be decided rather than deferred again |
| 8 | The detail route is `/books/:id` for every domain | (a) leave; (b) `/items/:id` with a redirect | (a) a cosmetically wrong URL; (b) every `navigate` call and seven e2e specs, on the screens 029 rebuilds | **(a) leave. Do nothing** — and revisit inside 029, which is already there |
| 9 | The import layer is book-only end to end | — | Sprint 030's whole outcome | Named, not moved. Out of scope by the sprint's own boundary |
| 10 | The frontend fallback vocabulary in `labels.ts` is the book vocabulary | (a) keep; (b) drop the fallback | (a) a row from an unknown domain renders under a book's label if the registry fetch fails; (b) an unreadable row instead | **(a) keep. Do nothing.** The registry must never be the reason a row is unreadable |

- **Decision — what Phase B should be, if it runs.** In this order, each its own commit:

  1. **The per-domain packages** the contract now prescribes (technical spec 6.6), with books and
     albums moved into them. This is the row that is not in the table, because it is not a coupling
     to remove but the layout that makes the remaining ones visible. It is also the largest piece,
     and the one to hand forward with the contract already written if it runs long.
  2. **`provider_health` derived from the registry** (row 5).
  3. **The cover chooser declared per domain** (row 7), which re-arms the walkthrough gate.
  4. **Dropping `ck_entries_status`** (row 1) — separately, because it is the only schema change and
     the only irreversible one.

- **Consequences.** Rows 2, 4, 8 and 10 are recorded as **deliberate couplings that stay**, so a
  later reader finds a decision rather than an oversight. Row 3 is the one place the "second domain
  never tested this" risk is real, and it is left with its trigger named: the first domain that
  wants background enrichment on a non-ISBN key pays for (b) then, with a real case to design
  against instead of a hypothetical one.

## DEC-068 — IGDB on paper: no seventh seam, one new kind of infrastructure, six files two teams would fight over

- **Date:** 2026-08-15
- **Status:** accepted
- **Context:** Sprint 028 Phase A deliverable 4, and where DEC-052's falsifiable prediction —
  *"games need no seam albums did not"* — is finally tested. A paper walk against the conformance
  suite is cheaper and more honest than a third bespoke sprint, which is the whole reason the plan
  stops at a contract rather than at a third domain (DEC-058).
- **What this is and is not.** **Reasoned from IGDB's published API, not measured against it.** DEC-052
  earned its conclusions from live probes on 2026-08-14; this one has not, and must not be read as
  though it had. Every claim below that a real integration would depend on is marked as one to
  verify first.
- **Seam by seam, against the contract in technical spec 6.6.**

  1. **Creators.** IGDB attributes a game to companies through `involved_companies`, flagged
     developer / publisher / porting / supporting. A company is an organisation and its name never
     inverts, so the adapter supplies `creator_sort` unchanged and the `creator_sort_name` heuristic
     never runs — **exactly the rule MusicBrainz's `Group` already exercises** (DEC-051, DEC-052
     seam 1). No new seam. *Verify:* that a developer is reliably distinguishable from a publisher,
     because which one is "the creator" is a product decision, not an API one.
  2. **Identity.** With one provider there is nothing to merge across, so `identity_key` returns
     `None` — albums' answer, and a complete one. No new seam. *Verify:* if a second games provider
     is ever added, whether `external_games` (Steam appids and the like) is unique enough to group
     on; a barcode was not, which is the precedent for not assuming.
  3. **Metadata.** Platforms and genres are lists of text, summary is long text, the release year is
     a number, developer and publisher are text. Every one fits an existing `FieldSpec`; the only
     candidate for the `rows` type the tracklist introduced is per-platform release dates, and
     nothing requires it. No new seam.
  4. **Covers.** Art is served from `images.igdb.com` at a template-sized path. **One allowlist
     entry** — DEC-067 row 4 keeps that central deliberately. *Verify:* whether the URL arrives
     protocol-relative (`//images.igdb.com/...`), which the seam-4 https upgrade already handles but
     which decides whether the adapter normalises it or the pipeline does.
  5. **Statuses and formats.** Games plainly want a vocabulary of their own — `playing` and a
     backlog have no book or album equivalent — which is seam 5b working exactly as designed at the
     domain level, and which lands squarely on **DEC-067 rows 1 and 2**: the published unions and
     the frozen CHECK constraint. No new seam; two known couplings, and this is the domain that
     makes row 1 unavoidable rather than theoretical.
  6. **Enrichment and add-by-URL.** One IGDB query returns everything the field list asks for, so
     `enriches=False` — albums' answer again, and the reason DEC-067 row 3 can wait. The recognizer
     is an `igdb.com/games/{slug}` URL resolving through the adapter's own slug lookup. No new seam.

- **Decision — the prediction holds, with one qualification.** Games need **no seventh seam**. What
  they need that no domain has needed is **authentication with a lifetime**: IGDB requires Twitch
  client credentials exchanged for a bearer token that expires and must be refreshed, where every
  provider so far has needed at most a static key or a descriptive User-Agent. That is not a seam —
  it fits inside the adapter, which already owns its own rate limit and headers — but it is the
  first adapter to hold **mutable state and a secret pair**, and it adds a `config.py` entry, which
  DEC-067 already counts as a coupling. *Verify before building:* the token lifetime and the refresh
  failure mode, and whether a 401 mid-import is retryable without losing the batch.
- **What two parallel domain teams would collide over.** The epic's actual question, answered by
  listing the files an IGDB team and a `spotify → music` team would both edit today:
  `domain/domains.py`, the three published unions inside it, `domain/providers.py`, `main.py`,
  `config.py`, `infrastructure/covers.py` and `frontend/src/api/library.ts` — **six files and one
  block of enums.**

  **The sharp one is not a file, it is the migration.** Both teams need a status of their own, both
  therefore write a migration widening `ck_entries_status`, and both point `down_revision` at the
  same head. Whoever merges second rebases a schema change — the one class of conflict that cannot
  be resolved by reading two diffs side by side. **That single fact is the strongest argument for
  DEC-067 row 1(b)**, and it is worth more than the file count: after it, two domain teams contend
  over declarations, which merge, rather than over a schema, which does not.
- **Consequences.** DEC-052's prediction is recorded as **held**, tested the way DEC-058 said it
  would be. Games remain an unnumbered future epic. Nothing here authorises building one, and the
  verification list above is what that epic starts from rather than repeats.

## DEC-069 — Phase B ran in full, and the move found three things the measurement could not

- **Date:** 2026-08-15
- **Status:** accepted
- **Context:** DEC-067 costed ten couplings and recommended four Phase B items. The owner authorized
  **all four** at the gate. This records what changed against that plan and what the work itself
  turned up, because DEC-067 was written from reading the code and Phase B was written by moving it.
- **Decision — one deliberate departure from DEC-067's ordering.** It put the per-domain packages
  first, on the reasoning that the layout makes the remaining couplings visible. They ran **last**
  instead, smallest first, so the largest piece was the tail that could be handed forward intact if
  it ran long — which the sprint's own risk note provides for and which costs nothing, since none of
  the three smaller items depended on the layout. It did not run long.
- **What the move found that reading could not.** All three are repaired in the same sprint, and all
  three are the same species: **a shared thing quietly shaped like books.**

  1. **`Domain`'s defaults were the book vocabulary.** `statuses`, `default_status`, `entry_fields`,
     `formats` and `entry_panel_label` all defaulted to books' answers, so a third domain that
     omitted one would inherit `read`/`reading`/`to_read` or "Your reading data" **silently** — the
     precise failure the whole seam model exists to prevent, sitting in the shared type the model is
     built on. It was invisible while books lived in the same file as the type. All five are required
     now, and `chooses_covers` defaults to `False` rather than `True` on the same principle: a domain
     that has not thought about covers offers no chooser.
  2. **Both status migrations read the live registry.** `0013` rendered its CHECK from
     `ALL_STATUSES` *when the migration ran*, so two installs applying the same revision a month
     apart could end up with different constraints, and a migration's meaning changed whenever a
     domain was added. A migration is history and must not read live code; both lists are frozen
     literals now. This is a second, subtler form of the same coupling DEC-067 row 1 removed.
  3. **The container smoke script imported an adapter by module path.** `make smoke-container` failed
     on it after the move — no unit test, type check or e2e run could have, because the import
     happens inside the running image. The DEC-025 gate earning its place again.
- **Consequences.** Two couplings remain by decision (DEC-067 rows 2 and 4): the hand-spelled
  published unions and the central cover-host allowlist. **A third domain now costs: its own package,
  one entry in `DOMAINS`, its provider wired in the lifespan, three enum lines, one allowlist line if
  its art is hosted somewhere new, and configuration if its provider needs credentials. No migration,
  and no edit to another domain's files.** That is what DEC-058 asked the two gate sprints to
  deliver, and it is the state Sprint 029 and Sprint 030 inherit.

  Sprint 030 is unaffected in scope but its ground is better: `domains/book/goodreads.py` and
  `domains/book/calibre.py` already sit in the domain they serve, so the boundary that sprint draws
  is between the shared ledger and importers that already live in the right place.

## DEC-070 — Sprint 028 reopened for the documentation pass, and the guide was proved by following it

- **Date:** 2026-08-15
- **Status:** accepted
- **Context:** Sprint 028 closed having built the contract, the conformance suite and the per-domain
  packages. The owner then asked, before considering it closed, that **the documentation convey the
  new structure**: a contributor-facing guide to adding a module, old documents removed or updated,
  diagrams welcome, and a general cleanup. The sprint was reopened rather than the work scheduled —
  the same precedent Sprint 020 set for its Phase B and Sprint 027 for its add flow. A contract
  nobody can find is not a contract.
- **Decision.** Three new documents, and a rule for the old ones.

  - **`docs/guides/adding-a-domain.md`** — the practical counterpart to technical spec 6.6. Three
    diagrams (where a domain plugs into the layers, where its one declaration travels, and the nine
    points a single add consults it), the whole job as a nine-row table, the step-by-step against
    `domains/album/` as the worked example, what a domain gets for free, what it may never touch, the
    two things that are not solved yet, and the IGDB verdict as a worked plan.
  - **`CONTRIBUTING.md`** — the human entry point, which the repository did not have. Setup, the
    gates and why each exists, the rules that are not style preferences, and a pointer to the domain
    guide above everything else. `AGENTS.md` still governs agent sessions and says so.
  - **`docs/README.md`** — the documentation map. **Every document is labelled `canonical`,
    `historical` or `proposal`**, which is the rule that replaces deleting things: *a historical
    document is not wrong, it is dated.* A path inside a closed sprint describes the repository on
    the day it closed and is not an instruction. Nothing was deleted; four documents gained status
    headers saying what they are and what supersedes them.

- **The guide was verified by following it**, which is the documentation equivalent of the
  walkthrough gate. A throwaway `game` domain — its own package, three fields, a status vocabulary
  containing `playing` and `finished`, its own formats and identity strategy — was built from the
  guide alone and registered. **The conformance suite and all 480 backend tests passed, with no
  migration**, which is exactly what DEC-067 row 1 bought. The only gate that failed for a legitimate
  reason was the OpenAPI drift check, which is a documented step.

  **Three things broke that the guide had not predicted, and each was repaired rather than written
  down as a gotcha** — a step a contributor must know about is a step the design failed to remove:

  1. A conformance test used `playing` as its example of "a status no registered domain declares".
     A real games domain would have broken its premise rather than its point; it derives an unclaimed
     value now.
  2. `test_item_types.py` asserted the published set was exactly `{"book", "album"}` — a closed-world
     assertion a third domain fails. It asserts against `DOMAINS` now. (Four similar-looking
     assertions elsewhere were checked and left: they assert over rows the test itself seeded, which
     is correct.)
  3. `statusLabels` in the frontend was an exhaustive `Record<EntryStatus, string>`, so a new status
     was a **TypeScript error** until somebody wrote a fallback label. It is `Partial` now and the
     lookup falls back to the stored value, which is legible. DEC-067 row 10 keeps the fallback
     table; what changes is that a domain no longer has to edit it.

- **Consequences.** The registration cost in DEC-069 is unchanged and now written where a contributor
  will find it. Two documentation defects from earlier in this sprint were also repaired: technical
  spec 6.6 still said the per-domain layout was "not yet inhabited" — a Phase B edit lost to a second
  write in the same script — and product spec section 9 still said the registry would be extracted
  when a second domain existed and that games and series were Sprints 027 and 028, both superseded by
  DEC-058. `AGENTS.md` gains the domain boundary as a non-negotiable invariant and `docs/README.md`
  as required reading.

## DEC-071 — Depth is one level and provider-shaped; copy neutrality lands in 029; the music release is not gated on a third domain

- **Date:** 2026-08-15
- **Status:** accepted
- **Supersedes:** section 6 of `docs/domain-expansion-assessment.md` where the two differ. The
  assessment recommended deciding depth *before* a third domain and folding the chrome copy into
  Sprint 029. The owner accepted the second, resequenced the first, and rejected a premise the
  assessment had left implicit.
- **Context:** the Sprint 028 assessment found one item that could force a redesign — an entry is
  flat, which blocks television, anime, comics and podcasts — and separated it from six additive
  comfort gaps. The owner answered the same day.
- **Decision.**

  **1. Copy neutrality is Sprint 029's sixth deliverable.** Eighteen user-visible strings across
  eight files say "book" on screens that hold albums. Sprint 029 rebuilds most of those screens, so
  doing it anywhere else means doing it twice. The rule is written into that sprint: copy that names
  one domain comes from that domain's `label`, or is neutral. The `/books/:entryId` route stays out
  of scope (DEC-067 row 8, reaffirmed).

  **2. Entry depth is Sprint 030, Phase A only, and it runs after 029 rather than before it.** The
  assessment argued for deciding it first; the owner scheduled it second, which is the right call for
  a reason the assessment underweighted — 029 is already built and specified, and reordering settled
  work to answer an open question costs more than the question does.

  **The owner's hypothesis, which Phase A tests rather than assumes:**

  > Most scenarios can be modelled by going **one level down only** — series into seasons, books into
  > chapters if any, albums into songs, at most. The depth available is decided by **how the provider
  > stores it**: if a TV provider returns one entry per season, no finer grain exists to model. In
  > the other direction, items can be **grouped into sets** — the individual Harry Potter books as
  > one set — and a set may be useful for fields other than depth.

  **This hypothesis already has a precedent in the codebase, and Phase A must start from it.** A
  tracklist is one level down and is modelled as *metadata rows on the item, not as entities*
  (Sprint 026, DEC-057). It cost one `inc=recordings` parameter and nothing hangs off a track. So
  representation is solved. The open question is narrower and sharper than "hierarchy":

  **Does a child need state of its own?** A tracklist is read-only display. *"Watched through season
  3, episode 7"* is a status on a child. That difference is the entire sprint, and "flat, with a
  per-domain progress field" is a complete and correct Phase A outcome — on current evidence the
  likeliest one.

  Per-domain imports moves from Sprint 030 to **Sprint 031**; `FINAL_SPRINT` moves 30 → 31. This is
  the same renumbering DEC-065 performed on an unbuilt, unfiled sprint, for the same reason: the
  sprint has no file and no closed work depends on its number. The two forward references inside the
  closed Sprint 028 file are corrected *visibly*, naming the old number and this decision, rather
  than silently rewritten.

  **3. The music release is not gated on a third domain.** The assessment recommended building a real
  third domain to learn what two similar domains cannot teach, and the owner accepts the reasoning
  without accepting the gate: **a release waits for a feature, not for a validation exercise.** Music
  ships when music is ready. The only thing that would justify holding it is a specific feature going
  in with it — depth being the named example.

  This matters beyond scheduling, because it corrects a drift in how "gated" has been used. DEC-035
  and DEC-042 introduced gates to stop *building* something whose cost was unknown. Nothing in that
  pattern licenses withholding finished work until an unrelated experiment reports.

- **Consequences.** Plan revision **12**. The line is 029 → 030 (entry depth, gated) → 031
  (per-domain imports), and the project reaches `complete` at the end of 031. Sprint 029 gains a
  deliverable, an acceptance criterion and a test requirement. The assessment's options B and E
  (per-domain list mechanics; attachment level and per-domain caps) stay unscheduled and unbuilt,
  waiting for a real domain to ask — which is the assessment's own recommendation and DEC-052's
  standing rule against designing an abstraction from domains that agree with each other. Whether to
  merge and release the album work is a separate owner action, now unblocked by this entry.

## DEC-072 — The album work merges after Sprint 029, not before

- **Date:** 2026-08-15
- **Status:** accepted
- **Completes:** DEC-071, which unblocked the release without scheduling it.
- **Context:** DEC-071 established that a release waits for a feature rather than for a validation
  exercise, leaving the timing an owner action. The timing is now settled, and the reason is the
  sequencing consequence that entry named: Sprint 029 carries copy neutrality, so merging first would
  ship a music release whose screens say *Import books* and *Book added* over albums.
- **Decision.** **`sprint-025-albums` merges into `main` after Sprint 029 closes, and not before.**
  Music's first release is the one where the interface stops calling everything a book.

  Sprint 030 (entry depth) does **not** gate the merge. It is a Phase-A decision whose outcome may add
  a feature later; it is not a prerequisite for shipping what is already built and verified.
- **Consequences.** Sprints 025–029 all land on `main` in one merge. Two things must be done *with*
  that merge rather than after it, because both describe the product to a user:

  1. **`README.md`'s product copy** stops describing a book-only product. Its Development section
     already documents the domain structure; the feature copy was deliberately left book-only until
     albums could actually be run (DEC-066 era note in the handoff).
  2. **`docs/operations/release-notes-v1.2.md`**, following the v1 and v1.1 precedent.

  The branch keeps its DEC-053 property until then: a sprint may run on it, it ends clean, nothing is
  pushed, and merging remains a deliberate act rather than a side effect.
- **Carried out 2026-08-17.** `sprint-025-albums` merged into `main` as one `--no-ff` merge, with
  both required items in it: `README.md`'s feature copy and
  `docs/operations/release-notes-v1.2.md`. Tagged **`v1.2.0`**, and `main` pushed to `origin` — the
  first push in this repository since v1.1.0, and the end of the DEC-053 arrangement for this line
  of work.

## DEC-073 — What Sprint 029 actually built: the firing rule, results below, `/add` without a chooser, and no new `Domain` field

- **Date:** 2026-08-17
- **Status:** accepted
- **Implements:** DEC-065, whose two owner amendments this sprint carried out. **Amends:** DEC-062's
  "starting at All" (already overridden by DEC-065) and DEC-064's account of where the confirm step
  lives. **Narrows:** DEC-071's deliverable 6, which reserved the option of a new `Domain` field.
- **Context:** DEC-065 accepted a design; it did not decide four things that only building it could
  decide. Sprint 029 decided them, and they are recorded here rather than left in the code, because
  each one is a promise a later sprint could break without noticing.

- **1. The firing rule, as built and as verified.** A provider search fires when *all* of: the query
  has been still for ~800 ms **measured from the last keystroke**, it is at least three characters,
  the URL has caught up with the box, the library query has **succeeded and is not refetching**, and
  it returned **zero** rows — and never twice for the same string within a domain. **Add** overrides
  every clause and searches immediately, serving a repeat from cache.

  Three of those clauses are not in DEC-065's sentence and each is load-bearing:

  - **Measured from the last keystroke, not from the last condition becoming true.** The conditions
    settle at their own pace; timing the wait from whichever settled last means a slow library
    pushes the search out by however long the library took.
  - **Succeeded and not fetching.** Pending or errored is *"we do not know yet"*, not *"the library
    has nothing"*. Guessing there costs a request every time the library is slow.
  - **Strictly zero rows.** Searching `dune` while owning *Dune* returns one row and may well be
    somebody looking for *Dune Messiah* — but a threshold ("few enough rows") guesses on the
    reader's behalf, and the strict rule never does.

  **Verified by counting requests against live providers**, which is the acceptance criterion:
  a title in the library costs 0, one not in it costs exactly 1, the same string retyped costs 0,
  **Add** on a query with local hits costs 1, and a pasted ISBN takes `/api/search/resolve` instead.

- **2. Results render *below* the library, not above.** Deliverable 3 and the accepted proposal both
  say below; acceptance criterion 7 said *"with a web-results block above it"*. **Below shipped**,
  because the deliverable is the specification and the AC's phrase was incidental — and the choice
  is worth more than a tie-break. The library virtualizes against the **window**, so anything of
  variable height above it moves the `scrollMargin` every row measures itself against, which is
  precisely the Sprint 013 class of bug. Below means the offset never moves: the library's bounding
  box is unchanged when results appear, measured. The Sprint 013 bug is avoided **by construction
  rather than survived**, and a later sprint that moves the block above the list re-opens it.

- **3. `/add` lost its domain chooser rather than keeping a decorative one.** `LibraryService.add`
  types a manual item as `DEFAULT_DOMAIN.item_type` whatever the client sends (DEC-067 row 6). The
  old screen offered the choice anyway, so picking Records showed a record's statuses and fields and
  then wrote a book. **A control that cannot keep its promise is worse than its absence**, so the
  screen now names the one domain it actually writes. Giving manual entry a real domain needs an API
  change and stays unscheduled; this is the honest state until then, not the end state.

  The same reasoning settled the copy the sprint file left open. Books offered *"You can still enter
  this book manually"* on a failed provider search and albums offered *"Try again in a moment"* —
  one arm promising a recovery path the other withheld. **Manual entry is offered to every domain**,
  because the route exists and works for anyone; what it cannot yet do is honour the domain, and the
  neutral copy does not claim it can.

- **4. Deliverable 6 needed no new `Domain` field.** The sprint authorized one — a per-domain search
  placeholder, with the conformance check such a field requires — and it was not taken. One neutral
  placeholder naming title, creator, ISBN and link serves every domain, and the resolve path it
  advertises is domain-neutral anyway (a MusicBrainz URL resolves as an Open Library one does). So
  **the backend contract is untouched after all**, which is what the roadmap originally claimed for
  this sprint before DEC-071 added the deliverable, and the narrowing that entry forced can be
  narrowed back. Twenty-four strings across eleven files became registry labels or neutral copy;
  `N books` on a shelf became `N items`, because a shelf spans domains and always did.

  **The `Domain` field remains the right shape for the day a domain actually needs different copy.**
  This decision is that no domain needs it yet — not that per-domain copy is disallowed.

- **Consequences.**
  - Product spec section 7 now describes `/` as the screen you search and add from, and `/add` as
    manual entry; technical spec section 7.1 names the two searches and section 8 carries the firing
    rule, the two-regions rule and the focus rule for shortcuts.
  - **The quota rule is a counted test, permanently.** Any change to the firing conditions is
    re-verified by counting requests, not by feel.
  - `j`/`k` and the digit shortcuts address the surface that has focus: standing inside the results
    region, neither reaches the library.
  - A defect the walkthrough found is fixed and worth not re-introducing: a successful add from `/`
    must clear the query, because the web search only ran when the library had nothing, so closing
    the dialog onto that filtered view highlights a row nothing can see. The old flow got this free
    by navigating to an unfiltered `/`.

## DEC-074 — Sprint 029's second pass: five things the screen got wrong, and the two judgement calls in fixing them

- **Date:** 2026-08-17
- **Status:** accepted
- **Context:** the owner used what Sprint 029 built, against the real library, and found five
  defects in the small — four on the screens 029 rebuilt and one on the detail page. None is a
  regression from the sprint; three are things the sprint's own rebuild made newly visible, and two
  predate it. **Sprint 029 reopened for a second pass** rather than deferring them to a sprint that
  is about something else, on the precedent of Sprint 028's third pass (DEC-070).
- **Decision.** Five changes, all frontend, no API and no schema:

  1. **A `long_text` field spans both columns of the confirm step.** The split is on the field's
     declared type, the way the detail page already splits `inlineFields` from `blockFields` — not
     on the name "description", which no shared layer may know.
  2. **The search bar clears in one press.** The box, the URL's `q` and the web results go
     together; the successful-add path already did exactly this and both now call one function.
  3. **An empty result is not an empty library.**
  4. **The status filter is a control, not a row.**
  5. **Files is its own region on the detail page**, at the weight of *Edit opinion*.

- **Two judgement calls a later sprint could otherwise reverse blind:**

  **The status counts moved inside the panel.** The chips showed every status's count at all times,
  which is real information the dropdown hides behind a click. The row was still the wrong trade:
  it was a whole row of chrome, above the library, for the fourth of four filters — and for a
  vocabulary the domain tab already names. The counts are in the panel rather than dropped, and the
  trigger names the current selection, so what is *chosen* is still readable without opening it.
  **If the counts turn out to be read constantly, the answer is to surface them in the trigger, not
  to bring the row back.**

  **The empty state is suppressed during an active query, not deleted.** "Your library is waiting"
  is correct and worth its screen for somebody with no library. Shown to somebody mid-search it is
  two hundred pixels of encouragement between the bar and the results that the miss is about to
  produce — and a miss is the *ordinary* path, since settled-and-empty only reaches a provider when
  the library came back with nothing (DEC-073). So the tall state is kept for the empty library and
  replaced, for an active query, by one line naming the string that missed. **One line rather than
  nothing** is deliberate: the settle rule waits ~800 ms before searching, and a page that goes
  blank in that gap reads as broken.

- **Consequences.**
  - Product spec section 7 describes four filters in one row, the clear control, the two silences
    and Files as its own region.
  - `StatusFilter` is the second control built on the `FormatPicker` shape — popover, checkmark
    column, list stays open. **The two must keep behaving identically**; a third multi-select on
    this page should copy them rather than invent a third interaction.
  - The `Attachments` component no longer owns its frame: the page wraps it in the labelled region.
    A future screen hosting it supplies its own.
- **A sixth item, found reviewing the five, repaired after the close** — recorded here rather than
  by reopening the sprint a third time, because `WORKFLOW.md` has no `completed → in_progress`
  transition and the repair is small, closed and tested. **The shell's *Library* link, pressed while
  already on the library, produced a permanent *Loading your library…*.** It points at `/` with no
  query, so it strips `type` from the URL; deliverable 2 made every list request name a domain, and
  the restore that supplies one ran **once per mount**. Every other way of reaching the library
  remounts the page, so the one that does not was the one nothing covered.

  **The rule this establishes: the domain restore answers to the URL, not to the mount.** A URL
  without a `type` is precisely the state the restore exists to fix, whenever it occurs — and
  writing the value back is what stops it repeating, so the effect is its own guard and needs no
  other. A future control that clears the domain from the URL will be caught by the same effect
  rather than needing its own.

  Held at two layers on purpose: a unit test that clicks a `Link` to `/` beside a mounted page, and
  an e2e test through the real shell, because **this is an integration defect between the shell and
  the page and the unit layer alone did not see it for a whole sprint.** The e2e test was shown to
  fail against the old guard before being kept.

  - **A trap the e2e suite has and does not announce:** the dev server proxies `/api` to
    `localhost:8000`, so a container left running on that port answers every request an e2e test
    forgot to stub, with the real dev library. It fails tests that look like regressions and are
    not — `add-detail.spec.ts`'s stagger test clicks a real *Rayuela* card instead of the web
    result. **Stop the container before running the suite.**

## DEC-075 — `data` and `backups` default to named Docker volumes; bind mounts move to an opt-in second Compose file

- **Date:** 2026-08-18
- **Status:** accepted
- **Extends:** DEC-040 (backups live outside the data volume)
- **Context:** First install required `mkdir -p data backups calibre` followed by `sudo chown -R
  10001:10001 data backups`, because Compose creates a missing bind-mount directory as root:root
  and the container's fixed non-root user (uid 10001) cannot write into it — producing `attempt to
  write a readonly database` at startup, which reads like corruption and is only permissions. The
  Dockerfile already does `mkdir -p /data /backups && chown -R akasha:akasha /app /data /backups`
  before `USER 10001:10001`, and a freshly created, never-before-populated named Docker volume is
  seeded from that same image directory the first time a container mounts it — ownership included.
  The `sudo chown` step was solving a problem specific to bind mounts, not to the deployment as a
  whole, and requested by the owner ahead of sharing the repo more widely.
- **Decision.** `/data` and `/backups` are named volumes by default — `data`/`backups` in
  `compose.yaml`'s top-level `volumes:`, with the Docker volume name itself overridable via
  `AKASHA_DATA_VOLUME`/`AKASHA_BACKUP_VOLUME` (`name: ${AKASHA_DATA_VOLUME:-akasha_data}`,
  unprefixed by the Compose project — confirmed against a real `docker compose config` merge).
  `sudo chown` and the `data`/`backups` `mkdir`s drop out of first install entirely. `/calibre`
  stays a host bind mount unconditionally — it points at a real, pre-existing library, is mounted
  read-only, and ownership is moot for a read-only mount. Operators who want `./data`/`./backups`
  as real host directories — a NAS-backed `BACKUP_DIR`, or direct host access to the sqlite file —
  opt in with a second, explicitly invoked Compose file, `compose.bind-mounts.yaml`
  (`docker compose -f compose.yaml -f compose.bind-mounts.yaml up -d`), which restores today's
  `${DATA_DIR:-./data}:/data` / `${BACKUP_DIR:-./backups}:/backups` mounts verbatim, `mkdir`+
  `chown` dance included. Deliberately not named `docker-compose.override.yml`, so it is never
  merged in by accident. This does not touch DEC-040: backups still live on a separate mount from
  data, named-volume or bind-mount either way.
- **Consequences.**
  - Restore and rollback lose the `mv data data-restored`-shaped move they used to reach for —
    Docker has no volume rename — so both now restore into a fresh, separate named volume and flip
    which volume Compose points at via `AKASHA_DATA_VOLUME`, leaving the previous volume untouched
    as the safety net. `docs/operations/runbook.md`'s "Restoring" and "Rolling back" sections are
    rewritten around that, each keeping a full, copy-pasteable snippet rather than cross-referencing
    the other, and each noting the one-clause substitution (`-v "$PWD/backups:/backups:ro"`) that
    covers the bind-mount tier instead of duplicating the whole procedure.
  - `scripts/smoke_container.sh` drops the `DATA_DIR`/`BACKUP_DIR` host-tmp-dir dance, including the
    throwaway root container that used to hand ownership back on cleanup, but must give
    `AKASHA_DATA_VOLUME`/`AKASHA_BACKUP_VOLUME` a name unique per run: the `name:` override that
    makes the volume's Docker name predictable also removes Compose's usual project-prefix collision
    avoidance. A new step, AC4, drills the documented host-side restore-and-flip procedure directly
    — AC3 only ever restored inside the already-running container's own filesystem, which never
    exercised the bare `docker run` + volume-flip mechanic this decision introduces.
  - `attempt to write a readonly database` and `Refusing to migrate without a backup` in the
    runbook's troubleshooting table become tier-2 (bind-mount) symptoms specifically — a tier-1
    install cannot reach either through an ownership mistake.
  - `README.md`'s Quick Start, Configuration table and `docs/specs/technical-spec.md`'s Compose
    mounts list move to the named-volume defaults, each pointing at `compose.bind-mounts.yaml` for
    the host-path alternative. `.gitignore`'s `data/`/`backups/` entries are now tier-2-only.

## DEC-076 — Sprint 031 absorbs the import boundary, manual entry's domain, and the README's import story

- **Date:** 2026-08-20
- **Status:** accepted
- **Context:** Owner feedback after the v1.2.0 release, before committing to any new connector work:
  the +Add surface has no clear way to indicate the domain; the README does not describe when
  triage and import are relevant or why; and the real question underneath both — can a contributor
  build a connector (a reworked Calibre importer, a future `spotify → music`) in its own module,
  plug-and-play with its domain, without touching the rest of the repo? The owner is in no hurry to
  build any specific importer and wants the ground stable underneath first, so the answer is
  scheduled rather than attempted in the margins. This entry records the measurement behind the
  plan revision 13 changes to Sprint 031's contract.
- **What the code actually says, measured 2026-08-20.** Three of the four things the feedback
  worried about are already fine, and saying so is part of the decision because it halves the
  imagined scope: **triage is domain-agnostic end to end** (statuses, hotkeys and the bulk
  vocabulary all render from `GET /api/item-types`; a mixed selection intersects; the inbox
  deliberately has no domain tab) and needs no per-domain expansion; **the import ledger, preview
  storage, undo and fingerprint idempotency are already neutral** — `import_batches` /
  `import_records` / `import_effects` key on an opaque `normalized_payload` and a `kind` string and
  know nothing about books; **the readers already live in the right place** since Sprint 028
  (`domains/book/goodreads.py`, `domains/book/calibre.py`, and Calibre is a clean read-only
  adapter). What is book-shaped is five specific places: `api/imports.py` (per-source routes and a
  preview record typed with book fields), `application/imports.py` (two copy-pasted service
  classes, ISBN/`calibre_uuid` identity, `first_author=` matching), `ImportRepository.commit` (a
  *shared* layer that reads `payload["isbn"]`, builds metadata from a fixed book key list, types
  created items as `DEFAULT_DOMAIN.item_type`, and writes entry fields a domain without those
  passage fields refuses — the shared-layer branching technical spec §6.6 forbids everywhere
  else), `ImportPage.tsx` and `api/imports.ts` (sources as literal tabs and typed fields). The
  manual add path is the fifth: `AddService.add` binds every manual item to
  `DEFAULT_DOMAIN.item_type` whatever the client sends, which is why `/add` names no domain —
  honestly, per DEC-073, rather than by oversight.
- **Decision.** Plan revision **13**; `FINAL_SPRINT` stays 31. Sprint 031's contract in
  `docs/sprints/ROADMAP.md` is expanded to carry the measured coupling, the boundary's concrete
  shape (an `Importer` contract beside the `Provider` protocol, generic preview/commit routes
  `/api/import/{importer}/...`, the importer set published over the API like `GET /api/item-types`,
  records validated against the target domain's own declaration, conformance checks in
  `test_domain_conformance.py`), and two absorbed scopes:
  1. **DEC-067 row 6 lands here.** Manual entry honours the domain: `AddService.add` takes the
     manual payload's domain from the client and validates against that domain's field spec, and
     `/add` regains the chooser — truthfully this time. The row was parked for Sprint 029's rebuild
     of the add screens ("named for Sprint 029"); 029 scoped it out (DEC-073), and 031 is the first
     sprint that both touches the add path's validation and benefits from it — a third domain gets
     a manual fallback from day one instead of never.
  2. **The user-facing account of these flows.** The README gains a real *Importing and triage*
     section — what the `unsorted` inbox is, that every import lands there and the default library
     hides it, when a re-run is relevant (Calibre re-sync fills empty fields only; owner edits
     always win) — and `docs/guides/adding-a-domain.md` gains the importer half of the story beside
     the provider steps, so a connector can be built from the guide alone the way the throwaway
     game domain proved the domain half.
- **Consequences.**
  - **No importer is built in 031**, re-stated: the boundary is the deliverable, and the first
    connector built against it is a separate epic, because an importer built in the same sprint as
    its boundary contaminates the boundary with one case's needs. `spotify → music` stays in
    *Future epics* as an architecture goal rather than a commitment, with its real constraint
    recorded: Spotify imports are playlist/saved-*track* shaped, so whether it rolls tracks up to
    albums or models songs directly is a Sprint 030 question, and the epic is shaped by that
    verdict whenever it is picked up.
  - **Sprint 030 is unaffected and stays first.** Its Phase A verdict determines what an import
    record may carry (flat entry, progress field, or child entities), which is why 031 follows it;
    nothing in this revision weakens that dependency, and 030's acceptance criterion 7 (impact-
    review 031 against the verdict) now has a richer contract to review against.
  - The expanded contract is what the closing agent for Sprint 030 expands into
    `docs/sprints/031-*.md` from `TEMPLATE.md`; until then the roadmap paragraph is the binding
    boundary, per the roadmap's own rule for planned sprints.

## DEC-077 — Entry depth: the flat entry holds; depth is per-domain progress or provider rows; sets are ordered shelves

- **Date:** 2026-08-20
- **Status:** accepted
- **Cross-references:** DEC-071 (the two-phase entry this closes the first phase of),
  DEC-052 (the measurement method, and the Strategy-B rejection this verdict echoes),
  DEC-058 (the series vocabulary collision), DEC-068 (the IGDB paper walk).
- **Context:** Sprint 030 asked one question with evidence: does a child of an entry
  need state of its own? The full reasoning, the costed table over the nine shared
  surfaces, and the provider provenance are in `docs/entry-depth-verdict.md`; this
  entry adopts that document and does not reproduce it.
- **Decision.** The flat entry holds; **nothing is built in Phase A.** A child of an
  entry does not need state of its own, because the two providers measured or walked
  that could have forced the question refused to: MusicBrainz delivers depth as
  metadata on the parent (one `inc=recordings` parameter, no extra request — shipped
  in Sprint 026 as the `rows` field, re-measured live on 2026-08-20 and unchanged),
  and IGDB models its would-be children as sibling records with typed edges. Depth,
  when a domain needs it, is shape (a) — a per-domain `progress` field, declarative
  under the Domain contract — or shape (b), a progress marker in provider-supplied
  `rows`. Shape (c), real child entities with their own status, is rejected on
  evidence: it is the only shape that taxes every shared surface (cursor, triage,
  bulk, facets, export, undo, library row, detail page), and no measured provider
  asks for it. **A set is not depth.** The Harry Potter set and the Malazan series
  (product spec §11 item 4) are the same request twice, and the answer is an ordered
  shelf — an additive feature on the flat model, deferred, not denied.
- **Honest gaps, stated rather than smoothed over.** TMDB's series/season/episode
  hierarchy — the strongest candidate for shape (c) — is **reasoned, not measured**:
  no credential was available and the owner did not supply one, so that arm is a
  labelled paper walk with the closing cost named (a token, two requests, committed
  captures). Its first draft was written from model memory; challenged by the owner,
  it was re-grounded against the published API reference on 2026-08-20 and every
  claim now names the document it stands on — but a documented schema is still not
  an observed response, and the arm stays a paper walk until the captures exist.
  And "I've read the first four Malazan books" — per-member state inside
  a curated set — has no cheap shape; the verdict refuses to buy it with a redesign.
- **What would reopen this:**
  1. A domain whose provider, measured live, returns children carrying their own
     user-facing state — the TMDB arm is the standing candidate.
  2. The owner stating the Malazan sentence as a need rather than an example.
  3. Two domains shipping shape (a) and their `progress` vocabularies drifting,
     promoting the field to a shared typed concept.

## DEC-078 — Importers normalize once; the shared pipeline validates and commits

- **Date:** 2026-08-21
- **Status:** accepted
- **Extends:** DEC-069 (readers belong to their domain), DEC-076 (the measured import coupling)
- **Context:** Sprint 031 had to choose the concrete contract a future connector implements. The
  choice determines whether the next importer stays inside its domain or has to teach shared code
  its source vocabulary. It also had to settle route compatibility and the shape of manual entry,
  both called out as risks in the sprint contract.
- **Decision.** `Importer` is an explicit, runtime-checkable protocol beside `Provider`. A connector
  declares its permanent name, label, target domain, input descriptor and authoritative identity
  kinds, then implements three operations: `read` produces an immutable neutral snapshot; `stage`
  archives source bytes or prepares local assets only after fingerprint replay has been ruled out;
  and `match` applies the connector's identity strategy through a narrow library matcher. The
  normalized row has nested neutral item and entry halves plus opaque source fields. The shared
  `ImportService` owns domain validation, durable planning, commit, enrichment eligibility and the
  ledger; `ImportRepository` reads the target `Domain` declaration and importer identity kinds,
  never a book key list.
- **Route compatibility.** The two public URLs did not change: the generic template
  `/api/import/{importer}/preview|commit` resolves to the existing Goodreads and Calibre paths.
  Dedicated handlers were removed rather than retained as delegates because there is no distinct
  legacy path to redirect. `GET /api/importers` is the new catalog used by the screen. Preview keeps
  compatibility fields supplied by each reader while adding nested `item`, `entry` and
  `source_fields`; new shared code depends only on the nested shape.
- **Manual entry.** `manual.item_type` is required; absence is a 422 rather than a silent book
  default. `manual.metadata` and optional `manual.identifiers` replace the book-shaped manual body,
  and the server validates metadata against the named domain before matching or writing. `/add`
  renders ordinary metadata controls from `GET /api/item-types`; structured `rows` remain
  source-provided rather than being flattened into a hand-entry text box.
- **Consequences.** Goodreads and Calibre retain their parsers and observable behavior, held by
  their unmodified suites. A new importer adds one module and one registry tuple, and automatically
  receives the catalog tab, generic routes, preview/commit transaction, `unsorted` triage,
  fingerprint idempotency and undo. The contract deliberately does not provide discovery or a
  plugin runtime: connectors are code-owned and ship with the application, like domains and
  providers.


## DEC-079 — Sprint 032: fold triage into import, and make connectors self-describing

- **Date:** 2026-08-21
- **Status:** accepted
- **Context:** Sprint 031 closed the per-domain import boundary (DEC-078) and the owner used the result. Two UX defects surfaced immediately. (1) Triage is a top-level tab that is empty unless an import has just landed rows `unsorted`, so clicking it most of the time shows a dead page — it is not an independent destination, it is the tail of the import flow. (2) Neither importer explains itself: the Goodreads tab is a bare file input with no hint that the export lives at `goodreads.com/review/import` → Export Library (desktop web only), and the Calibre tab's only guidance is "Enter a relative folder only", which is unanswerable without knowing what folders exist under the configured mount (`frontend/src/pages/ImportPage.tsx:131-159`, `backend/src/book_tracker/domains/book/calibre.py:214-223`). Behind the UX sits an architectural gap: `ImportInputSpec` (`backend/src/book_tracker/domain/importers.py:27-36`) carries only `kind`/`label`/`field`/`accept`/`placeholder`/`help`, and `ImportReadError` carries only `code`/`message`/`details` mapped to a flat 422 (`api/imports.py:181-184`), so a connector cannot publish richer guidance, a drag-and-drop affordance, a browsable path picker, or a custom user-actionable error such as "locked calibre library, do X". A future Spotify/Steam connector would have to patch the shared screen, which is the coupling the boundary exists to prevent.
- **Decision:** Schedule Sprint 032 (plan revision 14; FINAL_SPRINT moves 31 → 32). Triage folds into Import as a tab — the existing `TriagePage` component moves unchanged, only its route wrapper and the Inbox/post-commit links change. Goodreads gains connector-declared guidance and drag-and-drop. Calibre gains guidance and a browsable folder picker backed by a read-only `GET /api/import/calibre/browse` endpoint confined to the mount, returning directory names only. The contract extends declaratively: `ImportInputSpec` gains optional `guide`, `empty_state`, `help_url`; `ImportReadError` gains optional `user_message` and `action`, surfaced in the 422 payload and rendered by the screen. Conformance checks reject a malformed declaration. A redirect from `/triage` to the folded path is the recommended answer to the bookmark question, to be settled at implementation.
- **Consequences:** The plan extends by one sprint; the project is no longer `complete` and state points at 032 as `ready`. The walkthrough gate applies — this is user-visible behavior, so the sprint closes only after both readers are exercised through the folded UI against realistic data. The reader suites (`test_goodreads_import.py`, `test_calibre_import.py`) remain the no-behavior-change net. Future epics (Spotify, Steam) inherit a contract whose connector can guide its own users without touching shared screens.

## DEC-080 — A connector guides its own users, in ordered steps and one actionable sentence

- **Date:** 2026-08-21
- **Status:** accepted
- **Implements:** DEC-079, whose four implementation-time questions this settles. **Extends:** DEC-078 (the importer boundary as built).
- **Context:** Sprint 032 had to make two connectors explain themselves without letting either of them special-case the shared import screen. The screen already rendered `ImportInputSpec`, but the spec carried only a one-line `help`, and `ImportReadError` reached the client as a flat 422 whose `message` was written for a log. The four open questions the sprint file listed — guide format, `/triage`'s fate, the browse endpoint's shape, and the default tab — all had to be answered before the screen could be written.
- **Decision.**
  - **A guide is ordered steps, not markdown.** `ImportInputSpec.guide` is a tuple of plain strings the screen renders as an ordered list, beside `empty_state`, an https `help_url` and `browsable`. Markdown was the alternative and was rejected twice over: it adds a rendering dependency to a shared screen, and it lets a connector ship arbitrary markup into a surface it does not own. Import guidance is a numbered procedure; that is the shape it gets.
  - **An error carries what a person can do.** `ImportReadError` gains `user_message` and `action`. `code` is what the client branches on, `message` is what the log keeps, and `action` is one imperative sentence naming the next move — "Close Calibre and try again; it locks the database while it is writing". Only the connector knows that sentence. Both surface in the 422 payload and are **omitted when absent**, so every other error in the application keeps the envelope it has always had. `error_codes` becomes a required, closed member of the `Importer` contract, and `declared_read_error` republishes anything outside it as `undeclared_import_error` rather than leaking an unknown vocabulary.
  - **A `path` connector may be browsed, by declaring it.** `BrowsableImporter` is a separate protocol rather than an optional method on `Importer`, because an upload has nothing to browse and folding it in would make every future connector implement a method it has no use for. `GET /api/import/{importer}/browse?path=` returns **directory names only** — never an absolute path, which would publish the deployment's filesystem layout to anyone on the LAN — and the connector resolves confinement with the same code its reader uses, so the picker can never walk anywhere a preview could not open.
  - **`/triage` redirects; it does not 404.** It was a top-level nav item for thirty sprints and is in bookmarks and history. The tab lives in the URL as `?tab=`, and an unnamed tab falls back to the connector used last, mirroring DEC-062.
  - **A staged source belongs to its connector.** Moving to another connector clears the staged file, path, preview and result; moving to Triage and back does not, because Triage is not a connector and the undo window is only reachable from the result panel.
- **Consequences:** The next connector (Spotify, Steam) ships its own guidance, its own affordances and its own error vocabulary as part of its package, with no edit to `ImportPage.tsx`. The conformance suite gained checks that fail on a malformed guide, a non-https help URL, an empty or shouted error vocabulary, and browsing declared without a `browse` method. The last three sub-decisions were found or confirmed by the walkthrough gate rather than by a test: the connector-scoped preview, the contradictory empty-folder copy, and the duplicated "← Library" on the triage tab were all visible only in the running application (DEC-025).

## DEC-081 — Sprint 033: a Calibre library is a folder you choose, not a mount you configure

- **Date:** 2026-08-21
- **Status:** accepted
- **Extends:** DEC-080 (connector-declared input and guidance), DEC-078 (the importer boundary).
- **Context:** The owner used Sprint 032's folder picker against a real library and found the cost was never the picker — it was the mount underneath it. `CALIBRE_DIR` is a container-level setting, so aiming Akasha at a different library means editing `.env` and recreating the container; and the library that matters is held open by calibre-web-automated, where several services reading one Calibre library concurrently is not supported. Measurement ruled out the cheap fix: `metadata.db` is one 416 KB file and could simply be uploaded, but covers live one per book directory and cannot, and only 19% of the 21-book NAS library carries an ISBN — so enrichment would refill four covers and leave seventeen blank. Measurement also ruled the real fix *in*: the browser can read the chosen folder, and `metadata.db` plus covers is 8.7 MB of a 95 MB library, because the ebooks are what make a library big. Two structural findings came from looking at the actual files rather than reasoning about them: `.caltrash/b/1/cover.jpg` is a deleted book's cover, so a `cover.jpg` glob ships Calibre's trash; and `webkitRelativePath` prefixes every path with the picked folder's own name.
- **Decision:** Schedule Sprint 033 (plan revision 15; FINAL_SPRINT 32 → 33). A Calibre import is primarily a **folder chosen in the browser**: the client filters the selection to `metadata.db` and `*/cover.jpg`, excluding dot-directories, and uploads only that. The server materializes the bundle into a temporary directory and points the **existing** `CalibreAdapter` at it, so an uploaded library and a mounted one normalize through identical code and the reader learns nothing new. `ImportInputSpec` gains `kind="directory"`, a one-deep `alternate` so a connector can offer a second way in on the same tab, and per-connector `max_bytes`/`max_files` so the shared route's 5 MiB ceiling is not raised for everyone. **The mount stays** — the owner chose to keep the 032 picker and the typed path as secondary affordances beneath the folder chooser rather than delete either, so automation and a too-large-to-upload library both keep a path.
- **Consequences:** The plan extends by one sprint and the project leaves `complete`. The multipart branch must stream rather than buffer — a per-connector ceiling large enough for a real shelf is far past what a ZimaBoard should hold in memory — and client-supplied member paths are attacker-controlled, so traversal and shape are validated before a byte is written. The walkthrough gate applies with the mount deliberately absent, since "no setup required" is the claim under test. Future connectors inherit `alternate`, which is the first contract member that lets one connector present two affordances without the shared screen knowing which it is rendering.

## DEC-082 — Sprint 034: the server decides what to upload, because the client cannot hash

- **Date:** 2026-08-21
- **Status:** accepted
- **Extends:** DEC-081 (the folder chooser), DEC-048 (content-addressed attachments).
- **Context:** Sprint 033 removed the mount, and the owner immediately asked the right follow-up: is it reasonable to drag a 600 MB folder into a browser every time you sync? It is not. Content-addressing dedupes **storage** and not **transfer** — the server can only recognise bytes after they have arrived — so an unchanged re-sync pays full price today, uploading 10.0 MB of covers to be told they were already held. The same flow carrying ebooks would be 163 MB every time. The standard fix is to hash in the client and ask which digests are missing, and it was ruled out by measurement rather than by taste: `crypto.subtle` is gated on a secure context, and in Chromium `http://localhost:8000` and `http://127.0.0.1:8000` report `isSecureContext=true` with `crypto.subtle.digest` present, while `http://books.home.lan` — the reverse-proxied LAN hostname the runbook describes — reports `isSecureContext=false` and `crypto.subtle` **undefined**. A digest negotiation would work when the owner browses the box directly and fail silently from every other machine on the LAN, which is worse than not building it.
- **Decision:** Schedule Sprint 034 (plan revision 16; FINAL_SPRINT 33 → 34). **The server decides what it wants.** The client uploads `metadata.db` plus a JSON manifest of `{path, size}` — sizes come from `File` objects and need no reading — to `POST /api/import/{importer}/plan`, and the connector answers with the subset it actually wants by comparing identities the library already holds. `ImportInputSpec` gains `incremental`, refused by conformance unless the connector implements the new `IncrementalImporter` protocol, matching the `browsable`/`BrowsableImporter` shape DEC-080 established. The connector reaches the library only through a narrow `ImportInventory` view with two batched questions — which identities exist, and which of those already have a cover — the same containment `ImportMatcher` established. **The plan is never load-bearing:** a failed plan degrades to sending everything, with the screen saying so, because an optimisation that can fail closed turns a working import into a broken one.
- **Consequences:** An unchanged re-sync becomes a 416 KB round trip. `metadata.db` is uploaded twice, once to plan and once to preview, which is stated rather than engineered around — avoiding it would mean a second batch-shaped lifetime on the server to save 416 KB. Planning by identity rather than by digest means a **changed file under an unchanged identity is not detected**; the escape hatch is that an item without a cover is always wanted, so a failed first attempt heals on the next import. A connector whose source has no durable identity must decline to declare `incremental` rather than guess. This lands deliberately **before** ebook attachments (the owner's next request), because shipping those first would mean 163 MB on every sync — the problem this sprint exists to remove. The owner also settled the scope question behind that feature: attaching files belongs to the importer, and Akasha's own file UI stays simple and file-type agnostic rather than growing toward an ebook manager.

## DEC-083 — Sprint 035: the importer may attach the files, and the ledger is what tells them from the owner's

- **Date:** 2026-08-21
- **Status:** accepted
- **Extends:** DEC-082 (planning by identity), DEC-048 (content-addressed attachments), DEC-047 (the attachment cost measurement and the undo guard it demanded).
- **Context:** The owner asked why the Calibre import advertises that ebooks never leave the machine when attachments already exist and this is their ideal use case, and settled the scope in the same breath: attaching files is a feature of **the importer**, while Akasha's own file surface stays simple and file-type agnostic. Sprint 034 landed first on purpose — with the plan step in place the incremental cost of turning this on is near zero, where before it would have been the whole corpus on every sync. Measured on the owner's library on 2026-08-21: 18 books, 18 epub at 95.4 MB (mean 5.3 MB, max 14.8 MB), 14 azw3 at 67.4 MB, and **nothing above the 25 MiB attachment cap**. The blob store is 1.5 MB today, so this is the first time the store's size is set by the library rather than by hand.
- **Decision:** Schedule Sprint 035 (plan revision 17; FINAL_SPRINT 34 → 35). Three things settle the shape.
  - **One file per book, epub first.** Both formats is 163 MB against 95 MB for epub-only, and two rows for the same book in a file-type-agnostic list is noise. The preference order is `epub, azw3, mobi, pdf, cbz, cbr, txt`; a second format is one manual upload away and that UI already exists.
  - **One request per file, after the batch commits**, rather than folding the ebooks into the preview bundle. The bundle route's ceiling is per request (`max_bytes` is 256 MiB), so folding them in would cap the feature at roughly forty books; a per-file route is bounded by the attachment cap instead, which makes a 600-book shelf behave exactly like an 18-book one. It also means a bad file costs one book rather than the import, that skip-and-report above the cap falls out of per-file error reporting instead of being built, and that progress can be counted honestly.
  - **The undo ledger gets a sixth entity type**, and it is the sprint's real work. DEC-047 made "this item has an attachment" mean "the owner did something deliberate here, do not delete it". An import that attaches files makes that sentence false. Only the ledger can tell an imported file from a hand-uploaded one: an attachment effect carries the row id, `sha256` and `filename`, is reversed before its item's create effect because it is written later, and is reversed **only while the row still matches what the import recorded** — a renamed or replaced attachment is retained, like any hand-edited field. Get this wrong in one direction and undo destroys an owner's file; wrong in the other and every imported book is permanently un-undoable.
- **Consequences:** Two shared-layer contracts widen. `NormalizedImportRecord` gains `source_files`, so a record can name the files that belong to it and a shared route can resolve an uploaded path without knowing what a Calibre library looks like; and `ImportInputSpec` gains `members` patterns, which removes the hardcoded Calibre bundle shape from `_bundle_member` — a real `if calibre` in a shared layer that this sprint is forced to pay off. `ImportInventory` answers a third question, `attached`, keeping the connector out of storage. The disk curve is **stated rather than bounded**: 95 MB here, roughly 3.2 GB for a 600-book library at the measured mean, with DEC-047's strategy E holding backups at ~1.0 effective copies only while `BACKUP_DIR` shares a filesystem with the data directory. No disk budget exists anywhere in this repository and this entry does not invent one. Product spec §1's "not an ebook server" non-goal **stands as written**: no reader, no format parsing, no progress, no format-aware file UI. What changes is that the importer can put a file where the owner could already have put it by hand.

## DEC-084 — Exhaustive verification runs once after code freeze; closure reruns follow the diff

- **Date:** 2026-08-21
- **Status:** accepted
- **Extends:** DEC-025 (the walkthrough gate) and the agent protocol's verification/closure rules.
- **Context:** Sprint 035's healthy closure gates were not intrinsically long: about 8 seconds for
  `make check`, 60 seconds for 559 backend tests, 25 seconds for 179 frontend tests and 1 minute 40
  seconds for 101 Playwright cases. The session nevertheless spent much longer testing. Two
  avoidable causes dominated. First, FastAPI `TestClient` deadlocked inside Codex's isolated
  PID/network sandbox; the same export cases passed in 3.79 seconds outside it, but only after the
  opaque sandboxed run and then a focused sandboxed rerun had both been allowed to wait for minutes.
  Second, AGENTS.md required `make check` and `make test` once during verification and then “once
  more” after edits limited to Outcome, roadmap, worklog, handoff and state. That repeated about 85
  seconds of product tests without changing the product. The realistic-data walkthrough also had to
  be reconstructed and failed twice on its own selectors before the successful script was retained.
- **Decision:** `docs/agent/TESTING.md` is the canonical verification cadence. Work climbs from
  focused TDD to neighboring regressions to one stable walkthrough, then freezes implementation and
  runs every distinct exhaustive gate once. Closure changes are classified by effect. Pure
  documentation/state closure reruns project validation, applicable document checks and
  `git diff --check`; a later runtime, test, migration, dependency, build/test-configuration or
  generated-contract change invalidates and reruns the affected exhaustive gate. A stalled command
  is diagnosed against recorded phase durations and reproduced once with one changed variable;
  agents do not repeat the same opaque command in the same environment without a new hypothesis.
  Useful realistic-data walkthroughs are parameterized and retained locally under an ignored path,
  then promoted to tracked sanitized infrastructure only when generally reusable.
- **Consequences:** No acceptance criterion, external-boundary proof, walkthrough, full-suite or
  failure test is removed. The routine documentation-only closure no longer pays for a second
  product suite, and an environment deadlock should cost one focused comparison rather than several
  open-ended waits. The playbook records current duration baselines and an explicit, unimplemented
  optimization backlog: isolate the two serial Playwright cases so the rest can parallelize, remove
  known Vitest warning noise, build a one-command realistic-data launcher and add bounded phase
  timeouts. Those are future implementation work, not claims about the current suite.

## DEC-085 — Import is a two-step flow; triage is row-local until a checkbox says bulk

- **Date:** 2026-08-21
- **Status:** accepted
- **Extends:** DEC-079 (Triage folded into Import), DEC-026 (shared row controls), DEC-028
  (optimistic rollback), and DEC-084 (verification cadence).
- **Context:** After successfully importing the real library with Sprint 035, the owner found two
  interaction mismatches. Connector choice and Triage appeared as peers in one tab strip even
  though they are different levels: choose a connector to import, then triage what arrived. Inside
  Triage, a row click implicitly selected the entry, so changing one score took three actions —
  select the row, open the bulk score menu, choose a value — and ordinary reading was forced through
  a bulk mental model. The existing checkbox already communicates selection and should be the
  pointer boundary for bulk work.
- **Decision:** Schedule Sprint 036 (plan revision 18; FINAL_SPRINT 35 → 36). `/import` keeps one
  route and its existing `?tab=` addresses, but presents a prominent main switch between **1.
  Import** and **2. Triage**; connector tabs appear only inside the Import step. Triage reuses the
  shared compact `ScorePicker` and domain-aware `StatusSelect` on each virtual row. Those controls
  always patch one entry. Row-body clicks open detail. Only checkboxes select by pointer, while
  Shift ranges, Ctrl/Cmd+A, the bulk toolbar and keyboard-first actions remain supported.
- **Consequences:** “Bulk-first” no longer means every pointer edit begins by selecting a row; it
  means the bulk path stays fast once the owner explicitly selects. The fixed-height row becomes
  denser and must be checked at narrow widths. Status changes naturally remove a row from the
  unsorted inbox after success; optimistic failure restores the prior row and announces one error.

## DEC-086 — Fixed virtual rows use native selects for row-local triage edits

- **Date:** 2026-08-21
- **Status:** accepted
- **Refines:** DEC-085's row-control implementation; preserves DEC-026's score color language and
  DEC-028's optimistic rollback contract.
- **Context:** The planned reuse of the library card's compact `ScorePicker` does not fit a triage
  row: its panel is anchored above a fixed-height card, so the first visible row clips it at the
  scroll edge. Replacing it with the shared Radix select avoided the geometry problem but the open
  portal applied modal `aria-hidden` behavior to the route containing its own focused trigger; axe
  correctly failed `aria-hidden-focus`. A fixed working row needs controls that neither expand its
  box nor leave its accessibility tree.
- **Decision:** Triage uses named native `<select>` controls for row-local status and score. The
  status options still come from `statusesFor(entry.item.type, registry)`, and the score uses the
  same DEC-026 fill ramp and provisional marker. Both patch one entry optimistically and restore the
  cached page on failure. The library cards, add form and detail form keep their established shared
  controls; this is a geometry-specific choice, not a replacement design system.
- **Consequences:** The controls are keyboard-native, do not portal, cannot resize the row and work
  at the first and last scroll positions. At 390 px the cover and redundant chevron hide, status and
  score narrow, and the row is asserted not to overflow. The realistic walkthrough also exposed the
  old fixed 70vh blank panel under a short inbox; triage now sizes to its virtual content until the
  same 70vh/760px scroll cap is reached.

## DEC-087 — Triage uses page scroll and status drafts

- **Date:** 2026-08-21
- **Status:** accepted
- **Supersedes:** DEC-085's immediate row-status write and DEC-086's nested-scroll consequence;
  preserves their checkbox-only selection, native row-control and optimistic score decisions.
- **Context:** In the owner's first sustained use, the 70vh Triage box made the wheel manage a
  second vertical position while unused document space remained below it. More seriously, a native
  status selection patched immediately and invalidated the `status=unsorted` query. The browser
  could repaint the controlled select as Inbox during refresh or remove the row altogether, so an
  ordinary one-row decision interrupted the act of reading down the list. This was technically the
  contract Sprint 036 wrote and still the wrong interaction.
- **Decision:** Triage window-virtualizes its fixed rows using the measured document offset and lets
  the browser own scrolling. A row-local status choice is a client-side draft, visibly marked as not
  saved. One explicit toolbar applies all drafts, grouped into one existing bulk request per chosen
  status; another discards them without a request. Successfully applied groups clear and may leave
  Inbox, while failed groups remain staged for retry with one error announcement. Row-local scores
  and explicit checkbox bulk actions continue saving immediately.
- **Consequences:** Review order stays visually stable until the owner chooses the commit boundary.
  Applying several different statuses is not transactionally atomic because the existing endpoint
  accepts one status per request; the UI reports partial failure honestly and retains only the
  failed drafts. No backend, schema or API change is required. A 200-row browser test asserts window
  scroll and bounded mounted DOM, and the realistic 16-row walkthrough confirms that discard sends
  nothing and apply is the first status write.

## DEC-088 — Anime's providers, measured: AniList and Kitsu, and Jikan rejected on evidence

- **Date:** 2026-08-27
- **Status:** accepted
- **Cross-references:** DEC-052 (measure a domain rather than reason about it), DEC-051 (a curated
  sort name beats a heuristic), DEC-067 row 3 and row 4, `docs/domain_metadata_roadmap_report.md`
  (which called anime "a good domain, wrong default provider" and is superseded on that point by
  what follows).
- **Context:** The owner asked for anime as a third domain, with an importer for their own
  MyAnimeList export. Four candidate providers were probed live from the deployment host on
  2026-08-27 between 16:20 and 17:00 UTC. Nothing below is reasoned from documentation; each claim
  names what was observed.

### What was measured

| Provider | Auth | Search | Resolve the export's 81 ids | Studios | Observed availability |
|---|---|---|---|---|---|
| **AniList** GraphQL | none, but a User-Agent is mandatory | 6/6, 0.3–1.5s median | **2 requests, 54 KiB** via `media(idMal_in:)` | `studios(isMain:true)`, same request | 100% |
| **Kitsu** JSON:API | none | 6/6, 3.7s median, one 8.2s | 5 requests, 552 KiB via the mappings filter | `include=animeProductions.producer`, same request, `role == "studio"` | 100% |
| **Jikan** (unofficial MAL mirror) | none | **0/12** | **1/81** | yes, when it answers | **~40 minutes of continuous HTTP 504** |
| MyAnimeList API v2 | client id the owner must register | — | — | — | not measured; no credential |

- **Jikan is rejected on measurement, not on principle.** Across two windows fifteen minutes apart it
  returned `504 BadResponseException — Jikan failed to connect to MyAnimeList` to every request.
  The single by-id success in 81 was a record fetched moments earlier, so it was Jikan's own cache
  rather than a working path. `myanimelist.net` itself answered this host in 0.66s throughout, so
  MAL was up and Jikan could not reach it. A scraper in the path is a dependency on somebody else's
  tolerance, and that is what an availability measurement looks like when the tolerance runs out.
- **AniList carries the MAL identity, so Jikan was never needed for it.** `Media.idMal` is published
  on the record and `media(idMal_in: [...])` queries by it. The export's `series_animedb_id` is
  therefore resolvable without MyAnimeList or any mirror of it in the request path.
- **Kitsu answers the same question on a search row.** `include=mappings` returns the
  `myanimelist/anime` external id for every result in the same request (14 KiB for two rows), which
  is what makes an identity strategy possible rather than aspirational.

### Decision

- **Two providers: AniList first, Kitsu second.** `source_preference = ("anilist", "kitsu")`.
- **`identity_key` returns `mal:<id>`, and returns `None` when a candidate carries no MAL mapping.**
  This is the **first domain since books with a real cross-provider identity**. Albums answered
  `None` because a barcode is not an edition key; anime has a global identifier that both providers
  publish, so merging is correct rather than approximate. A row without a mapping — AniList returned
  `idMal: null` for several legitimate ONA entries — merges with nothing, which is the honest answer.
- **Kitsu is the hedge as well as the second source.** If the terms question below closes against
  AniList, Kitsu already carries search, fetch, MAL-id identity and studios on its own. That is why
  the domain ships with two adapters rather than one and a plan.
- **The curated sort name is the studio name unchanged.** A studio never inverts, exactly as DEC-068
  predicted for IGDB's companies, so both adapters supply `creator_sort` verbatim and the DEC-051
  heuristic never runs on `MAPPA`.

### Two things the owner has to own, stated rather than buried

1. **AniList's terms name this application's category.** They prohibit use "within competing
   noncomplementary services", listing "Anime/Manga list/tracker services", and permit non-commercial
   use under $150/month revenue otherwise. Akasha with an anime domain is an anime tracker by the
   plain reading. It is also single-user, LAN-only, self-hosted and unmonetised, and the terms carry
   an authorization path at `contact@anilist.co`. **The owner chose to proceed on 2026-08-27** on
   that reading. The Kitsu adapter exists so that reversing this decision is a configuration change
   and not a sprint.
2. **AniList requires a User-Agent.** Without one, Cloudflare answers `error code: 1010` with HTTP
   403. One otherwise-normal request also took 40.04s against a sub-second median, so the adapter
   goes through `bounded_json` with the interactive retry policy rather than a bare client.

### Cover art

Both hosts are new and each is one line in the allowlist (DEC-067 row 4 keeps that list central on
purpose). Measured against the pipeline's bounds — `MIN_PROVIDER_COVER_EDGE` 200, `MAX_COVER_EDGE`
600, aspect ratio under 3.0, 10 MiB:

| Host | Variant to use | Measured |
|---|---|---|
| `s4.anilist.co` | `coverImage.extraLarge` | 460x635, 110 KiB, ratio 1.38 |
| `media.kitsu.app` | `posterImage.large` | measured good; `original` is 980x1420 at **1.6 MiB PNG** and is not the one to ask for |

`cdn.myanimelist.net` is **not** added, because Jikan is not registered. Note for whoever revisits
this: MAL's default image variant is 225x313, which clears `MIN_PROVIDER_COVER_EDGE` by 25 pixels;
the `l` suffix variant is 431x600 and is the one that would be correct.

## DEC-089 — Anime is four sprints, and it collects two seams the plan deliberately left unbuilt

- **Date:** 2026-08-27
- **Status:** accepted
- **Cross-references:** DEC-058 (the numbered plan ended at the domain contract; further domains are
  epics), DEC-067 row 3 (enrichment beyond the ISBN, reserved for the first domain that needs it),
  DEC-077 (entry depth: shape (a) is a per-domain progress field, and nothing was built),
  DEC-088 (the providers), DEC-053 (a domain-line sprint runs on a branch).
- **Context:** The owner asked whether anime is one sprint or several, and framed the exercise as a
  test run for domain expansion whose findings feed back into the repository. `docs/guides/adding-a-domain.md`
  promises that a domain is its own directory plus small registration points, with no migration and
  no screen. **That promise holds for the anime domain itself and fails for the anime domain the
  owner actually asked for**, because the MyAnimeList export carries two facts the core has no home
  for. Both were foreseen and costed by earlier decisions; neither was built, because no domain had
  yet asked.
- **Decision — four sprints, in this dependency order.**

  ```text
  038 Anime: the third domain
   ├─ 039 Enrichment beyond the ISBN     (DEC-067 row 3)
   └─ 040 Entry progress                 (DEC-077 shape (a))
        └─ 041 The MyAnimeList import    (depends on both)
  ```

  - **038 is the guide's promise, kept.** Package, two adapters, registration, recorded responses,
    conformance. No migration, no new screen. If the guide is accurate, this sprint is evidence of it;
    if it is not, this sprint is where that is discovered, and saying so is the point of the exercise.
  - **039 pays DEC-067 row 3**, which named its own trigger: "the first domain that wants background
    enrichment on a non-ISBN key pays for (b) then, with a real case to design against instead of a
    hypothetical one." An imported MAL row is a `mal_id`, a title, a type and an episode count.
    Everything else — cover, studio, year, synopsis, season — has to be fetched, and `_backfillable_items`
    joins `item_identifiers` on the literal `'isbn'` while `_fetch` calls `fetch_by_isbn` against a
    module-level `PROVIDER_ORDER` of two book providers. The row costed this at about half a sprint.
  - **040 builds DEC-077 shape (a).** Every one of the 81 rows carries `my_watched_episodes`; one is
    `Black Clover`, dropped at 20 of 170. The entry model has `date_started`, `date_finished` and
    `reread_count` and nowhere to put that number. The verdict already chose the shape — "a
    per-domain `progress` field, declarative under the Domain contract" — and built none of it. This
    is the sprint that does, and it is **the only one of the four that touches a shared table.**
  - **041 is the importer**, which lands complete because 039 and 040 precede it.

- **Why not one sprint.** The four slices are 038 alone at roughly the size of Sprint 025, plus a
  costed half-sprint, plus a migration on `entries` with its contract, API, UI and export surfaces,
  plus a connector with a real 81-row source to walk through. Folding them together would mean
  trimming the design to fit rather than splitting the plan, and would put a schema change on a
  shared table in the same commit range as a new domain's first walkthrough.
- **Why not gate 039 and 040.** A gate exists where cost is unknown (DEC-035, DEC-042). Both of these
  were already measured and costed by the decisions that deferred them, and the owner settled both
  forks at planning time on 2026-08-27: generalize enrichment rather than let the connector fetch at
  read time, and build progress before the import rather than drop the data and re-import. Gating
  what has already been priced and decided is ceremony.
- **Consequences.** `FINAL_SPRINT` moves to 41 and plan revision to 20. The line runs on the
  `sprint-038-anime` branch under DEC-053's rule, because a third domain is exactly the class of work
  that could fail spectacularly and `main` is what it is abandoned back to. **Anime is no longer an
  unnumbered epic**; games, series and Spotify remain so. If 038 completes without needing 039 or
  040 — that is, if the guide's promise survives contact — those two sprints are still owed, because
  the export the owner brought is what defines "complete" here.
