# Handoff — Sprint 050 is complete; Sprint 051 (multi-domain imports) is ready

Sprint 050 shipped **TVmaze as the second series provider**: a real synopsis, an airing status, and
the Spanish-language shows Wikidata's title search misses. `docs/agent/state.json` names **051** as
active with status `ready`. `make test` is 989 backend + 190 frontend, green; `make check` is green.
Nothing is tagged, released or pushed — the whole series/TVmaze line is local on this branch.

A series search now reaches both Wikidata and TVmaze and returns one merged list through the shared
`merge_and_rank` + `fill_empty` (no domain-specific merge code). The credit line naming both sources
is in the AppShell footer. Two deliberate refusals hold: `episodes` is never sourced from TVmaze
(Wikidata's `P1113` is the declared total), and `static.tvmaze.com` never joins the cover allowlist
(Stremio's 500×750 is already the right variant).

## What the next session is picking up

Sprint 051 builds the seam both importers force: **a connector may target more than one domain.**
Read `docs/sprints/051-multi-domain-imports.md` first. The shape, measured at planning time:

- `Importer.item_type: str` becomes `Importer.item_types: tuple[str, ...]`; every existing connector
  declares a one-element tuple and changes in no other way.
- `ImportService` resolves the domain **per record** at three call sites (`_validate`, `commit`, the
  enrichment guard), not once per batch. The record's `item_type` is written into `normalized_payload`
  at preview time so commit never re-opens the source.
- The screen renders a target checkbox per declared type; **the service, not the reader, applies the
  selection**. The chosen targets fold into the preview fingerprint, or a file imported as films and
  then as series silently returns the first preview.
- Built and proved against a **test** connector, not IMDb — a seam proved only by the connector it
  was built for is not proved (DEC-093's lesson, applied ahead of the failure).

Three findings already shrink it: the Import screen is already source-shaped and ignores `item_type`;
Triage already renders per-row from `entry.item.type`; `_backfillable_items` already loops every
domain. DEC-106 records the owner's choice (the reader chooses the source, not the target) and
DEC-107 records that anime rows from a TV source stay series (the metadata switch was measured and
dropped).

## Known and left, in the order they are likely to bite

- **One live series search is still owed.** Both Sprint 049's and Sprint 050's walkthroughs ran
  against **recorded** provider responses (DEC-108's substitution rule) — Wikidata was maxlag-shedding
  and TVmaze was captured the same day. What is proven is the rendered flow, the merge, the credit and
  the poster pipeline; what is **not** proven is that the adapters' request shape is still what live
  Wikidata and TVmaze answer today. When the network is healthy, run one live series search before
  Sprint 051's own walkthrough leans on the same assumption.
- **The intermittent 422 in the series walkthrough is a harness artifact, not a defect.** It appears
  only when two add-tests run back-to-back against a reused walkthrough data dir: the designed
  `near_match_confirmation_required` guard (`application/add.py:197-202`) fires on a leftover row.
  Restart the runner on a fresh disposable data dir and it disappears. Don't chase it as a bug.
- **Sprint 047 was verified at a reduced level by owner direction (DEC-102).** Nobody has seen the
  Letterboxd connector rendered on the Import page, nobody has approved a movie row through the
  Triage UI, and undo has no coverage in that sprint at any level. Sprint 052's walkthrough gate is
  where that debt is scheduled to be paid.
- Two recorded defects from Sprint 046 (DEC-100) are still open and neither is movie-specific:
  `_backfillable_items` counts a null `cover_path` or `year` as "worth a lookup" in every domain,
  regardless of `completeness_fields`; and `GET /api/search/resolve` maps every exception from
  `resolve_input` to a 502, so a typed `record_not_found` reads as a provider outage.

## Private data and operational constraints

- **`exports/` is the owner's private source archive and is gitignored as a whole directory.** It
  holds the Letterboxd ZIP, the MyAnimeList XML, two IMDb CSVs, a Trakt archive and a Spotify export.
  Every one carries account ids, usernames or ratings; the Trakt archive carries the owner's **email
  address**. These are read-only walkthrough input. **No fixture may be cut from any of them** — every
  committed importer fixture is invented. Sprint 051's test connector and Sprint 052's IMDb reader
  both need invented fixtures, not slices of the real exports.
- Wikidata and TVmaze both need no key, only `USER_AGENT_CONTACT`. Stremio's poster host is already
  in `ALLOWED_COVER_HOSTS`.
- `frontend/e2e/scratchpad/` is gitignored; the series walkthrough specs there are local only.
