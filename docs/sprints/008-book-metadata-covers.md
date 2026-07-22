# Sprint 008 — Working book metadata and covers

**Status:** completed
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

Delivered normalized Open Library nested-edition/work/author fetching, edition/original-year
separation, optional same-ISBN Google Books fill-empty merging, and retained source identities.
Migration `0005_book_metadata` converts legacy `publishers` arrays without replacing a canonical
publisher. Typed metadata responses and partial patches support explicit clearing.

Covers now use bounded HTTPS redirects restricted to provider/archive hosts, byte/pixel/type limits,
atomic JPEG installation, ordered cover-ID/OLID/ISBN fallback, old-cover preservation, and controlled
versioned `/api/items/{id}/cover` serving. Search, virtual rows/cards, and detail/edit/refresh expose
cached covers, authors, edition/original years, and all standard metadata without render-time provider
calls.

Commits: `62861fa` (metadata/cover boundary and UI), `85bcc86` (roadmap insertion and contracts), and
`2e9ff12` (live-discovered cover/year fallbacks). Verification: 85 backend and 15 component tests;
eight normal Chromium flows plus two opt-in live/offline flows; validation, format, lint, mypy,
TypeScript, OpenAPI check, build, and `git diff --check` pass. The live smoke selected Cien años de
soledad (2012), Harry Potter (2015), and La sombra del viento (2005), cached all covers, then rendered
all three after restart with provider proxies disabled.

Deviation: the official Open Library cover service redirects through `archive.org` and dynamic
`*.us.archive.org` hosts, so those narrowly scoped HTTPS hosts are included in the allowlist. Some
work search rows omit nested edition data; one bounded editions lookup resolves the leading result
instead of accepting an arbitrary `edition_key`. Both behaviors were discovered and verified live.
