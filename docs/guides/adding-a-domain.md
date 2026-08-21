# Adding a domain

**Status:** canonical. This is the practical guide; the binding contract is
[technical spec §6.6](../specs/technical-spec.md). Where they disagree, the spec wins and this
document is wrong.

A **domain** is a kind of thing the library holds. Books and albums ship today. A third one — games,
films, board games — is built by following this guide, and **you should not need to read how albums
were built to do it.** If you find yourself reading Sprints 025–028 to answer a question this guide
does not, that is a defect in this guide; say so.

The promise this structure exists to keep: **adding a domain touches your own directory and small,
explicit registration points. It does not touch another domain's files, and it does not require a
database migration.** An optional importer is another object in that same directory plus one
registry tuple entry; it does not change the shared pipeline.

---

## 1. What you are plugging into

The storage core has been neutral since Sprint 002. An `item` is a `type`, a `title`, a `subtitle`,
a `year`, a `cover_path`, some `identifiers` and an opaque `metadata` object. An `entry` is one
person's opinion of an item. **Nothing in the shared layers branches on which domain it is holding**
— when a shared layer needs to know something domain-specific, it asks the registry for a
declaration.

```text
                         ┌──────────────────────────────────────────────┐
   HTTP requests ───────▶│  api/            routers, error mapping      │
                         ├──────────────────────────────────────────────┤
                         │  application/    use cases, transactions     │
                         ├──────────────────────────────────────────────┤
                         │  domain/spec.py      what a domain IS        │
        the neutral core │  domain/registry.py  which domains EXIST     │
                         │  domain/providers.py candidates, merging     │
                         ├──────────────────────────────────────────────┤
                         │  infrastructure/ SQLite, HTTP, files, jobs   │
                         └──────────────────────────────────────────────┘
                                    ▲                        ▲
                       declares its │                        │ declares its
                       vocabulary   │                        │ vocabulary
                         ┌──────────┴─────────┐   ┌──────────┴─────────┐
                         │  domains/book/     │   │  domains/album/    │
                         │   __init__.py      │   │   __init__.py      │
                         │   providers.py     │   │   providers.py     │
                         │   goodreads.py     │   └────────────────────┘
                         │   calibre.py       │
                         └────────────────────┘
                                    ▲                        ▲
                                    └──── never import ──────┘
                                          each other
```

Your domain declares itself once, and that one declaration travels two ways:

```text
   domains/game/__init__.py
        DOMAIN = Domain(...)
              │
              ├──────────────▶ domain/registry.py ──▶ GET /api/item-types ──▶ every screen
              │                    DOMAINS              (the whole record)      tabs, status chips,
              │                                                                 format picker, the
              │                                                                 metadata dialog,
              │                                                                 triage hotkeys,
              │                                                                 the detail page
              │
              └──────────────▶ writes ──▶ LibraryService._validated ──▶ 422 naming your domain
                                          (validate_status / _formats /
                                           _entry_fields / _metadata_patch)
```

You write the declaration. **You do not write a single screen.**

And this is one add, end to end, with every point your domain is consulted marked `◆`:

```text
   somebody types "Outer Wilds" or pastes a URL
        │
        ▼
   ◆ recognize(value)          each domain in turn, until one answers
        │                      → an ISBN? an IGDB URL? nothing?
        ▼
   ◆ your adapter.search()     your rate limit, your auth, your parsing
        │                      → SearchCandidate rows
        ▼
   ◆ identity_key()            merge_and_rank asks your strategy which rows
        │                      are the same record — `None` means never merge
        ▼
     the confirm screen        rendered from ◆ your field spec, with
        │                      ◆ your statuses and ◆ your formats offered
        ▼
   ◆ your adapter.fetch()      the full record, once, on demand
        │
        ▼
     cover pipeline            you supply URLs; it owns https, the allowlist,
        │                      redirects, pixel and byte bounds
        ▼
   ◆ validate_status / _formats / _entry_fields / _metadata_patch
        │                      all keyed on the item's own domain — a 422 here
        │                      names your domain and leaves nothing written
        ▼
     items + entries           the neutral core. One row. No domain columns.
```

Nine `◆`, and every one of them is a value or a function you declared in your package.

---

## 2. The whole job, on one page

| # | What | Where | Required |
|---|---|---|---|
| 1 | Your domain package | `backend/src/book_tracker/domains/<item_type>/__init__.py` | yes |
| 2 | Your provider adapter | `backend/src/book_tracker/domains/<item_type>/providers.py` | yes |
| 3 | Register the domain | `domain/registry.py` — one import, one tuple entry | yes |
| 4 | Publish your values | `domain/registry.py` — `EntryStatus`, `EntryFormat`, `ItemTypeName` | if you declare a status or format no domain has |
| 5 | Mirror them client-side | `frontend/src/api/library.ts` — `entryStatuses`, `entryFormats` | same condition as 4 |
| 6 | Wire the adapter | `main.py` lifespan — construct it into the provider catalog | yes |
| 7 | Credentials | `config.py` + `.env.example` | if your provider needs a key |
| 8 | Cover host | `infrastructure/covers.py` allowlist | if your art is hosted somewhere new |
| 9 | Recorded responses | `backend/tests/fixtures/providers/` | yes |
| 10 | Your importer | `backend/src/book_tracker/domains/<item_type>/<source>.py` | if this domain imports an external source |
| 11 | Register the importer | `domain/registry.py` — one import, one tuple entry | same condition as 10 |

**That is the complete list.** Items 3–8 and 11 are the shared registration points, and they are
deliberately shared — §5 explains why each one was kept rather than removed. Everything else about
your domain lives in your own directory.

Items 4 and 5 are two ends of one chain and **you cannot forget either silently**: the registry is
pinned to the backend enums by `test_domain.py`, the enums reach `openapi.json` by generation, and
`openapi.json` is pinned to the client arrays by `src/api/library.test.ts`. A missing link fails a
test rather than dropping your values out of the API or the filter chips.

**Your domain needs no other frontend change at all.** The tabs, chips, pickers, dialogs, hotkeys and
detail layout all render from `GET /api/item-types`. The shared fallback label table in
`features/library/labels.ts` is deliberately *partial*, so your statuses need no entry there — before
the registry arrives a row renders its stored value, which is legible.

**No migration.** `entries.status` has had no CHECK constraint since migration `0014`, precisely so a
domain's vocabulary is never a schema change (DEC-067 row 1).

---

## 3. Step by step

The worked example throughout is `domains/album/`, which is the shortest complete domain in the
repository — read it start to finish, it is about 120 lines.

### Step 1 — Create the package

```text
backend/src/book_tracker/domains/game/
├── __init__.py      # the declaration: fields, statuses, formats, identity, recognizer
└── providers.py     # the adapter that talks to IGDB
```

### Step 2 — Declare the domain

Every field of `Domain` is an obligation. There are no book-shaped defaults to inherit: the five
vocabulary fields are **required**, so a domain that forgets one fails to construct rather than
silently rendering as a book.

```python
DOMAIN = Domain(
    item_type="album",              # stored in items.type — PERMANENT, never renamed
    label="Album",                  # user-facing copy — free to change
    identity=ALBUM_IDENTITY,        # how two candidates are judged the same record
    fields=ALBUM_FIELDS,            # your metadata, described (not modelled)
    statuses=ALBUM_STATUSES,        # your vocabulary, in the order a control offers it
    default_status="owned",         # what a newly added entry gets
    entry_fields=frozenset(),       # which passage fields you have: none, for an album
    formats=ALBUM_FORMATS,          # how a copy is held
    entry_panel_label="Your copy",  # the heading over the personal region
    enriches=False,                 # background enrichment: see §6
    recognize=lambda value: recognize_album_url(value),
    chooses_covers=False,           # the cover chooser: see §5
)
```

**The rules each part must satisfy**, all enforced by the conformance suite:

- **Statuses.** Values are permanent and stored; labels are copy. Every domain has `unsorted` —
  imports land there and the default library view hides it — and it is never choosable. Every
  choosable status carries a triage hotkey, unique within your domain. The hotkey lives on the
  status, not in a second table that can drift from it.
- **Formats.** Multi-valued on the entry and independent of status, so "wishlist → vinyl" is
  expressible. The vocabulary is **closed and declared**. A value the owner invents is a *shelf*,
  which is a different feature; the two must never converge into one control (DEC-059).
- **Entry fields.** You declare which of `date_started`, `date_finished`, `reread_count` your entries
  have. Anything you do not declare is **refused on write**, not merely hidden — a reread count on a
  record is not a display problem (DEC-057).
- **Metadata fields.** Names are permanent, labels are copy. A `rows` field declares `columns` and no
  other field type may. A field may never shadow `title`, `subtitle`, `year` or
  `creator_sort_override` — those are neutral item columns edited *beside* your metadata.
- **The URL recognizer must answer for any string and must never raise.** `resolve_input` asks every
  registered domain in turn, so a recognizer that throws does not fail your domain — it denies every
  domain after you its turn. Parse through `split_url`, never `urlsplit` directly. (This is not
  hypothetical: it shipped, and `http://[` broke the add box for every domain until Sprint 028.)

### Step 3 — Write the adapter

Implement the `Provider` protocol from `domain/providers.py`:

```python
class IgdbProvider:
    name = "igdb"
    item_type = "game"

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]: ...
    async def fetch(self, source_id: str) -> ItemPayload: ...
```

Your adapter owns its own rate limit, User-Agent and authentication. It reaches for the shared HTTP
boundary in `infrastructure/providers.py` — `bounded_json` (bounded, retrying, size-capped) and
`parse_year` — and it **never leaks a raw provider response above infrastructure**.

Two things to get right, both learned the expensive way:

- **A curated sort name beats a heuristic.** If your source knows how a creator sorts, put it in
  `SearchCandidate.creator_sort`; it seeds the owner's override and the heuristic never runs.
  MusicBrainz knows a Person from a Group and only inverts a person, which is why `Daft Punk` sorts
  under D. A heuristic would have produced `Punk, Daft` (DEC-051, DEC-052).
- **Cover URLs are candidates, not fetches.** Hand the shared pipeline URLs. It keeps sole ownership
  of https upgrading, the host allowlist, redirect policy and the pixel and byte bounds.

### Step 4 — Choose an identity strategy

```python
IdentityStrategy(identity_key=..., source_preference=("igdb",))
```

`identity_key(candidate) -> str | None` decides whether two candidates from different providers are
the same record. **Returning `None` means "never merge", and that is a complete answer, not a
degraded one** — albums return `None` because a barcode was measured on three distinct releases, so
merging on it would be wrong rather than approximate. `source_preference` decides which row of a
merged group wins and breaks ranking ties.

### Step 5 — Register

```python
# domain/registry.py
from book_tracker.domains.game import DOMAIN as GAME

DOMAINS: dict[str, Domain] = {d.item_type: d for d in (BOOK, ALBUM, GAME)}
```

If you declared a status or format no existing domain has, add it to the published union in the same
file (`EntryStatus`, `EntryFormat`, `ItemTypeName`) **and to `entryStatuses` / `entryFormats` in
`frontend/src/api/library.ts`**. These are spelled out by hand on purpose: a dynamically built
`StrEnum` is opaque to mypy and this is a public API surface. **A test fails at each link if you
forget**, so the vocabulary cannot drift between the registry, the API and the client.

Then run `make openapi` so the checked-in schema carries your values.

Then construct your adapter in the `main.py` lifespan, into the provider catalog. Everything else —
`/api/health/providers`, search routing, add-by-URL — picks it up from there.

### Optional step — Add an importer

An importer is for an existing external library, not interactive provider search. Put it in your
domain package and implement `Importer` from `domain/importers.py`:

```python
class SteamImporter:
    name = "steam"                 # permanent route and batch kind
    label = "Steam"                # user-facing tab
    item_type = DOMAIN.item_type    # the domain every normalized row must satisfy
    input = ImportInputSpec(
        kind="upload",             # or "path" for a configured host mount
        label="Steam export",
        field="file",
        accept="application/json",
        # Guidance the shared screen renders without knowing who wrote it.
        # Ordered steps, not markdown: the screen has no markdown renderer and
        # a connector has no business shipping markup into it.
        guide=(
            "Open steamcommunity.com and request your data export.",
            "Download the JSON and drop it below. This is a snapshot, not a sync.",
            "Everything lands in Triage rather than in the library.",
        ),
        empty_state="Drop your Steam export here, or choose a file.",
        help_url="https://help.steampowered.com/",   # https, or leave it out
        browsable=False,            # `path` connectors may set this; see below
        # If one source is reachable two ways, declare the second here rather than
        # registering a second connector — one source, one tab (DEC-081). Exactly
        # one level deep, and it must use a different `field`.
        alternate=None,
        # Per-input, because the shared route's 5 MiB default is the wrong size for
        # some sources and raising it for everyone is how a limit stops meaning
        # anything.
        max_bytes=None,
        max_files=None,
        # Whether `read` can take `ImportSource.directory`. Required by
        # `kind="directory"`; conformance refuses the kind without it.
        accepts_files=False,
        # Whether you can say what is worth uploading before it is uploaded. Needs
        # `IncrementalImporter` and a durable identity in the source; leave it false
        # rather than guess (DEC-082).
        incremental=False,
    )
    identity_kinds = frozenset({"steam_app"})
    # Closed. An undeclared code is republished as `undeclared_import_error`
    # rather than reaching the client, because no screen has copy for it.
    error_codes = frozenset({"invalid_steam_export", "unsupported_export_version"})

    def read(
        self, source: ImportSource, context: ImportReadContext
    ) -> ImportSnapshot: ...

    def stage(
        self, snapshot: ImportSnapshot, directory: Path, data_dir: Path
    ) -> ImportSnapshot: ...

    def match(
        self, record: NormalizedImportRecord, matcher: ImportMatcher
    ) -> MatchDecision: ...

IMPORTER = SteamImporter()
```

`read` owns decoding, source validation and fingerprinting. It returns an immutable snapshot whose
records use only the neutral shapes:

- `ImportItem`: title/subtitle/year, an identifiers mapping, metadata declared by `DOMAIN.fields`,
  and an optional curated creator sort;
- `ImportEntry`: score, notes, date added, values declared by `DOMAIN.entry_fields`, an optional
  provisional score flag and suggested status;
- `NormalizedImportRecord`: those two halves plus shelves, row errors, opaque source fields and an
  optional cover source.

Raise `ImportReadError(code, message, details)` for an invalid source, with the code drawn from your
declared `error_codes`. Give it `user_message` and `action` too: `code` is what the client branches
on and `message` is what the log keeps, but **`action` is the only part a person can act on** — one
imperative sentence naming the next move ("Close Calibre and try again; it locks the database while
it is writing"). Only your connector knows that sentence, which is why the shared layer cannot write
it. Both reach the client in the 422 payload and the screen renders the action beside the message.

Do not return a raw provider row or put domain metadata in `source_fields`: the shared service
validates `metadata`, entry values, status and identity kinds before it calls `match`.

If your source is a **folder on the reader's own machine**, use `kind="directory"` and set
`accepts_files=True`. The screen renders a folder chooser, the client filters the selection to the
members you want and uploads only those, and the route streams them to disk, validates every
client-supplied relative path, and materializes them at `<bundle>/library/...`. Your `read` then
receives `ImportSource.directory` and should point its **ordinary adapter** at that folder — the
whole point is that an uploaded source and a local one normalize through the same code, so the
reader never learns there were two ways in. `CalibreImporter.read` is nine lines and is the worked
example. Declare `max_bytes`/`max_files` honestly: a refusal that names your `alternate` is far
better than a timeout.

**If a re-import would resend what the library already has**, implement `IncrementalImporter` and set
`input.incremental = True`. `plan` receives the cheap half of the source, the client's `{path, size}`
offer, and an `ImportInventory` with two batched questions — `existing` and `with_cover` — and
answers with the subset worth uploading. Plan by a **durable identity** in the source, never by a
digest: the client cannot hash, because `crypto.subtle` is undefined outside a secure context and
this application is served over plain HTTP on a LAN. A source with no stable identity should leave
`incremental` false rather than guess. Remember that the plan is an optimisation the client is
allowed to skip, so `read` must still behave correctly when it receives everything.

If your source is a place the **server** can see, implement `BrowsableImporter` as well and set
`input.browsable = True`. `browse(path, context)` returns an `ImportBrowseResult` with the relative
path, its parent, the **names** of the immediate subdirectories and whether that folder is itself
importable. Names only: an absolute path publishes the deployment's filesystem layout to anyone on
the LAN. Resolve confinement with the same code your reader uses, so the picker can never walk
somewhere a preview could not open — `CalibreAdapter.confine` is the worked example. The screen then
renders a breadcrumb and a folder list at `GET /api/import/<name>/browse`, and the typed path stays
available for automation.

`stage` runs only after fingerprint replay has been checked. Copy an uploaded source into
`directory`, or prepare covers there and return records whose `cover_stage` paths are relative to
`data_dir`. Remove raw bytes and host paths from the returned snapshot. Commit never opens the
source again.

`match` receives the one narrow library operation it may use. Normalize only identifiers listed in
`identity_kinds`, then call `matcher.match(...)`; never query storage directly. Finally register the
connector:

```python
# domain/registry.py
from book_tracker.domains.game.steam import IMPORTER as STEAM_IMPORTER

IMPORTERS_BY_DOMAIN = {
    # ...
    GAME.item_type: (STEAM_IMPORTER,),
}
```

That one entry publishes the tab — with your guide, your empty state and your help link — through
`GET /api/importers`, and serves preview/commit at
`POST /api/import/steam/preview` and `POST /api/import/steam/commit`. The shared service supplies
durable preview, ambiguity choices, one bounded commit, `unsorted` triage, fingerprint idempotency,
the 24-hour undo window and enrichment only when the target domain declares it.

Add parser/adapter fixtures for the source itself and a generic route round-trip. Do not edit the
shared service or screen. `test_domain_conformance.py` is parametrized over registered importers and
will reject a missing protocol member, an unknown target domain, empty identity kinds, a misplaced
registration, a malformed guide, a non-https `help_url`, browsing declared without a `browse`
method, an empty or shouted error vocabulary, a nested `alternate`, an `alternate` reusing the
primary's `field`, a non-positive `max_bytes`/`max_files`, `kind="directory"` without
`accepts_files`, or `incremental` without a `plan` method.

### Step 6 — Prove it

```bash
cd backend && uv run pytest tests/test_domain_conformance.py -q
```

The suite is parametrized over `DOMAINS`, so **your domain is held to the contract by existing**. You
add no test to it. Its checks come in two groups: what your domain satisfies on its own, and whether
the core can host it.

Then the rest of the gates:

```bash
make check && make test          # lint, types, OpenAPI drift, 469 backend + 130 frontend tests
cd frontend && npm run test:e2e  # 86 browser tests
cd .. && make smoke-container    # the container, end to end
```

And **run the application against real data and use your domain**. Passing tests are not evidence
that a flow works — that rule exists because thirteen sprints once closed green on a product whose
entire feedback layer was invisible (DEC-025).

### This guide was tested by following it

A throwaway `game` domain — its own package, three metadata fields, a status vocabulary containing
`playing` and `finished`, its own formats, an identity strategy — was built from this page alone and
registered. **The whole conformance suite passed, the 480 backend tests passed, and no migration was
needed**: a status no other domain declares was accepted by the database on the first try, which is
what migration `0014` bought.

Three things broke that this guide had not predicted, and all three were repaired rather than
documented as gotchas, because a step you have to know about is a step this guide failed to remove:

1. A conformance test used `playing` as its example of "a status no registered domain declares" — a
   real games domain would have broken its premise. It derives an unclaimed value now.
2. `test_item_types.py` asserted the published set was exactly `{"book", "album"}`. It asserts
   against the registry now.
3. The frontend's fallback label table was an exhaustive `Record`, so a new status was a TypeScript
   error until somebody added a label. It is `Partial` now, and the lookup falls back to the stored
   value.

The only gate that failed for a legitimate reason was the OpenAPI drift check, which is Step 5's
`make openapi`. That is the guide working.

---

## 4. What you get for free

Everything below already works for your domain the moment it is registered. If you find yourself
writing any of it, stop — you are about to duplicate something:

| | |
|---|---|
| The library screen | tabs, status chips, format picker, sorting, keyset pagination, facet counts |
| The detail page | your metadata fields in your order, your status vocabulary, your panel heading |
| Triage | your hotkeys, bulk operations, selection across pages |
| The add flow | search, add-by-URL, manual entry and the confirm screen rendered from your field spec |
| Import | registry-driven source tab rendering your declared guidance, preview/commit, validation, a folder chooser for a directory source and a picker for a browsable one, your alternate beneath your primary, triage as a tab, and undo |
| Shelves | the owner's own tier of organisation, across every domain |
| Import ledger and undo | 24-hour reversal of anything an import did |
| Export | entity-shaped JSON carrying `type`, identifiers and your opaque metadata |
| Attachments | files on an item, addressed by content digest |
| Backup and restore | nightly, verified, with a tested restore |
| Covers | validated, resized, stored locally, never re-fetched while a page renders |

---

## 5. What a domain may never touch

- **`items` and `entries` columns.** Everything your domain knows that the neutral columns do not
  carry goes into opaque `metadata`. Never add a column; never store a value one of the four reserved
  item columns already holds.
- **Another domain.** Do not import one, read its vocabulary, or render under its labels. A value two
  domains share (`wishlist`, `digital`) is a coincidence of spelling, not shared state.
- **The shared pipelines.** Keyset pagination and cursors, the job runner, the import ledger and
  undo, backup, attachments, shelves, and the score/notes/dates entry layer belong to the core. If
  your domain appears to need a change in one of them, you have found a seventh seam — that is a
  decision to record in `docs/decisions.md`, not a patch to make.
- **The cover pipeline's safety rules.** You supply URLs. You do not relax the scheme, the allowlist,
  the redirect check or the size bounds.
- **The screens.** No screen branches on the item type. If a screen must render differently for your
  domain, declare the difference and let the screen render your declaration.

**Four couplings are deliberate** and were kept after being costed (DEC-067). Do not "fix" them
without reading that entry:

1. **The published unions are hand-spelled.** Three type-safe lines, and a test refuses to let them
   drift. Every alternative was worse.
2. **The cover host allowlist is central.** It is central precisely so a domain cannot widen it from
   its own package. That is what an allowlist is for.
3. **`chooses_covers` declares a capability, not a mechanism.** The shared chooser is Open Library's
   work-editions path, so only a domain Open Library serves may declare it. The conformance suite
   enforces that. Generalising the mechanism is a real option and nothing has needed it yet.
4. **The detail route is `/books/:id` for every domain.** Cosmetically wrong, not worth the churn.

---

## 6. One thing that is not solved yet

Read these before you design around them.

**Background enrichment is ISBN-keyed.** `Domain.enriches` is a real switch — a domain that declares
`False` is queued no jobs — but everything behind it (`_backfillable_items`, `_fetch`,
`PROVIDER_ORDER`) assumes an ISBN and books' provider order. **No domain has ever exercised that
seam**: albums declare `False` because one MusicBrainz fetch returns everything an album has. If your
domain genuinely needs background enrichment on another key, that is the point at which the seam gets
built properly, with your real case to design against (DEC-067 row 3). Declare `enriches=False` and
say so in your sprint or issue.

---

## 7. A worked verdict: games on IGDB

DEC-068 walked IGDB against this contract without writing any code, and that walk is the best
available example of what "planning a domain" looks like here. In short:

| Seam | Verdict |
|---|---|
| Creators | Companies never invert, so the adapter supplies `creator_sort` unchanged. **No new seam.** |
| Identity | One provider, so `identity_key` returns `None`. **No new seam.** |
| Metadata | Platforms, genres, summary, release year all fit existing field types. **No new seam.** |
| Covers | One allowlist entry for `images.igdb.com`. **No new seam.** |
| Statuses | Games want `playing` and a backlog. That is the vocabulary working as designed. **No new seam.** |
| Enrichment / add-by-URL | One query returns everything; `enriches=False`. **No new seam.** |

**What games need that nothing has needed: authentication with a lifetime.** IGDB requires Twitch
client credentials exchanged for a token that expires and must be refreshed, where every provider so
far needed at most a static key. That is not a seam — it fits inside the adapter — but it is the
first adapter to hold mutable state and a secret pair.

That verdict is **reasoned from published documentation, not measured against the live API.** Do not
cite it as measurement; it carries its own list of what to verify first.

---

## 8. File map

| Path | What it is |
|---|---|
| `domain/spec.py` | What a domain *is*: `Domain`, `FieldSpec`, `StatusSpec`, `FormatSpec`, the validators, `UrlMatch`, `split_url` |
| `domain/registry.py` | Which domains *exist*: `DOMAINS`, `DEFAULT_DOMAIN`, the three published unions |
| `domain/providers.py` | `SearchCandidate`, `ItemPayload`, the `Provider` protocol, `IdentityStrategy`, `merge_and_rank` |
| `domain/importers.py` | The `Importer` protocol and neutral import snapshot/record shapes |
| `domains/book/` | Books: declaration, Open Library and Google Books adapters, Goodreads and Calibre importers |
| `domains/album/` | Albums: declaration, MusicBrainz and Cover Art Archive adapter |
| `infrastructure/providers.py` | The shared HTTP boundary only: `bounded_json`, `parse_year`, retry policy, the client |
| `backend/tests/test_domain_conformance.py` | The suite every domain passes by existing |
| `backend/tests/fixtures/providers/` | Pinned real provider responses. **Never re-record one to make a test pass** |

---

## 9. Where the reasoning lives

This guide says *how*. The reasoning behind each rule is in `docs/decisions.md`, and the entries
worth reading before you design a domain are:

- **DEC-052** — the six seams, and why albums are not books with a different identifier field.
- **DEC-057 / DEC-059** — what an entry is per domain: status is a *concept*, format is an
  independent axis, a shelf is neither.
- **DEC-060** — what `Domain` declares about entries, as built.
- **DEC-066 / DEC-067** — what a third domain cost before Sprint 028, and the costed decision behind
  every coupling that remains.
- **DEC-068** — the IGDB walk.
- **DEC-069** — what moving the code found that reading it could not.
- **DEC-076 / DEC-078** — why importers are domain-owned, and the concrete boundary that shipped.
