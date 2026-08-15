# Did the domain expansion reach its goal? — assessment

**Status:** assessment, 2026-08-15. Requested by the owner after Sprint 028 closed, before
committing to a third domain.
**Question:** *"Did we reach our goals? Is the abstraction good enough to work comfortably without
having to rewrite it? Is the frontend modular enough? Does the attachment feature carry risk?"*
**Short verdict:** **Yes for the class of domain we have proved, no for the class we have not.**
Nothing here needs a rewrite. One open question needs deciding **before** a particular kind of
domain is started, and it is the only item on this page that could force a redesign.

---

## 1. What was actually proved

Not asserted — measured, on 2026-08-15:

- A **throwaway third domain built from the guide alone** (own package, three metadata fields, its
  own `playing`/`finished` status vocabulary, own formats, own identity rule) registered and passed
  **the whole conformance suite and all 480 backend tests, with no migration and no screen work.**
- It required edits to exactly **five shared lines**: one import, one registry entry, two enum
  members, and the client's mirrored union. Everything else lived in its own directory.
- The dry run found **three closed-world assumptions** in the codebase that a third domain would
  have tripped over. All three were removed rather than documented.
- **No cross-domain import exists.** `domains/book/` and `domains/album/` do not know about each
  other, and no shared layer branches on item type.

That is a real result and it should not be undersold: the second-domain cost that Sprint 025 paid
(a whole sprint, six seams, a rename across 27 files) is now roughly *an afternoon* for a domain of
the same shape.

## 2. The honest limit of that proof

**The conformance suite proves conformance to the contract. It cannot prove the contract is
sufficient.** A domain that needs something the contract does not model will pass every check and
still be uncomfortable to build. That is the gap the owner is asking about, and the suite is
structurally incapable of finding it.

Two further caveats on the evidence:

- **The dry-run domain was shaped like the two that already exist**, deliberately: DEC-052 predicted
  games would need no new seam, and the walk confirmed the prediction rather than testing the
  boundary. It is a confirmation, not a stress test.
- **We have generalised from two domains that are the same kind of thing** — a catalogue record with
  a title, creators, a year and cover art, held once, with one opinion attached. Books and albums
  differ in vocabulary, not in shape.

## 3. What is missing, ranked by how much it hurts

### 3.1 The one that could force a redesign — a serial domain

**An entry is flat: one entry per item, one status, one score, one `reread_count`.** There is no
hierarchy anywhere in the model.

This is fine for films, games, papers, artworks, wine, LEGO, trading cards. It is **wrong for
television, anime, manga, comics and podcasts** — where "watched through season 3, episode 7" is the
normal thing a user wants to record. Product spec section 10 and DEC-058 both name this; neither
resolves it.

**Why it is the only rewrite risk on this page:** hierarchy reaches the entry model, keyset
pagination and its cursor, triage selection, bulk operations, every facet count, and the shape of
the library row. Every other gap below is *additive*. This one is not.

**Why it matters more than it looks:** of the ten domains
`docs/domain_metadata_roadmap_report.md` names as best candidates or attractive-with-care, roughly
half are serial. If the intent behind "MyAnimeList for everything" includes anime, this is the
architecture's central unanswered question, and building three flat domains first will not answer it.

### 3.2 Comfort gaps — real, and all additive

| Gap | Evidence | What a domain cannot do today |
|---|---|---|
| **Sorting is closed** | `api/library.py` types `sort` as a six-value `Literal`; `application/library.py` holds a fixed `sort_expressions` dict | A games domain cannot sort by playtime, a film domain by runtime, an album domain by release date |
| **Search is title + creator only** | The `q` clause matches `title_normalized` and `creator_primary_normalized`, nothing else | You cannot find an album by its label, a game by its studio, anything by a metadata field |
| **Facets are closed** | Only `status_counts`, `status_counts_by_type`, `format_counts` | No per-domain filter dimension: platform, genre, decade, medium |
| **Field *types* are a closed set** | `text` / `long_text` / `number` / `rows` | A date, a rating, a URL, an image list is a shared-code change |
| **Manual entry is a book form** | `application/add.py` binds it to `DEFAULT_DOMAIN`; the validator says "A book needs a title" | A new domain has no hand-entry path at all |
| **Import is book-only above the readers** | `application/imports.py`, `api/imports.py`, and the whole 376-line `ImportPage.tsx` | Already scheduled as Sprint 030 |
| **Enrichment is ISBN-keyed** | `_backfillable_items` joins `kind = 'isbn'`; `PROVIDER_ORDER` is books' | Deferred with a trigger (DEC-067 row 3); no domain has exercised it |

**One of these is measured rather than estimated.** Adding the `rows` field type for tracklists
(commit `c2a1e82`) touched five files and about 43 lines of shared code. So "a new field type is a
shared change" is true, and it is also *cheap*. Sorting and search are bigger, because the cursor is
bound to the sort key and Sprint 013 exists as a warning about that area.

### 3.3 The frontend — modular where it counts, book-branded where it shows

**The rendering logic is genuinely domain-neutral.** Tabs, status chips, format pickers, the
metadata dialog, triage hotkeys, the detail page's field order and the add screen's confirm step all
render from `GET /api/item-types`. There is no `type === "album"` branch anywhere. That is the half
that matters and it works.

**Two real weaknesses:**

1. **The chrome still says "book" in 18 user-visible places**, across eight files: `Import books` as
   a page title, `Book added` as a toast, *"Your books are retained"*, *"N books"* on shelves,
   *"This book has no provider reference"* in the cover dialog, *"A book needs a title"* in the
   manual form, and the detail route `/books/:id` for every domain. None of it is structural. All of
   it is what a user of a non-book domain would notice within one minute.
2. **There is no per-domain component seam.** A domain extends the UI by declaring data the shared
   renderers already understand. That is a *deliberate strength* — it is why a third domain needs no
   frontend work — but it means a domain wanting a genuinely bespoke widget (a map, a playtime
   chart, a rating breakdown) has no extension point short of adding a shared field type. Whether
   that is a limitation or a discipline depends on how bespoke the roadmap gets.

### 3.4 Attachments — bounded risk, one modelling tension

The owner asked specifically. Reviewed against `infrastructure/attachments.py`, `backup.py` and
`reclaim.py`:

**Sound:** content-addressed storage means the same file attached twice costs one copy; backups
hardlink blobs rather than re-archiving them, so seven nights cost about one copy; the restore is
tested; `akasha-attachments reclaim` collects orphans and is dry-run by default; upload and download
stream, measured at +2.6 MiB peak RSS on a 25 MiB file; files are served as downloads and never
rendered inline.

**Three risks, none blocking, in order:**

1. **An attachment hangs off the *item*, never the entry.** For an epub that is right — it belongs to
   the edition. For a game save, a personal rip, or an annotated scan it is wrong: those are yours,
   not the release's. Adding entry-level attachments later is a schema change plus a UI change, and
   nothing today prevents it — but the choice was made when books were the only domain and it has
   never been re-examined against another.
2. **The size cap is global** (`attachment_max_bytes`, 25 MiB). A domain whose natural attachment is
   a FLAC set or a video cannot have a different bound without raising it for everything, which
   weakens the one thing bounding disk growth on a LAN app with no auth.
3. **No per-domain policy of any kind** — no allowed types, no per-domain quota. Fine at one user
   and two domains; worth a decision before a domain arrives whose files are large.

**Not a risk:** attachments are opaque by design and nothing parses them. That line has held.

## 4. So: is it good enough?

| Question | Honest answer |
|---|---|
| Can a team add a flat catalogue domain without touching another domain? | **Yes, proved.** |
| Without a migration? | **Yes, proved.** |
| Without frontend work? | **Yes for rendering; no for copy** — they would want the chrome de-booked. |
| Comfortably, without wanting to rewrite the abstraction? | **Mostly.** They will hit sorting and search first, and both are additive. |
| For a serial domain (TV, anime, podcasts, comics)? | **No. That question is open and it is the real one.** |
| Is any of this a rewrite? | **Only hierarchy.** Everything else extends the existing shape. |

## 5. Options, costed

| # | Option | Cost | What it buys | What it risks |
|---|---|---|---|---|
| **A** | **Stop here. Start a real third domain (games or films) as an epic.** | 0 planning; the epic itself | The only thing that finds what two similar domains cannot. Sprint 025's method, which worked. | The first team hits the comfort gaps and works around them; you learn the priority order from a real case rather than guessing it |
| **B** | Per-domain list mechanics sprint: declared sort keys, searchable fields, facet dimensions | 1 sprint, touching keyset pagination and its cursor | Removes the two gaps a domain hits first | Designing three abstractions from *zero* new domains — the Strategy-B failure DEC-052 rejected on evidence |
| **C** | **Gated decision sprint on entry hierarchy**, Phase A only: does an entry gain depth, or is a serial domain modelled flat with a "progress" field? | Half a sprint, no build | Unblocks the whole serial class, or rules it out honestly, *before* anyone builds against the wrong answer | None. Phase A concluding "flat, with a progress field" is a complete answer |
| **D** | Frontend chrome neutrality: 18 strings, the `/books/:id` route, the manual form | Small; overlaps Sprint 029, which rebuilds the add and library screens anyway | A non-book domain stops looking like a guest in a book app | Doing it before 029 means doing parts of it twice |
| **E** | Attachments: entry-level option + per-domain cap and policy | 1 small sprint incl. a migration | Removes the modelling tension before a domain needs it | Speculative — no domain needs it yet |
| **F** | Do everything (B + C + D + E) before any new domain | 3–4 sprints | Maximum comfort | Three of the four are designed without a real second case. This is how abstractions get built for imagined users |

## 6. Recommendation

**A + C, in that order, and explicitly not B/E yet.**

1. **Run the hierarchy decision (C) now**, as a Phase-A-only gated sprint. It is cheap, it is the
   only rewrite risk, and every serial domain is blocked behind it. Deciding it late is what makes it
   expensive; deciding it costs half a sprint.
2. **Then build one real third domain (A)** — games via IGDB is the best-understood candidate, and
   DEC-068 already lists what to verify. Let that team's real friction rank the comfort gaps rather
   than ranking them from this desk.
3. **Fold the chrome copy (D) into Sprint 029**, which is already rebuilding those screens. It is a
   handful of strings and it should not be its own sprint.
4. **Hold B and E** until a real domain asks. Both are additive, both are cheap to add later, and
   building either now means designing from two domains that agree with each other — which is
   precisely the mistake this architecture was chosen to avoid (DEC-052, Strategy B rejected on
   evidence).

**What I would not do:** treat the successful dry run as proof the design is finished. It proves the
easy case is easy. The hard case has not been attempted, and the one thing that would tell us whether
the abstraction is right is a domain that does not look like the two we have.
