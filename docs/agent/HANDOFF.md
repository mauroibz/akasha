# Handoff — Sprint 052 is complete; Sprint 053 (the IMDb import) is ready

The shared import boundary holds more than one domain now, and it was proved against a test
connector before either reader that needs it exists. `docs/agent/state.json` names **053** as active
with status `ready`. `make test` is 1012 backend + 194 frontend, green; `make check` is green;
Playwright is 106 passed + 2 skipped serially. Nothing is tagged, released or pushed — the whole
series line is local on this branch.

Two debts carried in the last handoff are **closed**: Sprint 051's owed flow-through proof (a
Playwright flow ran through `scripts/walkthrough.py` for the first time) and Sprint 050's owed live
series search (live Wikidata and TVmaze both answered and merged on the IMDb id).

## What Sprint 052 changed, for the sprint that picks up next

- `Importer.item_types: tuple[str, ...]` replaces `item_type`, ordered, first-declared first.
  `NormalizedImportRecord.item_type` names a row's own domain; `None` means the first declared. A
  type the connector did not declare is refused at the boundary with `invalid_import_record`.
- `ImportService.domains` replaces `.domain`. Validation, commit and the enrichment guard each
  resolve per record. `ImportRepository.commit` takes `domains: Mapping[str, Domain]` and reads the
  type from the stored payload, so commit still never re-opens the source.
- `IMPORTERS_BY_DOMAIN` is **derived** from what connectors declare. Registering one is a single
  entry in `REGISTERED_IMPORTERS`; the index and the declaration cannot drift.
- `POST /import/{importer}/preview` takes an optional `targets` — comma-separated multipart field,
  or a JSON list. Absent means everything declared; an undeclared or empty set is a 422
  `invalid_import_targets`. The **service** applies it and drops unwanted rows before staging.
- `ImportSnapshot.skipped` is `(ImportSkip(reason, count), …)` — what a reader saw and could not
  target. It reaches the summary as `skipped_unsupported` / `skipped_reasons`, separately from
  `skipped_not_requested`, and neither is ever an error. **This is the channel Sprint 053's
  `Title Type` table maps onto directly.**
- `GET /api/importers` publishes `item_types` (a list). That is the one breaking published change.
- The fingerprint gains the chosen targets **only on a strict subset**, which is why there is no
  migration: a one-domain connector always selects all of it and fingerprints as it always did.

DEC-112 records the two mechanisms and why each was chosen.

## What the next session is picking up

Sprint 053 — the IMDb import. Read `docs/sprints/053-imdb-import.md`; its baseline section was
rewritten at 052's closure with what is actually built. One connector, `imdb`, declaring
`("movie", "series")`, over two CSV shapes detected from the header. Its sharpest criterion is the
negative one: **no change to `application/imports.py`, `api/imports.py`, `ImportPage.tsx` or
`TriagePage.tsx`.** If that cannot be met, the finding is the deliverable and Sprint 052 was
incomplete.

**Answer this before AC9 can pass:** `movie.enrichment.identity_kind` is `letterboxd` while
`series` is `imdb`. An IMDb export carries no Letterboxd id, so post-commit enrichment will queue
the series rows and not the films. Either the movie domain learns to enrich on `imdb` — which its
Wikidata provider already resolves — or AC9 narrows with the reason recorded. Do not let it pass as
a silent gap.

## Running the walkthrough gate

`scripts/walkthrough.py` is the launcher and it works; use it rather than hand-rolling a fourth
runner. Two things cost a Sprint 052 iteration and are worth knowing:

- The `--replay` hook is the launcher's only in-application seam, so a module may use it to
  **register** a fixture connector and return the live transport unchanged — that is what
  `scripts/walkthrough_two_domains.py` does, importing `TwoDomainImporter` from
  `backend/tests/test_multi_domain_imports.py` so the browser flow and the suite share one
  definition.
- Navigating to `/import?tab=<connector>` by URL does not record the source preference, so coming
  back from Triage lands on the remembered connector and discards the batch — which puts undo out
  of reach. **Click the tab instead.** Designed behaviour, commented in `ImportPage.tsx`.

The command pair, both halves needed:

```bash
cd backend && uv run python ../scripts/walkthrough.py --replay ../scripts/walkthrough_two_domains.py
cd frontend && BOOK_TRACKER_INCLUDE_SCRATCHPAD=1 \
  BOOK_TRACKER_E2E_BACKEND=http://127.0.0.1:<printed port> \
  npx playwright test --project=chromium --workers=1 e2e/scratchpad/sprint52-walkthrough.spec.ts
```

`frontend/e2e/scratchpad/` is gitignored, so that spec is local only, as Sprint 050's was.

## Known and left, in the order they are likely to bite

- **An intermittent accessibility failure under parallel Playwright, and it is not this sprint's.**
  Six workers make axe report `color-contrast [serious]` on `.text-muted-foreground/80` — one class,
  used once, at `frontend/src/features/library/VirtualLibrary.tsx:100`. Serial runs are green every
  time and the failing spec moves between the two that render that caption. Computed statically the
  composite is 5.26:1 on the background and 4.88:1 on a surface, both above the 4.5:1 that size
  needs, so this reads as a sample taken mid-fade rather than a palette defect. Sprint 051's
  parallel split surfaced it. Worth a scoped look: stop the caption fading before axe reads it, or
  drop the opacity.
- **The e2e dev server proxies `/api` to a backend that is not running** unless
  `BOOK_TRACKER_E2E_BACKEND` is set. The gate prints `ECONNREFUSED` noise throughout while passing —
  the specs stub their own API. Recorded, not fixed.
- **Sprint 047 was verified at a reduced level by owner direction (DEC-102).** Nobody has seen the
  Letterboxd connector rendered on the Import page, nobody has approved a movie row through the
  Triage UI, and undo has no coverage in that sprint at any level. Sprint 053's walkthrough is where
  that debt is scheduled to be paid — and it is now cheap, because Sprint 052's walkthrough already
  proved mixed-domain Triage and undo through the real screens.
- Two recorded defects from Sprint 046 (DEC-100) are still open and neither is domain-specific:
  `_backfillable_items` counts a null `cover_path` or `year` as "worth a lookup" in every domain,
  regardless of `completeness_fields`; and `GET /api/search/resolve` maps every exception from
  `resolve_input` to a 502, so a typed `record_not_found` reads as a provider outage.

## Private data and operational constraints

- **`exports/` is the owner's private source archive and is gitignored as a whole directory.** It
  holds the Letterboxd ZIP, the MyAnimeList XML, two IMDb CSVs, a Trakt archive and a Spotify
  export, all carrying account ids, usernames, ratings, and in Trakt's case the owner's **email
  address**. Read-only walkthrough input. **No fixture may be cut from any of them** — every
  committed importer fixture is invented, including Sprint 052's two-domain connector. Sprint 053's
  IMDb reader needs invented fixtures, not slices of the real exports.
- Wikidata and TVmaze both need no key, only `USER_AGENT_CONTACT`. Stremio's poster host is already
  in `ALLOWED_COVER_HOSTS`.
