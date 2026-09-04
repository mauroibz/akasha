# Akasha v1.7 — release notes

**The insights screen, redrawn.** Sprint 065 (v1.6.0) shipped Insights as a ranked table
behind a query builder. The owner used it, said the data was right and the screen was
not (`docs/insights-redesign-proposal.md`, accepted as **DEC-132**), and Sprints 066 and
067 rebuilt the screen against that same ranking query and response contract — score
ramp, magnitude bars, a card per key answered on arrival, a superlative strip, covers on
every row, and the ability to rank inside the library's own current filters.

**Tagged `v1.7.0`.**

## A note on versioning

`1.7.0` is a feature release on top of v1.6. **Nothing migrates.** Both sprints are
application-level: `GET /api/insights` gained four query parameters
(`status`/`shelf`/`format`/`q`) and two response fields (`covers` per row,
`total_entries`/`rated_entries`), and the `/insights` screen was rebuilt twice. No new
table, no new domain field, no schema change. The pre-upgrade backup still runs on
startup and finds nothing to do.

The version surfaces — `backend/pyproject.toml`, `frontend/package.json`, the FastAPI
version and the generated OpenAPI contract — say `1.7.0` together.

## What's new since v1.6.0

- **Insights answers on arrival, in colour, without a round trip.** Mean score is the
  same DEC-026 score chip every other screen already paints it with, instead of plain
  body text. Every ranking row is filled to its own share of its ranking's leader, so a
  bar carries how many you hold while the chip carries how you rate them — both on
  every row, regardless of sort order, where the shipped screen threw half of every
  response away under one of its two modes. The key popover is gone: one card per
  groupable key renders at once, ordered by how much each key actually has to say about
  your library (a key whose values all repeat once has nothing to say and is stated in
  a line instead of drawn as a card) rather than by declaration order. A row expands in
  place to the entries behind it — no navigation — and the library shows a dismissable
  breadcrumb naming the ranking a filter came from.
- **A ranking row has a face.** Up to three covers from a row's own members, highest
  scored first, the same three on a repeat request. Works for every domain with cover
  art, not only the one domain that offers a manual cover picker.
- **Three answers above the fold.** A superlative strip names the leading key's most
  collected, highest rated, and steadiest value, beside how many of your library is
  rated at all — a superlative with no honest answer (nothing meets the ratings
  threshold, or nothing has two ratings to have a spread) is left out rather than
  guessed at.
- **Insights can rank inside your current library filters.** A "within my current
  filters" toggle, off by default, ranks only the entries matching whatever
  status/shelf/format/search filters the library page currently has set, and states in
  words which filters are applied.

## Upgrading

Nothing migrates and nothing new is required to configure. Pull, rebuild the
container, and the existing database opens as-is. `/insights` looks different; nothing
about how you reach it changed.

## What this release deliberately does not do

- **No cross-domain ranking, no entity pages, no time series, no new metric.** Still
  count and mean score, still one domain at a time, still a row that expands to
  entries and links to the filtered library rather than to a page of its own.
- **No grouping by entry fields** beyond the library's own current filters, which
  Insights can now rank inside of rather than ignore.
- **No caching, resizing, or new pipeline for covers.** Existing cover URLs only.
- **No new auth.** v1 remains LAN-only, by design.

## Known, unfixed

- **At 390px, the domain radiogroup (book/album/anime/movie/series) overflows the
  viewport by about 39px.** Pre-existing markup, unchanged by either sprint in this
  release — it was never exercised past one or two domains by either sprint's own
  tests, real domains being harder to reach from a mock. Recorded as **DEC-134**;
  belongs to whichever sprint next touches `InsightsPage.tsx`'s header.
