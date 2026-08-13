# Akasha v1 — release notes

A self-hosted, keyboard-first personal book tracker. It tracks opinions, not
ebook files: what you thought of a book, when you read it, and where it sits in
your library. Built to run on one small home server.

**Tagged `v1.0.0`** during Sprint 019, at the owner's request. The tag sits at
`4ccf431`, the last commit before post-v1 work began, so it includes the brand
and the CI repairs that followed Sprint 018 and none of Sprint 019.

The tag is local. Nothing is pushed by the agent workflow, tags included, so
publishing it is `git push origin v1.0.0` when you want it on the remote.

## What v1 does

- **Library.** Ten thousand entries stay responsive: a virtualized grid and a
  compact view, keyset pagination, and six sorts. Text sorts and search are
  accent-insensitive, so `avila` finds `Ávila`.
- **Adding books.** Search Open Library and Google Books, or enter a book by
  hand. Covers are fetched and stored locally; providers are never consulted
  while rendering a page you already have.
- **Opinions.** Score out of ten, status, dates, reread count, free-text notes,
  and shelves. Your opinions are never overwritten by a provider — refreshing
  metadata is always an explicit action.
- **Triage.** A keyboard rhythm for working through an inbox: `j`/`k` to move,
  digits to score, letters to set status, `Enter` to accept.
- **Imports.** Goodreads CSV and a read-only Calibre library, both with a
  preview before anything is written and an undo afterwards.
- **Enrichment.** A durable job queue fills in metadata and covers in the
  background, retrying failures and surviving a restart.
- **Accessibility.** Twelve automated axe checks gate every release, and both
  list surfaces are proper ARIA feeds.

## What v1 deliberately does not do

- **No authentication, and therefore LAN only.** This is the single most
  important limitation. There is no login, no user accounts, no authorization.
  Do not expose it to the internet.
- **No multi-user support.** One library, one set of opinions.
- **No ebook storage, reading or syncing.** Calibre is read, never written.
- **No cross-provider metadata merging.** A book takes its metadata from one
  provider; combining fields across providers is assessed in Sprint 020.
- **No mobile apps.** It is a responsive web application.

## Operating it

See `docs/operations/runbook.md` for install, upgrade, rollback, backup,
restore and reverse-proxy guidance. The short version: one container, two bind
mounts plus a read-only Calibre mount, a nightly cron entry for backups, and a
restore that has actually been performed rather than described.

## Known issues carried into v1

- `s` on the triage page does nothing, and no longer promises to: the spec
  listed it as the shelf-autocomplete shortcut, and Sprint 019 retired it
  unbuilt rather than carrying it further (DEC-043). Shelves are assigned from
  a book's detail page. Triage's *Add shelves* bulk action is still unbuilt.
- Author sort is a first-name sort, because providers give `authors[0]` in
  natural order. "Adolfo Bioy Casares" sorts before "Jorge Luis Borges".
- Some providers return an "image not available" placeholder that is stored as
  though it were a real cover.
- Entries added through the UI carry no score until you set one, and imports
  land as `unsorted`, so the library looks briefly as though an import did
  nothing.
