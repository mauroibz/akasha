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
