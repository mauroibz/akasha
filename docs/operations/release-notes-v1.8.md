# Akasha v1.8 — release notes

**Covers first.** The owner used the app after v1.7 shipped and reported it plainly: *"there is a
lot of wasted space everywhere... covers and the main number should be larger... the insights
page reads bland... the shelves tab is too bland."* `docs/readability-proposal.md` measured all
three screens on the owner's own running instance rather than describing them, and the owner
accepted it whole as **DEC-139**, scheduled as three sprints. Two further layout fixes landed
after the owner compared the shipped screens against the proposal's own accepted mockup
(**DEC-142**, **DEC-143**).

**Tagged `v1.8.0`.**

## A note on versioning

`1.8.0` is a feature release on top of v1.7. **Nothing migrates.** All three sprints are
application-level: Sprint 073 added one read-only endpoint (`GET /api/insights/scores`); Sprint
074 added two response fields to `GET /api/shelves` (`members_by_type`, `updated_at`, the second
an existing column exposed rather than a new one). No new table, no new domain field, no schema
change. The pre-upgrade backup still runs on startup and finds nothing to do.

The version surfaces — `backend/pyproject.toml`, `frontend/package.json`, the FastAPI version and
the generated OpenAPI contract — say `1.8.0` together.

## What's new since v1.7.0

- **The library is a wall of covers, not a row of them.** The card turns vertical: the cover
  takes the full card width at a pinned height (crops rather than resizing the row — the
  virtualized grid stays fixed-size), the title gets the whole card's measure instead of a
  105px column, and the score is a 44px chip on the cover's own scrim, at the opposite corner
  from the status pill rather than sharing one cramped, centred control with it. Four rows of
  chrome collapse into one sticky command bar behind a single **Filters** popover; the response's
  own match count is visible for the first time (`18 of 342`, not just `aria-setsize`); wide
  screens reach six columns; the dense list view is now genuinely dense.
- **Insights stops repeating itself.** The leading key becomes a hero panel — its own top result
  promoted large, the three superlatives (most collected, highest rated, steadiest) folded inside
  it instead of a page-level strip that repeated the card below it. Decade and Year, previously
  two cards ranking the same field, are one card with a grain toggle. A chronology strip draws
  decades in actual time order (previously sorted by count, destroying the one ordering that
  meant anything), with a capped bar width so it reads as a compact chart rather than stretching
  to fill whatever width the page gives it. A new score-distribution band (the one backend
  addition) draws the 1-10 spread in the same ramp every other screen already uses. An asymmetric
  grid sizes cards by how much each key has to say; the long tail of once-held values is a card of
  clickable chips instead of a grey footnote.
- **A shelf is a place, not a row with two buttons.** The shelves index is a board: each card
  draws its shelf's covers stood up side by side in a scrolling rail, on a rule, plus a size bar
  and one chip per domain the shelf holds (the sprint's other backend addition). A domain filter,
  a sort (largest / recently added / name), and a name search work the board. Every shelf gets its
  own page (`/shelves/:slug`) showing the set whole **across every domain it holds** — a
  deliberate exception to the library's one-domain-at-a-time rule, the same precedent `/triage`
  and the export already stand on — with the count at the library's own scale, a status
  breakdown, a format mix, and rename/delete moved here off the index. A shelf can be pinned into
  the library's own command bar as a one-press filter chip.

## Upgrading

Nothing migrates and nothing new is required to configure. Pull, rebuild the container, and the
existing database opens as-is. The library, insights and shelves screens all look substantially
different; nothing about how you reach any of them changed.

## What this release deliberately does not do

- **No masonry or natural-aspect covers.** The library's virtualized grid stays fixed-size; a
  poster crops to the pinned frame rather than the row resizing to fit it.
- **No cross-domain insights ranking, no new metric.** Still one domain at a time for a ranking,
  still a row that expands to entries and links to the filtered library.
- **No bulk shelving, manual ordering, shelf goals, merging, or auto-shelving rules.** Costed in
  the proposal and deliberately not built.
- **No saved views ("smart shelves").** Accepted in principle, needs a table and a migration
  neither sprint asked for; unscheduled until asked for.
- **No new colour, accent, typeface, or charting library.** Every new shape (the hero, the
  chronology strip, the score distribution, the cover rail) is drawn with the existing score ramp
  and amber accent.

## Known, unfixed

- **A shelf's "recently added to" sort reads the shelf's own last-created-or-renamed time, not a
  true last-member-addition time.** `entry_shelves` carries no timestamp of its own; a precise
  version needs a new column and a migration nobody has asked for yet.
- **The shelf page's mean score chip is a mean over currently-loaded entries**, not a server
  aggregate — accurate for any shelf that fits on one page, approximate beyond it.
- **The Insights score-distribution band stretches its ten bars to fill whatever width the page
  gives it**, the same way the chronology strip did before this release capped that one. Left
  alone deliberately — out of scope for both owner reports that drove this release — for whenever
  Insights is next touched.
- **Changing a library entry's status inline can leave the Filters popover's status option
  showing a stale count until reload**, even though the filtered response and the visible total
  are correct. A cache-invalidation gap, not a data error.
