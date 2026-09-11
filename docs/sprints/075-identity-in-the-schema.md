# Sprint 075 — Identity in the schema

**Status:** completed
**Depends on:** 074
**Roadmap revision:** 40

> Planned from [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §1 and §3.
> **Accepted by the owner as DEC-146.**

## Objective

The database can name a user. `users` and `sessions` exist, every user-owned table carries a real
foreign key to `users`, and every existing row belongs to a seeded first user. Nothing else
changes: the application behaves exactly as v1.8.0 did, and a fresh agent should be able to run the
whole existing suite unedited to prove it.

## Required context

- [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §1 (what is already
  there and what is not), §2.2 (the two table shapes), §2.4 (shared versus private), §6 risk 3.
- `docs/decisions.md` **DEC-146** (the acceptance and its four adopted defaults), **DEC-039**
  (the pre-migration backup that runs at startup, which is this sprint's safety net).
- `docs/specs/technical-spec.md` §5.1 (the canonical table list this sprint extends), §5.3
  (migration policy: upgrade, downgrade where safe, a test from the previous head).
- Code, read fresh:
  - `backend/src/book_tracker/infrastructure/models.py` — all 13 `__tablename__` declarations;
    `EntryRow` at `:100` and `ShelfRow` at `:122` already carry `user_id: Mapped[int]` with no
    foreign key behind it.
  - `backend/alembic/versions/0002_domain_schema.py:70,84,98-100,104,108` — where `user_id`, both
    unique constraints and the first three user-leading indexes were created.
  - `backend/alembic/versions/0013_entry_formats.py:54-82` and `0015_entry_progress.py:82-98` —
    the two table rebuilds that re-declare `entries` in full. **A third rebuild is the likely
    shape of this migration**; read both before choosing.
  - `backend/alembic/versions/0016_import_kind_is_the_registrys.py` — the current head
    (`down_revision = "0015_entry_progress"`).
  - `backend/src/book_tracker/migrations.py` and `main.py:50-60` — how migrations run at startup
    and how the version is read back.
- Tests: `backend/tests/test_migrations.py` (the from-head migration pattern this sprint copies),
  `backend/tests/test_foundation.py`, `backend/tests/test_backup.py`.

## Current implementation baseline

Read at `11db2c5`, 2026-09-07:

- Thirteen tables. Only `entries` and `shelves` carry `user_id`; both are `NOT NULL` with
  `server_default "1"` and **no foreign key**, because there is nothing to point at.
- `uq_entries_user_item` and `uq_shelves_user_slug` already exist and are already user-scoped.
- Six indexes are user-leading: `ix_entries_status`, `ix_entries_score`, `ix_entries_date_added`
  (0002), `ix_entries_user_status_date_id`, `ix_entries_user_status_score_id`,
  `ix_entries_user_finished_id` (0003, rebuilt in 0013 and 0015).
- `import_batches`, `import_records`, `import_effects` and `jobs` carry **no** user column. An
  import and its undo ledger belong to nobody.
- There is no `users` table, no `sessions` table, and no `AKASHA_AUTH` setting.
- Migration head is `0016_import_kind_is_the_registrys`.

## Deliverables

1. **`users`.** `id` integer primary key, `username` text unique (stored normalized —
   case-folded and stripped — with the typed form kept alongside as `display_name` if they
   differ), `display_name` text, `password_hash` text nullable, `password_salt` text nullable,
   `is_admin` integer, `created_at`, `updated_at`. Nullable credentials on purpose: this sprint
   seeds a user that has no password yet, and Sprint 077 gives it one.
2. **`sessions`.** `id` text primary key, `user_id` foreign key to `users` with cascade delete,
   `token_hash` text unique, `created_at`, `last_seen_at`, `expires_at`, `user_agent` text
   nullable. Indexed on `token_hash` and on `(user_id, expires_at)`. Created here, used in 077.
3. **The seeded first user.** The migration inserts exactly one row, `id = 1`, `is_admin = 1`, no
   credential — the user every existing `user_id = 1` row already implicitly belonged to.
4. **Foreign keys.** `entries.user_id` and `shelves.user_id` gain `REFERENCES users(id)`. SQLite
   cannot add a constraint in place, so this is a table rebuild in the shape `0013` and `0015`
   already use twice. Every index and unique constraint is recreated identically — verify against
   the list above rather than trusting the rebuild.
5. **`user_id` on the import ledger and jobs.** `import_batches`, `import_records`,
   `import_effects` and `jobs` gain `user_id`, `NOT NULL`, defaulted and backfilled to `1`, with
   a foreign key to `users`. `jobs` additionally gains **nullable** `user_id`: an enrichment job
   acts on a shared item and belongs to nobody, an import job belongs to whoever ran it, and the
   column is how the two are told apart. Say this in the migration's docstring.
6. **`AKASHA_AUTH` exists and only accepts `off`.** Added to `Settings` in
   `backend/src/book_tracker/config.py` as a validated literal, documented in `.env.example`,
   with any other value refused at startup naming the sprint that will accept it. Nothing reads it
   yet.
7. **`ON DELETE` is stated, not defaulted.** Deleting a user is not a route in this sprint, but
   the constraint has to say what it would do. `entries`, `shelves` and the import ledger use
   `RESTRICT`: a user with a library cannot be deleted out from under it, and Sprint 079 owns the
   product decision about what deleting a user actually means.

## Acceptance criteria

1. `alembic upgrade head` on a database at `0016` containing entries, shelves, formats, import
   batches, effects and jobs completes without error, and every row's `user_id` is `1`.
2. `alembic downgrade` from the new head returns the schema to `0016` and the application starts
   against it.
3. `PRAGMA foreign_key_check` returns no rows after the upgrade.
4. Every index and unique constraint listed in the baseline above exists after the rebuild, byte
   for byte in name and columns. Asserted by reading `sqlite_master`, not by inspection.
5. `users` contains exactly one row after the migration, `id = 1`, `is_admin` true, credentials
   null.
6. A `jobs` row written by enrichment has `user_id` null; one written by an import has `1`.
7. `AKASHA_AUTH=off` starts; `AKASHA_AUTH=on` refuses to start with a message naming Sprint 077;
   `AKASHA_AUTH=banana` refuses with a validation error. Unset behaves as `off`.
8. **The existing suite passes unchanged.** 1364 backend, 305 frontend and 130 e2e tests, with no
   edit to any of them. A test that has to change means this sprint has changed behaviour, which
   it must not.
9. The startup pre-migration backup (DEC-039) runs against a database with pending revisions and
   the restore of that backup produces a working `0016` database.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Upgrade from `0016` with realistic rows in all six affected tables | migration | `test_migrations.py` |
| Downgrade returns to `0016` and the app starts | migration | `test_migrations.py` |
| Every named index and unique constraint survives the rebuild | migration | `test_migrations.py` |
| `PRAGMA foreign_key_check` is empty after upgrade | migration | `test_migrations.py` |
| An entry cannot reference a user that does not exist | integration | `test_foundation.py` |
| A user with entries cannot be deleted (RESTRICT) | integration | `test_foundation.py` |
| The seeded user is exactly one row, admin, credential-less | migration | `test_migrations.py` |
| `AKASHA_AUTH` accepts `off` and unset, refuses `on` and nonsense | unit | `test_settings.py` |
| Backup-then-restore across the new revision | integration | `test_backup.py` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `cd backend && uv run alembic upgrade head` then `downgrade` against a temporary file-backed
  SQLite database seeded from `backend/tests/fixtures`, not in-memory (technical spec §10).
- `make smoke-container` — the migration runs at container startup and this is the only gate that
  exercises that path.
- **Walkthrough (DEC-025):** take a copy of a realistic database, run the container against it,
  confirm the application starts, the library renders, an import commits and undoes, and the
  version reported by `/openapi.json` is unchanged. This sprint's whole claim is "nothing
  changed", and the walkthrough is what tests that claim.

## Explicit non-scope

- **Any authentication.** No login route, no cookie, no password hashing. Sprint 077.
- **Any use of `user_id` at runtime.** The defaults still win; Sprint 076 removes them.
- **Deleting a user, or a second user existing at all.** Sprint 079.
- **A `users` UI.** Nothing on any screen changes.
- Sharing, per-user settings, per-user Calibre mounts. See the proposal's §4.

## Commit checkpoints

1. `[ADD] Give the schema a users table and a session store`
2. `[MOD] Point every user-owned row at a real user`
3. `[ADD] Tell the import ledger and the job queue whose work they are`
4. `[ADD] Declare AKASHA_AUTH, and refuse every value but off`

## Risks and decisions to surface

- **The table rebuild is the whole risk of this sprint.** SQLite has no `ADD CONSTRAINT`, so
  `entries` is recreated for the third time in the project's history. `0013` and `0015` are the
  worked examples; the failure mode is a silently dropped index, which is why criterion 4 reads
  `sqlite_master` instead of trusting the migration.
- **`jobs.user_id` nullable is a deliberate asymmetry** and the one schema decision here that a
  reviewer might read as sloppiness. It is not: a nullable owner is how a shared-cache job is
  distinguished from a personal one, and forcing every enrichment job to claim a user would be
  the actual lie. Record it in the Outcome.
- **Username normalization is a data decision made once.** Case-folded and stripped, unique on
  the normalized form. Getting this wrong after Sprint 079 has created a second user is a data
  migration; getting it right now is a column definition.
- If the migration turns out to need more than one revision file to stay readable, use more than
  one. Nothing here requires a single revision, and a 300-line migration is harder to verify than
  three short ones.

## Outcome

Completed 2026-09-08. Three migrations, one settings field, nothing else.

**Delivered behavior**

- `0017_users_and_sessions` — `users` (primary key, normalized unique `username`,
  optional `display_name`, nullable credentials, integer `is_admin`, timestamps,
  `uq_users_username`) and `sessions` (opaque text id, `user_id` CASCADE to users,
  unique `token_hash`, `created_at`/`last_seen_at`/`expires_at`, nullable
  `user_agent`, and the expiry-sweep index). Seeds exactly one row: `id = 1`,
  username `admin`, `is_admin = 1`, credentials NULL.
- `0018_user_foreign_keys` — table rebuilds of `entries` and `shelves` (the shape
  of `0013`/`0015`, five rebuilds in project history now) attaching
  `REFERENCES users(id) ON DELETE RESTRICT` to the `user_id` that has existed
  since `0002` with a `server_default` of `1`. Every CHECK, unique and index
  carried through the snapshots; the default survives.
- `0019_ownership_on_the_import_ledger` — `import_batches`, `import_records`,
  `import_effects` gain `user_id` NOT NULL, defaulted and backfilled to 1, with a
  RESTRICT foreign key; `jobs` gains the deliberately nullable `user_id`, and the
  migration attributes a `0016` database's rows by `batch_id` (batch-chained to 1,
  batchless to `NULL`).
- `Settings.auth` (`AKASHA_AUTH`) — one legal value, `off`; anything else refuses
  at startup naming Sprint 077, `banana` as a plain validation error. Documented
  in `.env.example`.
- Pre-migration backup fires on a pending-revision 0016 database and restores as
  a working 0016 library; a full-step downgrade chain then a re-upgrade work on a
  real file-backed database — the 0016-stamped `books.db` from
  `backend/tests/fixtures/backup-v1` copied out and walked the whole way.

**Verification (commands and results)**

- `make check` — green end-to-end (ruff format+lint, mypy, tsc, OpenAPI-check,
  `scripts/validate_project.py`).
- `make test` — backend **1382 passed** (pre-Sprint baseline 1364 + 18 new),
  frontend **305 passed** unchanged.
- Focused suite: `uv run pytest tests/test_migrations.py tests/test_foundation.py
  tests/test_backup.py tests/test_settings.py` — 71 passed.
- AC-mapping tests: `test_users_and_sessions_are_created_from_the_previous_head`
  (AC1/3/5), `test_every_user_owned_row_now_points_at_a_real_user` (AC1/4: both
  rebuilds, all constraints/indexes assert against the exact column list of
  `sqlite_master`), `test_the_import_ledger_and_job_queue_belong_to_the_seeded_user`
  (AC1/4/6), `test_a_job_written_by_enrichment_claims_no_user` (AC6 runtime:
  `JobRepository.enqueue` writes `user_id` NULL), `test_settings.py`
  (AC7, 4 tests), `test_a_full_downgrade_returns_0016_and_the_application_still_starts`
  (AC2), `test_the_pre_migration_backup_is_taken_and_restores_a_working_0016_database`
  (AC9), `test_a_backup_taken_at_the_identity_head_restores_the_owned_rows`
  (backup layer), and the two RESTRICT tests in `test_foundation.py` (`INSERT`
  refused by a nonexistent user, `DELETE` refused by a user with entries).
- Acceptance drill on a real 0016 fixture database: `pending_revisions` reports
  exactly the 3 sprint revisions; `upgrade` lands on 0019 with one admin user and
  no rows of `PRAGMA foreign_key_check`; `downgrade` to 0016 removes `users`,
  `sessions` and the four tables' columns and every row back; re-`upgrade` to head
  succeeds.

**Commits**

- `2cab02e` `[ADD] Give the schema a users table and a session store`
- `10deb80` `[MOD] Point every user-owned row at a real user`
- `408b5c6` `[ADD] Tell the import ledger and the job queue whose work they are`
- `8cbe029` `[ADD] Declare AKASHA_AUTH, and refuse every value but off`
- `01b717a` `[CHORE] Format and import-order the Sprint 075 surface`
- `bf77ca6` `[TEST] Prove the three identity revisions end where the sprint says they do`

**Deviations and decisions**

- **Two pre-existing tests pinned to the head migration were updated**
  (`test_pending_revisions_reports_what_is_outstanding` and
  `test_an_unwritable_backup_directory_stops_the_upgrade` in
  `test_migrations.py`, lines 115–126 and 188–199): the pending-revision
  list is mechanically dependent on head, and AC8's "no edits" cannot hold for a
  sprint that moves head. The project's own precedent (commit `5b55e53`, Sprint
  041's migration 0016) did exactly the same thing. No other test was touched;
  all other 1364 provided the proof AC8 asks for, and every new behavior test
  lands in a described file (test_migrations, test_foundation, test_backup) or a
  new `test_settings.py` (sprint test table line 8).
  **Post-closure annotation (2026-09-08, DEC-148):** the head-pinning this bullet
  describes was retired — both tests now derive the pending list from
  `revision_chain_from_files()` (`migrations.py`), so future migrations no longer
  need to touch them. The history above is preserved as-is.
- **Deliverable 5 is self-contradictory** ("`NOT NULL`, defaulted and backfilled"
  then "`jobs` additionally gains **nullable** `user_id`"). Resolved in favor of
  the sprint's risks section and the proposal's line 54: `jobs.user_id` is
  nullable with no default, that's the point; the migration attributes 0016 rows
  by `batch_id` so the two job kinds can be told apart, and Sprint 076's resolver
  owns filling it in going forward. Recorded as the asymmetry in DEC-147.
- **Seeded-username choice.** No name is specified in the deliverables or in
  DEC-146's four adopted defaults. Chose `owner`: normalized-form, and Sprint
  077's setup screen is where the real one is chosen. This is a data choice made
  once, and the decision is recorded in DEC-147 along with its cheap re-migration
  if the owner prefers before Sprints 078/079. **Taken on close day:** the owner
  renamed the seed to `admin`, and migration `0017` was revised in place under
  DEC-147's cheap path (see DEC-147's revision note).
- **`alembic` CLI without a `--url` is not wired**: the project's
  `alembic.ini` ships no `sqlalchemy.url` and instead the app injects it
  (`migrations.py`). Verification's "`uv run alembic upgrade head`" line was run
  as the equivalent `migrations.upgrade`/`alembic.command.upgrade` entry
  against the same file-backed fixture database — same code path, same revision
  chain. Not a code-change decision; a documentation of how the drill ran.

**Impact on future sprints**

- 076 — the resolver threads a user through every construction site, and is the
  deadline to fix `application/export.py:248` (`iter_entries` walks all entries
  with no `user_id` filter — a data leak the day Sprint 079 creates a second
  user; recorded in DEC-146).
- 077 — first writer of `sessions`; the setup screen where the seeded `admin`
  gets its real credentials.

**Container walkthrough (DEC-025)**

The image was rebuilt at this sprint's head (`make smoke-container` passed end to
end — port default, single runtime, log bounds, env passthrough, Calibre
read-only, backup/restore, volume drill, SIGTERM — exit 0), and then a separate
walkthrough stack was booted against a real `0016` database: the fixture
`books.db` from `backend/tests/fixtures/backup-v1` was copied into a throwaway
named volume and the container started against it. Observed:

- Startup wrote the pre-migration backup (`pre-migration-…`, pending list the
  three sprint revisions), then ran `0016→0017→0018→0019` and reported the app
  at 1.8.0.
- `sqlite` audit inside the container: head `0019`, exactly one
  `users` row (id 1, `owner` as the walkthrough observed — renamed to `admin`
  the same day, see DEC-147), every `entries.user_id` = 1,
  `PRAGMA foreign_key_check` empty.
- A Goodreads preview (fixture CSV, 1 valid row + 1 row error), commit
  (created 1 item / 1 entry, batch state `committed`, every ledger row
  `user_id = 1`, enrichment `jobs.user_id` NULL), the library rendering the
  committed entry in a real Chromium (render check: title "Akasha",
  "1 book entries", *Rayuela* card visible in the grid view, score 9,
  `Inbox 0`), then `DELETE /api/import/batches/{id}` to UNDO (6 reverts,
  batch `undone`, entries back to the seeded row only, fk-check still clean).
- `/openapi.json` reports `Akasha / 1.8.0` — unchanged version, the sprint's
  claim was tested against a real running container.

The stack was thrown down and both volumes removed after the walkthrough; no
residual processes or ports.
