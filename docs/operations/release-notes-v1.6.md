# Akasha v1.6 — release notes

**The insights release.** Sprint 064 imports your real Spotify library as albums;
Sprint 065 builds on the dataset that import produces to ask the library a question it
already has the answer to — which authors you rate highest, which bands you own most
of, which decade you keep going back to — ranked from the fields items already
declare, with no new entity and no cross-domain identity. Sprints 066 and 067 then
redrew the screen itself, at the owner's request after using what 065 shipped: the
score ramp, a card per key answered on arrival, a superlative strip, covers on every
row, and the ability to rank inside the library's own current filters.

**Tagged `v1.6.0`.**

## A note on versioning

`1.6.0` is a feature release on top of v1.5. **Nothing migrates.** All four sprints
are application-level: a new import connector, a new declared field on `FieldSpec`
(`groupable`) and one on `Domain` (`insight_suppressed_keys`), a new endpoint that
later gained four query parameters and two new response fields (per-row covers,
library totals), and a screen redrawn twice. The pre-upgrade backup still runs on
startup and finds nothing to do.

The version surfaces — `backend/pyproject.toml`, `frontend/package.json`, the FastAPI
version and the generated OpenAPI contract — say `1.6.0` together.

## What's new since v1.5.7

- **Import your Spotify library.** Drop the account-data export (`YourLibrary.json`)
  onto the Import screen and your saved albums arrive as real MusicBrainz records —
  metadata, covers, tracklists — resolved through the exported Spotify id itself
  wherever MusicBrainz stores that relationship (measured at roughly 95% resolving to
  an exact release), with the rest going to Triage rather than being guessed at. The
  other Spotify export (Technical Log Information) is refused by name: it is
  recommendation-carousel impressions, not albums you chose. Albums the importer
  creates are enriched in the background the same way a search-added album is.
- **Insights: a ranking from what your library already declares, redrawn twice.** A
  `/insights` screen, one domain at a time, answers on arrival — one card per
  groupable key (an author, a genre, a label, `year`, `decade`), ordered by how much
  each key actually has to say about your library rather than by declaration order.
  Every row is its own bar (how many you hold) beside a DEC-026 score chip (how you
  rate them), both on every row regardless of sort order. A superlative strip above
  the cards names the leading key's most collected, highest rated and steadiest
  value, beside how many of your library is rated at all. A row carries up to three
  covers from its own members and expands in place — no navigation — to the entries
  behind it, cover and all, with a link to open the rest in the library. `Julio
  Cortázar` and `julio cortazar` rank as one row, displayed under whichever spelling
  occurs most. Insights can also rank inside the library's own current status,
  shelf, format and search filters — off by default, stated in words when it is on.
  A ranking never merges across domains — an author identity that survived across
  domains is exactly the entity two earlier decisions (DEC-052, DEC-077) declined to
  build, and this feature exists to keep it that way.
- **A precise library filter.** `/api/entries` (and the library screen behind it)
  gained a `key`/`value` filter that matches a metadata value exactly, distinct from
  the existing free-text search — searching `Gorillaz` no longer risks a false hit
  inside a description, and an Insights ranking row can now link to a filtered view
  that is provably the same set the ranking counted.
- **An album's own suppression list.** `Various Artists` is not suppressed because of
  what it is — it's suppressed because ranking by it would put a non-artist third in a
  real library, measured against the owner's own Spotify data. It's a declared,
  reversible list per domain, not a hidden constant: a ranking that leaves something
  out says so, and a control brings it back.

## Upgrading

Nothing migrates and nothing new is required to configure. Pull, rebuild the
container, and the existing database opens as-is. A new "Insights" tab appears in the
main navigation; the Spotify import appears as a new source on the Import screen.

## What this release deliberately does not do

- **No cross-domain ranking, and no Author/Artist/Director entity page.** A
  ranking's scope is one domain; the same name in two domains produces two separate
  rankings. A row still expands to entries and links to the filtered library — the
  moment a key gets a page of its own it is a subdomain.
- **No second album provider, and albums still have no cross-provider identity**
  (DEC-052) — the Spotify import resolves through MusicBrainz alone.
- **No ranking by anything but count and mean score.** No time series, no "year in
  review", no comparison against anyone else's data.
- **No grouping by entry fields** — status, shelf, format, date finished — beyond the
  library's own current filters, which Insights can now rank inside of rather than
  ignore.
- **No new auth.** v1 remains LAN-only, by design.
