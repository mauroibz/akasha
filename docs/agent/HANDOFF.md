# Handoff — Sprint 038 closed, Sprint 039 ready

Anime ships. Plan revision 20, `FINAL_SPRINT` 41, active sprint **039 — Enrichment beyond the ISBN**,
status `ready`. Work is on the branch **`sprint-038-anime`**, cut from `main` at `bcb11ca` under
DEC-053. Nothing is pushed. Merging the branch is the owner's call at the line's close, not per sprint.

## What Sprint 038 delivered

A registered `anime` domain with two adapters — AniList primary, Kitsu second — added and used
through the existing screens. **No migration, no screen written for it, no other domain's file
touched.** Full detail in the sprint's Outcome; the reasoning is DEC-088 (the providers, measured)
and DEC-090 (what building it found).

Verification at closure: `make check` green, `make test` **616 backend / 183 frontend**, Playwright
**103 passed / 2 skipped**, and a 5-of-5 walkthrough at 390x844 against a disposable data directory
and the live provider APIs. Live `data/` untouched.

## Sprint 039 in one paragraph

DEC-067 row 3 named its own trigger — "the first domain that wants background enrichment on a
non-ISBN key" — and anime is it. `PROVIDER_ORDER` is a module constant naming two book providers,
`_backfillable_items` joins `item_identifiers` on the literal `'isbn'`, and `_fetch` calls
`fetch_by_isbn`. A domain declares its enrichment key and provider order instead; **books' behaviour
must not change**, and the existing enrichment tests are the guard rather than something to relax.
No migration — a job is a row with a JSON payload — but there **is** a compatibility path for jobs
already queued under the old shape, and it needs a test, because nobody would notice it failing.

## Things a fresh session will otherwise rediscover

- **`bounded_json` already takes `method` and `json_body`.** Sprint 038 added them for AniList's
  GraphQL POST. A provider reached by POST costs Sprint 039 nothing extra. Do not write a bespoke
  request loop.
- **Translate provider HTTP errors at the adapter.** A 404 is `record_not_found`, anything else is
  `provider_http_error`; enrichment's retry reads the difference. Both anime adapters and
  `domains/book/providers.py` do this.
- **AniList needs a User-Agent** or Cloudflare answers `error code: 1010` / HTTP 403. It answers a
  missing record with **404**, not a 200 carrying null.
- **Anime's enrichment key is `mal`,** and both providers resolve it: AniList through `Media(idMal:)`,
  Kitsu through the mappings filter. Measured resolving all 81 of the owner's export ids — AniList in
  2 requests / 54 KiB, Kitsu in 5 requests / 552 KiB (DEC-088).
- **Jikan is not an option** and is not registered. It returned HTTP 504 to every request across a
  forty-minute window while `myanimelist.net` answered in 0.66 s. Do not re-add it without measuring.
- **A test that enumerates what exists today is a test the next domain breaks.** Sprint 038 hit this
  in `test_provider_health.py`; Sprint 028 hit it in `test_item_types.py`. Assert against the registry.
- **Writing a walkthrough?** The domain chooser is a `radiogroup`, the status filter is a popover
  whose options carry facet counts, and library row controls are popovers where Triage's are native
  selects (DEC-086). Four of my first assertions were wrong about the UI, none about the product.
  `frontend/e2e/scratchpad/anime-walkthrough.spec.ts` is the working example; it is gitignored.

## After 039

**040 — Entry progress** builds DEC-077 shape (a) and is the **only shared-table migration in the
line**; it and 039 are independent of each other and both block **041 — The MyAnimeList import**. The
owner's export sits gitignored at the repository root; use it for 041's walkthrough only, and commit
trimmed anonymised fixtures instead.
