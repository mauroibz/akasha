# Handoff — plan revision 20, Sprint 038 ready

The numbered plan was complete through Sprint 037. The owner then asked for **anime as a third
domain**, with an importer for their own MyAnimeList export, explicitly as a trial run of the Sprint
028 domain contract whose findings feed back into this repository. Plan revision 20 adds Sprints
038–041; `FINAL_SPRINT` is 41; the active sprint is **038** with status `ready`.

Work is on the branch **`sprint-038-anime`**, cut from `main` at `bcb11ca` under DEC-053's rule that
a domain-line sprint runs on a branch. Merging it back is the owner's call at the line's close.

## What was decided, and where

- **DEC-088** — the providers, measured live on 2026-08-27 rather than chosen from documentation.
  AniList first, Kitsu second, Jikan rejected. Read it before touching an adapter; it carries the
  numbers, the two things the owner has to own, and the cover-host measurements.
- **DEC-089** — why anime is four sprints and not one, and the two seams it collects.
- Sprint files `038`–`041` carry the acceptance criteria. `038` is the only one that is `ready`.

## The plan in one paragraph

038 builds the domain the way `docs/guides/adding-a-domain.md` says one is built — a package, two
adapters, small registration points, no migration, no screen — and reports whether that guide was
sufficient on its own. 039 pays DEC-067 row 3, whose stated trigger ("the first domain that wants
background enrichment on a non-ISBN key") is now met. 040 builds DEC-077 shape (a), the per-domain
progress field that verdict chose and did not build; it is the **only shared-table migration in the
line**. 041 is the MyAnimeList connector, which lands complete because 039 and 040 precede it.

## Things a fresh session will otherwise rediscover

- **Jikan is not an option.** It returned HTTP 504 to every request across a forty-minute window —
  0/12 on search, 1/81 by id, and that one success was its own cache. `myanimelist.net` answered this
  host in 0.66s throughout. Do not re-add it on the theory that it was a bad afternoon without
  re-measuring first.
- **AniList needs a User-Agent** or Cloudflare answers `error code: 1010` with HTTP 403.
- **Kitsu returns the MyAnimeList id on a search row** with `include=mappings`, and studios plus
  categories in the same fetch with `include=animeProductions.producer,categories`. Studios are not an
  extra request per item; an earlier note in this planning session said they were and was wrong.
- **Anime is the first domain since books with a real cross-provider identity.** Both providers
  publish the MAL id, so `identity_key` returns `mal:<id>` and candidates merge. Albums' `None` is not
  the precedent to copy here.
- The owner's export is gitignored now, at the repository root. Use it for the Sprint 041 walkthrough
  only; the committed fixtures are trimmed and anonymised.

## State at this handoff

- `python scripts/validate_project.py` passes.
- Nothing outside `docs/`, `.gitignore` and the validator's sprint bound has changed. No product gate
  applies to the planning commit.
- No runtime code has been written for anime yet.
