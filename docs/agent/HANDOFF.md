# Handoff — current reality

**Last completed:** Sprint 025 (second domain, albums — the six seams), 2026-08-14.
**Next:** Sprint 026 (statuses, formats and tracklists) — status `ready`, file at
`docs/sprints/026-statuses-formats-tracklists.md`. Plan revision **11**.

## Do this first

**You are on branch `sprint-025-albums`, not `main`.** Sprint 025 ran there per DEC-053 and was
closed there; twelve commits are local and nothing was pushed. **Merging back is the owner's
decision** — that is the entire reason the branch exists. Ask before merging, and cut Sprint 026's
branch from whatever the owner settles on.

**The plan changed on 2026-08-14 — read DEC-058 first.** This line no longer adds a third and fourth
domain. It finishes music (026), polishes the library shell (027), then builds a **domain contract**
(028) and **per-domain imports** (029) so that games, series and `spotify → music` become epics on
top of a contract, developed in parallel without touching the core. Games and series are named under
"Future epics" in the roadmap and carry no sprint number. `FINAL_SPRINT` is now **29**, and the
project reaches `complete` when 029 closes.

**Sprint 026's product decisions are made — DEC-057 and DEC-059.** An album's status records
possession (`wishlist` / `pending` / `owned`) with no relisten counter and no started/finished dates;
format is an **independent, multi-valued, per-domain tag on the entry**, legal on any status, so
"wishlist → vinyl" works and "sort by owned, see how" is a filter plus a card. Formats reuse shelves'
machinery and none of its meaning — shelves stay the higher tier ("work", "fiction"). Neither needs
re-litigating; both need building.

## Read this first

**The seam model held.** `docs/domain-architecture-proposal.md` section 4 described six seams; all
six landed where it put them, and **DEC-055 is the write-up, including the parts that were clean**.
Two seams reached slightly further than written, and both matter to the next domain:

- **The https upgrade applies to every redirect hop, not just the first URL.** The Cover Art Archive
  answers `http://` in its JSON *and* in both hops of its chain. The allowlist gained a
  `.archive.org` **subdomain** rule because CAA lands on numbered storage nodes
  (`dn710907.ca.archive.org`) that no fixed list can enumerate.
- **The field spec reaches the export, not only the dialog.** The walkthrough caught the Goodreads
  CSV emitting albums as books. The CSV is one domain's view; the entity-shaped JSON is the library.

**The registry is `backend/src/book_tracker/domain/domains.py`.** A `Domain` carries `item_type`,
`label`, `identity`, `fields`, `enriches`, `status_labels` and `recognize`. It is the only place
`"book"` and `"album"` are named, and `DEFAULT_DOMAIN` is what the book-era call sites use.
Providers are selected by `Provider.item_type`, which is what makes "an album search spends no book
request" structural rather than careful.

## What Sprint 025 left behind

- **`GET /api/item-types`** publishes each domain's metadata fields and status-label overrides. The
  metadata dialog, the detail page's facts panel and `/add`'s domain chooser all render from it, and
  the frontend shares one cached query (`features/library/useItemTypes.ts`).
- **`metadata.creators` replaced `metadata.authors`** and `sort_author` became `creator_primary`
  (migration `0012_creators`, no table rebuild — the generated column is VIRTUAL, so SQLite can drop
  and re-add it). The API field and the sort key are both `creator` now. `creator_sort_override`
  stays owner data and is **carried, never recomputed**.
- **`ItemResponse.metadata` is an opaque object** and no longer invents empty defaults (DEC-056): an
  item with no subjects has no `subjects` key.
- **Albums declare no background enrichment**, so nothing queues a job for one. MusicBrainz is only
  ever reached from interactive paths, which is why its ~1.1 s pacing lives in the adapter rather
  than in the job runner's shared `RateLimiter`.
- **Seam 5a only renames statuses.** An album shows "Listened"; it still *has* books' statuses. That
  is the visible one-sprint debt 026 clears.

## Known and left, in the order they are likely to bite

- **The dev library at `data/` gained two real albums on 2026-08-14**: item 8 *Kind of Blue* and item
  9 *Discovery*, both with entries and installed covers. They are walkthrough artifacts, kept
  deliberately as the only mixed-type data on hand. The same session auto-migrated that database
  0011 → 0012 after writing `backups/pre-migration-20260814T220529Z`.
- **The container cannot run a walkthrough against the dev checkout.** `docker compose` runs as uid
  10001 and `data/` is owned by the host user, so it dies with `attempt to write a readonly
  database`. Use `make smoke-container` for the container gate and run the app directly
  (`BOOK_TRACKER_STATIC_DIR=../frontend/dist`) for a library walkthrough.
- **Release selection is arbitrary between same-day originals.** *Kind of Blue* resolved to the mono
  US pressing and *Discovery* to an Australian CD. Both are official releases carrying the group's
  own `first-release-date`; the tiebreak is stable but not meaningful.
- **"Choose a cover" appears on an album and can only say no** — the chooser is Open Library's
  work-editions path. It answers `no_provider_reference` and the dialog explains itself.
- **"Rereads" and "Your reading data" still appear on an album's detail page.** That is Sprint 026's
  product question showing through, not a defect to patch around it.
- One dev-library item has **`OL14454691A` as its creator** — an Open Library author key that reached
  the metadata as if it were a name. Pre-existing; not this line of work's defect.
- Item 7 stores `"O'Reilly Media, Inc."` **with the quotes as part of the value**.
- The list API takes repeated `status=`, not `statuses=`; an unknown parameter is ignored silently.
- `HEAD` on any route returns 405, application-wide.
- "Replace cover" on the detail page is still a raw unstyled `<input type=file>`.
- The orphaned cover file is still not collected; the reclaim is scoped to attachments on purpose.

## State

Migration head `0012_creators`. Worktree clean; all commits local on `sprint-025-albums`, nothing
pushed.
