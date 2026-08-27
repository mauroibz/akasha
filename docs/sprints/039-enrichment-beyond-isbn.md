# Sprint 039 — Enrichment beyond the ISBN

**Status:** completed
**Depends on:** 038
**Roadmap revision:** 20

## Objective

A domain declares the identifier its background enrichment is keyed on and the providers that answer
it, so enrichment stops assuming an ISBN and two book providers. Books' behaviour does not change.

## Required context

- `docs/decisions.md`: **DEC-067 row 3** — this sprint is the option (b) that row costed and
  deferred, and its trigger condition ("the first domain that wants background enrichment on a
  non-ISBN key") is now met. Also **DEC-089**, DEC-088, DEC-008 (fill-empty-only), DEC-044 and
  DEC-045 (the edition-verification rule and the provider quota that enrichment runs under),
  DEC-025 (why a mock of the unit under test proves nothing at a boundary).
- `docs/specs/technical-spec.md` §6.2, §6.4 and §6.6.
- `docs/guides/adding-a-domain.md` §6 — the section that names this gap. **It is rewritten by this
  sprint.**
- Code: `application/enrichment.py` in full, `application/imports.py` around
  `enqueue_enrichment_backfill`, `api/imports.py` backfill route, `infrastructure/jobs.py`,
  `infrastructure/quota.py`, `domain/spec.py`, `domains/book/providers.py`.
- Tests: `tests/test_enrichment.py`, `tests/test_enrichment_pipeline.py`, `tests/test_provider_quota.py`.

## Current implementation baseline

Observed on 2026-08-27 at `bcb11ca`. Three things below `Domain.enriches` assume books:

- `PROVIDER_ORDER = ("openlibrary", "googlebooks")` is a module constant in `application/enrichment.py`.
- `_backfillable_items` selects items whose type is one of the enriching domains and joins
  `item_identifiers` on the literal `ident.kind = 'isbn'`, returning `(item_id, isbn)`.
- `enqueue_enrichment_backfill` enqueues `enrich_item` jobs with the payload `{"item_id", "isbn"}`;
  `EnrichmentHandler.process` reads `payload["isbn"]`, fails with `error_code: "no_isbn"` when absent,
  and `_fetch` calls `provider.fetch_by_isbn(isbn)`.

`Domain.enriches` is therefore a real switch over *which item types are considered* and nothing
below it is neutral. Albums declare `False`, so no domain has ever exercised the seam.

## Deliverables

### 1. The declaration — `domain/spec.py`

`Domain.enriches: bool` is replaced by a declaration that says what enrichment means for this domain:

```python
@dataclass(frozen=True)
class EnrichmentSpec:
    """What background enrichment is keyed on, and who answers it."""
    identity_kind: str            # "isbn", "mal"
    provider_order: tuple[str, ...]
```

`Domain.enrichment: EnrichmentSpec | None`, where `None` is the complete answer albums give. Keep the
`enriches` reading available as a property so no call site has to ask two questions.

The conformance suite gains no test — it is parametrized over `DOMAINS` — but the malformed-domain
fixtures at the bottom of `test_domain_conformance.py` gain a case: a domain declaring an enrichment
spec with an empty provider order, or a `identity_kind` no adapter answers, must fail.

### 2. The provider protocol — `domain/providers.py`

`fetch_by_isbn` becomes `fetch_by_identifier(kind: str, value: str) -> ItemPayload`, declared on an
optional protocol a provider opts into. Book providers implement it and keep their ISBN behaviour
including DEC-044's edition-verification rule, which is the correctness property this sprint must not
lose. `fetch_by_isbn` may remain as a thin call for readability; it must not remain as the interface.

### 3. The query — `_backfillable_items`

Selects per enriching domain using that domain's declared `identity_kind` rather than the literal
`'isbn'`, and returns `(item_id, kind, value)`. One statement per enriching domain is acceptable;
a domain with no enrichment spec contributes no rows.

### 4. The job — payload and handler

- New jobs carry `{"item_id", "kind", "value"}`.
- **A job queued under the old shape must still process.** Rows survive restart by design, so a
  payload carrying `isbn` is read as `kind="isbn"`. This is a compatibility path with a test, not a
  comment.
- `_fetch` iterates the *domain's* provider order, keeps the existing quota gate, the defer-rather-
  than-fail rule when everything is capped, and the requirement that every attempt contributes a
  sentence to the recorded reason.
- `error_code: "no_isbn"` becomes `"no_enrichment_key"`. Anything rendering the old code is updated.

### 5. Anime turns it on

`domains/anime/__init__.py` declares `EnrichmentSpec(identity_kind="mal", provider_order=("anilist", "kitsu"))`,
and both adapters implement `fetch_by_identifier("mal", value)`. AniList answers it with
`Media(idMal:)`; Kitsu answers it through the mappings filter. Both were measured resolving all 81 of
the owner's ids (DEC-088).

### 6. The guide

`docs/guides/adding-a-domain.md` §6 is titled "One thing that is not solved yet" and describes this
gap. Rewrite it as what a domain declares. The guide promises a third domain never has to read how
the second was built; a section describing an unbuilt seam is the opposite of that.

## Acceptance criteria

1. Books enrich exactly as before: same provider order, same fill-empty-only rule, same
   edition-verification refusal, same quota behaviour, same ledger effects, same undo. The existing
   enrichment tests pass **unmodified** except where they name `no_isbn` or the payload shape.
2. An anime item carrying a `mal` identifier and empty metadata is enqueued by the backfill and
   filled from AniList; Kitsu is used when AniList fails, and the recorded reason names both attempts.
3. An item whose domain declares no enrichment spec is never enqueued.
4. An item whose domain declares a spec but which carries no identifier of that kind is not enqueued.
5. A job persisted under the old `{"item_id", "isbn"}` payload processes correctly after upgrade.
6. Enrichment never overwrites a value the owner edited, in any domain.
7. Nothing above the registry names an identifier kind or a provider. `grep` for `'isbn'` in
   `application/` returns only the book domain's own concerns.
8. **No migration.** Jobs are rows with JSON payloads; this changes what is written into one.

## Required tests (TDD)

- `tests/test_enrichment.py` — extended with the anime key path, the old-payload compatibility case,
  and the no-spec / no-identifier skip cases. Boundary behaviour against recorded responses.
- `tests/test_enrichment_pipeline.py` — an end-to-end backfill over a library holding books and anime,
  asserting each is enqueued under its own key and neither is enqueued under the other's.
- `tests/test_domain_conformance.py` — malformed-domain fixtures for an empty provider order and an
  unanswerable `identity_kind`.
- `tests/test_provider_quota.py` — unchanged behaviour under the new provider order lookup.

## Verification

```bash
cd backend && uv run pytest tests/test_enrichment.py tests/test_enrichment_pipeline.py \
  tests/test_provider_quota.py tests/test_domain_conformance.py -q
make check && make test
```

Walkthrough: with the running application, add an anime by URL so the item exists with a `mal`
identifier, clear its metadata, trigger the backfill route, and watch the job fill it from AniList.
Then do the same for a book and confirm nothing about that path changed. Record the job rows observed,
not a summary of them.

## Explicit non-scope

- **Moving enrichment behind the adapter** (DEC-067 row 3 option (c)). Costed as reaching the job
  payload and the ledger; not bought.
- **A second enrichment pass or a refresh scheduler.** Explicit refresh remains the only overwrite
  path.
- **Widening the quota model.** Neither AniList nor Kitsu is metered by key; both are unmetered in
  `provider_daily_limits` and stay that way unless measured otherwise.
- **The importer.** Sprint 041 is what makes this sprint's work visible in anger.

## Commit checkpoints

1. `feat(sprint-039): declare what a domain enriches on`
2. `feat(sprint-039): fetch by identifier rather than by isbn`
3. `feat(sprint-039): key the backfill on the domain's own identifier`
4. `feat(sprint-039): anime enriches from AniList and Kitsu`
5. `docs(sprint-039): rewrite the guide's unsolved seam as a declaration`
6. `docs(sprint-039): close sprint and hand off`

## Risks and decisions to surface

- **Silently changing books' enrichment is the failure mode.** The existing tests are the guard and
  must not be relaxed to fit the new shape. If one has to change, say exactly why in the Outcome.
- **The old-payload compatibility path** is easy to forget and impossible to notice: a queued job
  fails quietly on a machine that upgraded mid-run. It has a test for that reason.
- If generalizing turns out to cost materially more than DEC-067 row 3's "about half a sprint",
  record the difference. That row is the repository's own estimate and its accuracy is worth knowing.

## Outcome

**Completed 2026-08-27** on branch `sprint-038-anime`. Commits `c62c559` (the contract),
`81e110f` (the provider interface), `16e2f20` (the backfill and handler), `eb03114` and `19a3361`
(documentation). Recorded as **DEC-091**.

### The deliverable the plan did not name

`EnrichmentSpec` has **three** parts, not the two this sprint's baseline described. The baseline
listed the ISBN join, the payload and `PROVIDER_ORDER`; it missed that `_backfillable_items` also
judged **incompleteness** by `publisher`, `page_count` and `description`. An anime has none of the
three, so under the old rule every anime would have looked permanently incomplete and been re-queued
on every backfill — the domain would have appeared to enrich while never finishing. DEC-067 row 3's
option (b) did name "an incompleteness rule per domain", so this is a gap in the sprint file rather
than in the original costing. `completeness_fields` is the third part, and conformance refuses one
naming a field the domain does not declare.

### Acceptance criteria, one line each

1. **Books are unchanged.** Same provider order (now declared in `domains/book/` rather than a shared
   constant), same fill-empty-only rule, same edition verification, same quota, same ledger effects.
   Every existing enrichment test passes **unmodified**; none named `no_isbn` or the payload shape.
2. **An anime is enqueued and filled from AniList.** Proved by test against a recorded response and
   live in the walkthrough below.
3. **A domain declaring no enrichment is never enqueued** — albums, with an explicit `None`.
4. **An item carrying the wrong kind of identifier is not enqueued** — an anime with an ISBN.
5. **A job under the old `{item_id, isbn}` payload processes.** Test plus a live exercise.
6. **Enrichment never overwrites an edited value.** The existing tests carry this; the walkthrough
   confirmed `kind` and `episodes` survived a fill that added eleven fields around them.
7. **Nothing in the enrichment path names an identifier kind or a provider.** `PROVIDER_ORDER` is
   gone; what remains in the shared layer is `PROVIDER_LABELS`, display copy for naming a provider in
   a reason a person reads. **Stated precisely rather than claimed broadly**: `grep isbn
   application/` still returns hits in `export.py` (the CSV column names of a books export),
   `add.py` (the near-match check) and `providers.py` (the cover chooser's Open Library path, kept
   deliberately by DEC-067 rows 6 and 7). Those are other features with their own decisions, not
   enrichment.
8. **No migration.** A job is a row with a JSON payload.

### Verification

- `make check` — green. One real catch: the backfill route's docstring is its OpenAPI description,
  so rewording it made the checked-in schema stale until `make openapi`.
- `make test` — **641 backend, 183 frontend** (from 616/183 at Sprint 038 closure).
- `npm run test:e2e` — **103 passed, 2 skipped**, unchanged.

### Walkthrough, against live providers on a disposable database

Added Chainsaw Man by MyAnimeList URL, stripped it to what a MyAnimeList import really leaves —
`{"kind": "TV", "episodes": 12}`, no year, no cover, one `mal` identifier — and triggered
`POST /api/enrichment/backfill`.

```text
payload : {"item_id": 1, "kind": "mal", "value": "44511"}
state   : succeeded    provider: anilist
filled  : year, creators, english_title, japanese_title, episode_minutes, season,
          source, genres, airing_status, synopsis, cover
```

`kind` and `episodes` were left alone. A second backfill queued **0** — the completeness rule worked,
which is the bug this sprint existed to avoid. A thin book beside it queued
`{"item_id": 2, "kind": "isbn", "value": "9788437604572"}`, succeeded against Open Library and filled
publisher, language, page_count, description, subjects, series and original_year: the book path is
untouched. A job hand-written in the **old** payload shape succeeded too, read as `isbn` from the
domain's own spec. Live `data/` untouched throughout.

### Observed and left alone

`JobRepository.complete` does not clear `error`/`error_code`, so a job that failed once and then
succeeded on retry shows `state: succeeded` beside stale failure text. Seen live. Pre-existing and
unrelated to this sprint; recorded in DEC-091 rather than fixed inside it.

### Impact on Sprints 040 and 041

Neither is invalidated. 040 is untouched — it is the entry model, not the item's. **041 inherits a
working fill path**, which is why this sprint precedes it: its connector produces rows carrying a
`mal` identifier and little else, and they now enrich without the connector fetching anything. One
thing for 041 to watch: the backfill queues one job per item, so the owner's 81-row export is 81 jobs
against a provider publishing `X-RateLimit-Limit: 30`. That is named in 041's risks already.
