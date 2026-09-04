# Getting your data out — an export proposal

**Status: proposal.** Written 2026-09-04 at the owner's request, alongside
[`ui-cohesion-proposal.md`](ui-cohesion-proposal.md), as the two features that close the
next minor release. It is written to be accepted, rejected, or cut down. Nothing here is
built; nothing here changes what the product currently does.

The owner's words: *"the export feature should follow the principle that we base our
importers on: everyone should be able to easily migrate their data. So exporting to a
common format from the UI, at least the primary data (entries and opinions), should be
supported."*

That principle already has a shape in this repository, and it is the import side:
**a connector declares itself and the shared screen renders the declaration** (DEC-080),
**a domain's source knowledge lives in the domain's own package** (technical spec §6.6),
and **a reader is proven against a real file rather than a mock** (DEC-025). This proposal
is that same shape, pointed the other way.

---

## 1. What exists

Export shipped in Sprint 024 and has not been touched since. It is good work and most of
it survives this proposal intact. Six findings, each traced to a line.

| # | Finding | Where |
|---|---|---|
| 1 | **There is no way to export from the application.** `GET /api/export` is the entire surface. `App.tsx` has no `/export` route, no screen links to it, and the product spec says so in as many words: *"There is no export button in the UI; the route is the surface."* A person who has not read the API docs cannot get their library out. | `product-spec.md:894`, `frontend/src/App.tsx:59-64` |
| 2 | **One domain of five can leave in a format another application reads.** `?format=csv` writes Goodreads' seventeen columns and `continue`s past every row that is not a book. Albums, anime, films and series have only the JSON, which nothing but this application reads. | `application/export.py:421` |
| 3 | **The book-shaped writer lives in a shared layer.** `application/export.py` holds Goodreads' column list, its 1–5 rating halving, its `Exclusive Shelf` spelling and its date format — and branches on the item type to apply them. Sprint 024 predates the domain contract (Sprint 028), and its own comment says it is "one domain's export view, not the export". Under §6.6 that view now belongs beside the reader of the same file, in `domains/book/goodreads.py`. | `application/export.py:297-427` |
| 4 | **The export declares nothing about itself.** An importer publishes a label, ordered guide steps, an empty state and a help URL, and `GET /api/importers` is what the import screen renders (DEC-080). Export publishes one query parameter with two values, so any screen built on it today would have to hard-code what each value is, what it carries and where it goes. | `api/export.py:21-35`, `api/imports.py:157` |
| 5 | **The generic view drops two things the entry knows.** The Goodreads CSV carries status, score, shelves, dates, review and read count, because Goodreads has columns for them. It has nowhere to put `formats` — "I have this on vinyl", which DEC-054 calls out by name as owner data — and nowhere to put `progress`. The JSON carries both. | `application/export.py:273` vs `:349-378` |
| 6 | **The JSON is right and stays right.** Entity-shaped, opaque `metadata`, owner data in and derived data out, attachments by reference plus `sha256` (DEC-054), streamed in bounded keyset batches so peak memory is flat against library size. Nothing below changes it. | `application/export.py:1-24` |

**None of these is a defect in the data model.** The export knows everything it needs to
know; it has no vocabulary for saying it and no door to say it through.

---

## 2. What replaces it

### 2.1 An export view is the mirror of an importer

One new protocol in `domain/exports.py`, shaped like `domain/importers.py`:

```python
class ExportView(Protocol):
    name: str                      # "goodreads", "myanimelist", "letterboxd"
    label: str                     # what the screen calls it
    item_types: tuple[str, ...]    # which domains it can carry
    media_type: str
    lossless: bool                 # whether it is the full record or a view of it
    filename: str
    guide: tuple[str, ...]         # ordered steps: where this file goes, in their app
    help_url: str | None
    carries: tuple[str, ...]       # the entry fields it can express, in words
    def write(self, rows: Iterator[ExportRow]) -> Iterator[str]: ...
```

The split follows the import split exactly. **The shared layer owns the walk** — the
keyset batching, the child-row grouping, the streaming response, the filename header —
and hands the view one row at a time. **The view owns only how a row is spelled.** It
writes no SQL, holds no session, and cannot hold the library in memory even by mistake.

Registration is the fifth shared registration point, and derived the way the fourth is:
`EXPORTS_BY_DOMAIN` is built from what each view declares, never hand-maintained
(`domain/registry.py:43-59` is the pattern).

### 2.2 Every domain gets a table, rendered from its own declaration

One shared view, `table`, that emits a CSV for any domain by **asking the registry** for
that domain's `fields`, `statuses`, `formats` and `entry_field_labels` — the same
declarations `GET /api/item-types` already publishes to every screen. Columns are the
neutral entry layer (title, creator, year, status, score, shelves, formats, dates,
progress, notes) plus the domain's own declared metadata fields under their declared
labels.

This is the floor, and it is what makes the principle true rather than aspirational:
**no domain can be added that cannot be exported**, because the view is written against
the contract rather than against a domain. A spreadsheet opens it; so does anything that
takes a CSV.

### 2.3 The formats the other applications actually read

On top of the floor, a domain declares the spelling its ecosystem imports.

| Domain | View | Read by | Confidence |
|---|---|---|---|
| book | `goodreads` — the seventeen columns, moved to `domains/book/` | Goodreads, StoryGraph, Bookwyrm, Calibre | **Built.** Our own reader parses it. |
| anime | `myanimelist` — the export XML, gzipped | MyAnimeList, AniList, Kitsu | **High.** `domains/anime/myanimelist.py` reads that exact shape, measured against the owner's real file. |
| movie | `letterboxd` — their documented import CSV | Letterboxd, and several tools that take it | **Verify before building.** We read their *export archive* (five tables); their *import* takes a different, simpler file. Sprint 070 confirms the columns against Letterboxd's own documentation before a line is written. |
| series | undecided — IMDb-shaped list CSV is the likely lingua franca | Trakt and others accept it | **Open.** The one real product question here; §6 states it. The `table` floor covers series regardless. |
| album | `table` only | spreadsheets, Discogs-style tooling by hand | **Honest answer.** No service in this space imports a library file. Saying so is better than inventing a format nobody reads. |

### 2.4 The endpoints

```text
GET /api/exports                    → the declarations, for the screen to render
GET /api/export                     → unchanged: the lossless JSON, every domain
GET /api/export?format=csv          → unchanged: kept as an alias of the goodreads view
GET /api/export/{view}?type=<domain> → one view, streamed, named by Content-Disposition
```

Nothing that works today stops working. `?format=csv` is a published contract in the
product spec and in `openapi.json`; it becomes an alias rather than a deprecation.

### 2.5 The screen

The export surface renders the declarations and nothing of its own: one row per view,
carrying its label, what it carries in words, how many entries it would write for the
library as it stands, the guide steps for the application it is going to, and a download.

Two consequences worth stating because they are the point of the design:

- **Adding a format later costs no frontend work.** Sprint 070 adds two views and changes
  no `.tsx` file. If it does, the declaration is not carrying its weight.
- **A domain with nothing but the `table` view still gets a complete row**, because
  "carries", "how many" and "where it goes" are all declared.

### 2.6 Verified by the importer standing next to it

Every format in §2.3 except the series decision is a format this repository **already
reads**. So the test is not "does the file look right":

> Export a seeded library through a view, feed the bytes to that domain's own importer,
> and assert the entries come back with the same status, score, dates, shelves and
> progress.

That is a real round trip over a real parser, and it is exactly the standard DEC-025 sets
for a boundary. Where a target's importer is not ours — Letterboxd's — the round trip is
run by the owner against their own account, and the sprint says so rather than claiming
coverage it does not have.

---

## 3. Where it goes

| Option | What it means | For | Against |
|---|---|---|---|
| **A third tab on `/import`** *(recommended)* | The screen becomes the one place data enters and leaves. The numbered workflow strip keeps Import (1) and Triage (2); Export joins it unnumbered, because it is not a step of importing. `/export` becomes a real address that lands there, the way `/triage` lands on `?tab=triage`. | One destination for "move my data"; the connector guide component, the tab machinery and the declaration-rendering pattern are already there and get reused rather than copied. | The nav item says *Import*, and someone looking for export will not read that word as "and out". Fixed by copy: the item becomes **Data**, or **Import & export** if the owner prefers the longer label. |
| Its own nav item `/export` | A sixth top-level destination. | Impossible to miss. | Six items in a bottom bar at 390px, for a screen used a handful of times a year. DEC-079 removed a nav item for less. |
| A control on the library header | Export what you are looking at, filters and all. | Filtered export falls out for free. | The header is the search bar and Add; this is the fourth thing competing for it, and a whole-library export is not a library-page action. Worth revisiting *after* the tab exists — see §5. |

**Recommendation: the first.** The copy decision — *Data* versus *Import & export* — is the
owner's, costs one line either way, and does not block the work.

---

## 4. What it costs

Three sprints, split so that the release stays coherent if it is cut short.

| Sprint | Delivers | Frontend |
|---|---|---|
| **[068 — Export the way we import](sprints/068-export-the-way-we-import.md)** | The `ExportView` contract, the registry point, the shared streaming walk, the `table` view for every domain, the Goodreads writer moved into `domains/book/`, `GET /api/exports` and `GET /api/export/{view}`. Round-trip tests through the existing importers. | **None.** |
| **[069 — A door out of the app](sprints/069-a-door-out-of-the-app.md)** | The export tab: declarations rendered, entry counts, guide steps, download, empty and failure states, 390px and axe. After this sprint the feature is complete and usable for every domain. | All of it. |
| **070 — Their formats, not ours** (no surviving file — withdrawn by DEC-136) | The MyAnimeList XML view, the Letterboxd CSV view, and the recorded decision for series. Each verified by round trip. | **None** — and that is the acceptance criterion that proves §2.5. |

**If the release has to be cut, cut 070.** After 069 every domain can leave in JSON and in
a CSV, from a button, which satisfies the owner's principle. 070 makes the landing softer
at the other end.

---

## 5. What this proposal deliberately does not do

- **No attachment bytes.** DEC-054 stands: references plus `sha256`, because the digest
  resolves against any backup and bytes turn a file you can read into a multi-gigabyte
  archive. The nightly backup is still the restore story; export is still portability.
- **No scheduled, automatic or remote export.** No cron, no cloud target, no share link.
  A share link needs auth, which is a v2 deferral (product spec §9).
- **No re-import of our own JSON.** Moving to a *new Akasha instance* is a real need and
  the JSON is already lossless, so an `akasha` importer is roughly half a sprint against
  a pipeline that already does matching, preview, commit and undo. It is deliberately not
  in this line: the owner asked for the door out, and this is a door back in. Cheap to
  pull forward if wanted.
- **No filtered export** — "export this shelf", "export what I finished this year". The
  library already computes exactly that filter, so it is a small addition *later*, and it
  is the one thing that would justify revisiting option three in §3. Not now: the first
  export should be the one that cannot lose anything.
- **No new metadata and no new columns in the database.** Every value in every view is
  already stored.
- **No cover or ebook archive.** Same reason as attachments.

## 6. Risks

- **We cannot test somebody else's importer.** A target changes its columns and our view
  silently stops fitting. Mitigated by round-tripping through our own reader where we have
  one, by naming the measurement date in the view's own module the way every importer here
  does, and by the owner running one real import at the far end during the walkthrough.
- **Series has no obvious target, and picking one on documentation alone is how this
  repository gets things wrong** (DEC-088, DEC-127 both measured instead). Sprint 070 must
  either measure a target or record that the `table` floor is the answer for series. Both
  are complete answers; guessing is not.
- **CSV injection.** `_safe_cell` neutralizes leading `=`, `+`, `-`, `@` today. Every new
  view that writes a spreadsheet format inherits that rule, and a test per view enforces
  it — a notes field is free text and this is a file whose purpose is to be opened in
  Excel.
- **Streaming discipline is easy to lose at a new seam.** The reason `application/export.py`
  selects columns rather than entities is that an ORM identity map holds the whole library
  (its own comment records the regression). A view that materializes rows to sort them
  would undo that quietly, so the memory test in `test_export.py` must cover every view,
  not only JSON.
- **`?format=csv` must keep working**, including its exact filename and media type. It is
  in `openapi.json` and in the product spec, and someone's script may already call it.
