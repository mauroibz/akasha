# Sprint 075 — Identity in the schema

**Status:** in_progress
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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
