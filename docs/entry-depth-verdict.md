# Entry depth: the verdict

- **Date:** 2026-08-20
- **Sprint:** 030 (Phase A of DEC-071's two-phase entry)
- **Status:** verdict delivered; awaiting the Phase B go/no-go question to the owner
- **Question:** does a child of an entry need state of its own?

---

## 1. What the providers actually return

### MusicBrainz — recordings (control; **measured**)

Already measured in Sprint 026 (DEC-052), re-measured live on 2026-08-20 to confirm
the finding still holds. The request is the one the adapter makes:

```
GET https://musicbrainz.org/ws/2/release/bee5e0cd-1767-4a8e-9578-6455e87ba60b
    ?inc=artist-credits+labels+media+release-groups+recordings&fmt=json
```

One `inc=recordings` parameter turns `media` into a tracklist inside the same
response — **no extra request**, 6.5 KB for *Kind of Blue*. The 2026-08-20 capture
(`musicbrainz_release_kind_of_blue_recordings_only_20260820.json`) is identical to
the 2026-08-15 one in `(number, title, length, recording.id)` across all five
tracks, and the release-group re-capture
(`musicbrainz_release_group_kind_of_blue_releases_20260820.json`) still returns
**25 releases in one group**. A track carries both a sequential `position` and the
printed `number` (`A1` on a record), and its identity is a **recording MBID** — an
identifier the track owns, not a row number on this release. MusicBrainz answered
one `503` during the run (its throttling shape, not `429`); the retry after five
seconds succeeded, matching the Sprint 026 observation.

A second live capture on 2026-08-20 with `inc=recordings` *only* (2.2 KB) dropped
`artist-credit`, `label-info` and `release-group` — the parameter is additive, so
the adapter's full `inc` string is what costs 6.5 KB, and recordings alone are
cheaper than that.

**What this is evidence for:** the cheapest depth is the one a provider hands you
as metadata on the parent. MusicBrainz gives a track's identity for free, and the
app already stores it as a `rows` field — nothing in the entry model moved.

### TMDB — seasons and episodes (**reasoned**, not measured)

**No API key was available in this environment** (`.env` carries Google Books and
the contact address only), and the owner was asked and did not supply one before
the sprint's measurement window. The unauthenticated probe returns
`{"status_code":7,"status_message":"Invalid API key"}` (HTTP 401), which confirms
the endpoint and the auth contract and nothing else. **This arm was originally
written from model memory; on the owner's challenge it was re-grounded against the
published API reference itself on 2026-08-20** (`developer.themoviedb.org/reference/
tv-series-details` and `/tv-season-details`, response schemas quoted below). It
remains a paper walk — the schemas are documented, not observed — but every claim
now names the document it stands on.

Documented shape: `GET /tv/{series_id}` returns the series with a `seasons` array
embedded — each row carries `air_date`, `episode_count`, `id`, `name`, `overview`,
`poster_path`, `season_number`, `vote_average` — and **no episode objects**. The
reference's own example is series 1399 (Game of Thrones), which is the example this
sprint would have picked anyway. Episodes cost **one extra request per season**:
`GET /tv/{series_id}/season/{season_number}` returns an `episodes` array whose rows
carry `air_date`, `episode_number`, `episode_type`, `id`, `name`, `overview`,
`production_code`, `runtime`, `season_number`, `show_id`, `still_path` and vote
fields. So unlike MusicBrainz, episode-level data is *not* free with the parent: a
7-season series is 8 requests, paced.

An episode's identity is a TMDB episode `id` — globally unique (the doc example's
first episode of GoT is `63056`), not positional — and each episode also echoes its
`show_id` and `season_number`, so a child knows its parent without a join. Seasons
are numbered children of the series; episodes are numbered children of the season.
The hierarchy is real and two levels deep, which is the strongest provider case for
shape (c) — and also the one with no domain in the app asking for it.

**What it would take to close this arm:** a TMDB read-access token in `.env`, one
live request against `/tv/1399` and one against `/tv/1399/season/1`, the captures
committed, and this paragraph rewritten as measured. Half an hour of work.

### IGDB — DLC, editions, collections (**reasoned**, not measured)

DEC-068 already walked IGDB on paper; this sprint confirms the auth contract live
and adds nothing beyond it. The unauthenticated probe returns HTTP 401 with the
`Authorization: Bearer …` / `Client-ID` hint — the Twitch client-credentials pair
DEC-068 described (a bearer token that expires and must be refreshed, the first
adapter to hold mutable state and a secret pair). **Everything below is reasoned
from IGDB's published docs, labelled as such.**

Reasoned shape: DLCs and expansions are **separate game records** linked to the
parent by category, not nested objects — a graph of siblings, not children.
Editions are not a first-class concept (the closest is version titles or bundles,
which are again separate records). Collections are a *grouping* entity a game
points at — structurally a series, not a parent. So IGDB's answer to "is a DLC a
child of the game" is: **no, it is a sibling with a typed edge.** Nothing hangs
state off the relationship; a DLC you own is a game you own.

**What it would take to close this arm:** a Twitch client id + secret, one
`games` query with `fields name, category, dlcs, collections;`, the capture
committed, and this paragraph rewritten as measured.

---

## 2. The three shapes, costed

One row per shape, one column per thing it touches. No cell is blank; "nothing"
is a cost too — it means the surface never learns the concept.

| Surface | (a) per-domain `progress` field on the flat entry | (b) `rows` metadata + a progress marker in it | (c) real child entities with their own status |
|---|---|---|---|
| **Entry model & migration** | One nullable column on `entries` (or one metadata key, validated per domain). One additive migration. | None — `rows` already exists (Sprint 026); the marker is a column name inside it. | New `parent_entry_id` on `entries` (self-FK) or a new child table; the only shape that breaks the flat contract. The migration DEC-068 warned two domain teams would collide over, squared. |
| **Keyset cursor & `_filter_key`** | Nothing — progress is not a sort or filter unless you make it one, and then it is one more key in an existing dict. | Nothing — metadata is not in the cursor today and the marker changes that only if you ask to sort by it. | Everything — `list_entries` assumes one row per entry; children must be excluded from counts, folded into the parent, or paginated as their own tier. The null-bucket cursor logic gets a third case. |
| **Triage selection** | Nothing — an entry is still one row. | Nothing. | Children either flood triage (a 25-episode season is 25 unsorted rows) or need a grouping rule the selection code does not have. |
| **Bulk operations** | A status write is a status write. | Nothing. | "Mark the season watched" must fan out to children or not — either way it is a new decision in `bulk_update`, which today validates each entry against its own domain and refuses mixed writes. |
| **Facet counts** | Nothing. | Nothing. | `status_counts` and `status_counts_by_type` count entries; children either inflate them or need a `WHERE parent_id IS NULL` everywhere. |
| **Export** | One more field in the entity JSON. | Already exported — the tracklist rides the item's metadata. | A tree to serialize and re-import; the Sprint 024 exporter is flat. |
| **Import ledger & undo** | Nothing — `fill_empty`/`create` effects already cover entry fields. | Nothing — the album tracklist is already filled and undone as item metadata (`metadata.tracklist`). | Every child create is an effect row; undo of a 25-child import is 25 deletes with the attachment/modification guards each. Doable — the ledger is the strongest existing surface — but it is the only shape that grows it. |
| **The library row** | A progress string under the title ("Season 3 · 4/7"), same slot as the year line. | Nothing — a tracklist does not render on the card today. | Children have no business on the card; the row shows the parent. Fine — but only because the row stays flat. |
| **The detail page** | One labelled line in the entry panel. | The `rows` renderer already draws a tracklist; a marker column is a badge per row. Read-only today (DetailPage.tsx:545 says a wrong tracklist is fixed at the source, not edited). | A child list with per-child status controls — a new component, a new route or an accordion, and the first time the detail page stops being one entry. |

### What the table says

Shape (b) is nearly free because Sprint 026 already paid for it: the `rows` type,
its validation, its renderer and its undo path all exist and are exercised by the
album tracklist. Its honest cost is the two cells that are not "nothing": the
marker is read-only (a wrong marker is fixed at the source, which is fine for a
tracklist and wrong for "I'm on season 3"), and it can only express progress
*against provider-supplied rows* — it cannot say "I've read the first four
Malazan books," because no provider hands you a reading-order row list for a
series.

Shape (a) is one column and one line of UI. It answers exactly one user sentence
per domain that declares it, declaratively, and it never touches a shared surface.
Its cost is that it is per-domain vocabulary with no cross-domain meaning — which
under the Domain contract (technical spec 6.6) is a feature, not a defect.

Shape (c) is the only one that costs something in **every** shared surface, and
the two provider measurements that could justify it point the other way:
MusicBrainz hands depth over as metadata (already shipped), and IGDB says its
children are siblings (no parent entity needed). The only provider with a real
two-level hierarchy is TMDB — the unmeasured one, for a domain the app does not
have.

---

## 3. Is "a set" the same concept as depth?

**No — and answering them together means refusing to merge them.**

The owner's Harry Potter set and the spec's Malazan series (§11 item 4) are the
same request twice: *group items across a domain in a declared order.* A set is
not a parent entity. The evidence is in the existing model, not in argument:

- **Shelves already group entries** — an unordered, user-named set with a slug,
  a join table, and no schema cost. A set is a shelf with an order column and
  (probably) a domain-scoped, curator-named rather than user-named membership.
- **MusicBrainz's release group** is the provider's own set concept, and it
  arrived as *metadata on the item* (`release-group` id), not as a parent row.
- **IGDB's collections** are the same answer from a second provider: a grouping
  entity games point at.

The vocabulary collision DEC-058 flagged ("series" the book metadata field vs.
"series" the grouping concept) is real but it is a naming problem, not a model
problem. What a set costs, if the owner wants it: one `sets` table (id, name,
domain, ordered membership join), one UI grouping, and a decision about whether
set membership is imported (MusicBrainz release groups) or curated (Harry
Potter). That is an additive feature on the flat model — closer to shelves than
to anything in shape (c) — and it is **deferred, not denied**: §11 item 4 keeps
its "add later if you miss it" standing, now pointing here.

Left open honestly: whether set membership should carry per-member state ("I've
read 4 of 10") — that is shape (a) scoped to a set, and it is the one sentence
below that has no cheap answer yet.

---

## 4. The cheapest thing that satisfies a real user sentence

The sentences, and what each costs:

- **"I'm on season 3."** — shape (a): one `progress` value on the entry,
  declared by a future `series` domain. Cheap, declarative, unbuilt (no domain
  asks for it).
- **"I've watched through S3E4."** — shape (b) with a marker, *if* TMDB seasons
  are stored as `rows`. Costs the read-only edit path and the per-season fetch
  pacing. Unbuilt, and gated on the TMDB measurement this sprint could not run.
- **"I've read the first four Malazan books."** — **no cheap shape answers
  this.** It is a set with per-member state: shelves have no order, `rows` has
  no provider row list for a book series, and shape (c) is a redesign bought for
  one sentence. This is the sentence that would reopen the verdict — see below.
- **"I own the Harry Potter set."** — a shelf named "Harry Potter" today, an
  ordered set tomorrow. Already satisfiable, badly, for free.

The verdict refuses to buy a sentence nobody has said. The owner has said the
Harry Potter one (DEC-071) and the spec said the Malazan one; neither has said
"track my progress *inside* a season" as a need rather than an example.

---

## Verdict

**The flat entry holds. Build nothing now.** A child of an entry does not need
state of its own, because the two measured providers that could have forced the
question refused to: MusicBrainz delivers depth as metadata on the parent
(shipped in Sprint 026 as `rows`), and IGDB models its would-be children as
sibling records with typed edges (no parent entity). The only real hierarchy in
evidence is TMDB's, which is unmeasured and belongs to a domain the app does not
have. Depth, when a domain needs it, is shape (a) — a per-domain `progress`
field, declarative under the Domain contract — or shape (b) where a provider
supplies the rows. Sets are a different concept from depth: they are ordered
shelves, an additive feature on the flat model, deferred alongside §11 item 4.
Shape (c) — real child entities — is rejected on evidence, the same way DEC-052
rejected Strategy B: it is the only shape that taxes every shared surface, and
no measured provider asks for it.

**What would reopen this verdict:**

1. A domain whose provider *measured live* returns children that carry their own
   user-facing state (not just identity) — the TMDB arm, closed with a token and
   two requests, is the standing candidate.
2. The owner saying the Malazan sentence as a need: per-member state inside a
   curated set has no cheap shape, and that is the honest gap in this verdict.
3. A second domain shipping shape (a) and the two `progress` vocabularies
   drifting — at which point the field promotes to a shared, typed concept.

---

## Provenance

| Claim | Status | Evidence |
|---|---|---|
| MusicBrainz tracklist: one parameter, no extra request, stable | **Measured** 2026-08-20 | `musicbrainz_release_kind_of_blue_recordings_only_20260820.json`, `musicbrainz_release_group_kind_of_blue_releases_20260820.json`; `backend/tests/test_sprint030_control.py` |
| MusicBrainz throttles as 503 | **Measured** 2026-08-20 (third observation) | This sprint's capture run; fixtures README |
| TMDB series/season/episode hierarchy | **Reasoned** from the published API reference (fetched 2026-08-20, `developer.themoviedb.org/reference/tv-series-details` + `/tv-season-details`); auth contract probed live (401) | No credential available; owner did not supply one. First draft was model memory; re-grounded against the docs on the owner's challenge. |
| IGDB DLC/edition/collection shape | **Reasoned** from published docs (DEC-068); auth contract probed live (401) | No credential available |
| Shape costs over the nine surfaces | Derived from the code as read 2026-08-20 | `application/library.py`, `application/undo.py`, `domain/spec.py`, `DetailPage.tsx`, `VirtualLibrary.tsx` |
