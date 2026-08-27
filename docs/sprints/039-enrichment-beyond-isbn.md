# Sprint 039 — Enrichment beyond the ISBN

**Status:** ready
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

_Not started._
