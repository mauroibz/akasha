# Handoff — the plan is complete at Sprint 055; the release decision is the owner's

Sprint 055 closed with every recorded defect fixed and every verification gate repaired,
so all 55 planned sprints are done. `docs/agent/state.json` reads `complete` with null
active fields. Nothing is tagged, released or pushed — every commit is local on
`sprint-049-series`. The next move is the owner's, not an agent's: the **v1.5.0 release
decision** (five domains, four import sources, the series line, zero known open
defects), and whether the movie line's v1.4.0 gets tagged before it. Sprint 018's
release procedure is unchanged; nothing moves without being asked.

## What Sprint 055 delivered

**A series gets the synopsis somebody would actually read (DEC-115).**
`EnrichmentSpec.fuller_answer_fields` — the declaration shape the sprint preferred —
with series declaring `("synopsis",)`. The first usable payload still wins everything
else; the remaining providers are asked for the declared fields alone and the longest
string fills the field. The walkthrough caught the unit suites' blind spot: the *add
path* never consulted a second provider and never queues enrichment, so a series added
by hand kept the one-liner for ever. `prefer_fuller` lives in `domain/merge.py` and both
arrival paths apply it; verified live — BoJack stores TVmaze's 151-char synopsis with
Wikidata's `episodes: 77` and `network: Netflix` untouched.

**The two DEC-100 defects (DEC-116).** Cover and year backfill conditions are
`wants_cover`/`wants_year` declarations (default True; a future domain opts out instead
of being re-queued for ever). `/api/search/resolve` answers a typed `record_not_found`
with **404** under the provider's own code and message; transport failures keep the 502.

**The gates, as measured at this closure** (TESTING.md carries the full table):

- **Parallel Playwright is the gate** — three consecutive green runs (44.5, 44.5,
  45.3 s) plus a fourth (43.7 s) after the last change. Four load-sensitive tests live
  in the serial `heavy-library` project (18.8 s alone): DEC-023's two, two crossfade
  samplers, and the three library-view axe checks. The card caption no longer fades.
- **Coverage left `addopts`.** `make test` and `make coverage` carry the flags; a focused
  run is 1–5 s with no table. A session that never runs either sees no number — the
  intended trade, named in TESTING.md.
- **`make check` is green with scratchpad specs present** (Prettier and ESLint ignore
  the gitignored directory), and **a green `npm test` prints no stderr** (motion's
  Reduced Motion notice filtered; vitest's empty labels suppressed).
- `make test`: 1184 backend + 194 frontend, coverage 90%.

## The one question this sprint leaves with the owner

The IMDb list export's `Description` column is deliberately dropped by the reader. If
you use it as a note, it can be mapped to entry notes — a product decision, not a
defect, so nothing was implemented. Say yes and it becomes a small follow-up.

## If a future session starts anything new

There is no next sprint. A new sprint requires a plan revision (state flips `complete →
ready` with a new active file — the seeds skill's extension worked example is the
mechanics, including the validator's sprint-file-at-`ready` trap). The roadmap's future
epics list the candidates: games via IGDB, music imports via Spotify, ebook
attachments' follow-ups. The walkthrough launcher (`scripts/walkthrough.py`) and the two
sprint-specific API scripts (`walkthrough_trakt_054.py`, `walkthrough_synopsis_055.py`)
are tracked and take owner paths through the environment, never inline.

## Private data and operational constraints

- `exports/` is the owner's private source archive, gitignored as a whole. Read-only
  walkthrough input. **No fixture may be cut from any of them** — every importer
  fixture is invented. Trakt's two email-carrying members are never opened by the
  reader, and a test asserts it.
- Wikidata, TVmaze and AniList need no key, only `USER_AGENT_CONTACT`. Stremio's poster
  host is already in `ALLOWED_COVER_HOSTS`. IGDB would need Twitch OAuth credentials.
- Secrets, databases, uploaded imports and covers are never committed; v1 has no auth
  and stays LAN-only; Calibre is opened read-only.
