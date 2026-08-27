# Handoff — the anime line is complete and waiting to be merged

Plan revision 20 is complete. Sprints 001–041 are closed, `docs/agent/state.json` has no
active sprint, and `project_status` is `complete`. Sprint 041 was the final numbered
sprint selected by `scripts/validate_project.py`.

**The work is on the branch `sprint-038-anime`, unpushed and unmerged.** It was cut from
`main` at `bcb11ca` under DEC-053, which says merging back is the owner's call at the
line's close rather than an automatic step. `main` still holds everything through Sprint
037 and is what a failed experiment would be abandoned back to.

## What merging would bring

Four sprints, eleven commits, and a third domain:

- **038** — the `anime` domain: a package, two adapters (AniList, Kitsu), small
  registration points, no migration, no screen written for it.
- **039** — enrichment off the ISBN: a domain declares the identifier it is keyed on, the
  providers that answer it, and what counts as still incomplete.
- **040** — the entry holds a progress count. **One migration on a shared table**
  (`0015_entry_progress`).
- **041** — the MyAnimeList connector, plus `0016_import_kind_is_the_registrys`, which
  deletes a frozen `kind IN ('goodreads','calibre')`.

**Two migrations mean the live database changes on the first real start after a merge.**
It currently holds 16 entries and no `progress` column. Both were applied to a *copy* of
it during the walkthroughs with everything preserved and `integrity_check ok`, but take a
backup before the first start anyway — that is what the nightly backup is for and this is
the one moment it earns its keep.

At closure: `make check` green, `make test` **698 backend / 189 frontend**, Playwright
**103 passed / 2 skipped**, and the owner's real 81-row export imported, triaged and
enriched end to end against a disposable database.

## The verdict the trial run returned

The owner framed this line as a test of the Sprint 028 domain contract. Both halves were
built by a session that did not write them.

- **The domain half held.** ~45 lines of shared registration; no migration; registering a
  third domain broke no existing test.
- **The connector half held in code and failed once in the schema.** `api/imports.py` and
  both import screens were never touched. `ck_import_batches_kind` was a frozen list —
  `ck_entries_status`'s mistake one table over — and cost a migration to delete.

Everything else the line spent went on two seams the export forced, both already foreseen
and priced: enrichment beyond the ISBN (DEC-067 row 3) and a per-domain progress field
(DEC-077). The reasoning is in **DEC-088 through DEC-093**, and the guide has been
corrected from what each sprint found rather than left describing an intention.

## Recurring findings worth carrying forward

- **A test that enumerates what exists today is a test the next change breaks.** Four
  instances in four sprints: `provider_health`, the enrichment revision lists,
  `test_backup.py`'s head revision, and the published importer ids. Assert against the
  registry.
- **A schema constraint that freezes a vocabulary the application owns will be wrong.**
  Two instances now: `ck_entries_status` (DEC-067 row 1) and `ck_import_batches_kind`
  (DEC-093). `grep "CheckConstraint" alembic/versions | grep " IN ("` finds no third.
- **Rebuilding a table is a `DROP TABLE`.** Under `PRAGMA foreign_keys=ON` it cascades
  children away silently. `alembic/env.py` never enables it; that is load-bearing and now
  asserted.
- **A reader tested only against the file in front of you is tested against one file.**
  Sprint 041's connector passed, imported all 81 rows, and still held seven defects the
  owner's export does not exercise (DEC-093).

## Known and unowned

- `goodreads.py` shares two of the defects repaired in the MyAnimeList reader: it calls
  `shelf_slug` unguarded (a 500 on a punctuation-only shelf) and leaves a blank title
  blank (which would 422 a whole import).
- `JobRepository.complete` never clears `error`/`error_code`, so a job that failed then
  succeeded shows `succeeded` beside stale failure text (DEC-091).
- `createEntry`'s body type in `frontend/src/api/add.ts` is out of sync with what
  `AddForm` sends; the extra keys slip past excess-property checking via conditional
  spreads.
- Watched-episode counts do not appear in Triage. That was the owner's scoping decision in
  Sprint 040, not an oversight — worth living with before changing.

## If more work follows

There is no next numbered sprint. New work must be planned explicitly and must reactivate
state through the normal workflow. The unnumbered epics in `docs/sprints/ROADMAP.md` —
games on IGDB, series on TMDB, a Spotify connector — remain possibilities rather than
commitments. Manga is refused by name in the MyAnimeList connector and would be its own
domain, not a mode of this one.

The owner's export sits gitignored at the repository root and is not committed; the
fixtures under `backend/tests/fixtures/imports/` are trimmed and anonymised copies.
