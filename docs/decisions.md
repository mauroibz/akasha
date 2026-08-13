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
