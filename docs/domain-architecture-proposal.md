# Domain architecture — proposal

**Status:** **accepted** by the owner, 2026-08-14 — see DEC-052
**Written:** 2026-08-14, against Sprint 023's close (024 not started)
**Supersedes nothing.** `docs/domain_metadata_roadmap_report.md` assessed *which* domains are
viable; this assesses *how* they attach to this codebase. It is the design input Sprint 025 was
going to discover by walking, and it exists because the mapping can be checked against a live API
in an afternoon rather than guessed at.

---

## 1. The question

> Are we casting every domain into the book shape, or abstracting books into a generalist shape,
> adapting it, then incorporating new domains?

**Neither, and the framing hides the actual state of the code.** The storage core is *already*
generalist and has been since Sprint 002 — `items` is `type`, `title`, `subtitle`, `year`,
`cover_path`, `identifiers`, `metadata` JSON, exactly as product spec 3.1 describes it. Nothing
about that row is book-shaped.

What is book-shaped is every layer built *on* it: the sort projection reads
`json_extract(metadata, '$.authors[0]')`, the API contract types `metadata` as
`BookMetadataResponse`, cross-provider merge dedupes by ISBN, and enrichment selects work by joining
`item_identifiers` on `kind = 'isbn'`.

So the work is not generalizing the core (done) and not casting albums into books (see §3, where the
evidence says this actively destroys data). It is **lifting book-specific logic out of the shared
layers into a per-domain plugin, leaving the shared layers speaking only in neutral terms.** The
core does not move. The seams do.

---

## 2. What was actually tested

Probed live on 2026-08-14 against MusicBrainz `ws/2` and the Cover Art Archive, with a descriptive
User-Agent. Raw responses are in the sprint scratch; the load-bearing observations:

| # | Observation | Evidence |
|---|---|---|
| 1 | **Release-group ≈ work, release ≈ edition.** *Kind of Blue* has 25 releases in one group. | `release-group/8e8a594f…?inc=releases` |
| 2 | **MusicBrainz ships a curated sort name per artist**, and only inverts people. | `Miles Davis` type=`Person` → `Davis, Miles`; `Daft Punk` type=`Group` → `Daft Punk`; `Various Artists` type=`Other` → `Various Artists` |
| 3 | **Barcode is not a unique edition key.** Unlike ISBN. | `888837168625` appears on 3 different *Random Access Memories* releases (US/BR/AU), twice more with a leading zero; 8 of 10 sampled releases carry one, a 1959 release carries none |
| 4 | **A credit is a rendered string, not a list.** | `Dean Blunt` + joinphrase `" Meets "` + `James Ferraro` |
| 5 | **CAA JSON returns `http://` URLs and redirects off-allowlist.** | `image` field is `http://coverartarchive.org/…`; final host `dn710907.ca.archive.org` |
| 6 | **Album art is ~16× a book cover at full size**, with usable thumbnails. | full 811 KiB · 1200px 244 KiB · 500px 49 KiB · 250px 16 KiB |
| 7 | **MusicBrainz rate-limits with `503`, not `429`**, and answers `X-RateLimit-*` headers. | one 503 on the second call of a paced run; `x-ratelimit-limit: 1200` |
| 8 | Language lives on the release, not the group. | `text-representation: {script: Latn, language: eng}` |
| 9 | Publisher analogue is label + catalogue number. | `label-info: [("CS 8163", "Columbia")]` |

Two of these are decisive, and both cut against casting albums into the book shape.

**Observation 2 is the one that settles it.** DEC-051's `creator_sort_name` heuristic assumes its
input is a person's name — first token given, remainder surname. That assumption holds for books,
where nearly every author is a person. It is false for a large fraction of album creators:
the heuristic turns `Daft Punk` into `Punk, Daft`, `Pink Floyd` into `Floyd, Pink`, and
`Various Artists` into `Artists, Various`. MusicBrainz already knows the answer and gives it away
for free, because it models artist *type*. Casting an album into `metadata.authors` throws that
knowledge away and then applies a heuristic that is wrong for exactly the cases the provider had
already solved. This is not a cosmetic loss — DEC-051 established that a sort name the owner has to
correct by hand is owner data, so this manufactures hand-correction work that the provider had
already eliminated.

**Observation 3 is the structural one.** ISBN is a globally unique edition key, which is why
`merge_and_rank` can group candidates from two providers by it. Barcode is not: the same barcode
appears on three distinct releases. So the album case is not "books but with a different identifier
field" — it is a domain where **cross-provider identity does not exist**, and merge must be keyed
on the source-scoped MBID or not happen at all. A per-domain "which identifier do we merge on"
setting cannot express that. The seam has to be a strategy, not a field name.

---

## 3. Strategies, costed

| | Strategy | Up-front cost | Time to first album | What it costs later | Verdict |
|---|---|---|---|---|---|
| **A** | **Cast into the book shape.** artist→`authors`, label→`publisher`, tracks→`page_count`. No new abstraction. | ~none | days | `BookMetadataResponse` accretes optional fields per domain into one god-model; the detail page shows "Page count" on an album; **group names get inverted by the sort heuristic (obs. 2)**; barcode merge is silently wrong (obs. 3). Sprints 026–027 compound it. | **Rejected** — obs. 2 and 3 make it lossy, not merely untidy |
| **B** | **Generalize everything first**, refactor books onto a neutral plugin contract, then add albums. | high, all before any user-visible value | weeks | Designs the abstraction from one real domain plus a paper study of a second — the exact confident-but-unfounded answer the roadmap's gated shape exists to prevent. | **Rejected** — designs from n=1 |
| **C** | **Pilot then extract** (Sprint 025 as currently written). Duplicate freely, let the duplication specify the seam, extract in Phase B. | medium, spread | ~1 sprint | Honest, but rediscovers by hand what §2 already established, and the "temporary" fork calcifies if Phase B is never authorized. | **Superseded** — its discovery phase is now partly done |
| **D** | **Neutral core, seam-by-seam extraction.** Core is already neutral; define the plugin contract for the *six seams albums actually touches* (§4), leave everything else book-only until a second domain proves it needs to move. | medium, incremental | ~1 sprint | Each seam is independently testable and independently revertible. Risk is under-abstracting, which is cheap to fix; B's risk is over-abstracting, which is not. | **Recommended** |

D is C with the design step moved in front of the build, now that the build's main unknowns have
been measured. It keeps the gate: each seam is small enough to stop at.

---

## 4. The proposed architecture

One idea: **the shared layers speak in neutral terms; a domain plugin supplies what only it knows.**
A domain never translates itself into book vocabulary, and the shared layer never asks what type it
is holding.

Six seams. Everything else stays as it is.

### Seam 1 — Creators

*Neutral concept:* an item has ordered **creators**; each has a display name and a sort name. The
sort name is **authoritative when the source supplies it**, heuristic only as fallback, and the
owner's override always wins.

This is not a new pattern — it is DEC-051's Calibre seed, generalized. Calibre supplies
`authors.sort`; MusicBrainz supplies `artist.sort-name` and knows Person from Group. Both are
curated truth about exactly the names no heuristic can resolve. The rule becomes: *a source that
knows the sort name seeds the override; the heuristic runs only when nothing knew.*

Also needed, from obs. 4: store the ordered creator list **and** the rendered credit, because
`["Dean Blunt", "James Ferraro"]` joined by `", "` is not `Dean Blunt Meets James Ferraro`.

This seam subsumes the `metadata.authors` → `creators` and `sort_author` rename the roadmap already
assigned to Sprint 025.

### Seam 2 — Identity and merge

*Neutral concept:* a domain supplies `identity_key(candidate) -> str | None`. `None` means **never
merge this candidate with another** — which is the correct, complete answer for albums (obs. 3), not
a degraded one.

This replaces `_isbn()` as `merge_and_rank`'s hardcoded grouping key. Note that this seam lives in
`domain/providers.py`, not in an adapter — it is the one place the roadmap's touched-list did not
anticipate, and it is the strongest argument that Strategy A's "just swap the identifier field"
does not work.

`item_identifiers` (global keys) and `item_sources` (source-scoped identity) already model both
halves correctly. No schema change.

### Seam 3 — Metadata schema

*Neutral concept:* storage stays an opaque JSON object. A domain publishes a **declarative field
spec** — ordered field name, label, type, multiplicity — which drives the metadata dialog, the
detail page's display order, and the export's human-readable half.

`ItemResponse.metadata` stops being `BookMetadataResponse`. The field spec is *data*, served over
the API, so `MetadataDialog.tsx` stops hardcoding twelve book fields and renders whatever the type
declares.

**This confirms Sprint 024 rather than breaking it.** 024's instinct — export `type`, identifiers
and an opaque `metadata` — is exactly right, and the field spec is what makes an opaque dump
readable without making the format book-shaped. See §5.

### Seam 4 — Cover acquisition

*Neutral concept:* a domain supplies candidate cover URLs; the shared pipeline keeps sole ownership
of https-upgrade, host allowlist, redirect policy, pixel/byte bounds and normalization.

Three concrete changes, all measured:

- CAA's JSON gives `http://` URLs and `validate_url` requires https. Upgrade the scheme before
  validating rather than loosening the check.
- `validate_url` runs on **every redirect hop** (`covers.py:117`), and CAA's final host is
  `dn710907.ca.archive.org` — matched by neither `archive.org` exactly nor the `.us.archive.org`
  suffix. The allowlist needs an archive.org subdomain rule, not a new literal host.
- Fetch the **1200px thumbnail (244 KiB)**, not the full image (811 KiB). `MAX_COVER_EDGE` is 600,
  so the full image is downscaled to 600px anyway — 567 KiB spent per album to be thrown away. The
  500px thumbnail (49 KiB) is under the 600px target and would upscale.

### Seam 5 — Status vocabulary

*Neutral concept:* the shared layer knows only that statuses exist, that exactly one is the inbox,
and that a subset is directly choosable. The vocabulary itself is the domain's.

`unsorted` stays universal — imports land there and the default library hides it. `read`/`reading`/
`to_read` do not survive contact with an album. Validation moves from the global `EntryStatus`
StrEnum to a per-type lookup, which reaches the filter chips, `entryStatuses`, and the triage
hotkey map.

Fix the duplication first: `statusLabels` exists in `features/library/labels.ts` **and verbatim
again** in `pages/TriagePage.tsx:42`, with `statusHotkeys` beside it. Per-domain vocabulary against
a duplicated map is how the book vocabulary silently survives on one screen.

Expect this to be the largest single piece, as the roadmap predicted.

### Seam 6 — Enrichment and add-by-URL

*Neutral concept:* a domain declares whether background enrichment applies, and on what key.

Albums plausibly need **none**: one MusicBrainz release fetch returns title, date, country, label,
catalogue number, language, tracks and artist credit in a single call, where books need enrichment
because a Goodreads CSV row starts as little more than an ISBN. "This domain does not enrich" is a
simplification to confirm, not a gap to fill.

`resolve_input` (ISBN / openlibrary.org / books.google.com) becomes a per-domain URL recognizer.

### Predicted to need no change

Keyset pagination and `CursorState`, the job runner, the import ledger and undo, backup,
attachments, shelves, and the whole score/notes/dates entry layer. **These are predictions, and the
pilot's job is to falsify them.** If any of the first three moves, that is the finding that stops
the plan — it is the same tripwire the roadmap set.

---

## 5. What this changes upstream

**Sprint 024 (export) can proceed, and should go first.** Its format bet — entity-shaped, opaque
`metadata` — is confirmed by Seam 3 rather than threatened by it. One addition: the CSV's
human-readable story should be described in terms of the field spec, so that "Goodreads-shaped CSV
for books" reads as *one domain's export view* rather than as the export's only shape. That is a
paragraph in the sprint file, not a redesign.

**Sprint 025 should be rewritten around the seams.** Its Phase A becomes *test this proposal* rather
than *discover blind*: implement albums against the six seams, and report which seam was wrong.
That is a sharper instrument than an unstructured touched-list, and it preserves the gate — a seam
that turns out to reach into pagination or the ledger still stops the plan.

**Sprints 026–027 gain a falsifiable prediction:** games should need only seams 1–4 and 6, and
series should break seam 5 plus the entry model (product spec 10 item 4). If games needs a seventh
seam, the abstraction was wrong.

---

## 6. Open questions for the owner

1. **Accept Strategy D?** It is the recommendation, but B is defensible if you would rather pay the
   refactor once, up front, and not carry a fork.
2. **Does the album domain enrich?** §4 seam 6 argues no. Cheap to confirm during the pilot,
   irreversible-ish to bolt on later.
3. **Album status vocabulary.** "Listened / Listening / To listen" is the obvious mapping, but an
   album is re-listened continuously in a way a book is not re-read, so `reread_count` and
   `date_finished` may be meaningless here. This is a product decision, not an implementation one,
   and it is the seam most likely to need your answer rather than mine.
4. **Order:** 024 → revised 025, as §5 recommends? Or hold 024 until the seams are accepted?

**All four were answered on 2026-08-14 and are recorded in DEC-052:** Strategy D accepted; albums
perform no background enrichment, to be confirmed by the pilot; Sprint 024 runs first; and the
status vocabulary splits as §7 describes.

---

## 7. Sprint shape — how six seams fit without over-specifying one sprint

The owner's objection to the first draft of Sprint 025 was that six seams is too much for one
sprint. It is, and the fix is not to trim the design but to cut it in the one place that survives
being cut.

**The obvious split is a trap.** "Extract the seams first, add albums second" is Strategy B wearing
a different hat: a seam cannot be validated with only one domain present, so extracting first means
designing the abstraction from books alone and discovering in the next sprint that it was wrong.
Albums stay whole in Sprint 025.

**Seam 5 is where the cut belongs**, because it is the only seam with a real internal boundary —
between what a status is *called* and what statuses a domain *has*:

| | Slice | Sprint | Why it splits cleanly |
|---|---|---|---|
| **5a** | Per-domain status **labels** over the existing values — `read` renders as "Listened" | 025 | No schema change, no validation change, no hotkey change. Sits inside the standing invariant that internal names are permanent and only user-facing copy moves. |
| **5b** | Per-domain status **vocabularies** — different sets, validation off the global `EntryStatus`, filter chips, triage hotkeys, and whether `reread_count`/`date_finished` mean anything for an album | 026 | The largest single piece and the one carrying a genuine product decision, which is much better made with two domains in hand than one. |

So Sprint 025 carries seams 1–4, 5a and 6 — an album that is correct in every respect except that
its statuses are books' statuses under album names, which is honest, visible, and a one-sprint debt
rather than a hidden one. Sprint 026 is seam 5b alone.

Prerequisite for 5a, done first inside 025: collapse the `statusLabels` duplicate in
`pages/TriagePage.tsx:42` into `features/library/labels.ts`. A per-domain label map against a
duplicated table is exactly how the book vocabulary silently survives on one screen.

Resulting roadmap: **025** albums · **026** status vocabulary · **027** games · **028** series.
