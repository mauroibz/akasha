# Spotify import, and the insights feature

**Status:** proposal — measured 2026-09-02 against the owner's own two Spotify exports and the
live MusicBrainz API. This is the evidence behind two decisions that have not been made yet:
whether `spotify → albums` is worth building, and what "insights" would cost. No sprint is
planned from it and no code was written.

The Spotify epic has been on `docs/sprints/ROADMAP.md` since Sprint 031 as *an architecture
goal, not a commitment* (DEC-076), gated on one question DEC-077 has since answered: a track is
metadata on the album, not a child entity, so an importer rolls tracks up to albums and never
touches the entry model. This document takes the next step and measures whether the export can
actually carry that.

---

# Part 1 — `spotify → albums`

## Verdict

**Viable, and cheaper than expected, because the export carries an exact identity.** The decisive
finding is that Spotify album ids resolve to MusicBrainz releases through MusicBrainz's own URL
relationships, so the importer is not the fuzzy title-matching exercise DEC-052 would otherwise
force it to be. Measured end to end on the owner's real library: **~95% of saved albums reach an
exact MusicBrainz identity**, 73% of them without any text matching at all.

Two caveats shape the scope rather than block it: the export is a **file drop, not an OAuth
connector**, and the only defensible thing to import is the **saved-albums list**, not everything
in the bundle.

## What is actually in a Spotify export

The owner supplied two bundles. They are different products and only the second is usable — worth
recording, because a first-time reader will request the wrong one:

| Bundle | Contents | Usable |
|---|---|---|
| **Technical Log Information** (`my_spotify_data.zip`, 2.2 MB) | 28 telemetry files: auth events, device capabilities, ad requests, session validation, home-page impressions | **No** |
| **Account Data** (`my_spotify_data_2.zip`, 728 KB) | `YourLibrary.json`, `Playlist1.json`, `StreamingHistory_music_0.json`, `Wrapped2025.json`, `Marquee.json`, `Follow.json`, `Identity.json`, `Payments.json` | **Yes** |

The technical-log bundle is not merely thin — it is actively misleading. It contains 291
`spotify:album:` URIs, which look like a library until you read the section names they sit under:
`spotlight-nsa-release-radar`, `discover-weekly`, `artist-mixes`, `made-for-x-dailymix`. Those are
**recommendation carousels Spotify rendered at the user**, and across 1,036 rows they amount to
only 28 distinct albums. Importing them would fill a library with things the owner was advertised,
not things they chose. The connector must refuse this bundle by name rather than scavenge it.

### What the account bundle holds

`YourLibrary.json` is the only file that matters, and its shape is ideal:

```json
"albums":  [{"artist": "Gorillaz", "album": "Plastic Beach", "uri": "spotify:album:2dIGnmEIy1WZIcZCFSj6i8"}]
"tracks":  [{"artist": "Justin Bieber", "album": "Purpose", "track": "No Sense", "uri": "spotify:track:..."}]
"artists": [{"name": "1915", "uri": "spotify:artist:..."}]
```

| Source in the bundle | Count (owner's library) | Carries an album URI | Verdict |
|---|---:|---|---|
| `YourLibrary.albums` | **157** | **yes** | **The import.** A deliberate "save this album" act. |
| `YourLibrary.tracks` | 1,362 tracks → 128 distinct albums | no, track URIs only | **Threshold-gated at most** — see below |
| `Playlist1.playlists` | 15 lists, 783 items → 406 distinct albums | no | **Out of scope** |
| `StreamingHistory_music_0` | **1 row** | no | Empty in this export |
| `YourLibrary.shows` / `episodes` | 5 / 1 | — | No podcast domain |
| `Wrapped2025` | topArtists/topAlbums/topGenres | no | Not an import; see Part 2 |

**Track roll-up earns much less than it appears to.** Rolling the 1,362 saved tracks up to albums
yields 128 distinct albums, but **87 of those are already saved albums**. The genuinely new ones
number **41 — and only 9 of those have two or more saved tracks, only 4 have three or more.** So
the roll-up mostly discovers albums where the owner saved exactly one song, which is a statement
about a song and not about an album. If the roll-up ships at all it should be opt-in with a
minimum-track threshold; at a threshold of 3 it adds four albums to a 157-album import.

**Playlists are firmly out of scope.** They would add 345 further albums — more than doubling the
import — on the strength of one track appearing in a playlist. A playlist is a context, not a
judgement about an album.

**`StreamingHistory` is empty here (one row).** Spotify's fuller listening history is the separate
*Extended streaming history* request, which is delivered on a different, slower schedule. Any
design that depends on play counts must not assume it is present.

## The identity question, and the measurement that answers it

DEC-052 established that albums have **no cross-provider identity** — barcode `888837168625`
appeared on three distinct releases — which is why `ALBUM_IDENTITY` is `no_shared_identity`. Taken
at face value that makes a Spotify importer a text-matching problem, which is the failure mode
every importer here has been designed to avoid.

**It is not, because MusicBrainz stores Spotify links as URL relationships.** A Spotify album id
can be resolved to an exact MusicBrainz release:

```
GET /ws/2/url?resource=https://open.spotify.com/album/<id>&inc=release-rels
```

Measured against **60 randomly sampled albums from the owner's own 157**, paced and with backoff
on MusicBrainz's `503` throttling (0 errors in the final run):

| Outcome | Count | Share |
|---|---:|---:|
| Resolved to a MusicBrainz release by URL relation | **44** | **73%** |
| No Spotify relation stored in MusicBrainz | 16 | 27% |

The 27% is not an obscurity problem — the unresolved list includes *In Rainbows*, *Purpose* and
*Strangeland*. MusicBrainz simply does not hold the Spotify link for every release.

**Text search recovers most of the rest.** Querying `releasegroup:"<album>" AND artist:"<artist>"`
against the release-group index, over those 16:

| Outcome | Count |
|---|---:|
| Exact title **and** artist match, score 100 | **10** |
| Right artist, near title (`AVĪCI` → `AVĪCI (01)`) | 1 |
| No usable result | 1 |

**Combined: ~90–95% of saved albums reach an exact MusicBrainz release**, with roughly 5–10%
needing a human decision. The existing Triage flow (Sprints 036–037, 042–043) is already where
those rows would land, so this needs no new UI concept.

### An important caution about the first measurement

An earlier pass over the *technical-log* album ids reported 35% resolution. **That number was
wrong** and is recorded here so it is not repeated: 18 of its 28 probes were MusicBrainz `503`
throttling responses counted as misses, at 1.2 s pacing with no retry. This is the same throttling
DEC-125 addressed inside the application. Any future measurement against MusicBrainz must pace at
≥1.5 s **and** back off on `503`, or it will measure our own request rate rather than their
coverage.

## How it fits the existing importer contract

The connector is a **file drop**, which is the shape every importer here already has, and this is
the point where DEC-076's stated worry — that Spotify is an OAuth source and `upload | path |
directory` are "all still things you hand over, and an authorization handshake is none of them" —
turns out not to bite. A zip upload needs no new `ImportInputSpec.kind`; Sprint 061 already added
`"export"` for exactly this shape (a small set of opaque files a source's own export produced),
and the Trakt and Letterboxd connectors already read zips.

What it does need:

1. A reader that accepts the **account** bundle and refuses the technical-log one with a typed,
   explanatory error naming the right export to request.
2. Identity resolution against MusicBrainz in two passes — URL relation, then text — recording
   which pass matched, because a text match is weaker evidence and Triage should be able to say so.
3. Roll-up as an **opt-in** with a track threshold, defaulting to off.
4. Nothing else. No playlists, no streaming history, no podcasts, no follow graph.

## Alternatives considered

| Strategy | Identity quality | Effort | Verdict |
|---|---|---|---|
| **Export file + MusicBrainz URL relation, text fallback** | ~95% exact | ~1 sprint | **Recommended** |
| Export file, text matching only | ~85%, weaker evidence per row | slightly less | Discards a free exact key |
| Export file, exact matches only, Triage the rest | 73% auto | slightly less | Sends ~27% to Triage for no reason |
| Spotify Web API via OAuth | 100% (reads the live library) | 2+ sprints: OAuth, token refresh, secret storage, a new input kind | Real, and a much larger build. The export answers the same question today |
| Import tracks as first-class entities | — | large | Already rejected by DEC-077 |

The OAuth connector remains the better long-term product — it stays current, needs no manual
export, and would also serve play counts. It is a different and much larger sprint, and nothing in
the file-drop design blocks it later: both produce the same normalized album rows.

## Cost

**About one sprint**, comparable to Sprint 054 (Trakt) — a zip reader, a two-pass identity
resolver, connector declaration and guidance, recorded MusicBrainz fixtures, and the Triage path
for unmatched rows. The two risks worth naming up front are MusicBrainz's throttling on a
157-request resolve pass (it is one paced sweep, and DEC-125's retry budget now covers it) and the
fact that **157 albums is one library** — the resolution rate should be re-measured on a second
person's export before the number is treated as general.

---

# Part 2 — Insights

## The idea, and why it is the right shape

Aggregate entry scores by a keyed field — creators, genres, publisher, network, label — and rank
the keys. "Top authors" falls out of the books you rated; "top artists" out of the albums. The
owner's framing is that this **avoids creating a subdomain for every such entity**, and that
instinct is correct: an Author or an Artist would otherwise become a domain with its own identity,
providers, enrichment and screens, which is the cost DEC-052 and DEC-077 have twice declined to
pay for exactly this kind of entity.

It is also a natural fit for machinery that already exists, which is what makes it small.

## What already exists, and what does not

| Piece | State |
|---|---|
| Field declarations to group by | **Exists.** Every domain already declares its fields with `multiplicity`, so the groupable surface is published — no new declaration layer |
| Aggregation pattern in the repository | **Partially.** `/api/entries` returns `facets`, but they are a hand-written status × type count, not a general grouping engine |
| Key normalization | **Exists, partially.** `creator_sort`, `creator_sort_normalized` and the per-item `creator_sort_override` already solve "Cortázar, Julio" vs "Julio Cortázar" for the primary creator |
| First-creator access | **Exists.** `items.creator_primary` is a computed column, `json_extract(metadata, '$.creators[0]')` |
| Access to *all* creators | **Missing.** A `many` field is a JSON array; grouping over it needs `json_each`, which no query here does yet |
| A screen | **Missing** |

So the honest read is that perhaps a quarter of the backend work is already standing, and the
`creator_primary` column makes the single-creator case (books, albums) nearly free while the
multi-creator case (movie directors, series creators, cast) needs new query work.

## What the measurements say

Taken from the owner's Spotify library, as the closest available stand-in for a populated Akasha
library:

- **157 albums produced 88 distinct artists.** The distribution is steep: 57 artists have exactly
  one album, and **only 14 have three or more**. A ranking is about those 14.
- **Normalization merged zero variants.** Spotify's artist strings are already canonical, so the
  feared "Gorillaz vs GORILLAZ" problem does not exist in this source. It will exist for book
  authors from Calibre and Goodreads, which is precisely what `creator_sort_override` is for.
- **No collaboration markers** in 78 track-artist strings, so no "feat." parsing is needed here.
- **`Various Artists` holds 7 albums** and would rank third. It is not an artist. Any ranking needs
  a suppression rule, and that rule is the sort of thing that has to be a visible, editable list
  rather than a hidden constant.

Two things could not be measured and should not be guessed:

- **Score density.** The owner's live library holds 13 entries, 6 of them scored — a test instance,
  not evidence. Insights is only as good as how many entries carry a score, and that is unknown
  until a real library exists. **This is the single biggest open risk to the feature's value**, and
  it is a question about the owner's habits, not about the code.
- **Whether a ranking over ~14 keys is interesting enough to build a screen for.** At 157 albums it
  is a short list.

## The design questions that are actually hard

None of these are engineering problems; all of them change what the user sees.

1. **What is the ranking statistic?** A mean alone puts an artist with one 10 above one with eleven
   9s. The options are a minimum-count threshold (simple, explicable, discards data) or Bayesian
   shrinkage toward the library mean (fairer, harder to explain in a UI). A count column beside the
   score covers much of the gap and is the cheapest honest answer.
2. **Which fields are keyable?** `multiplicity == "many"` is the obvious rule and it is wrong:
   `tracklist` is a `many` field of row objects, and `original_title` and `catalog_number` are
   scalar text that is near-unique per item. Grouping by them is meaningless. The fix that matches
   this codebase's style is an explicit `groupable=True` on `FieldSpec`, sitting beside
   `completeness_fields` and `fuller_answer_fields` — one reviewed decision per field rather than a
   heuristic over the data.
3. **Per-domain or cross-domain?** "Top creators across books, films and albums" is a different and
   much harder feature: it needs a creator identity that survives across domains, which is the
   subdomain this feature exists to avoid. Per-domain is the coherent scope.
4. **Does a ranking row link back to the library?** It should — "show me the 11 Gorillaz albums" is
   the obvious next click — and that is a filter the library view does not currently support
   (filter by creator).

## Size

| Scope | What it is | Estimate |
|---|---|---|
| **A. Minimum honest version** | One endpoint: group by `creators` for one domain using the existing `creator_primary` column, mean + count, min-count threshold, one simple screen | **~half a sprint** |
| **B. The declared version** *(recommended)* | `groupable=True` on `FieldSpec`; `json_each` over `many` fields so all creators/genres/cast count; per-domain field picker; count + mean with a threshold; the "Various Artists" suppression list; ranking rows link into a filtered library view | **~1 sprint**, plus a small one for the library's creator filter if that does not already exist |
| **C. The full idea** | B, plus cross-domain creator identity, score histograms over time, "your year in review" | **2–3 sprints**, and it needs the creator identity this feature was meant to avoid |

**Recommendation: B, and not before there is a real library to run it against.** The feature's
value is entirely a function of score density, and that is currently unmeasurable. The cheapest way
to de-risk it is to import the Spotify library first — 157 albums with artists attached is exactly
the dataset that makes "top artists" testable, and it makes the Part 1 sprint a prerequisite worth
doing on its own merits.

One ordering note: if both are built, **do the importer first**. It produces the data the insights
feature needs to be judged by, and it stands on its own if insights is never built.
