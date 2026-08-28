# Handoff — Sprint 046 ready: movies on measured Wikidata

Sprint 045 is complete on `sprint-045-movies` in `83646a7`, `36621ef` and `0e93be8`; DEC-098 and
`docs/movie-domain-viability.md` hold the evidence. **Wikidata is the selected launch provider.**
Its official API was live-tested across Spanish/Argentine, old, recent and remake cases, linked
labels and exact IMDb/TMDB/Letterboxd identities. It needs no key. Image coverage was poor and the
one image was not a poster, so Sprint 046 deliberately offers no automatic cover.

TMDB/OMDb both require absent owner credentials and returned 401. TMDB is not merely waiting for a
token: its six-month cache/attribution terms conflict with the current permanent, owner-editable
cache. Do not add either to make the movie walkthrough prettier.

## Next sprint

Sprint 046 is ready. Read `docs/sprints/046-movie-domain.md` and every required source, then inspect
the actual current registry/provider/conformance code. Build the movie declaration and recorded
Wikidata adapter with exact external-id and HEAD-only Letterboxd URL resolution. It is a user-visible
domain sprint: run the focused tests, ordinary gates and disposable realistic walkthrough it names.
No migration, shared screen or container work is planned.

Sprint 047 is planned after it and owns the Letterboxd ZIP reader plus neutral title/year ambiguity.
Do not pull importer work into 046.

## Private and operational constraints

- `letterboxd-tomateperitarg-2026-08-27-22-42-utc.zip` remains untracked private data. Sprint 046
  must not read it; Sprint 047 may use it only as read-only walkthrough input and never a fixture.
- Public provider fixtures must be freshly recorded and bounded, with source/date/probe documented.
- The user asked to avoid redundant investigation of the working container. Follow each sprint's
  actual gates; neither planned sprint includes container/build work unless packaging changes.
- The v1.3.0 anime/MyAnimeList release remains merged, tagged and pushed on `main` at `3bce2de`.
