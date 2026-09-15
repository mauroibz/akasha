# Handoff

## Where the project stands

Sprint 084 ("any list, any domain") is **completed and closed** — the plan is
complete at 84/84. All commits are local on `main` (nothing pushed, per
protocol). Worktree clean.

The last user-visible change: the custom-list importer accepts any domain.
The screen shows a single-pick library dropdown (book, album, movie, series,
anime) before the file; header auto-detection and the creators-column label
follow the picked domain's own declaration; one list is one library per
batch.

## What this session changed

- `backend/src/book_tracker/domain/list.py` — the list reader, moved out of
  `domains/book/`, serving every domain that declares `Domain.list_columns`
  (`ListColumnSpec` in `domain/spec.py`; `None` = deliberately not
  list-importable).
- The library pick rides the existing `targets` form field into
  `ImportSource.options`; it is required, single-token, and composes the
  fingerprint (`csv#<hash>#album`). The service trusts a reader that consumed
  the choice (`source_descriptor.item_type`) rather than double-composing.
- `ImportInputSpec.single_domain_pick` (published in the catalog; OpenAPI
  regenerated) — the ImportPage renders one native dropdown instead of the
  tick-many checkboxes, and the mapping labels read the picked domain's
  creators field label (Author/Artists/Creators).
- **DEC-161**: confirming a proposal now fetches its `cover_url` (provider
  client, allowlist, `prepare_cover`) and stages it through the existing
  `cover_stage` channel; commit installs it; discard clears it. This — not the
  identifier-keyed enrichment backfill — is a confirmed row's cover path.
  Found live (album walkthrough: cover=no), fixed, re-proven clean.
- Conformance suite covers `list_columns` (registered check +
  malformed-domain rejection); recorded MusicBrainz replay proves a non-book
  row through the search job; per-domain CSV fixtures committed.

## Verified (all on the final tree)

Backend 1595 passed · Vitest 334 · `make check` green · Playwright 144 + 2
skipped (full parallel run) · live album walkthrough CLEAN
(`frontend/scripts/walkthrough-list-albums.mjs`, fresh data dir, live
MusicBrainz: 4 rows → confirm → commit 4 albums with covers → undo → 0).

## Known and left, in the order they are likely to bite

- **The version surfaces still say 2.1.0.** The sprint owed no bump (DEC-160).
  When the owner wants the batch in users' hands: release as v2.2.0 (merge
  commit, tag the merge, per the release convention).
- **The owner's dev container predates this sprint.** To validate the album
  flow by hand: `docker compose -f compose.yaml -f compose.build.yaml up -d
  --build` (the two-file form; plain `pull` would downgrade below the
  volume's migration head). Freshness is the image's created timestamp, not
  the tag.
- Mixed-domain batches and extra-column mapping stay out by design (one list,
  one domain; columns ride `source_fields`).
- `walkthrough-list-albums.mjs` spends real MusicBrainz quota (4 search
  requests + 1 cover fetch chain per run); run it when needed, not on a loop.

## Next session

Nothing owed. If the owner says "release", the publishing-a-release recipe
applies verbatim (survey, PR with merge commit, tag the merge, verify images
anonymously, GitHub Release from committed notes).
