# From working to finished — a production-grade proposal

**Status: accepted** (DEC-165, 2026-10-21) after the owner reviewed a mock of the look; scheduled
as Sprints 087–101. Written 2026-10-21 at the owner's request, after v2.3.0 closed Sprint 086 and
the plan stood complete at 86/86. §9's decisions are answered in DEC-165.

The owner's words: *"it still feels like a vibe-coded project of sorts, no theme selection, no
microanimation, no intent in the design (feels generic). the import screen is messy, some user
flows are not easy to get to (drag ebooks) or some QOL features are still missing (paste media
URL to add quickly) or dont feel that great to use. I want you to propose a set of changes, as
big in scope as you feel like, to improve the system and make it feel 'production grade'."*

The evidence comes from three places:

- the application run against the owner's own data, at 1440px and 390px wide;
- a read-only audit of every page, component, connector and service;
- spot checks of the audit's claims against the code.

Line references describe the tree at `e8127f6`.

---

## 1. The diagnosis in one paragraph

The code is disciplined. Tokens are used: about 481 semantic colour classes against 10 raw
palette classes. Motion is centralised and honours reduced motion. The domain contract holds,
since nothing above the registry branches on item type. 1,264 backend tests, 337 Vitest cases
and 209 Playwright tests stand behind it.

**It feels generic because the brief asked for generic, and because the application grew one
sprint at a time.** `brand-handoff.md` asks for:

- dark only;
- zinc greys with one amber accent;
- Inter only;
- "nothing playful".

Every one of those was honoured. What was never built is the half of the brief that carries
the intent: "closer to a card catalogue or a reading journal" (`brand-handoff.md:25-28`). Nothing
on screen looks like either one. The UI is effectively one type size (`text-sm`, 165 uses) at two
weights.

On top of that, 86 sprints each added a screen or a connector and none owned the paths between
them. Adding something has three doors, and the best one is hidden. Import has grown into a
1,561-line component that also hosts Triage and Export.

None of this is a defect in behaviour. It is the absence of an owner for the whole.

---

## 2. Findings

Grouped by what the owner named. The **#** column is referenced by the sprints in §8.

### 2.1 Identity, theme and motion

| # | Finding | Where |
|---|---|---|
| D1 | **No theme choice exists and none can be added cheaply today.** The things that pin it to dark: `color-scheme: dark` is set on `:root`; there is no light token block; `darkMode: ["class"]` is configured but never toggled; `index.html` hardcodes `theme-color #09090b`. Two `dark:` variants in the act-as banner have never applied. The good news is that the semantic token layer means a second theme is a token file, not a rewrite. | `index.css:14-60,56`, `AppShell.tsx:142,147` |
| D2 | **One typeface, one size.** Inter only, with no display or serif face. `text-sm` ×165 and `text-xs` ×75, against `text-2xl` and up ×13 in the whole app. `tracking-tight` appears 4 times. The 1.65 body line height that `brand-handoff.md:92` specifies is not set anywhere. | `tailwind.config.ts:68-70` |
| D3 | **The brand's motif is unused.** The mark is "an arch enclosing a single point of light" (`BRAND.md:11`). It appears in the logo and nowhere else: not in empty states, loaders, the focus ring, or the score commit. The *PERSONAL LIBRARY* lockup the brand docs call "the closest thing the product has to an identity" no longer exists in the code. | `brand-handoff.md:98-103` |
| D4 | **Motion exists in five places and is disabled by construction in the rest.** `LazyMotion features={domAnimation} strict` removes `layout`/`layoutId` from the whole app. Shared-element transitions (cover → detail), list reordering and animated nav indicators are therefore impossible. There are no route transitions, no hover or press feedback on cards (no `active:` class anywhere), no drag-over state on drop zones, and no enter/exit on library, shelf or proposal rows. | `AppShell.tsx:173-178` |
| D5 | **Depth is flat.** 19 shadow uses in total. Surfaces differ only by a zinc step. The detail page is a stack of identical bordered boxes. | `DetailPage.tsx` |
| D6 | **Loading is the word "Loading…".** There is no skeleton component; the cover pulse is the only placeholder. Examples: the route fallback, `DetailPage.tsx:209`, `PeoplePage.tsx:371`, `CoverDialog.tsx:83`, `Attachments.tsx:127`. | `App.tsx:68-74` |
| D7 | **Empty states are one muted sentence**, with no illustration, no mark and no next action. | `ShelvesPage.tsx:179,184`, `InsightsCard.tsx:94,100`, `HomePage.tsx:956` |
| D8 | **Native controls show through the design.** Unstyled native `<input type=file>` controls read *"Choose File  No file chosen"* on Add, Import and the detail page's *Replace cover*. There are about 15 native `<select>`/`<input>` controls outside `ui/` (Import separator, Import library, People, Triage). | screenshots; `ImportPage.tsx:712-715` |
| D9 | **Missing primitives**, so pages hand-roll them: card, badge, skeleton, tooltip, dropdown-menu, sheet/drawer, separator, kbd. There are 23 hand-written `rounded-* border` boxes outside `Panel`. | `components/ui/` |

### 2.2 Getting things in

| # | Finding | Where |
|---|---|---|
| A1 | **Paste-a-URL already works, and nobody can tell.** Each domain declares `recognize`. Between them they cover Open Library, Google Books, MusicBrainz, AniList, Kitsu, MAL, IMDb, TMDB, Letterboxd, boxd.it, TVDB, TVmaze and Wikidata, and `GET /api/search/resolve` routes to the right one. The library search box sends URLs there, but only as its placeholder hints (*"Title, creator, ISBN or link"*), and only after the library match returns zero rows. The feature the owner asked for is about 90% built and 0% visible. | `api/add.ts:81-83`, `application/providers.py:65-129`, `HomePage.tsx:544-561,666` |
| A2 | **Three doors to "add", and the best one is not the one labelled Add.** The nav's *Add* opens ebook drop plus a 17-field manual form. Its lede tells you to go elsewhere: *"To add from a provider, search from the library."* The header's yellow *Add* only focuses the search box. Searching providers, the thing most adds are, lives on the Library screen. | `AddPage.tsx:84`, `HomePage.tsx:847-849` |
| A3 | **URL gaps.** Links without a scheme (`imdb.com/title/tt…`) skip resolution. Spotify album links are not recognised, although album identity *is* `spotify`. Goodreads links are not recognised. The not-found message lists only book and album examples. | `api/add.ts:81`, `application/providers.py:127-128` |
| A4 | **Dropping files works in two places only.** You can drop on `/add` and `/import`. Dropping an EPUB on the library — the screen with the *Add* button — does nothing. Global drop was explicitly scoped out of Sprint 086. | `SourceDropZone.tsx:32-37`, Sprint 086 |
| A5 | **Web search results are noisy.** A search for "dune" puts *Go Ask Alice*, *Peril at End House*, *Potent Pleasures* and *Mémoires d'une jeune fille rangée* among the first 20. Provider ids are printed in amber capitals (`OPENLIBRARY`). There is no visible *Add* affordance on a result: the whole card is the button. | live, `/?q=dune` |
| A6 | **Phone width is an afterthought on the main screen.** At 390px the library header stacks to about 280px before the first cover. The grid is one column, so one book per screen of scrolling. The brand mark is missing from the mobile shell. AddPage and ShelfPage have zero responsive classes. | `m-library` screenshot |

### 2.3 Import

| # | Finding | Where |
|---|---|---|
| I1 | **One component, everything in it.** `ImportPage.tsx` is 1,561 lines with 26 `useState` and 10 `useEffect`, and its test file is 2,688 lines. It holds all of the following: nine connectors' input variants, CSV column mapping with a sniffed sample row, Calibre bundle planning, proposal polling, ambiguity answers, attachment upload and the undo window. It also hosts Triage and Export as tabs. | `ImportPage.tsx:112-1561` |
| I2 | **Tabs inside tabs.** The page stacks an *Import / Triage / Export* step strip, then a horizontally scrolling strip of nine sources that is cut off mid-word at 1440px, then a numbered guide, then the form. At 390px the step strip wraps each label over four lines. | screenshots |
| I3 | **Four names for two places.** The nav item is *Data*, the page is *Import*, the second step is *Triage*, its title is *Inbox*, and the library button is *Inbox 0*. | `AppShell.tsx:48`, `TriagePage.tsx:671-672`, `HomePage.tsx:843` |
| I4 | **Words the reader cannot use.** The ambiguity choice reads *"Use existing item 42"*, a database id, with no cover or title. Other examples: *"Choice for {title}"*; *"How to get a Your list"*, a template bug in `ConnectorGuide.tsx:92`; and provider ids printed verbatim. | `ImportPage.tsx:1319,1339-1346` |
| I5 | **The user picks the source, though the file already says what it is.** A Letterboxd zip, a Trakt zip, a Spotify data zip, a MAL XML and a Goodreads CSV each have unmistakable contents. The user still chooses one of nine tabs first. | `ImportPage.tsx:861-904` |
| I6 | **After commit, nothing tells you anything.** Enrichment jobs are queued per item, and `GET /api/import/jobs/{id}` and `getJobProgress` exist, but **no screen calls them**. Covers and metadata arrive silently, or don't. | `api/imports.ts:496`, `application/imports.py:1108-1113` |
| I7 | **Two review passes.** Rows are confirmed on the preview, then reviewed again in Triage, where every imported entry lands as `unsorted`. That holds even when the source already said *read, 8/10, finished 2024-03-02* (Goodreads, Letterboxd, MAL). | DEC-079 |

### 2.4 Reliability under the surface

| # | Finding | Where |
|---|---|---|
| R1 | **The job runner can reclaim a job that is still running.** It uses a 5-minute lease, and `heartbeat()` is defined but never called. A large `search_import_rows` batch is therefore reclaimed and counted as another attempt. | `jobs.py:30,152` |
| R2 | **Rate limiting dead-letters enrichment.** When the limiter is not ready, enrichment returns `state: failed, error_code: rate_limited`, which spends a retry. Back-to-back jobs can exhaust all three. Import search waits instead, which is the correct behaviour. The limiter is one global timestamp, not one per provider. | `enrichment.py:294-299`, `jobs.py:334`, `import_search.py:171` |
| R3 | **Sync database work on the event loop.** `api/library.py` has 30 async routes and no `off_loop`. Auth middleware does two sync lookups on every request. Job handlers open sync sessions inside `async process`. With one worker, a slow job stalls every request. | `main.py:377,383`, `enrichment.py:230,239` |
| R4 | **Search is a leading-wildcard `LIKE`** over title and first creator. It ignores secondary creators, series, notes and subjects, and scans every row. | `application/library.py:842-852` |
| R5 | **The API contract is mirrored by hand.** The TypeScript types are written by hand, and the checker only asserts that about 15 property names exist. Error parsing is re-implemented in five client files. `auth.ts` calls raw `fetch` 8 times. Three error shapes reach the client: the envelope, `{"detail": …}` from the catch-all and `HTTPException`, and FastAPI's default 422. | `scripts/check-openapi-types.mjs`, `main.py:357,579`, `auth.py:123` |
| R6 | **Provider health says "configured", not "working".** There is no response cache, no circuit breaker, and no record of recent failures. A provider outage is invisible until a search comes back thin. | `main.py:534-563` |
| R7 | **No request ids, no metrics.** A self-hoster debugging a slow import has structlog JSON and nothing to join it on. | `logging.py` |
| R8 | **Small rot.** Examples: `compose.yaml` defaults the image to `1.5.7` while the app is 2.3.0; `manifest.webmanifest` still says "personal book tracker"; `create_app` is 448 lines; the patch-entry optimistic update is copy-pasted between Triage and Library; there is no query-key factory. | `compose.yaml:28`, `TriagePage.tsx:220-264`, `HomePage.tsx:350-390` |

### 2.5 Defects seen during the walkthrough

They are recorded so they are not rediscovered. Each is small.

- *Harry Potter and the Sorcerer's Stone* has `language = "{'"`. A provider handed back a
  structured value and normalisation kept its first two characters. Insights then shows a
  language chip reading `{'`.
- Book descriptions from Wikipedia render their Markdown literally (`*Rayuela* es la segunda…`).
- A book's *Subjects* is an unsorted dump of 30 provider strings, duplicates included
  (*Fiction*, *Fiction, general*, *Fiction*).
- The DEC-105 TVmaze credit sits under every screen, books and albums included. The decision is
  correct; the placement could be an About panel plus the series screens.
- The detail route is `/books/:entryId` for all five domains.

---

## 3. Design direction: make the catalogue literal

The brand already chose its metaphor: a card catalogue, a reading journal, an arch with one
point of light. The proposal is to draw that metaphor instead of describing it. It is the cheapest
way to "intent", because the decision is already made and recorded.

### 3.1 Alternatives

| Option | What it is | Cost | Verdict |
|---|---|---|---|
| **A. Polish in place** | Keep zinc, amber and Inter. Add skeletons, motion, a light theme mirrored from dark. | ~2 sprints | Fixes D4, D6 and D7. It does not answer "generic": the result is a better-finished version of the same default shadcn look. |
| **B. Editorial catalogue** *(recommended)* | Pair a serif display face with Inter for UI. Add two first-class themes: *Ink* (today's dark, warmed) and *Paper* (warm off-white, not inverted zinc). The arch motif carries loaders, empty states and the score commit. Your own data is drawn as calm property rows. | ~3 sprints | It takes intent from documents that already exist. It is reversible at the token layer and changes no behaviour. |
| C. Per-domain accent colours | Books amber, films red, music green… | ~2 sprints | **Rejected.** `BRAND.md:207` forbids a second colour for a reason that still holds: colour already means *score* (DEC-026). Domain identity belongs in iconography and type. |
| D. Full redesign by an outside designer | | unknown, owner's money | Out of an agent's hands. B would give a designer a coherent system to start from rather than one to undo. |

### 3.2 What B consists of

**Themes.**

- Setting: `system | ink | paper`. It is stored per user (Sprint 077 gave users a row), with
  `localStorage` as the first-paint cache.
- `theme-color` and `color-scheme` follow the setting.
- *Paper* is designed rather than inverted:
  - a warm ground (about `#f6f3ec`) and ink text (about `#1c1917`);
  - amber deepened to about `amber-600` so it passes AA as text;
  - the score ramp re-measured for contrast on paper, keeping the same hues and meaning.
- Covers get a hairline border and a soft shadow on Paper, because a jacket on white needs an
  edge.
- *Ink* keeps today's ground and gains a small warm shift and an elevation scale (D5).
- This **amends `brand-handoff.md` §"Environment: dark only"**, which is a decision for the owner
  (§9).

**Type.**

- Add a self-hosted serif for display: titles on detail and shelf pages, page headings, and the
  wordmark.
- Candidates are *Newsreader* and *Fraunces*, both OFL and both on Fontsource. Pick one by
  setting the detail page in each against real covers.
- Inter stays for every control.
- Set a real scale with `tabular-nums` on counts and scores, and apply the 1.65 body line height
  the brand doc already specifies.

**Motif.**

- The arch-and-dot becomes the loader: the dot breathes inside the arch.
- It also becomes the empty-state illustration: an empty arch, *"Nothing on this shelf yet"*
  with the one action that fills it.
- It becomes the score-commit flourish: the dot settles.
- On the detail page, *Your reading data* becomes a list of property rows: a muted label with a
  small icon, a plain value, and a soft fill on hover that shows the value can be edited in
  place. Status and shelves are soft tinted pills; the note is a tinted callout marked with the
  arch. These are borrowed from Notion's patterns, not its look. A lined index card was mocked
  and rejected by the owner on 2026-10-21 as skeuomorphic.

**Motion system.** A short written budget is added to the brand doc and enforced in review:

- Remove `strict` and load `domMax` lazily, which is about 25 kB gz more, measured in the sprint.
  This makes `layoutId` possible.
- **Cover → detail shared-element transition.** This is the single most "finished"-feeling
  change available. The View Transitions API is the alternative; Firefox support decides it in
  the sprint.
- Route crossfade, 120–160 ms.
- Animated nav and segmented-control indicator.
- List enter/exit for library, shelf, Triage and proposal rows.
- Press feedback (`scale .98`) on cards and buttons.
- Drop-zone drag-over state.
- Skeleton → content crossfade.
- Toasts restyled to the system.
- Every item has a reduced-motion variant; the existing `lib/motion.ts` pattern already does
  this.
- What it does not do: no bounce, no confetti, no parallax. "Nothing playful" stays true.

**Primitives (D8, D9).** The new pieces are:

- Card, Badge, Skeleton, Tooltip, DropdownMenu, Sheet (bottom sheet on phones), Kbd and
  EmptyState;
- a styled FilePicker that replaces every native file input;
- every remaining native control moved onto the Radix ones.

The cohesion rules of `ui-cohesion-proposal.md` §1 stay in force, and these are what make them
cheap to keep.

---

## 4. Getting things in: one door

The principle: **anything you can hand Akasha — a title, a link, an ISBN, a file — goes in the
same place, and that place is everywhere.**

### 4.1 The command bar

- `⌘K` / `Ctrl+K`, `/`, and a visible search field in the shell open one command bar. `cmdk` is
  already a dependency and `CommandDialog` exists but is unused.
- The bar does four things:
  - **Finds in your library:** titles, people, shelves.
  - **Finds on the web:** provider search, grouped by domain, with an explicit *Add* button and
    the status picker inline. This means no trip to a separate screen.
  - **Resolves** a pasted link or ISBN straight to one confirm card: cover, title, *Add as
    "Want to read"* / *"Read"*.
  - **Navigates and acts:** *Go to Insights*, *Import a file…*, *Switch theme*, *New shelf*.
- On phones it is a full-height sheet behind the search icon in the bottom bar.
- The Library screen keeps its own filter box for *filtering*. Adding moves out of it, so A2's
  three doors become one.

### 4.2 Paste and drop anywhere

- **Global paste.** Pasting a URL or ISBN anywhere outside a text field opens the command bar
  already resolving it. *Copy link in browser → switch tab → ⌘V → Enter* is the whole flow.
- **Global drop.** Dropping a file anywhere shows a full-window drop veil (*"Drop to add"*).
  Akasha then sniffs the file (§5.2) and routes it: EPUBs to quick-add, exports to the matching
  importer.
- **Phone share target.** A `share_target` in the web manifest makes Akasha appear in Android's
  share sheet. Share an IMDb or Letterboxd page from the phone and it is added. This needs a
  service worker, which also buys an offline shell (A6 is related). iOS Safari has no share
  target, so a bookmarklet covers desktop browsers there.

### 4.3 More links resolve (A3)

| Link | How | Cost | Note |
|---|---|---|---|
| Any recognised link without `https://` | Normalise before matching | trivial | |
| Spotify album | **a.** keyless oEmbed (`open.spotify.com/oembed`) for the title, then MusicBrainz search plus the existing confirm step. **b.** The Spotify Web API (client-credentials key). | a: ~⅓ sprint · b: ~½ | Recommend **a**. It keeps the "no keys required" posture, and the confirm step already exists. |
| Goodreads book | **a.** Fetch the page and read the ISBN from its metadata. **b.** Search by the title slug. | a: small, fragile · b: small, weaker | Recommend **b**, falling back to the confirm step. Scraping Goodreads is a terms question for the owner. |
| Apple Music, Bandcamp, Discogs, Hardcover, StoryGraph, MyDramaList | Title from the page `<title>`/OpenGraph, then search and confirm | ~⅓ sprint for a generic *"read the page's title"* fallback | One generic recogniser rather than one per site. |

### 4.4 Add page

`/add` keeps the manual form, which is the correct last resort. The form changes as follows:

- It **shows only the domain's required fields first**, with the other twelve behind *More
  details*.
- The drop zone becomes the styled FilePicker.
- Its lede points at the command bar.

---

## 5. Import, redrawn

### 5.1 Shape

A single **Import** page and a single **Inbox** page. Together they get one nav entry, *Import*,
which carries the inbox count as a badge. The *Data* label and the step strip are retired. Export
moves to *Settings → Your data*, next to backup, where the other "take everything with you"
controls live.

Import becomes three steps, each its own component and each its own route segment, so Back works:

1. **Source.** A big drop area (*"Drop an export from Goodreads, Letterboxd, Trakt, IMDb,
   MyAnimeList, Spotify, Calibre — or EPUBs"*) above a grid of source cards. Each card shows a
   domain icon, the source name and *"How to get this file"* behind a disclosure. A dropped file
   is detected (§5.2) and skips the grid.
2. **Check.** One table:
   - *Ready* rows collapsed to a count with covers.
   - *Needs a choice* rows expanded. An ambiguity shows **both covers side by side**: *"Your
     copy of Rayuela (Alfaguara, 2000)"* against *"A separate edition"*, never an id (I4).
   - *Problems* rows expanded, with the domain's field label and the connector's wording.
   - The custom-list column mapping lives here, inline on the sample rows, not as three number
     inputs.
3. **Done.**
   - Counts.
   - A live **arrivals** strip: covers filling in as enrichment completes (I6, via §6.1's job
     stream).
   - The 24-hour undo.
   - *Review in Inbox* when anything needs it.

Each connector's input variant becomes its own component behind one `SourceInput` interface. That
is a frontend mirror of `ImportInputSpec`, rendered from the declaration in the same way §6.6
renders domains. `ImportPage.tsx` becomes a router of three steps of a few hundred lines each.

### 5.2 Source detection

Add `sniff(head: bytes, name: str) -> float` to the `Importer` protocol, an optional extension
like `BrowsableImporter`. `POST /api/import/detect` returns the ranked connectors. The signals:

| File | Signal |
|---|---|
| Letterboxd | zip containing `watched.csv` and `ratings.csv` |
| Trakt | zip with `watched-*.json` |
| Spotify | zip containing `YourLibrary.json` |
| Goodreads | CSV header `Book Id,Title,Author,…` |
| IMDb | CSV header `Const,Your Rating,…` |
| MAL | XML root `<myanimelist>` |
| EPUB | `mimetype` = `application/epub+zip` |

A file nothing claims falls back to the custom-list connector with the domain picker. This is
the change that makes "drag anything" a real flow rather than a feature on one screen.

### 5.3 The second review (I7): alternatives

| Option | Behaviour | Verdict |
|---|---|---|
| A. Keep it | Everything lands `unsorted`. | Safe, and it is the behaviour DEC-079 chose. It is also the friction the owner feels. |
| **B. Trust what the source stated** *(recommended)* | Rows whose source carries a status (Goodreads shelf, Letterboxd watched, MAL status, Trakt history) land with that status. Only rows without one, or with a low-confidence match, go to Inbox. A checkbox on step 2 (*"Send everything to Inbox instead"*) keeps A available. | One preference and one branch in commit. It reverses part of DEC-079, so the owner decides. |
| C. No Inbox | Everything lands directly. | Rejected. Custom lists and EPUBs have no stated status, so they need a place to wait. |

---

## 6. Engineering: what "production grade" means underneath

### 6.1 Jobs that tell you what they are doing

- Fix R1 and R2:
  - heartbeat from long handlers, or per-row lease extension;
  - `rate_limited` returns `deferred`, not `failed`;
  - one limiter per provider, keyed by the provider's declared interval.
- Write `progress` incrementally.
- Add **`GET /api/events`** (Server-Sent Events) streaming job and batch progress for the current
  user.
  - Polling is the alternative. It costs less to build and more to run, and it is what the
    import page already does with `setInterval`.
  - SSE needs no new dependency in FastAPI or the browser, and it survives the single-worker
    deployment.
- A small **activity indicator** in the shell (the arch's dot, pulsing) shows background work
  anywhere in the app and opens a list of recent jobs, failures included, with *Retry*.

### 6.2 The request path stops blocking

- Convert sync-bodied async routes to plain `def`, so FastAPI's threadpool runs them, or wrap
  them in the existing `off_loop`. One rule, checked by a test that walks the route table.
- Move the auth middleware's two lookups off the loop.
- Run job handlers' database work through `off_loop`.

### 6.3 Search

Add an **FTS5** virtual table over title, every creator, series, subjects and notes, kept by
triggers and built by migration. It is accent-folded with the existing `normalize_text`, ranked
by bm25 with a title boost. This replaces R4's `LIKE` and makes the command bar's library half
instant at any library size. Backfill runs in the migration, and SQLite ships FTS5 in the
official image.

### 6.4 One contract, generated

- Generate the TypeScript types with `openapi-typescript` and a thin typed `fetch` wrapper
  (`openapi-fetch`, 6 kB). This replaces the hand-written mirrors and the property-name checker;
  CI fails when the generated file is stale.
- Have one `ApiError` parse the one envelope. Server-side, add handlers for
  `RequestValidationError`, `HTTPException` and the catch-all 404, so nothing else reaches the
  client (R5).
- Add a query-key factory and a shared `usePatchEntry` optimistic hook (R8).

### 6.5 Decomposition, done as part of the sprints that touch each file

This is not a standalone refactor sprint:

| File | Lines | Into |
|---|---|---|
| `pages/ImportPage.tsx` | 1,561 | `features/import/{SourceStep,CheckStep,DoneStep}` + one `SourceInput` per input kind (§5.1) |
| `pages/HomePage.tsx` | 1,145 | `useLibraryQuery`, `LibraryToolbar`, `useLibraryShortcuts`; adding moves to the command bar (§4.1) |
| `pages/TriagePage.tsx` | 1,099 | `useInbox`, `InboxBulkBar`, `useInboxShortcuts` |
| `application/library.py` | 1,582 | `library/{query,insights,covers,attachments}.py`; `LibraryError` → `application/errors.py` |
| `main.py:create_app` | 448-line function | `app/{providers,middleware,errors,health}.py`; the provider catalogue built from the registry, not eight `catalog.append` calls |
| `application/undo.py:undo` | 267-line if/elif | one handler per effect type in a table |

Routes stop importing `DomainRepository`, SQLAlchemy and covers directly
(`api/library.py:853,1144`, `api/export.py:20-28`, `api/auth.py:15`).

### 6.6 Operability

- A request id per request, carried in logs and returned as `X-Request-Id`.
- An opt-in `/metrics` endpoint (`AKASHA_METRICS=on`) covering:
  - queue depth;
  - job outcomes by type;
  - provider latency and error rate;
  - request latency.
- Provider health becomes *working / degraded / down* from the last N calls, so
  `ProviderHealthNotice` says something true.
- A small TTL response cache (in SQLite, keyed by provider and query, about 24 h) for search and
  resolve. It makes repeated imports and the command bar faster and kinder to free APIs.
- Fix `compose.yaml`'s default tag. Add a release check that every version surface agrees.

---

## 7. New capability

Costed in sprint fractions. Each item is independent of the redesign unless marked.

| Feature | What | Cost | Note |
|---|---|---|---|
| **Now** strip on Library | Things *in progress* across every domain at the top of the library: covers with progress bars and one-tap *+1 episode / +10 pages*. | ½ | Progress already exists per domain. This is the screen people would open daily. |
| **Diary** | A chronological view of finished dates across all domains, by month: *"March: 3 books, 5 films, 1 album"*. With covers, it is the "reading journal" the brand promises. | ½–1 | Reads existing `date_finished`. No schema change. |
| **Year in review** | A shareable single-page summary per year, rendered from Insights and Diary. | ½ | After Diary. |
| **Re-file into another domain** | Already costed in the roadmap. It is also the answer to an import that landed in the wrong library. | ⅓–½ | Unblocked since series closed. |
| **Saved views** | Accepted in principle by DEC-139 and never scheduled. | ½ | Fits the command bar: *Go to "Unread Spanish novels"*. |
| **StoryGraph, Hardcover → book** | CSV importers keyed on ISBN, the same shape as `goodreads.py`. | ⅓ each | |
| **AniList export → anime** | AniList is already a provider; ids are MAL-keyed. | ⅓ | |
| **Simkl / TV Time → movie+series** | Both carry IMDb ids; the same shape as `trakt.py`. | ⅓ each | |
| **Kindle / Audible library → book** | ASINs, not ISBNs, so it rides the custom-list search-and-confirm path with a column preset. | ⅓ | |
| **Last.fm top albums → album** | MBIDs, but album identity is `spotify`, so search and confirm. | ½ | |
| **More ebook formats** | azw3/mobi metadata (title, author, ASIN, cover) via a pure-Python reader; PDF as attachment-only. | ½ | Scoped out by Sprint 086. |
| **Games domain** | Already an unnumbered epic needing IGDB OAuth. | 4–5 sprints | Listed for completeness. Not recommended inside this plan. |

---

## 8. The plan, sprint-sized

Each line fits one sprint, per the owner's standing rule; anything bigger has been split.
Releases are suggestions.

**2.4 — Foundations.** These come first because §4 and §5 sit on them.

| Sprint | Delivers | Findings |
|---|---|---|
| 087 | Job runner correctness (heartbeat, deferred rate limits, per-provider limiter), off-loop request path, request ids, unified error envelope | R1–R3, R5 (server), R7 |
| 088 | Generated API client + `ApiError`, query-key factory, `usePatchEntry`; `create_app` split | R5, R8 |
| 089 | FTS5 library search + SSE event stream + shell activity indicator | R4, I6 |

**2.5 — Look and feel.**

| Sprint | Delivers | Findings |
|---|---|---|
| 090 | Token layer for two themes, *Paper* designed and contrast-measured, theme setting, display serif, type scale | D1, D2 |
| 091 | Primitives (Card, Skeleton, EmptyState, Sheet, Tooltip, DropdownMenu, Kbd, FilePicker); every native control replaced; skeletons on every loading state | D5–D9 |
| 092 | Motion system: `domMax`, cover → detail shared element, route and list transitions, press and drag-over feedback, arch motif in loader, empty states and score commit; detail page as property rows | D3, D4 |
| 093 | Phone pass: compact library header, two-column grid at 390px, bottom sheets, mark in the mobile shell | A6 |

**2.6 — One door.**

| Sprint | Delivers | Findings |
|---|---|---|
| 094 | Command bar (library, web, resolve, navigate) replaces adding-from-search; Add page trimmed; HomePage split | A1, A2, A5 |
| 095 | Global paste and global drop with file detection (`sniff` + `/api/import/detect`); scheme-less links; generic OpenGraph resolver; Spotify via oEmbed | A3, A4, I5 |
| 096 | Import redrawn as three steps; ImportPage split; ambiguity with covers; Inbox renamed and badged; Export to Settings | I1–I4 |
| 097 | Arrivals strip; trust-stated-status (if accepted); PWA service worker and share target | I6, I7 |

**2.7 — More to hold.** Order is the owner's choice.

| Sprint | Delivers |
|---|---|
| 098 | Now strip + Diary |
| 099 | StoryGraph, Hardcover, AniList, Simkl importers |
| 100 | Re-file into another domain + saved views |
| 101 | Metrics, provider health from real calls, response cache |

That is fifteen sprints. The walkthrough defects in §2.5 are folded into whichever sprint touches
their screen; none waits for its own.

**If only three sprints are funded,** take 090, 092 and 094: the themes, the motion and the
command bar. Those three change how the application *feels* the most per sprint. 087 should
still come before anything that adds load to the job runner.

---

## 9. Decisions only the owner can make

1. **Amend "dark only".** `brand-handoff.md` says no light mode is planned. §3 proposes *Ink* and
   *Paper* as equal citizens.
2. **The display serif.** Newsreader or Fraunces, chosen from two renders of the detail page. The
   alternative is no serif, which keeps option A.
3. **Trust stated status on import** (§5.3, option B). This partially reverses DEC-079.
4. **Goodreads and Spotify links.** Goodreads page scraping or title search, and Spotify oEmbed or
   an API key (§4.3).
5. **Scope.** All fifteen sprints, the three-sprint cut, or something between. Nothing here costs
   money or needs an account; the share target needs the app served over HTTPS, which the
   exposure rule already requires for anything off the LAN.

## 10. Deliberately not proposed

- **A framework migration** (React 19, Tailwind 4, TanStack Router). They are worth doing on
  their own schedule, but they do not change what the owner sees.
- **Per-domain colour.** See §3.1 C.
- **Gamification:** streaks, badges, goals with progress rings. They are playful, and the brand
  says no.
- **A second album provider.** It is still blocked on DEC-052's identity finding, which is a
  product conversation, not an adapter.
