# Sprint 008 — Working book metadata and covers

**Status:** in_progress
**Depends on:** 007
**Roadmap revision:** 3

## Objective

Create the shared edition-metadata and cached-cover boundary used by interactive adds, Calibre,
Goodreads enrichment, refresh, and manual editing. Open Library is primary; optional Google Books
fills missing fields only for an ISBN-identical edition.

## Required context

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 2–5
3. `docs/specs/technical-spec.md` sections 4–10
4. `docs/decisions.md` DEC-002, DEC-007, DEC-008, DEC-009, DEC-010, DEC-013, DEC-016
5. `docs/sprints/005-providers-add-api.md`, `docs/sprints/006-add-detail-edit-ui.md`, and roadmap 008–013
6. `docs/agent/WORKFLOW.md`, last worklog entry, and `docs/agent/HANDOFF.md`
7. Provider, cover, add/library API/service/repository code and their backend/frontend/browser tests

## Acceptance criteria (ordered, TDD)

1. Open Library selects a relevant nested edition; resolves edition/work/author records; keeps edition
   and original years distinct; and normalizes the standard metadata, identifiers, and cover fallback.
2. Optional Google Books fills only absent fields for the same canonical ISBN, retains every source
   reference, and never merges disagreeing exact identities.
3. Legacy `publishers` arrays migrate to singular `publisher` without replacing canonical values;
   API metadata responses/patches are typed, partial patches merge, and explicit null clears a field.
4. Covers follow bounded allowlisted HTTPS redirects, reject defaults/malformed/oversized images,
   install atomically, preserve old covers on failure, and serve through a versioned controlled API URL.
5. Search, virtual library, and detail show cached covers, authors, edition year, and labelled original
   year where relevant; editing covers every standard field and refresh preserves omitted values.
6. A live three-title browser smoke verifies add/cache/offline rendering for the titles named in the
   sprint plan and records the actual selected editions and years.

## Verification

`python scripts/validate_project.py`, focused backend/component/Chromium tests, `make format`,
`make check`, `make test`, `make build`, and `git diff --check`.

## Explicit non-scope

Calibre import, Goodreads enrichment jobs/undo, speculative providers, and network access during
cached library/detail rendering.

## Outcome

_In progress._
