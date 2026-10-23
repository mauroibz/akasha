# Sprint 110 — Where things are, and who has them: underneath

**Sprint:** 110
**Status:** ready
**Roadmap revision:** 49
**Depends on:** 109
**Owner:** Mauro

## Objective

An entry can record where its copy is ("Living room, shelf 2") and who has it on loan, since
when, and when it came back. This sprint builds the model and the API; Sprint 111 the screens
(DEC-176 point 2).

## Required context

- DEC-176; DEC-059 (formats are a vocabulary, not copies); DEC-167.
- `infrastructure/models.py` (`EntryRow`), the latest migration (0027), `application/library.py`
  (`update_entry`, `_entry_dict`, entry listing filters), `api/library.py` (entry `PATCH`,
  `EntryResponse`, list query parameters), `application/export.py`.

## Current implementation baseline

Entries hold no location and no loan. Formats say how a thing is held, not where.

## Deliverables

1. Migration 0028: `entries.location` (nullable text, trimmed, at most 120 characters) and a
   `loans` table: `id`, `entry_id` (cascade), `person` (text, required), `lent_on` (date,
   required), `returned_on` (nullable date), `note` (nullable), timestamps. At most one open loan
   per entry, enforced by a partial unique index.
2. Entry `PATCH` accepts `location` (blank clears). `EntryResponse` carries `location` and the
   open loan, if any.
3. `POST /api/entries/{id}/loans` lends (409 when one is open); `PATCH /api/loans/{id}` records
   the return or corrects a field; `DELETE /api/loans/{id}`; `GET /api/entries/{id}/loans` the
   history.
4. `GET /api/loans?open=true`: what is out, oldest first, with the entry. `GET /api/locations`:
   the owner's distinct locations with counts, for autocomplete and a filter.
5. The library list accepts `location=` and `lent=true` filters.
6. Lossless JSON export carries location and loans. Shared across every domain: no domain
   declaration, since where a thing is and who has it apply to all of them.

## Acceptance criteria

1. Location round-trips and clears; over-length is 422.
2. A second open loan is 409; returning one allows the next; deleting an entry deletes its loans
   (foreign keys on).
3. `/api/loans?open=true` lists only open loans of the current user (auth on: another user's
   loans are invisible).
4. Migration 0028 up and down on a real temporary SQLite copy.

## Required tests (TDD)

API and repository tests for each criterion; a migration test; the export test.

## Verification

Per DEC-167: backend tests for the changed modules, `make check` (OpenAPI regenerated).

## Explicit non-scope

Screens (111). Reminders or due dates on a loan. Per-format locations.

## Commit checkpoints

`[ADD]` migration, model and API; `[DOCS]` close.

## Risks and decisions to surface

- A person is free text, not a user of the install; the People page is for accounts.

## Outcome

_Not started._
