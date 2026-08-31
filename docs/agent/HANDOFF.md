# Handoff — the plan is extended; Sprint 049 is ready and nothing is implemented yet

Plan revision 27 added five sprints, 049–053, for **television series** and the two importers the
owner asked for. `docs/agent/state.json` names **049** as active with status `ready`. No runtime code
for any of it exists.

The whole planning session is evidence-backed: `docs/series-domain-viability.md` holds live provider
measurements, the poster measurement, both of the owner's real exports parsed structurally, and the
anime-overlap question measured and answered. DEC-104 through DEC-107 hold the decisions. **Read the
viability document before Sprint 049 — the sprint file leans on it rather than repeating it.**

## What the next session is picking up

Sprint 049 builds the series domain on keyless Wikidata with posters from day one. The three things
most likely to be got wrong, all of them recorded:

- **The movie search filter does not transfer.** A single `haswbstatement:P31=Q5398426` — the shape
  `domains/movie/providers.py` uses — found the right series at rank 1 for 9 of 14 measured titles and
  returned nothing at all for two. Five classes are needed. Copying the movie adapter is the right
  instinct; this is the one line where it fails.
- **`seasons` and `cast` must not be enrichment completeness fields.** They were absent on 2 of 13 and
  4 of 13 measured entities. Naming a legitimately empty field re-queues its row on every backfill
  for ever.
- **The domain introduces no new status and no new format.** Anime's five statuses and the movie four
  formats are already published and already mirrored client-side. `ItemTypeName` is the only
  published-vocabulary change, and adding an `EntryStatus` member would be a mistake, not a step.

`metahub_poster_url` currently lives in `domains/movie/posters.py` and Sprint 049 moves it to
`infrastructure/posters.py`, because a domain package may not import another domain package and
duplicating a ten-line URL builder is the worse answer.

## Still true from before, and still not repaired

Sprint 047 was verified at a reduced level by owner direction (DEC-102): nobody has seen the
Letterboxd connector rendered on the Import page, nobody has approved a movie row through the Triage
UI, and **undo has no coverage in that sprint at any level**. Sprint 052's walkthrough gate is where
that debt is scheduled to be paid, because it exercises the same screens with the same domain.

Two recorded defects from Sprint 046 (DEC-100) are still open and neither is movie-specific:

- `_backfillable_items` counts a null `cover_path` or `year` as "worth a lookup" in every domain,
  regardless of that domain's `completeness_fields`.
- `GET /api/search/resolve` maps every exception from `resolve_input` to HTTP 502 `provider_failure`,
  so a typed `record_not_found` is reported as an outage.

Nothing has been tagged, released or pushed. The movie line, v1.4.0 included, is entirely local on
this branch.

## Private data and operational constraints

- **`exports/` is the owner's private source archive and is gitignored as a whole directory.** It
  holds the Letterboxd ZIP, the MyAnimeList XML, two IMDb CSVs, a Trakt archive and a Spotify export.
  Every one carries account ids, usernames or ratings; the Trakt archive carries the owner's **email
  address** in `user-settings.json` and `user-profile.json`. These are read-only walkthrough input.
  **No fixture may be cut from any of them** — every committed importer fixture is invented.
- The directory is ignored wholesale rather than by pattern because IMDb names its CSVs after a list
  UUID and no pattern would have caught them.
- Wikidata and TVmaze both need no key, only `USER_AGENT_CONTACT`. Stremio's poster host is already
  in `ALLOWED_COVER_HOSTS`; series need no allowlist change.
- TVmaze's published rate limit is at least 20 calls per 10 seconds per IP, with HTTP 429 on breach.
- `frontend/e2e/scratchpad/` is gitignored; the movie walkthrough spec there is local only.
