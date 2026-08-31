# Handoff — Sprint 051 is complete; Sprint 052 (multi-domain imports) is ready

Sprint 051 emptied TESTING.md's *Optimization backlog*: the gates the remaining roadmap pays are
now faster, quieter, and bounded. `docs/agent/state.json` names **052** as active with status
`ready`. `make test` is 989 backend + 190 frontend, green; `make check` is green. Nothing is
tagged, released or pushed — the whole series line is local on this branch.

What changed for every later sprint: Playwright runs parallel except the two load-sensitive
10,000-entry invariants (serial `heavy-library` project, 49.4 s → 38.2 s); Vitest green output is
quiet (21 attachment-query warnings gone via the shared `frontend/src/test/mockApi.ts`); every test
is bounded (backend 30 s, frontend 15 s, Playwright 60 s) so a deadlock fails with its name; and
`scripts/walkthrough.py` is the tracked launcher — fresh temp data dir, ephemeral port, readiness
wait, clean stop, `--replay <module>` for the fixture seam.

## What the next session is picking up

Sprint 052 builds the seam both importers force: **a connector may target more than one domain.**
Read `docs/sprints/052-multi-domain-imports.md` first. The shape, measured at planning time:

- `Importer.item_type: str` becomes `Importer.item_types: tuple[str, ...]`; every existing connector
  declares a one-element tuple and changes in no other way.
- `ImportService` resolves the domain **per record** at three call sites (`_validate`, `commit`,
  the enrichment guard), not once per batch. The record's `item_type` is written into
  `normalized_payload` at preview time so commit never re-opens the source.
- The screen renders a target checkbox per declared type; **the service, not the reader, applies
  the selection**. The chosen targets fold into the preview fingerprint, or a file imported as
  films and then as series silently returns the first preview.
- Built and proved against a **test** connector, not IMDb (DEC-093's lesson, applied ahead of the
  failure).

Three findings already shrink it: the Import screen is already source-shaped and ignores
`item_type`; Triage already renders per-row from `entry.item.type`; `_backfillable_items` already
loops every domain. DEC-106 records the owner's choice (the reader chooses the source, not the
target) and DEC-107 records that anime rows from a TV source stay series.

## Known and left, in the order they are likely to bite

- **Sprint 051's flow-through proof is owed.** The walkthrough launcher is proven to boot and serve
  in live and replay modes, but no Playwright flow ran through it — the owner stopped further
  server launches during the session. Discharge it the first time a walkthrough gate runs:
  `cd backend && uv run python ../scripts/walkthrough.py --replay <module>`, point the spec's
  `BOOK_TRACKER_E2E_BACKEND` at the printed URL. Sprint 052's own walkthrough is the natural place.
- **One live series search is still owed** (carried from Sprint 050). Both series walkthroughs ran
  against recorded provider responses (DEC-108). What is not proven is that the adapters' request
  shape is still what live Wikidata and TVmaze answer today. Run one live series search when the
  network is healthy, before Sprint 052's walkthrough leans on the same assumption.
- **The intermittent 422 in the series walkthrough is a harness artifact, not a defect** — the
  designed `near_match_confirmation_required` guard (`application/add.py:197-202`) fires on a
  leftover row when two add-tests run back-to-back against a reused data dir. The launcher's fresh
  data dir per run makes this disappear; don't chase it as a bug.
- **The e2e dev server proxies `/api` to a backend that is not running.** The Playwright gate
  prints `ECONNREFUSED` proxy noise throughout while passing — the specs stub their own API.
  Recorded, not fixed; not one of the four backlog items.
- **Sprint 047 was verified at a reduced level by owner direction (DEC-102).** Nobody has seen the
  Letterboxd connector rendered on the Import page, nobody has approved a movie row through the
  Triage UI, and undo has no coverage in that sprint at any level. Sprint 053's walkthrough gate is
  where that debt is scheduled to be paid.
- Two recorded defects from Sprint 046 (DEC-100) are still open and neither is movie-specific:
  `_backfillable_items` counts a null `cover_path` or `year` as "worth a lookup" in every domain,
  regardless of `completeness_fields`; and `GET /api/search/resolve` maps every exception from
  `resolve_input` to a 502, so a typed `record_not_found` reads as a provider outage.

## Private data and operational constraints

- **`exports/` is the owner's private source archive and is gitignored as a whole directory.** It
  holds the Letterboxd ZIP, the MyAnimeList XML, two IMDb CSVs, a Trakt archive and a Spotify
  export, all carrying account ids, usernames, ratings, and in Trakt's case the owner's **email
  address**. Read-only walkthrough input. **No fixture may be cut from any of them** — every
  committed importer fixture is invented. Sprint 052's test connector and Sprint 053's IMDb reader
  both need invented fixtures, not slices of the real exports.
- Wikidata and TVmaze both need no key, only `USER_AGENT_CONTACT`. Stremio's poster host is already
  in `ALLOWED_COVER_HOSTS`.
- `frontend/e2e/scratchpad/` is gitignored; the series walkthrough specs there are local only.
