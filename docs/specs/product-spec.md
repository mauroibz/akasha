# Book Tracker — Product Spec v1

**Status:** approved baseline for v1 implementation
**Owner:** Mauro
**Deploy target:** self-hosted, ZimaBoard 2, Docker, single user
**Canonical companion:** [`technical-spec.md`](technical-spec.md)

Implementation details that refine this product intent are canonical in the technical spec. Product behavior wins if the documents ever conflict; agents must record and resolve the conflict before coding.

---

## 1. Purpose

A personal reading tracker modelled on how MyAnimeList is actually used: find a
thing, give it a score, forget about it, come back later and sort by score or
recency to remember what was good.

Explicitly *not* a social network, not a library manager, not an ebook server.
Kavita already handles files; this handles opinions.

### Success criteria

Adding a finished book — search, pick the right edition, set status, set score,
save — takes under 20 seconds and never requires leaving the keyboard.

### Non-goals for v1

- Multiuser, auth, registration
- Public sharing / profile links
- Reviews, comments, discussion, follows, activity feeds
- Reading progress (page counts, % complete), reading sessions, streaks
- Ebook file management or runtime linkage to Kavita/Calibre. Read-only Calibre
  metadata import is explicitly in scope.
- Recommendations, statistics dashboards, year-in-review
- Mobile app (responsive web is enough)

---

## 2. Core decisions (settled)

| Decision | Choice | Rationale |
|---|---|---|
| Rating | Integer 1–10, no half points, nullable | The whole reason for not using Goodreads |
| Shelves | Many-per-book (tags) | Confirmed |
| Statuses | Per domain (DEC-057). Books: unsorted (inbox), read, reading, to_read, wishlist, dropped. Albums: unsorted, wishlist, pending, owned | A book's status tracks consumption; an album's tracks possession |
| Formats | Per domain, multi-valued, on the entry (DEC-059). Books: physical, borrowed, digital. Albums: vinyl, cd, digital | How *you* hold a copy; independent of status, so "wishlist → vinyl" is expressible |
| Schema split | `items` (shared metadata) / `entries` (personal opinion) | Enables multiuser + sharing later without migration |
| Backend | Python 3.12 + FastAPI + SQLite | Confirmed |
| Frontend | React + Vite + TypeScript + Tailwind + shadcn/ui + Motion | Highest polish-per-unit-effort for someone without frontend experience |
| Imports | Goodreads CSV + Calibre `metadata.db`, both in v1 | Existing libraries in both; hand-entry is not viable |
| Metadata sources | Open Library + Google Books, manual fallback | Free, keyless (OL) / good Spanish coverage (GB) |
| Domain generality | Per-domain packages under `domains/`, a code registry, **no plugin runtime** | The registry was extracted once a second domain existed, as planned. See technical spec §6.6 and `docs/guides/adding-a-domain.md` |
| Metadata precedence | Sync fills empty fields only, never overwrites; explicit per-item re-pull | Hand-corrections must survive re-sync |
| List rendering | TanStack Virtual + keyset pagination on `/` and the triage surface | Calibre libraries reach thousands of rows |
| Auth | None. LAN-only; internal proxying allowed, no internet-reachable route | Deferred with sharing; see §9 |
| Rereads | Lossy — latest dates + one score, `reread_count` only | Matches actual usage |

---

## 3. Data model

SQLite. JSON columns are TEXT with the JSON1 functions; no jsonb, but
`json_extract` is indexable via generated columns if it ever matters.

### 3.1 `items` — metadata cache, domain-agnostic shell

One row per **edition** (not per work). Deduped, user-agnostic, safe to correct
globally.

```sql
CREATE TABLE items (
    id           INTEGER PRIMARY KEY,
    type         TEXT NOT NULL DEFAULT 'book',   -- 'book' | future: 'wine'
    title        TEXT NOT NULL,
    subtitle     TEXT,
    year         INTEGER,                        -- publication year of this edition
    cover_path   TEXT,                           -- relative path on disk, nullable
    identifiers  TEXT NOT NULL DEFAULT '{}',     -- JSON: {isbn13, isbn10, olid, gbooks_id}
    metadata     TEXT NOT NULL DEFAULT '{}',     -- JSON: domain fields, see below
    source       TEXT,                           -- 'openlibrary' | 'googlebooks' | 'manual'
    source_id    TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE UNIQUE INDEX idx_items_source ON items(source, source_id)
    WHERE source IS NOT NULL AND source_id IS NOT NULL;
CREATE INDEX idx_items_title ON items(title COLLATE NOCASE);
```

The SQL above is the product-level shape, not the final physical identity model.
The canonical technical schema normalizes authoritative ISBN/Calibre identifiers
and provider source IDs into relational tables with uniqueness constraints; the
JSON `identifiers` object is an API/cache projection only. This is required to
make concurrent dedupe safe.

`metadata` for `type='book'`, all optional:

```json
{
  "creators": ["Julio Cortázar"],
  "publisher": "Alfaguara",
  "language": "es",
  "page_count": 736,
  "description": "…",
  "subjects": ["Argentine fiction"],
  "series": null,
  "original_year": 1963
}
```

`creators` is an array of plain strings — an album's artists and a book's authors
are the same neutral concept, and the key was renamed from `authors` in Sprint 025
(DEC-052). **No creator table in v1.** Creator identity is its own resolution
problem and buys nothing until you want a creator page. `credit` beside it is the
credit as the source renders it, because `["Dean Blunt", "James Ferraro"]` joined
by `", "` is not `Dean Blunt Meets James Ferraro`. Sorting and searching use
`creators[0]`, exposed as a generated column:

```sql
ALTER TABLE items ADD COLUMN creator_primary TEXT
    GENERATED ALWAYS AS (json_extract(metadata, '$.creators[0]')) VIRTUAL;
```

### 3.2 `entries` — the personal layer

```sql
CREATE TABLE entries (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL DEFAULT 1,      -- present, unused, do not remove
    item_id     INTEGER NOT NULL REFERENCES items(id),
    status      TEXT NOT NULL,                   -- see enum below
    score       INTEGER CHECK (score BETWEEN 1 AND 10),  -- nullable
    notes       TEXT,
    date_added  TEXT NOT NULL,
    date_started TEXT,
    date_finished TEXT,
    reread_count INTEGER NOT NULL DEFAULT 0,
    score_provisional INTEGER NOT NULL DEFAULT 0,  -- 1 = derived from a 1-5 import
    suggested_status TEXT,                         -- importer's guess, triage pre-selects
    UNIQUE (user_id, item_id)
);

CREATE INDEX idx_entries_status ON entries(user_id, status);
CREATE INDEX idx_entries_score  ON entries(user_id, score DESC);

-- How you hold this copy (DEC-059). The value is stored rather than joined to a
-- vocabulary table: unlike a shelf, which you invent, the vocabulary is closed and
-- declared by the domain.
CREATE TABLE entry_formats (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    format   TEXT NOT NULL,
    PRIMARY KEY (entry_id, format)
);
```

`entries.status` carries a CHECK constraint listing the union of every domain's statuses.
It catches a typo; it cannot express the real rule, which depends on the joined item's
type and is enforced in the domain layer.

**Statuses belong to a domain, not to the application** (DEC-057, seam 5b). Each domain
declares an ordered vocabulary, which of its statuses may be chosen directly, the triage
key for each, and the status a newly added entry takes. `GET /api/item-types` publishes
all of it, and a status outside the item's own domain is refused with a 422.

**Books** — `unsorted`, `read`, `reading`, `to_read`, `wishlist`, `dropped`; default `read`:

- `unsorted` = **the inbox.** Exists in the library, has metadata, has no opinion
  attached yet. Everything imported lands here. Hidden from the main list by
  default; surfaced as a badge count. Nothing else in the app ever sets it.
- `to_read` = I own it or can get it, intent to read
- `wishlist` = I don't have it, want to acquire it
- `dropped` = started, abandoned; may still carry a score

**Albums** — `unsorted`, `wishlist`, `pending`, `owned`; default `owned`. An album's status
records **possession, not consumption**: a record is played hundreds of times or twice, and
the interesting fact is whether you have it. `pending` is "on the way". There is no
relisten counter, and `date_started` / `date_finished` / `reread_count` do not exist for an
album — they are refused on write, not merely hidden. The score and the note carry the
opinion, as they always did.

`unsorted` is universal, because an import lands there whatever the domain.

- Score is independent of status. A `dropped` book can be a 3. A `to_read` book
  has no score. Never block scoring on status.

**Formats** (DEC-059) are a second, independent axis on the **entry**: how *you* hold this
copy, multi-valued, from a closed vocabulary the domain declares — `physical`/`borrowed`/
`digital` for a book, `vinyl`/`cd`/`digital` for a record. Legal on any status, so a
`wishlist` record can be `vinyl`: the pressing you mean to buy. Not a shelf — shelves are
the higher tier of organization ("work", "fiction") — and not the item's `format`, which
describes the release rather than your copy.

Dates are ISO-8601 strings (`YYYY-MM-DD` for dates, full timestamp for
`date_added`). SQLite has no date type; be consistent and it sorts correctly as
text.

### 3.3 Shelves

```sql
CREATE TABLE shelves (
    id       INTEGER PRIMARY KEY,
    user_id  INTEGER NOT NULL DEFAULT 1,
    name     TEXT NOT NULL,
    slug     TEXT NOT NULL,
    UNIQUE (user_id, slug)
);

CREATE TABLE entry_shelves (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    shelf_id INTEGER NOT NULL REFERENCES shelves(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, shelf_id)
);
```

Shelves attach to **entries**, not items — a shelf is an opinion ("sci-fi I'd
recommend"), not a fact about the book. Created on the fly by typing a new name
in the shelf input. No hierarchy, no colours, no ordering in v1.

---

## 4. Metadata acquisition

### 4.1 Provider interface

Two methods. Hardcoded to the book providers in v1; no registry, no entry
points, no dynamic loading.

```python
class Provider(Protocol):
    name: str          # 'openlibrary'
    item_type: str     # 'book'

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]: ...
    async def fetch(self, source_id: str) -> ItemPayload: ...
```

```python
@dataclass
class SearchCandidate:
    source: str                       # primary display/fetch source
    source_id: str
    source_refs: list[SourceRef]      # all merged provider identities
    title: str
    subtitle: str | None
    authors: list[str]
    year: int | None
    cover_url: str | None
    identifiers: dict[str, str]     # at minimum isbn13 when known
    language: str | None
```

`ItemPayload` is `SearchCandidate` plus the full `metadata` dict.

Both the picker UI and cache-on-add operate on these shapes. `SourceRef` is the
provider name plus source ID; merge retains all refs while choosing one primary
source for display and later refresh. Import records are separate (§5.3).

### 4.2 Providers, v1

**OpenLibraryProvider**
- Search: `GET https://openlibrary.org/search.json?q={q}&limit=20&fields=key,title,subtitle,author_name,first_publish_year,isbn,cover_i,language,edition_key`
- `first_publish_year` is work-level context (`original_year`), never this edition's `items.year`; fetch edition data before assigning edition year.
- Fetch: `GET https://openlibrary.org/isbn/{isbn}.json` or `/books/{olid}.json`
- Covers: `https://covers.openlibrary.org/b/id/{cover_i}-L.jpg`
- No API key. Set a descriptive `User-Agent` with a contact address — they ask
  for it and will throttle anonymous hammering.

**GoogleBooksProvider**
- Search: `GET https://www.googleapis.com/books/v1/volumes?q={q}&maxResults=20&key={KEY}`
- Query operators worth exposing: `intitle:`, `inauthor:`, `isbn:`
- Covers: `imageLinks.thumbnail`, then strip `&edge=curl` and bump `zoom=1`→`zoom=3`
  for a usable size. Rewrite `http:`→`https:`.
- Free tier ~1000 req/day, ample. Key in env, and degrade gracefully if absent.

**ManualProvider** — not really a provider; a form. Title, authors, year,
publisher, language, ISBN, optional cover upload. Writes `source='manual'`.
Required for Argentine and small-press editions that neither source indexes.

### 4.3 Search flow

1. User submits a free-text query, or pastes a URL (see 4.4).
2. Fan out to both providers concurrently (`asyncio.gather`), 5s timeout each. A
   provider that errors or times out is skipped silently; results from the other
   still render. Log the failure.
3. Merge: dedupe on normalised ISBN13. If both sources have the same ISBN13,
   keep one card but retain both `source_id`s; prefer Open Library's record and
   Google Books' cover if OL has none.
4. Rank: keep the order the providers returned, interleaving the two by
   position so neither monopolises the top. Within one position, prefer
   exact-ish title matches, then `es`/`en`, then presence of a cover.
   Deliberately dumb — the human picks. "Dumb" means not over-engineering the
   ranking, *not* discarding the relevance the providers already computed:
   sorting the merged list alphabetically by title buried the obvious answer
   under unrelated books for thirteen sprints (DEC-024).
5. Render a picker grid: cover, title, subtitle, authors, year, publisher,
   language, source badge. Always include a **"None of these — enter manually"**
   card at the end.
6. On selection, run `fetch()` for full metadata, then cache-on-add.

**Duplicate handling.** Two distinct cases, handled differently:

- **Exact duplicate** (same `source`+`source_id`, or same ISBN13, resolving to an
  existing `item_id` you already have an entry for): no error, no new row.
  Navigate straight to `/books/{existing_entry_id}` with a toast reading
  *"Already in your library"*. The unique constraint is never allowed to surface
  as a 500. If the existing entry is `unsorted`, this is actually the fast path
  for triaging a single book — you searched for it, you're now editing it.
- **Near-duplicate** (different edition: same normalised title + first author,
  different ISBN): this is a *legitimate* second row under the edition model, so
  don't block it. Show an inline warning on the picker card — *"You already have
  the 1999 Alfaguara edition"* — with a button to open that entry instead.
  Warn, never prevent.

Near-match detection is normalised title + first author, both lowercased with
accents and punctuation stripped. Cheap, and good enough at your scale.

### 4.4 Add by URL

Regex the ID out and skip straight to `fetch()`:

| Pattern | Provider |
|---|---|
| `openlibrary.org/books/OL\d+M` | Open Library, by OLID |
| `openlibrary.org/works/OL\d+W` | Open Library, resolve to an edition-picker list; never silently choose an arbitrary edition |
| `books.google.*` with `id=` param | Google Books |
| bare ISBN-10/13, with or without hyphens | Open Library, then Google Books |

Goodreads URLs are out of scope — no API, scraping not worth it.

### 4.5 Cache-on-add — the rule that matters

On add, **copy every field into `items` and download the cover to local disk.**
Never store only a foreign ID and re-fetch at render time.

- Covers → `data/covers/{item_id}.jpg`, max 600px on the long edge, re-encoded
  as JPEG q85. Store the relative path in `cover_path`.
- Cover download failure is non-fatal: save the item with `cover_path = NULL`
  and show a placeholder.
- After add, the app makes **zero** network calls to render any page. This is
  what makes it immune to Open Library going down, Google deprecating the API,
  or the ZimaBoard being offline.
- Every field is editable by hand afterwards, at `/items/{id}/edit`. Assume the
  metadata is wrong for Spanish-language books and make correcting it painless.
  **Hand edits are permanent** — no automatic process ever overwrites a
  populated field (§5.2). Only the explicit re-pull button does.

---

## 5. Imports

Both sources are open formats. Neither requires scraping or an API key.

### 5.1 Goodreads CSV

Export lives at `goodreads.com/review/import` → **Export Library**, desktop web
only, produces `goodreads_library_export.csv`. It is a snapshot, not a sync —
Amazon killed the public Goodreads API in 2020 and there is no legitimate live
path. One-shot import, then Goodreads stops being authoritative.

**Columns used:** `Book Id` (provenance only), `Title`, `Author`, `Additional Authors`, `ISBN`, `ISBN13`,
`My Rating`, `Publisher`, `Number of Pages`, `Year Published`,
`Original Publication Year`, `Date Read`, `Date Added`, `Bookshelves`,
`Exclusive Shelf`, `My Review`, `Read Count`.

**Gotchas, all of them real:**

- ISBN fields are Excel-armoured as `="9780441013593"`. Strip `="` and `"`
  before use. Empty values arrive as `=""`.
- `Exclusive Shelf` is the status field, but it does **not** set status directly.
  Everything lands as `unsorted`; the Goodreads value is preserved as a
  *suggestion* (`entries.suggested_status`) that triage pre-selects and you
  accept or override in bulk. Suggested mapping:
  `read`→`read`, `currently-reading`→`reading`, `to-read`→`to_read`.
  Goodreads has no wishlist/dropped concept, so those never get suggested.
- `Bookshelves` is a comma-separated list of *non*-exclusive shelves → becomes
  your shelf tags. It redundantly repeats the exclusive shelf; filter it out.
- `My Rating` is 1–5, and `0` means unrated (**not** a score of zero).
- Dates are `YYYY/MM/DD`, not ISO. Frequently blank.

**Rating conversion.** Doubling (3★ → 6) is the default, but it only ever
produces even scores and quietly fabricates precision you never expressed. So:
double it, and set `score_provisional = 1` on imported entries. The UI shows
those scores in a muted style with a dot, and there's a filter for
"provisional scores" so you can re-rate at leisure. Any manual edit clears the
flag.

### 5.2 Calibre

Calibre's `metadata.db` is a plain SQLite database — no API needed, and this is
the better of the two integrations.

**Access:** mount the Calibre library directory read-only into the container and
open with `sqlite3.connect("file:metadata.db?mode=ro", uri=True)`. Never write
to it. Do not read it while Calibre is mid-write; a stale read is possible but
harmless for a one-shot import.

**Tables:** `books` (title, sort, pubdate, path, uuid), `authors` +
`books_authors_link`, `identifiers` (rows with `type` in `isbn`, `google`,
`amazon`), `tags` + `books_tags_link`, `comments` (description), `series` +
`books_series_link`, `ratings` + `books_ratings_link`.

**The nice surprise:** Calibre stores ratings as an integer 0–10 where 10 = five
stars. It's a half-star scale internally, so the values map to your 1–10 scale
**directly, no conversion, no provisional flag.** Calibre ratings are the one
imported score you can trust as-is.

**Covers:** `cover.jpg` inside each book's folder, at `<library>/<books.path>/`.
Copy into your own `data/covers/` rather than referencing across the mount.

**Mapping:** Calibre tags → shelves. Status is absent from Calibre entirely, so
everything lands `unsorted` with no suggestion. This removes the "is my Calibre
library owned or finished?" question — you answer it per-book in triage, in
bulk, in about a minute.

**Re-sync:** store `books.uuid` in `items.identifiers.calibre_uuid`. Re-running
the import adds new books and never touches `entries` — your scores and statuses
are yours, Calibre doesn't get a vote.

**Re-sync never overwrites.** On a matched item, sync fills only fields that are
currently empty. A publisher, title, or cover you corrected by hand survives
every subsequent sync, permanently, with no dirty-tracking machinery. The escape
hatch is an explicit per-item **"re-pull metadata"** button
(`POST /api/items/{id}/refresh`). It fetches and validates first, then overwrites
only fields actually present in the successful provider response; omitted fields
and all entry opinion data remain unchanged. This is the only path by which
provider values may overwrite populated item metadata, and you have to ask for
it. A failed or partial-invalid fetch leaves the old item untouched. Manual-only
items cannot refresh until linked to an authoritative provider source.

### 5.3 Shared import pipeline

Both importers emit an import-specific normalized record (score, dates, status
suggestion, shelves, review, source row, and metadata) and go through one path.
They do **not** reuse the interactive provider `SearchCandidate` shape:

1. Parse → normalised records, persisted for the preview
2. Match each row against existing `items`: provider identity → canonical ISBN13 →
   valid ISBN10/conversion-equivalent → calibre_uuid. A normalised title+author
   similarity is **ambiguous evidence only**: preview it for explicit resolution
   or create a separate edition; never auto-merge on that fuzzy key. If exact
   identities from one record resolve to different existing items, mark a typed
   identity conflict for explicit resolution and perform no mutation for that row.
3. **Dry-run preview**, always: counts of new items, new entries, empty item
   fields to fill, existing entries left unchanged, ambiguous records,
   conflicts, and idempotent skips. Parse errors and ambiguous rows are shown
   with enough detail to resolve before commit; value conflicts can remain for
   triage.
4. In one bounded transaction, create absent entries as `unsorted`, fill only
   empty item fields, preserve all existing entries, record effects/conflicts,
   and enqueue enrichment jobs
5. Background enrichment: for rows with an ISBN but no cover, queue Open
   Library/Google Books lookups at ~2 req/s. Runs for minutes on a large
   library; never inside the request. Triage is usable while it runs

**Collision handling gets much simpler.** With nothing needing to be final, the
The importer does not mutate a pre-existing entry to store conflict evidence.
For a new entry assembled from multiple source rows, deterministic confidence
(Calibre > Goodreads for metadata and scores) chooses its initial values. All
losing or incoming alternatives are stored in the batch's durable import audit
records. Triage joins unresolved audit conflicts to rows and offers an explicit
choice; personal edits always win.

Import is idempotent: re-running the same file changes nothing. Provenance and
safe undo are tracked by `import_batches` and an import ledger linking each batch
to the entries/items it created or filled. The canonical columns and undo
semantics are defined in the technical spec; do not add the previously proposed
but undefined `items.import_source` shortcut.

---

## 6. HTTP API

FastAPI, JSON, no auth in v1 (bind to LAN / behind Nginx Proxy Manager).

```
GET    /api/search?q=…                 → merged candidates
GET    /api/search/resolve?url=…       → single candidate, or edition candidates for a work URL
POST   /api/entries                    → {source, source_id, source_refs?[]} | {manual: {...}}
                                          + {status, score?, shelves?[]}
                                          refetches the primary source, validates secondary
                                          refs against canonical identity, creates/reuses item
                                          and entry
GET    /api/entries?status=&shelf=&sort=&order=&q=
PATCH  /api/entries/{id}               → status, score, notes, dates, shelves
PATCH  /api/entries/bulk               → {entry_ids[]} or
                                          {filter, excluded_entry_ids[]}, plus
                                          {set:{status?, score?, add_shelves?[],
                                          remove_shelves?[], clear_provisional?}}
POST   /api/entries/accept-suggested   → {filter} applies suggested_status in bulk
DELETE /api/entries/{id}
GET    /api/items/{id}
PATCH  /api/items/{id}                 → manual metadata correction
POST   /api/items/{id}/refresh         → re-pull from source, OVERWRITES edits
POST   /api/items/{id}/cover           → upload replacement cover
GET    /api/items/{id}/attachments     → files attached to this edition
POST   /api/items/{id}/attachments     → upload one opaque file, size-capped
GET    /api/items/{id}/attachments/{aid} → download; always Content-Disposition: attachment
DELETE /api/items/{id}/attachments/{aid} → detach; the bytes go when nothing references them
GET    /api/shelves
PATCH  /api/shelves/{id}               → rename
DELETE /api/shelves/{id}               → detaches, does not delete entries

POST   /api/import/goodreads/preview   → CSV upload, returns dry-run report
POST   /api/import/goodreads/commit    → {batch_id, options}
POST   /api/import/calibre/preview     → {library_path}, returns dry-run report
POST   /api/import/calibre/commit      → {batch_id, options}
GET    /api/import/calibre/browse      → ?path=, folder names under the mount
GET    /api/import/jobs/{id}           → progress for background enrichment
DELETE /api/import/batches/{id}        → undo an import batch

GET    /api/export                     → whole library as entity-shaped JSON;
                                          ?format=csv for a Goodreads-shaped CSV
POST   /api/enrichment/backfill        → re-queue enrichment for items whose
                                          metadata or cover is still empty
GET    /api/health/providers           → which providers are configured, and
                                          whether search is degraded
```

`POST /api/entries` is deliberately one client call: given a provider hit, it
fetches and dedupes, commits the item/entry relationally, then installs a prepared
cover or queues retryable cover work. Cover failure never rolls back the valid
entry. The 20-second add flow depends on this not being three client round trips.

**Sort keys:** `date_added` (default, desc), `score`, `title`, `creator`,
`year`, `date_finished`. NULL scores sort last regardless of direction.

**Pagination.** `GET /api/entries` is keyset-paginated, not offset-paginated:
`?after={last_sort_value},{last_id}&limit=100`. Always include `id` as the
tiebreaker so the cursor is stable when sort values collide (many books share a
score of 8). Offset pagination degrades badly and breaks under concurrent
edits; keyset is barely more code and pairs correctly with virtual scrolling.
Response returns `{items: [...], next_cursor, total}` — `total` powers the
scrollbar, computed with a separate `COUNT(*)` and cached per filter.

---

## 7. UI

**Stack: React 18 + Vite + TypeScript + Tailwind + shadcn/ui + Motion.**

Chosen over Jinja+HTMX (the earlier recommendation): HTMX minimizes machinery,
but the priority here is a polished result built by someone without frontend
experience, which favors an ecosystem of ready-made components to assemble over
hand-designed markup.

- **shadcn/ui** — component source copied into the repo rather than installed as
  a dependency; accessible and restrained by default.
- **Tailwind** — utility classes; no separate stylesheet, no class-naming decisions.
- **Motion** (ex-Framer Motion) — the microinteraction layer: grid re-sort,
  score-picker springs, list enter/exit via `<AnimatePresence>` and `layout`.
- **TanStack Query** — server state, caching, and optimistic updates; optimistic
  mutation is what makes inline score editing feel instant.

Cost: a Node build step and more code than the HTMX version, kept to one deployed
container by the multi-stage Docker build (§8).

### Design direction

Pick a real one rather than defaulting. Suggested: dark-first, near-black
(`zinc-950`) rather than pure black, one saturated accent for scores and active
states, covers as the primary visual element with generous spacing. Type: one
sans (Inter or Geist) at two or three weights. Avoid the default Tailwind blue
and the standard card-with-border-and-shadow look — those are what "AI-generated
dashboard" looks like.

### Rendering at scale

A Calibre import can produce several thousand rows, and triage is a dense
table of exactly those. Plain React rendering will visibly stutter past ~500.

- **TanStack Virtual** on both `/` and triage. Only visible rows mount.
- **TanStack Query with `infiniteQuery`** against the keyset cursor (§6), page
  size 100, prefetch the next page when the user scrolls within 200px of the
  bottom.
- Rows must be **fixed-height** in table view for cheap virtualization
  (`estimateSize` returns a constant). Grid view uses fixed-aspect cover cards,
  same benefit.
- **This constrains Motion.** Layout animations on a virtualized list fight the
  virtualizer — items unmount as they scroll out and re-animate on return. Rule:
  animate on *sort/filter changes only*, by keying the list container on the
  active sort and doing a single crossfade, rather than `layout` props on every
  row. Keep spring animations for things that don't scroll: the score picker,
  the action bar, dialogs.
- Text filtering runs server-side (SQL `LIKE` over cached title/author) rather
  than client-side, since the client only holds the loaded pages. At this scale
  `LIKE` is fine; FTS5 is a later optimisation if it ever isn't.

This is the one place where "make it look nice" and "make it fast" genuinely
conflict, and the resolution is to spend the animation budget on interactions
rather than on scrolling.

### Microinteractions worth building

These are the ones that carry the feel; everything else can be static.

- **Score picker** — 1–10 as a row of segments, fill animates on hover, spring
  on commit, colour shifts across the range. This is the thing you touch most.
- **Sort/filter transitions** — crossfade the list container on sort change,
  keyed by the active sort (see "Rendering at scale" — per-row `layout` props
  are off the table with virtualization).
- **Add flow** — search results stagger in; the selected card animates into
  place rather than a page navigation.
- **Optimistic writes** — score updates render instantly, reconcile in
  background, roll back with a shake on failure. Never a spinner for a local DB
  write.
- **Cover load** — blur-up or skeleton, never layout shift.

Respect `prefers-reduced-motion` throughout — Motion has a hook for it.

### Screens

**`/` — The library.** The primary screen and the one to get right. Since Sprint 029 it is
also **the screen you search from and the screen you add from** (DEC-065, DEC-073); adding
something no provider lists is the only thing that still leaves it.

- **One bar across the top: the domain selector, the search input, and *Add*.** One control
  picks two things at once — the rows you see *and* the providers a search would reach — so
  there is never a moment where the application has to ask which domain you meant. The input
  carries a clear control while it holds anything, and clearing empties the box, the query and
  any web results together, because they are one thing as far as the reader is concerned.
- **The domain strip names exactly one domain**, one tab per domain, rendered from the
  registry and present only when the build has more than one. **"All" is not a filter**
  (DEC-065): the choice lives in the URL like every other filter and is remembered between
  visits, and a visit with nothing remembered lands on the first declared domain (DEC-062,
  amended). The whole-library view is not lost — triage and the export both still span
  domains, and the unselected tab still carries a live count.
- **Typing searches your library, over SQL, and reaches no provider** — at any query length,
  for as long as the library has a match. This is the invariant §4.5 buys and it survives
  having one bar: rendering a library page never makes a network call.
- **A provider is reached only when the library has nothing and the query has settled**, or
  immediately when you press **Add**. The exact rule is in DEC-065 and technical spec §8;
  the reason it is a rule rather than a feel is the quota (DEC-045, and the tier breach
  DEC-044 measured).
- **Web results render below the library, in their own labelled region** — *From the web* —
  never inside it. Below rather than above is deliberate: the library virtualizes against
  the window, and a variable-height block above it moves the offset every row measures
  itself against (DEC-073).
- **Selecting a web result opens the confirm step as a dialog over the library**, not as a
  navigation: the same form `/add` used to host — what is already known about the result,
  *Load full details*, status, score, shelves, notes, format and the domain's passage
  fields — plus the near-match path and *None of these — enter manually*. On success the
  dialog closes onto the library with the new entry highlighted, and the query is cleared,
  because the filter that had just missed would otherwise hide the thing you added.
- Grid (covers) / compact table toggle, persisted in localStorage
- **Four filters in one row: sort, shelf, format and status.** Status is a multi-select rather
  than a single choice, because wanting *Read* and *Reading* at once is ordinary; it offers
  **the chosen domain's vocabulary and only that domain's**, with each status's count beside
  it, since a library holding two domains has no single status vocabulary and a shared status
  ("wishlist") is counted per domain rather than once. The tab already names the domain, so the
  control carries no heading of its own. The format list is narrowed to the domain on screen.
  Status had a row of its own until Sprint 029's second pass, which is a whole row of chrome
  for the fourth of four filters (DEC-074)
- **The page scrolls, not the grid.** The library is the primary surface and uses the whole
  page; the virtualizer measures the window rather than a fixed-height box of its own
- Sort dropdown per §6
- Inline score editing directly from the list — click the number, type, done.
  No modal, no navigation.
- Counts per status somewhere unobtrusive
- **An empty library and an empty result are different silences.** No library is news, and says
  so with the screen it deserves. A search that matched nothing is the ordinary case — it is
  what makes the web search fire — so it gets one line naming the string that missed, and the
  results land where the encouragement would otherwise have pushed them (DEC-074)

**`/add` — Enter by hand.** Searching moved to `/` in Sprint 029 (DEC-065); what is left
here is the one thing no provider can do for you.

- The full validated manual form: title, creator and the domain's fields, then status (the
  domain's default), score, shelves, notes and format — the same confirm step the dialog on
  `/` hosts, rendered from the registry rather than branching on the item type.
- **Reached deliberately**, from *None of these — enter manually* in the web results, or as a
  deep link. It stays a route rather than moving inline; it is lazy-loaded, so keeping it
  costs nothing in the bundle.
- **It offers no domain choice**, and that is honest rather than missing: a manual add is
  typed as the default domain whatever the client sends (DEC-067 row 6, DEC-073). Naming a
  domain here would show one domain's statuses and fields and then write another's row.
  Giving manual entry a real domain needs an API change and is unscheduled.
- On success it returns to `/` with the new entry highlighted.

The confirm step itself — **what we already know** about the thing you clicked, everything
the search returned rendered from the domain's field spec, at no cost and with nothing to
wait for, plus *Load full details*, which fetches the complete record (the description, the
page count, the tracklist) in one provider request when asked (DEC-064) — now lives in the
dialog on `/`, so a book you just finished is one action rather than an add followed by an
edit.

**`/books/{entry_id}` — Detail.**
- Cover, full metadata, description
- Editable: status, score, notes, format, and — for a domain that has them — dates and
  reread count, in one *Edit your opinion* dialog. A format is picked from one closed
  multi-select control, the same one the add screen uses, and never from a control that
  can invent a value (DEC-059, DEC-064)
- **Shelves are edited inline, where they are read** — the entry's shelves as removable
  chips plus one control that filters existing shelves as you type and offers to create
  what does not exist yet, creating and assigning in one action. Not in the opinion dialog
  and not a trip to `/shelves`; and never converged with the format control, because a
  shelf is one you invent and a format is a closed per-domain vocabulary (DEC-059)
- Link to edit underlying item metadata
- **Files** — its own region, at the weight of *Edit opinion* rather than a corner of the
  edition facts (DEC-074): attachments on the edition, with name, size, download, rename, remove.
  Loaded as its own request so a slow read never delays the page. Renaming is
  inline, since the name is metadata and changing it moves no bytes; removing
  confirms first, because once the removed row is the last reference the upload
  is gone. There is no *replace*: with rename in place it is remove plus attach
  and nothing more (DEC-050). An attachment is an **opaque file, or it is a
  reader**, and this is the opaque-file side of that line: no format parsing, no
  in-browser reading, no reading progress, no device sync (DEC-048).
- Delete entry

**Triage — the inbox, a tab on `/import`.** The surface that makes bulk import
viable, and the second-most-important in the app after `/`. Everything `unsorted`
lives here. It is **not a top-level destination**: it is empty until an import
lands rows in it, so as a nav item it was a dead page most of the time (DEC-079).
It reaches `/import?tab=triage`, the old `/triage` address redirects there, and
the Inbox button on `/` and the post-commit link both land on it.

Design goal: clear several hundred books in one sitting without it feeling like
data entry. That means bulk-first, keyboard-first, and never one-book-at-a-time
unless you choose it.

- **Dense table by default** — small cover thumb, title, author, year, suggested
  status, score, shelves. Compact rows, ~25 visible at once. Grid view optional
  but the table is the working surface.
- **Selection model** — checkbox column, click-drag to range-select,
  shift-click, `Ctrl/Cmd+A`. A persistent action bar appears when anything is
  selected: *Set status · Add shelves · Set score · Clear provisional · Delete*.
  All apply to the whole selection in one request.
- **Grouping and filters** — by import batch, by suggested status, by author, by
  shelf, by "has conflict", by "provisional score", by "no cover". The point is
  that you sort into a homogeneous group and then act on all of it at once:
  every Goodreads `to-read` row → `to_read`, one click, done.
- **Accept suggestions in bulk** — a single "Accept all suggested statuses"
  action, scoped to the current filter. For a Goodreads import that alone
  clears most of the backlog.
- **Keyboard flow for the rest** — `j`/`k` move, digits set score, `r`/`t`/`w`/
  `d` set status, `Enter` commits and advances. This is the MAL-style rhythm,
  and it's what makes the leftover hundred books tolerable. Shelving is not on
  this list: `s` was specified here as a shelf-autocomplete shortcut and
  retired unbuilt in Sprint 019 (DEC-043), because the surface it needs is a
  feature rather than a shortcut. Shelves are assigned from a book's detail
  page — or, for a whole selection at once, from the *Add to shelf* control in the
  bulk action bar.
- **Conflicts** — rows with unresolved conflicts in their joined import audit
  records show a marker; clicking expands both values inline with one click to
  choose. Never a modal.
- **Deferring is fine and explicit.** No "you must finish" pressure. The badge
  count on `/` is the only nag. Books can sit `unsorted` indefinitely and still
  be searchable.

**`/shelves` — Shelf management.** List, rename, delete, counts.

**`/import` — Import.** One tab per registered connector, plus **Triage** (above).
The tab lives in the URL and an unnamed one falls back to the connector used
last, the same rule the library's domain tab follows (DEC-062). A staged source
and its preview belong to the connector that produced them: moving to another
connector starts clean, moving through Triage and back does not.

**Each connector explains itself, and the screen renders the declaration rather
than copy of its own** (DEC-080). Goodreads states where the export lives
(`goodreads.com/review/import` → Export Library, desktop web only), that it is a
snapshot rather than a sync, that ratings are doubled and marked provisional, and
that shelves become tags; its input takes a dropped file as well as a chosen one.
Calibre states that it is opened read-only, that only empty fields are filled and
your edits win, and that covers are copied during preview — and it is **browsed
rather than typed**: a breadcrumb and a folder list rooted at the mounted library,
which says whether the folder you are standing in holds a library. Typing a
relative path still works, for automation.

Both show the dry-run preview before any write, with the unmatched/ambiguous rows
called out. A refused read says what to do about it in the connector's own words
— a locked Calibre database asks you to close Calibre and try again. Progress bar
for background enrichment. "Undo last import" for 24 hours.

### Interaction notes

- Keyboard: `/` focuses search, `a` focuses the same bar — adding is no longer a
  place to go, so there is nothing for it to open (DEC-073) — and digits `1`–`9` + `0`
  set score on a focused row
- **With web results on screen, focus decides which surface the shortcuts address.**
  Standing inside the results region, `j`/`k` do not scroll the library and a digit does
  not score a row you are not looking at; the results are reached by Tab, and the confirm
  dialog is covered already, since shortcuts are off while a dialog owns focus
  (technical spec §8)
- Confirmation dialogs are limited to delete and explicit provider refresh overwrite.
- Dark mode, since this runs next to Jellyfin at night

---

## 8. Deployment

- **Multi-stage Docker build:** stage 1 `node:22-alpine` runs `vite build`,
  stage 2 `python:3.12-slim` copies `dist/` in and FastAPI serves it as static
  files with an SPA catch-all route. Node does not ship in the final image.
  Still one container, one process on the ZimaBoard.
- Volume: `/data` → `books.db` + `covers/`
- Volume: `/calibre` → your Calibre library, **read-only** (`:ro` in compose)
- Env: `GOOGLE_BOOKS_API_KEY` (optional), `TZ`, `USER_AGENT_CONTACT`
- Behind Nginx Proxy Manager, e.g. `books.home.lan`, matching the AdGuard/NPM
  pattern already in use
- Backup: nightly `sqlite3 books.db ".backup /data/backups/books-$(date).db"`
  plus a covers tarball. The DB is the only irreplaceable thing — metadata is
  re-fetchable, your scores are not.
- Migrations: Alembic from commit one. Even single-user, hand-editing schema on
  a live DB with real ratings in it goes badly.

---

## 9. Out of scope, deliberately deferred

Listed so they're not re-litigated during build.

**Delivered — Export.** `GET /api/export` dumps entries + items as JSON, with
`?format=csv` for a Goodreads-shaped CSV. **Shipped in Sprint 024.** The JSON is
entity-shaped (`type`, identifiers, opaque `metadata`) rather than book-specific,
so a second domain needs no v2 format; the CSV is one domain's export view and is
allowed to stay book-only. Attachments are carried as references plus their
sha256, not as bytes (DEC-054): the digest resolves against any backup, because a
blob's path *is* its digest. The nightly DB backup (§8) remains non-optional in
production — the export is a portability story, not a restore story. There is no
export button in the UI; the route is the surface.

**v2 — Auth.** None in v1; LAN-only. Internal Nginx Proxy Manager routing is
allowed, but there must be no public DNS, internet port-forwarding, tunnel, or
internet-reachable proxy host until authentication exists. When auth lands:
single env-var password with a signed session cookie, which is also the
prerequisite for public share links. Docker may bind the container normally;
restrict exposure at published ports, firewall, DNS, and proxy layers. Keep this
warning in Compose so future-you doesn't expose it while adding a host at 1am.

**v2 — sharing.** Public read-only list URLs. Cheap *if* the list view is
already `render(entries WHERE user=X, filter, sort)` and authorization is a
separate check. Build the view that way now; add the route later.

**v2 — multiuser.** `user_id` on `entries` and `shelves` reduces data-model
churn, but multiuser still requires a real users table, ownership backfill,
authentication identities, authorization checks, and uniqueness validation.
Do not claim it is migration-free.

**v2 — Calibre write-back.** Pushing your scores into Calibre's `ratings` table
so the two stay in sync. Technically easy given the identical 0–10 scale, but it
means writing to a DB another program owns. Not worth the risk in v1.

**v2 — OPDS / Content Server as an alternative Calibre path.** If the library
ever lives on a different machine than the tracker, Calibre's Content Server
exposes `/ajax/search` and `/ajax/books` over HTTP. Direct `metadata.db` reads
are simpler while both are on the ZimaBoard.

**Built — the second domain (albums), and the contract behind it.** The
`items`/`entries` split and the two-method provider shape were the entire
preparation. Albums were chosen over wine, which this section originally assumed:
MusicBrainz needs no OAuth, release-group versus release maps onto the
work-versus-edition problem already solved for books, and Cover Art Archive
exercises the separate-image-provider case. DEC-052 replaced the "add a provider
and see" shape with **six named seams**, validated against the live MusicBrainz
API rather than assumed — and found that casting an album into book fields is
lossy, because MusicBrainz only inverts a *person's* sort name and a barcode is
not a unique edition key.

Sprints 025–027 built albums; **Sprint 028 wrote the contract and made a domain a
unit of code**: each one lives in its own package, holds its own vocabulary and
adapter, and is held to a conformance suite it passes by existing. A third domain
is now an **epic on top of that contract** rather than a sprint inside this plan
(DEC-058), and it costs its own package, one registry entry, provider wiring and
three enum lines — no migration, and no edit to another domain's files (DEC-069).
**Games and series are named as future epics and carry no sprint number.** The
guide is `docs/guides/adding-a-domain.md`.

The line that has not moved: **no plugin runtime.** The registry is code, built
and shipped with the application. Nothing here proposes discovery, sandboxing or
versioning between a domain and the core.

Wine stays exploratory and unscheduled — see `docs/domain_metadata_roadmap_report.md`.
Expect it to be manual-entry-first: there's no free equivalent of ISBN, identity
is producer + cuvée + vintage + format, all fuzzy, and the hosted option's
weakness is access economics rather than catalogue geography.

---


## 10. Settled decisions log

Resolved during spec review; recorded so they aren't reopened.

| # | Question | Resolution |
|---|---|---|
| 1 | Provisional scores in sorting | Double Goodreads 1–5, flag provisional, mix into sort with visual marking + exclude filter |
| 2 | Re-sync vs manual edits | Sync fills empty fields only, never overwrites; explicit per-item re-pull button (§5.2) |
| 3 | Adding a book you already have | Exact dupe → navigate to existing entry with a toast. Different edition → warn on the picker card, don't block (§4.3) |
| 4 | Rereads | Stay lossy: latest dates, one score, `reread_count`. No `readings` table |
| 5 | Scale | TanStack Virtual + keyset pagination; animation budget spent on interactions, not scrolling (§6, §7) |
| 6 | Export | Deferred through v1; nightly DB backup mandatory in the meantime (§9). **Delivered in Sprint 024** — entity-shaped JSON plus a Goodreads CSV, attachments by reference (DEC-054) |
| 7 | Auth | Deferred to v2. LAN-only; internal NPM is allowed, but no internet-reachable proxy/DNS/forwarding until auth (§9) |

---

## 11. Defaults pending owner override

These four defaults are adopted for implementation and are not blockers. They
remain easy for the owner to override before the affected sprint begins; any
override must update the technical spec, decision log, and downstream sprint
acceptance criteria.

1. **Does `unsorted` count as "in the library"?** Spec assumes yes — unsorted
   books are searchable and appear in shelf views, just hidden from the default
   list on `/`. The alternative is full quarantine until triaged. Low stakes,
   easy to flip later.
2. **Deleting an entry — what happens to the item?** Spec leaves orphaned
   `items` rows and their covers in place, treating them as cache so re-adding
   is instant, with a manual "prune orphans" maintenance action. Only matters
   for disk usage, and covers are ~50KB each. **Attachments changed the stakes
   of this and it is now answered for them** (DEC-047, DEC-049): an attached
   file is 2.5 MB rather than 50 KB and is not re-fetchable cache, so removing
   an attachment deletes its bytes once nothing references them, and
   `akasha-attachments reclaim` collects any blob that was orphaned some other
   way. The orphaned *cover* is still left in place: the reclaim command is
   scoped to the attachment store and deliberately does not generalize to
   covers, which are cache the application can re-fetch.
3. **Work vs edition.** One row = one edition; a reread of a different edition
   is the same entry with `reread_count++`. Changing this means a different
   uniqueness constraint on `entries`. Recommendation stands: don't.
4. **Series.** Free-text in `metadata`, not modelled. Only becomes a problem if
   you want "show me the Malazan books in reading order", which needs a real
   series + position pair. Add later if you miss it — it's an additive migration,
   not a destructive one. **Sprint 030 answered the adjacent question** (does a
   child of an entry need state of its own: no) and found a set is a different
   concept from depth — an ordered shelf, not a parent entity. The verdict and
   what would reopen it are in [`../entry-depth-verdict.md`](../entry-depth-verdict.md).
