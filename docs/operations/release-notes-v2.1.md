# Akasha v2.1 — release notes

**A list you wrote yourself becomes a library.** Every importer until now read
an export some platform produced, whose per-row identifiers made matching a
solved problem. v2.1 adds the first source with none: a spreadsheet a person
typed — a title column, an author column, nothing else — imported by
**search-then-confirm**. Akasha searches the providers for each row in the
background, proposes the matches it found, and you confirm, fix or drop each
one before anything lands.

**Tagged `v2.1.0`.**

## A note on versioning

`2.1.0` is a feature release with **no breaking change and no owner action**:
`docker compose pull && docker compose up -d`, the same two commands as
always. The pre-upgrade backup still runs on startup. One migration is added
(`0022_import_proposals`, a new table only); the search phase is new state on
new batches and touches nothing existing.

## What's new since v2.0.0

- **Custom list — a hand-written CSV/TXT importer** (Sprint 083, DEC-156).
  Drop a comma/semicolon/tab file; the title and author columns are found
  from the headers (Spanish and English, accents folded) or the first two
  columns, and can be picked by hand on the screen. Only title and author are
  read — the spreadsheet's other columns ride along visible but unmapped,
  per the recorded decision. The preview stays open while one durable
  background job searches the row's own domain's providers, **sequentially,
  one row at a time**, within the provider budgets; commit is refused until
  the search drains. Each row offers up to ten ranked proposals — cover,
  title, authors, year, language, provider — three rendered with the rest
  behind *Show more*.
- **Confirm, fix, or drop — per row** (Sprint 083, DEC-159). Confirming one
  proposal fills the row from the provider's full payload: the ISBNs, the
  year, the publisher the spreadsheet never had, and a cover a few seconds
  later through the same enrichment path the add screen uses. *None of these
  — keep as typed* leaves the row as your spreadsheet wrote it. *Wrong text?
  Edit and search again* fixes a bad query on any row — the transposed
  author/title row in the fixture imports as what it was meant to be.
  *Don't import this row* keeps a row out of the commit entirely, and the
  commit button's counts say so. Undo restores everything for 24 hours.
- **Triage's Discard action** (DEC-157). Selecting rows on the Triage tab now
  offers a red *Discard*: one confirmation dialog, one request, the selected
  entries are gone. Previously the only way out was deleting rows one by one
  from the detail page.
- **Detail returns to where you came from** (DEC-157). Opening a book from
  Triage and going back lands on Triage, not the Library — the back control
  names the screen that opened it. Deep links keep going to the Library.
- **`akasha-prune`** (DEC-158). An operator command that collects what no
  entry of any user references anymore: items with no entries and no import
  claim, their cover files, cascaded identifier rows, orphaned covers, and
  blobs nothing shares. Dry-run by default; `--apply` acts. The delete
  dialogs no longer promise a cache they cannot prove — with the command
  existing, the cache is an operator's choice, not a silent forever.

## What an existing install has to do

**Nothing.** The new importer waits in Data → Import as a new source card;
nothing about existing connectors, libraries or sessions changes.

## For the operator

- New API routes for the confirm flow are user-scoped like every import
  surface; the isolation inventory and the OpenAPI contract carry them
  (`POST …/records/{rid}/proposal|exclude|include|search`).
- The provider search a list import runs is **budgeted** (DEC-045's
  background half): a capped provider defers to the next day's window
  without spending attempts, and the per-row editing spends interactive
  budget, which is recorded but never blocks. `AKASHA_PROVIDER_DAILY_LIMITS`
  stays the dial.
- An upgrade on the board is the usual variable: set `AKASHA_VERSION=2.1.0`
  (or track `2.1`), `docker compose pull && docker compose up -d`.

## What still isn't here

Everything DEC-146 §4 deferred stays deferred — sharing, Calibre write-back,
OPDS, passkeys, email, per-user settings. Mapping a list's extra columns
(Editorial, Idioma, …) to domain fields is recorded as future work for
whatever spreadsheet a future user brings ("queda a futuro").
