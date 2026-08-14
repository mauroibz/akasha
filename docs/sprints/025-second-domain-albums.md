# Sprint 025 — Second domain, albums: the seams, proved by one domain

**Status:** planned
**Depends on:** 024
**Roadmap revision:** 10

## Objective

An album is searched, added, covered, listed, opened and edited alongside books — and it gets there
through **six named seams** rather than by being translated into book vocabulary. The sprint
succeeds when an album is correct in the library and fails loudly if a seam turns out to be cut in
the wrong place.

## Required context

1. `AGENTS.md`, `docs/agent/WORKFLOW.md`
2. **`docs/domain-architecture-proposal.md`** — accepted in full (DEC-052). Section 2 is the measured
   evidence, section 4 defines the six seams this sprint implements, section 7 explains why seam 5
   is split and albums are not
3. `docs/decisions.md`: **DEC-052** first, then DEC-051 (creator sort names, whose heuristic seam 1
   generalizes), DEC-044 (a provider fills fields only when its candidate is provably the record
   requested), DEC-045 (provider-agnostic quota), DEC-036 (the mapper event maintaining derived
   columns), DEC-008 (fill-empty-only)
4. `docs/sprints/ROADMAP.md`, Sprint 025 and 026 sections
5. `docs/specs/product-spec.md` 3.1, 3.2, 4.1–4.3, 7; `docs/specs/technical-spec.md` 5.1, 6.2,
   7.1, 7.2, 8
6. Sprint 024's Outcome — the export is the first consumer that notices if `type` stops being honest
7. `docs/domain_metadata_roadmap_report.md`, the music rows only. **Do not re-derive its research.**
8. `docs/agent/HANDOFF.md` and the last worklog entry

## Current implementation baseline

Observed 2026-08-14 at Sprint 023's close, before 024. **Re-derive at activation** — Sprint 024 will
have moved the serialization paths.

Already neutral, confirm rather than rebuild: `ItemRow.type` (`models.py:16`), serialized at
`application/library.py:166`, exposed as `ItemResponse.type` (`api/library.py:106`);
`item_identifiers` and `item_sources` already model global keys and source-scoped identity
separately; `ProviderQuota` names no provider (DEC-045); `normalize_identifier` has a generic
non-ISBN path.

Book-shaped, per seam:

| Seam | What is hardcoded today |
|---|---|
| 1 Creators | `sort_author` = `json_extract(metadata, '$.authors[0]')` (`models.py:24`); `creator_sort_name` assumes a person's name; 55 `sort_author` occurrences across 27 files including 7 e2e specs and `frontend/e2e/seed.ts` |
| 2 Identity | `_isbn()` is `merge_and_rank`'s only grouping key and `_merge_group` picks the `openlibrary` row as primary (`domain/providers.py`) |
| 3 Metadata | `ItemResponse.metadata` is typed `BookMetadataResponse` (`api/library.py`); twelve book fields hardcoded in `features/detail/MetadataDialog.tsx` and `features/detail/schemas.ts` |
| 4 Covers | `ALLOWED_COVER_HOSTS` = `covers.openlibrary.org`, `books.google.com`, `books.googleusercontent.com`, `archive.org`, plus a `.us.archive.org` suffix rule; `validate_url` requires https and runs on **every redirect hop** (`covers.py:117`); `MAX_COVER_EDGE` 600, `MAX_COVER_BYTES` 10 MiB |
| 5 Status | `statusLabels`/`chooseableStatuses` in `features/library/labels.ts`, **duplicated verbatim** at `pages/TriagePage.tsx:42` with `statusHotkeys` at `:51`; `EntryStatus` StrEnum is global |
| 6 Enrichment | `enqueue_enrichment` joins `item_identifiers` on `kind = 'isbn'` (`application/enrichment.py:347-350`); `_fetch` calls `fetch_by_isbn`, which the `Provider` protocol does not declare; `PROVIDER_ORDER`/`PROVIDER_LABELS` at `:32-33` duplicate `SOURCE_PREFERENCE` |

Also: `type="book"` at `repositories.py:156`, `:255`, `:587`. **`item_type` is declared on the
`Provider` protocol and read nowhere in `src/`** — treat the registry as unbuilt, not as
present-but-unused. The list endpoint has no `type` filter. `RateLimiter` is one shared instance at
0.5 s, not per provider.

## Deliverables

Ordered so that each lands green and the risky seams come early.

1. **Seam 5a prerequisite.** Collapse the `TriagePage.tsx:42` `statusLabels` duplicate into
   `labels.ts`. No behavior change; do it first so seam 5a cannot half-apply.
2. **Seam 2 — identity.** Replace `_isbn()` with a per-domain `identity_key(candidate) -> str | None`.
   `None` means never merge, which is albums' correct and complete answer. Do this **before** the
   adapter: it is the seam the earlier plan did not anticipate and the one most likely to be wrong.
3. **Seam 1 — creators.** Ordered creators with display name and sort name; a source that knows the
   sort name seeds `creator_sort_override` as owner data, exactly as Calibre does (DEC-051); the
   heuristic runs only when nothing knew. Carries the `metadata.authors` → `creators` and
   `sort_author` renames, with the migration and the e2e seeds. Store the rendered credit as well as
   the ordered list — `["Dean Blunt", "James Ferraro"]` joined by `", "` is not
   `Dean Blunt Meets James Ferraro`.
4. **Seam 3 — metadata field spec.** A per-domain declarative field spec (name, label, type,
   multiplicity) served over the API and consumed by `MetadataDialog.tsx`, which stops hardcoding
   book fields. `ItemResponse.metadata` stops being `BookMetadataResponse`; storage stays opaque.
5. **Seam 4 — covers.** MusicBrainz release / Cover Art Archive as the album cover source, plus the
   three measured pipeline fixes: upgrade `http://` to https before validating rather than loosening
   the check; extend the allowlist with an archive.org subdomain rule that survives the redirect-hop
   check; fetch the **1200px thumbnail**, not the full image.
6. **Seam 6 — enrichment.** Albums declare no background enrichment. `resolve_input` becomes a
   per-domain URL recognizer.
7. **The MusicBrainz adapter itself**, and `type="album"` reaching the three `repositories.py` call
   sites through the registry rather than as a fourth literal.
8. **Seam 5a.** Per-domain status *labels* over the existing values: `read` renders as "Listened".

## Acceptance criteria

1. An album is searchable, addable, and appears in the library with cover art, title and artist,
   openable and editable from the detail page — demonstrated in a browser, not asserted.
2. **`Daft Punk` sorts under D, not under P.** MusicBrainz's `sort-name` seeds the override, and the
   DEC-051 heuristic does not run on a name a source already knew. Verify with a `Group`
   (`Daft Punk`), a `Person` (`Miles Davis` → `Davis, Miles`) and `Various Artists`. This is the
   criterion the whole architecture turns on.
3. Two albums sharing a barcode are **not** merged into one item, and two book editions sharing an
   ISBN still are. Seam 2 proved from both sides.
4. A mixed library of books and albums paginates, sorts and filters correctly across the type
   boundary at a depth past page 1: no page skips a row, repeats one, or drops the cursor.
5. Adding an album spends no book-provider request and adding a book spends no MusicBrainz request,
   measured from the request log.
6. MusicBrainz's rate limit and User-Agent are honored per provider. The shared 0.5 s `RateLimiter`
   is not a per-provider limit and must not be treated as one. **MusicBrainz signals throttling with
   `503`, not `429`** — a retry policy keyed on 429 will not see it.
7. The metadata dialog renders album fields for an album and book fields for a book, from the field
   spec, with no `type === "book"` branch in the component.
8. Sprint 024's export still round-trips and an album exports through the entity-shaped path with no
   album-specific branch.
9. No row loses its creator sort name across the `authors` → `creators` rename, and
   `creator_sort_override` is carried, never recomputed.
10. Every book behavior the suite covers is unchanged: imports, enrichment, triage, undo, backup.
11. **A seam that had to be cut somewhere other than section 4 describes is written up in
    `docs/decisions.md`.** A clean run reports that too — silence is not evidence.

## Required tests (TDD)

- MusicBrainz and Cover Art Archive against **recorded real responses** under
  `backend/tests/fixtures/providers`, per the walkthrough gate: a mocked provider does not satisfy a
  correctness criterion at an external boundary (DEC-025). Follow that directory's `README.md`
  exactly — captures are verbatim, they are added in their own commit, and the README table gains a
  row per file with the URL it came from. The recordings this sprint needs, at minimum: a
  release-group with its releases, one full release with `label-info` and `media`, an artist of type
  `Person`, one of type `Group`, and a CAA `release-group` index response.
- Creator sort: `Person` inverts, `Group` does not, `Various Artists` does not, an owner override
  beats all three, and a book with no source-supplied sort name still falls back to the heuristic.
- `identity_key` returning `None` never merges; ISBN grouping still merges books.
- Release-group versus release: a candidate that cannot be tied to the requested release is rejected
  rather than partially merged (DEC-044).
- Cover pipeline: an `http://` CAA URL is upgraded and accepted; a redirect to
  `dn710907.ca.archive.org` passes the hop check; a redirect to a non-archive.org host is still
  refused.
- Mixed-type keyset pagination past page 1, with a cursor issued before the final page.
- An album with no creator sorts and renders without exception.
- Field spec drives the dialog: adding a field to the spec changes the rendered form with no
  component edit.
- `statusHotkeys` and `statusLabels` cannot drift — one source, asserted.
- Export of a mixed-type library, extending Sprint 024's tests rather than duplicating them.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && make build && make smoke-container
git diff --check
```

Plus the walkthrough gate against the container with a real library: add a real album you own and a
group-named one, find them beside your books, sort by creator across both types, page to the end,
and report what you saw — including anything wrong and out of scope.

## Explicit non-scope

- **Seam 5b — per-domain status vocabularies**, validation off the global `EntryStatus`, filter
  chips, triage hotkeys, and whether `reread_count`/`date_finished` mean anything for an album. That
  is Sprint 026, deliberately decided with two domains in hand (DEC-052). Albums here carry books'
  status *values* under album *labels*, which is a visible one-sprint debt rather than a hidden one.
- Games (027) and series (028). Do not generalize to three domains from one.
- Goodreads and Calibre import for albums. Those pipelines stay book-only; that is not a gap.
- Tracks as entities. A release's `media[].tracks` is metadata here, not a child item; entry
  hierarchy is Sprint 028's question.
- Auth, unchanged and unscheduled.

## Commit checkpoints

1. `refactor: collapse the duplicated status label map`
2. `feat: key candidate merging on a per-domain identity`
3. `feat: rename authors to creators` + `feat: seed creator sort names from the source`
4. `feat: describe item metadata with a per-domain field spec`
5. `feat: search MusicBrainz for albums` + `feat: take album art from the Cover Art Archive`
6. `feat: add an album end to end`
7. final `docs(sprint-025): close sprint and hand off`

## Risks and decisions to surface

- **Settled (DEC-053): this sprint runs on a branch cut from `main` at activation.** The invariant
  forbids pushing, not branching, so nothing is bent by it. Follow the ordinary protocol otherwise —
  state and handoff advance, the worktree ends clean, nothing is pushed — and treat merging back as
  the owner's decision at close, which is the reason the branch exists.

- **The renames in deliverable 3 are the largest blast radius in the sprint** — 55 `sort_author`
  occurrences across 27 files, 7 e2e specs, `frontend/e2e/seed.ts`, a migration, and the benchmark.
  DEC-051 deferred them here on purpose. If the sprint runs long, this is the slice to land alone
  and early, not the one to rush at the end.
- **Seam 2 is the least-proven seam.** It was derived from measurement, not from a walk through the
  code. If `identity_key` cannot be lifted out of `merge_and_rank` without dragging the ranking
  signals with it, that is a bucket-(c) finding and grounds to stop and re-plan rather than push.
- **Keyset pagination is predicted to need no change.** If that prediction fails, stop: it is the
  tripwire DEC-052 and the roadmap both set, and it invalidates the seam model rather than costing
  a day.
- **Breaching MusicBrainz's terms on a pilot is a real cost with no upside.** A descriptive
  User-Agent is required, ~1 req/s is the documented ceiling, and `configured.user_agent_contact`
  already exists.
- The `OL14454691A` author key in one dev-library item's `metadata.authors` (HANDOFF) will surface
  in any creator-sorted list and is **not** this sprint's defect. Note it; do not chase it.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
