# Sprint 034 — Incremental import

**Status:** completed
**Depends on:** 033
**Roadmap revision:** 16

## Objective

A re-import uploads only what the library does not already hold. Re-syncing an unchanged Calibre library costs one 416 KB `metadata.db` and a JSON manifest instead of the whole bundle, and the screen says what it is skipping and why.

## Required context

- `docs/specs/technical-spec.md` §6.5 (imports, incl. the 032/033 additions), §7.1 (`/api/import/...`), §6.6 (the domain contract).
- `docs/specs/product-spec.md` §5.2 (Calibre), §5.3 (shared import pipeline), §7 (`/import`).
- `docs/decisions.md`: DEC-081 (the folder chooser and the `alternate`), DEC-080 (connector-declared input), DEC-078 (the importer boundary), DEC-048/049 (attachments are content-addressed; reclaim), DEC-025 (walkthrough gate).
- Code, read fresh: `backend/src/book_tracker/domain/importers.py`, `api/imports.py` (`_bundle`, `_bundle_member`, `_chosen_input`), `application/imports.py`, `domains/book/calibre.py` (`CalibreAdapter.confine`/`read`/`_cover`, `CalibreImporter.read`), `infrastructure/repositories.py` (`DomainRepository`, `item_identifiers`), `frontend/src/features/import/{bundle.ts,DirectoryPicker.tsx}`, `frontend/src/pages/ImportPage.tsx`, `frontend/src/api/imports.ts`.
- Migration `0002_domain_schema` for `item_identifiers(item_id, kind, normalized_value, value)`, unique on `(kind, normalized_value)`.

## Current implementation baseline

Sprint 033 made a Calibre import a folder chosen in the browser: the client filters the selection to `metadata.db` plus `*/cover.jpg`, posts them as multipart parts named by relative path, and the route streams them to a bundle the connector's ordinary adapter reads. **Every member is uploaded every time.** Content-addressing dedupes attachment *storage* (DEC-048) but nothing dedupes *transfer*, because the server can only recognise bytes it has already received. Measured on the owner's library: a re-sync that changes nothing still uploads 10.0 MB of covers, and the same flow carrying ebooks would upload 163 MB.

The obvious client-side fix does not survive this deployment. `crypto.subtle` is gated on a secure context, and measured in Chromium: `http://localhost:8000` and `http://127.0.0.1:8000` are secure contexts where `crypto.subtle.digest` is a function, while `http://books.home.lan` — the reverse-proxied LAN hostname the runbook describes — reports `isSecureContext=false` and `crypto.subtle` **undefined**. A digest-based negotiation would therefore work when the owner browses the box directly and silently fail from any other machine on the LAN. The server has to be the one that decides.

## Deliverables

1. **A connector may plan before it uploads.** `domain/importers.py` gains `ImportCandidate(path, size)`, `ImportPlan(wanted, holding, reason)`, a narrow `ImportInventory` view, and a `runtime_checkable IncrementalImporter` protocol with `plan(source, candidates, inventory, context) -> ImportPlan`. `ImportInputSpec` gains `incremental: bool = False`, which conformance refuses without the protocol — the same shape `browsable`/`BrowsableImporter` already uses.
2. **The narrow library view.** `ImportInventory` answers exactly two questions and nothing else: `existing(kind, values)` — which identity values the library already holds as items — and `with_cover(kind, values)` — which of those already have a cover. Implemented on `DomainRepository` over `item_identifiers`, batched, never one query per book. A connector may not reach storage directly, exactly as `ImportMatcher` established.
3. **The plan route.** `POST /api/import/{importer}/plan` accepts the connector's declared upload/directory field plus a `manifest` JSON field of `[{path, size}]`, and returns `{wanted, holding, bytes}`. It is a 404 for a connector that does not declare `incremental`. It reuses `_bundle`'s streaming and `_bundle_member` validation unchanged, so a manifest cannot smuggle a path the upload route would refuse, and the bundle is removed when it returns.
4. **Calibre plans by identity, not by digest.** `CalibreImporter.plan` reads the uploaded `metadata.db`, maps each book to its cover's relative path, asks the inventory which `calibre_uuid` values are already held **with a cover**, and wants the rest. A book the library has but whose item has no cover is still wanted — "already imported" and "already has the picture" are different questions.
5. **The client asks first.** `DirectoryPicker` runs the plan when the connector declares `incremental`, then previews with only the wanted members. The summary states both halves: what is being sent and what is being skipped because the library already holds it. A plan that fails is not fatal — the client falls back to sending everything and says so, because a broken optimisation must not become a broken import.
6. **Documentation.** README's *Importing and triage*, `docs/guides/adding-a-domain.md`, technical spec §6.5/§7.1 and product spec §5.2/§5.3 follow.

## Acceptance criteria

1. Importing `/home/ibz/Calibre Library` twice in a row: the first sends `metadata.db` plus every cover; **the second sends `metadata.db` and no covers**, and the screen says how many books it skipped. Asserted on the request bodies, not on the screen.
2. A book added to the library between imports is the only cover the second import sends.
3. An item that exists but has no cover is wanted again, so a failed first attempt heals on the next import rather than being skipped forever.
4. The plan route refuses every member `_bundle_member` refuses, returns 404 for `goodreads` (which does not declare `incremental`), and leaves no bundle behind on either path.
5. The inventory answers in a bounded number of queries regardless of library size — asserted by counting statements over a several-hundred-book manifest, not by timing.
6. A failing plan request degrades to a full upload and the screen says so; the import still completes.
7. Conformance rejects `incremental` declared without `IncrementalImporter`, and an `ImportPlan` wanting a path that was not offered as a candidate.
8. The walkthrough gate passes: import the owner's real library, re-import it unchanged and observe the second upload, add a book and observe only that cover move, then break the plan endpoint and confirm the import still works.

## Required tests (TDD)

- Backend: plan wants everything on an empty library; wants nothing on an unchanged one; wants exactly the new book; wants a cover for an item that has none; refuses a bad member; 404 for a non-incremental connector; bundle removed on success and on failure; bounded query count.
- Conformance: `incremental` without the protocol; a plan naming an uncandidate path.
- Frontend: the two-phase submit sends only wanted members; the summary states sent and skipped; a rejected plan falls back to sending everything and says so.
- E2E: two consecutive imports of the same fixture directory, asserting the second body carries `metadata.db` only.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npx playwright test
git diff --check
```

Plus the walkthrough gate in AC8, recorded in `docs/agent/worklog.md`.

## Explicit non-scope

- **Attaching ebooks.** That is Sprint 035, and it is deliberately after this one: shipping it first would mean uploading 163 MB on every sync, which is the problem this sprint exists to remove.
- **Digest-based negotiation.** Ruled out above on secure-context grounds; if HTTPS ever arrives on the LAN this can be revisited as a refinement, not a replacement.
- **Incremental Goodreads.** A CSV is one small file; there is nothing to skip.
- **Changing what a re-import *does*.** Fill-empty-only and the fingerprint replay are unchanged; this sprint changes only which bytes travel.

## Commit checkpoints

1. `feat(sprint-034): a connector may plan before it uploads`
2. `feat(sprint-034): calibre plans by identity`
3. `feat(sprint-034): ask before sending`
4. `docs(sprint-034): incremental import`
5. final `docs(sprint-034): close sprint and hand off`

## Risks and decisions to surface

- **`metadata.db` is uploaded twice** — once to plan, once to preview — at 416 KB each. Keeping the planned bundle server-side to avoid it would introduce a second batch-shaped lifetime for a saving of 416 KB, which is the wrong trade; state the cost rather than build around it.
- **Identity is the key, so a connector without a stable one cannot plan.** Calibre has `calibre_uuid`. A future connector whose source has no durable identity must decline to declare `incremental` rather than guess, and the conformance check should make that a decision rather than an accident.
- **A changed file under an unchanged identity is not detected.** Re-exporting a cover for a book the library already has with a cover will be skipped. That is the deliberate cost of planning by identity rather than by digest; the escape hatch is that removing the cover in Akasha makes the next import want it again (AC3).
- **The plan must never be load-bearing.** AC6 exists because an optimisation that can fail closed turns a working import into a broken one.

## Outcome

**Completed 2026-08-21.** Commits: `fce12fe` (contract, inventory, plan route, Calibre's planner),
`8fcb0fc` (the two-phase client), `1d0e027` (documentation), and the closing state commit.

### Measured on the wire

A counting TCP proxy between the dev server and the backend, because neither
`request.postDataBuffer()` nor `request.sizes()` reports a multipart body of this size — both
returned zero, and the first two walkthrough attempts produced numbers that looked like a 100%
saving because nothing was being measured at all.

| Phase | On the wire | Result |
|---|---|---|
| First import | plan 0.49 + preview 10.05 = **10.55 MB** | 18 rows, nothing skipped |
| Unchanged re-sync | plan 0.49 + preview 0.49 = **0.99 MB** | 18 skipped, **90.6% less** |
| One book added | plan 0.49 + preview 0.50 = **0.99 MB** | 19 rows, 18 skipped |
| Plan broken | plan 0.00 + preview 10.06 = **10.06 MB** | fell back, said so, import completed |

90.6% rather than ~96% because `metadata.db` travels twice, which is exactly the cost the plan's
risk section predicted and declined to engineer around.

### Acceptance criteria

1. **A second import sends the database and nothing else** — measured above, and asserted on the
   request body in `import.spec.ts` and on the `FormData` in `ImportPage.test.tsx`.
2. **A new book is the only cover that moves.** Phase 3 previewed 19 rows and skipped 18.
3. **An item without a cover is wanted again**, so a failed first attempt heals rather than being
   skipped forever — `test_an_item_without_a_cover_is_offered_one_again`.
4. **The plan route refuses what the upload route refuses**, 404s for `goodreads`, and leaves no
   bundle behind on either the success or the failure path.
5. **Bounded queries:** 1200 identity values resolve in 3 statements, chunked at 500.
6. **A failing plan degrades**, verified in the walkthrough by aborting the route and in a
   component test.
7. **Conformance rejects** `incremental` without `IncrementalImporter`, and `planned_upload`
   rejects a plan naming a path that was never offered.
8. **Walkthrough passed**, four phases, recorded in `docs/agent/worklog.md`.

### Verification

`python scripts/validate_project.py` (pass), `make format` (no drift), `make check` (green),
`make test` (**backend 531 passed**, **frontend 176 passed**), `npx playwright test`
(**97 passed, 2 skipped** at `--workers=1`), `git diff --check` (clean).

### Deviations and decisions

- **`ImportSource` gained `manifest`**, so the plan route can carry the client's offer through the
  same `_bundle` streaming path the upload uses rather than parsing the multipart body twice.
- **`_bundle` gained `form_extras`** for the same reason — one streaming implementation, not two.
- **`book_path` is now kept on the reader's payload.** `_records` computed it and discarded it; the
  planner needs it to know where a book's cover would live.
- **No deviation on the two-phase cost.** `metadata.db` uploads twice, as planned and as measured.

### Observed and left

An unchanged re-sync shows "Local cover staged" on every row despite uploading no covers. That is
correct: the fingerprint of an unchanged `metadata.db` matches, so Sprint 031's replay returns the
**stored** batch, which did stage those covers. It looks alarming and is not — noted here because
the next person to see it will wonder.

### Impact on future work

Sprint 035 (ebook attachments on a toggle) is what this unblocks: with the plan in place, turning
attachments on costs one large first sync and near-nothing after, instead of 163 MB every time. It
still needs a sixth `attachment` entity type in the undo ledger, a decision about `.epub` versus
`.azw3` where a book has both, and skip-and-report for anything over the 25 MiB attachment cap.
