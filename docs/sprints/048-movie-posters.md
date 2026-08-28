# Sprint 048 — Movie posters, without a setup step

**Status:** completed
**Depends on:** 047
**Roadmap revision:** 26

## Objective

Give movies covers. Sprint 046 shipped the domain deliberately coverless because Wikidata has no
posters, and the owner's first real import made the consequence plain: a wall of blank tiles in
Library and Triage. Posters come from Stremio's keyless image service, keyed on the IMDb id the
Wikidata adapter already stores, with TMDB filling only the gap Stremio structurally cannot.

## Required context

- `docs/decisions.md`: DEC-098 (why movies launched coverless), DEC-099, DEC-100.
- `infrastructure/covers.py` in full — the allowlist, the bounds and the redirect rules are the
  contract this plugs into. Do not loosen any of them.
- `domains/movie/providers.py` and its recorded fixtures.
- `docs/guides/adding-a-domain.md` §2 row 8: the cover-host allowlist is a documented shared
  registration point.

## Measurement behind this plan

Taken live on 2026-08-28, before any code was written:

- **Stremio's `images.metahub.space` returned a poster for 14 of 14 films**, chosen to be hard:
  Argentine cinema (`Nueve reinas`, `Zama`, `La ciénaga`, `Pizza birra faso`, `La flor`),
  `Sátántangó`, `Tokyo Story`, `Cure`, and Apichatpong's first feature. No key, no account.
- **The URL is deterministic** — `images.metahub.space/poster/medium/<imdb id>/img` — so a poster
  costs **zero API calls**. TMDB by contrast needs one request per film to learn its opaque
  `poster_path`.
- **A miss is a clean 404**, not a placeholder, so nothing junk can be installed.
- **`medium` is 500×750 JPEG or WebP.** `MIN_PROVIDER_COVER_EDGE` is 200 and `MAX_COVER_EDGE` 600,
  so it downscales without upscaling, and `image/webp` is already an accepted content type.
- **Of 50 sampled films carrying a TMDB id, 49 also carry an IMDb id.** The ~2% that do not are the
  only case Stremio cannot serve and TMDB can.

## Deliverables

### 1. A poster source that needs no setup

Add `domains/movie/posters.py`. `metahub_poster_url(imdb_id)` builds the deterministic Stremio URL
and nothing else — no request, no client, no key. It is the primary source for every film carrying
an IMDb id, which is nearly all of them.

### 2. TMDB, only where Stremio cannot help

A small TMDB poster lookup, used **only** when a film has a TMDB id and no IMDb id, and only when a
read token is configured. It costs one request in the ~2% case and none otherwise. Absent a token
the domain simply has no answer for those films, which is the same coverless state they are in
today rather than a regression.

`TMDB_READ_TOKEN` joins `config.py` as an optional setting alongside `GOOGLE_BOOKS_API_KEY`. A
missing token disables the fallback; it never fails a search or an enrichment.

**Deliberately not included, at the owner's explicit direction:** the six-month cache refresh and
the TMDB attribution notice its terms ask for. This is a recorded decision, not an oversight — see
the decision entry this sprint appends.

### 3. Wiring, through the shape the pipeline already has

`WikidataMovieProvider` emits the poster in `cover_url`, and the shared cover pipeline owns
everything after that: https, the allowlist, redirects, byte, pixel and aspect bounds, and the
downscale. Two hosts join `ALLOWED_COVER_HOSTS`: `images.metahub.space` and `image.tmdb.org`.

No shared screen, model or route changes. A cover reaches Library, Triage and Detail because those
screens already render one.

### 4. The films already imported

The owner's two imported films must end up with posters without re-importing. The existing
`POST /api/enrichment/backfill` already re-queues coverless movies — the behaviour DEC-100 recorded
as a defect is, for exactly this once, the mechanism that fixes them.

## Acceptance criteria

1. A movie search or fetch carrying an IMDb id emits a Stremio poster URL, with no extra request.
2. A film with a TMDB id and no IMDb id emits a TMDB poster URL when a token is configured, and no
   cover when it is not. A film with both never spends a TMDB request.
3. The cover pipeline installs the poster unchanged: no bound is loosened, and both new hosts are
   allowlisted explicitly rather than by suffix.
4. A 404 from either source leaves the item coverless and never fails the search, fetch or job.
5. Posters are visible in Library, Triage and Detail against real data, verified in a browser.
6. No migration, no new route, no screen change, no OpenAPI change.

## Required tests

- Poster-URL construction, including a film with no IMDb id, no TMDB id, and neither.
- Recorded 404 and recorded image responses through `prepare_cover`, proving a miss is survivable and
  a hit installs.
- The TMDB fallback is not consulted when an IMDb id exists, and is skipped when no token is set.
- Existing movie provider and conformance suites pass unchanged.

## Verification

```bash
cd backend && uv run pytest tests/test_movie_posters.py tests/test_wikidata_provider.py \
  tests/test_covers.py tests/test_domain_conformance.py -q
make check
make test
```

Then a real check: run the app on a disposable data directory, import or add films, and **look at
the screens**. Sprint 046's gate passed while producing exactly the blank-tile experience this
sprint exists to fix, so "the field is populated" is not the standard — a visible poster is.

## Explicit non-scope

- The six-month TMDB cache refresh and the TMDB attribution notice (owner's decision).
- Backdrops, logos, stills, or a cover chooser for movies.
- Posters for books, albums or anime, all of which already have their own sources.
- Any change to the cover bounds, the allowlist mechanism or the redirect policy.

## Commit checkpoints

1. `feat(sprint-048): give movies posters from a keyless source`
2. `docs(sprint-048): close sprint and hand off`

## Outcome

Movies have posters. Verified where the last sprint did not look: on a screen.

### What ships

`domains/movie/posters.py` builds a Stremio poster URL from the IMDb id the Wikidata
adapter already extracts — no request, no key, no configuration. `WikidataMovieProvider`
attaches it as `cover_url`, and the shared cover pipeline owns everything after that.
`TmdbPosters` is consulted only when a film has no IMDb id and a token is configured.
Two hosts joined `ALLOWED_COVER_HOSTS`; no bound, redirect rule or aspect guard changed.

### Acceptance criteria

1. A film carrying an IMDb id gets a built poster URL with no extra request.
2. A film with only a TMDB id uses the fallback when a token exists and stays coverless
   without one. A film with both **never** spends a TMDB request — asserted with a
   transport that fails the test if it is called.
3. The pipeline installs it unchanged: both hosts are named explicitly, and a 500×750
   WebP arrives as a 400×600 JPEG through the existing downscale.
4. A 404 leaves the item coverless and fails nothing.
5. **Posters are visible in Library and Triage**, verified in a browser against the
   owner's own imported films.
6. No migration, no route, no screen change, no OpenAPI diff.

### Verification

- `tests/test_movie_posters.py` **22 passed**; `tests/test_wikidata_provider.py` **60**;
  conformance, covers and enrichment suites pass.
- `make check` clean, `make openapi` no diff, full suites **903 backend / 189 frontend**.
- Real data: the owner's Letterboxd archive re-imported on a disposable data directory
  with the real configuration. Both enrichment jobs succeeded and both films installed a
  400×600 JPEG poster; each was opened and confirmed to be that film's actual poster art.
- `frontend/e2e/scratchpad/movie-posters.spec.ts`, **2 passed**: an `<img>` pointing at
  the cover endpoint, with a non-zero `naturalWidth`, in **Triage** and in the
  **Library**. The width assertion is the point — an element whose image failed to load
  still has a `src`, which is exactly what a field-level check would have missed.

### The two `NoCover` tests from Sprint 046

Rewritten rather than deleted. They encoded a decision this sprint deliberately reverses,
but the invariant inside them still holds and still matters: `P18` is never read, and
`Q151599` must not wear its set photograph. Those assertions are now stronger — they name
the poster the film should have instead.

### Deliberately not built

The six-month TMDB cache refresh and the TMDB attribution notice its terms request. The
owner considered both and directed that they be left out (DEC-103). With TMDB reduced to
a ~2% fallback this is a narrower exposure than it would have been under the original
TMDB-primary design, but it is a real one and it is recorded rather than glossed.

### Commits

`beb4427` give movies posters from a keyless source · plus this closure commit.
