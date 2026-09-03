# Sprint 064 — A second source for anime and albums

**Status:** blocked
**Depends on:** 038, 052
**Roadmap revision:** 34

## Objective

The other two single-provider domains, split from Sprint 063 because each is blocked on
something that sprint was not: a re-measurement for anime, a product decision for albums.
See `docs/sprints/ROADMAP.md`'s own entry for this sprint, written when Sprint 063 was
planned.

## Why this file is a stub, not a plan

Sprint 063 closed needing `docs/agent/state.json` to point at the next sprint in
sequence. This one has no detailed plan yet — the roadmap entry says so explicitly
(`**[PLANNED, not yet written]**`) — so rather than invent one, this file records only
what is already established and marks itself `blocked` on the two things a real plan
needs first. Writing the actual plan (a fresh live measurement, and the owner's answer
below) is the first work of whichever session picks this up.

## Current implementation baseline

Measured 2026-09-02, recorded in `docs/sprints/ROADMAP.md`'s Sprint 064 entry:

- **Anime.** Jikan (MyAnimeList's API) is the obvious candidate — `mal:` is already the
  anime domain's declared identity, so it would merge with Kitsu for free. But its search
  endpoint answered `504` on every attempt on 2026-09-02 while `myanimelist.net` itself
  was up (DEC-088's own measurement run). Blocked on re-measuring whether it has become
  dependable enough to be worth the adapter.
- **Albums.** Blocked by DEC-052, which found deliberately that albums have **no**
  cross-provider identity — barcode `888837168625` appeared on three distinct releases —
  so a second provider means un-mergeable duplicate rows in every search. Deezer and
  iTunes were both measured keyless and working; neither can merge until the identity
  question is reopened. That is a product decision for the owner, not an adapter to
  write.

## Risks and decisions to surface

- **Anime:** re-measure Jikan live (search and by-id lookups) before committing to the
  adapter. A repeat `504` is a valid outcome and closes this half of the sprint with no
  adapter written, the same shape Sprint 063's AC1 gate allows.
- **Albums:** ask the owner whether DEC-052's "no cross-provider identity" finding
  should be reopened, and if so, on what basis (e.g. title+artist+track-count fuzzy
  matching, accepting the un-merged duplicate-row cost, or something else). Until that
  answer exists, no second album provider can be added without either duplicating every
  search result or inventing an identity rule nobody has agreed to.

## Outcome

_Not started._
