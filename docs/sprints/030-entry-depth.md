# Sprint 030 — Entry depth: the decision

**Status:** in_progress
**Depends on:** 029
**Roadmap revision:** 12

## Objective

**Answer one question with evidence, and write the verdict down: does a child of an entry need
state of its own?** An entry is flat today — one status, one score, one `reread_count`, on one row.
Hierarchy is the only thing on the Sprint 028 assessment's list that could force a *redesign* rather
than an extension, because it reaches the entry model, the keyset cursor, triage selection, bulk
operations, every facet count, export, the import ledger and the library row.

**This sprint is Phase A only, and it is gated (DEC-071).** Its deliverable is a written verdict
with measurements behind it, not a feature. **"Flat, with a per-domain progress field" is a complete
and correct outcome**, and on current evidence the likeliest one. Phase B, if it happens at all, is
authorized separately by the owner at the gate.

It runs **before per-domain imports and before any third domain**, because a domain built against
the wrong answer is the expensive mistake and the answer costs half a sprint.

## Required context

1. `AGENTS.md`, `docs/agent/WORKFLOW.md`, `docs/agent/HANDOFF.md`, the last worklog entry
2. `docs/sprints/ROADMAP.md` — the Sprint 030 contract, which this file expands, and the
   *Future epics* section, since series and games are the domains that would use the answer
3. `docs/domain-expansion-assessment.md` — the assessment that named depth as the one redesign risk
4. `docs/decisions.md`: **DEC-071** (the owner's hypothesis, quoted below, and the gating),
   **DEC-057** (the tracklist as metadata rows — the precedent Phase A starts from), **DEC-052**
   (six seams, and the Strategy-B failure this sprint must not repeat), **DEC-058** (the vocabulary
   collision between *series*, *set* and *shelf*), **DEC-067** (what each coupling costs to remove,
   rows 3 and 6 in particular), **DEC-068** (the IGDB paper walk, and its warning about citing
   reasoning as measurement), **DEC-073** (what Sprint 029 built on `/`, including the two result
   surfaces and the focus rule any third surface inherits)
5. `docs/specs/product-spec.md` **section 10 item 4** (rereads stay lossy — no `readings` table) and
   **section 11 item 4** (series is free text, not modelled, and names its own breaking point);
   `docs/specs/technical-spec.md` **sections 5.1, 6.6, 7.1, 7.2**
6. The code the answer would touch, read before costing anything:
   - `backend/src/book_tracker/infrastructure/models.py` — `EntryRow` is flat; `ItemRow` carries
     `metadata`; `EntryShelfRow` and `EntryFormatRow` are the two join precedents
   - `backend/src/book_tracker/application/library.py` — `_filter_key` (line ~566) and the keyset
     cursor built on it (~672); `_entry_dict`; `_validated`
   - `backend/src/book_tracker/domain/spec.py` — `FieldSpec`, `ColumnSpec`, `FieldType`, and the
     `rows` validation at ~242
   - `backend/src/book_tracker/domains/album/__init__.py` — `ALBUM_FIELDS`, the `tracklist` field
     and the comment stating why a track is not an entity
   - `backend/src/book_tracker/application/imports.py` and `undo.py` — the ledger a child row would
     have to appear in, or not
   - `frontend/src/features/library/VirtualLibrary.tsx` — fixed-height rows and the bounded mounted
     DOM a child row would have to live inside

## Current implementation baseline

Observed 2026-08-17 at Sprint 029's close. **Re-derive at activation.**

- **An entry is one flat row.** `EntryRow` holds `status`, `score`, `notes`, `date_added`,
  `date_started`, `date_finished`, `reread_count`, `score_provisional`, `suggested_status`. There is
  no parent column, no position column, and no child table.
- **One level down already exists, as metadata.** `FieldSpec(type="rows")` with `ColumnSpec`
  columns; albums declare `tracklist` with `number`, `title` and `length_ms`. It cost one
  `inc=…+recordings` parameter on a request the adapter already made. **Nothing hangs off a track**:
  it is display, validated on write, rendered from the field spec.
- **Sets and series are unmodelled.** Series is free text in `metadata` (product spec §11 item 4).
  Shelves are the only user-created grouping, and DEC-058 already flagged that *series*, *set* and
  *shelf* are three words circling one region.
- **The cursor is bound to a filter identity.** `_filter_key` lists every filter; a filter it omits
  accepts a cursor cut under a different query and silently skips or repeats a page. Cursor version
  is 2. Any child that becomes a *row* in the list is a change to this.
- **Facets are whole-library counts**, `status_counts` plus `status_counts_by_type` plus
  `format_counts`, each clearing its own dimension. A child with a status of its own is a question
  about every one of them.
- **Triage selection is either explicit IDs or `all_matching` plus exclusions**, so bulk operations
  act on rows the client never loaded. A child row inherits that problem or is exempt from it.
- Migration head is `0014_status_is_the_domains`.

## Deliverables

**One document**, `docs/entry-depth-verdict.md`, canonical and linked from `docs/README.md`, plus the
decision entry that adopts it. It must answer four questions with evidence, in this order.

1. **What the providers actually return.** Measured against the live APIs the way DEC-052 was, not
   reasoned about, and recorded with the request made and the shape returned:
   - **TMDB** — seasons and episodes: what one request returns, whether episode-level data costs
     another request per season, and what identity an episode carries.
   - **IGDB** — DLC, editions, collections: whether these are children, siblings, or a graph.
   - **MusicBrainz** — recordings, already measured in Sprint 026, re-stated here as the control:
     one parameter, no extra request.

   **DEC-068's warning applies and is explicit:** anything reasoned from published documentation
   rather than observed must say so in the sentence that states it. A paper walk is a legitimate
   finding; a paper walk presented as measurement is not.

2. **Which of three shapes wins, costed as a table** — one row per shape, one column per thing it
   touches (entry model and migration, keyset cursor and `_filter_key`, triage selection, bulk
   operations, facet counts, export, import ledger and undo, the library row, the detail page):
   - **(a) a per-domain `progress` field on the existing flat entry** — declarative, no new table;
   - **(b) `rows` metadata plus a progress marker into it** — extends the tracklist precedent;
   - **(c) real child entities with their own status** — the redesign.

   The table is the deliverable, not the recommendation alone. A shape whose cost is not costed has
   not been considered.

3. **Whether "a set" is the same concept as depth or a different one.** The owner's Harry Potter set
   and the spec's Malazan series (§11 item 4) are the same feature asked for twice, four months
   apart, and DEC-058 flagged the vocabulary collision separately. **Phase A answers both together
   or leaves both open honestly** — it may not answer depth and quietly leave the set question
   floating. A set that groups items across a domain is not a parent entity, and if that is the
   finding, say it and say what it costs instead.

4. **The cheapest thing that satisfies a real user sentence.** *"I'm on season 3."* *"I've read the
   first four Malazan books."* The assessment's own warning binds here: designing depth from zero
   serial domains is the Strategy-B failure DEC-052 rejected on evidence, so the verdict must name
   the sentence it is buying and refuse the ones nobody has said.

**And a stated verdict**, in one paragraph, adopted as a decision entry: the shape, what is built
now (possibly nothing), what is deferred, and **what evidence would reopen it**.

## Acceptance criteria

1. The verdict document exists, is linked from `docs/README.md`, and answers all four questions.
2. **Every provider claim is labelled measured or reasoned**, and each measured one names the request
   and summarizes the response shape. A recorded fixture accompanies anything a later sprint would
   build against.
3. The three shapes are costed as a table over every listed dimension; no cell is blank.
4. The set/series question is answered or explicitly left open with its cost stated, and product spec
   §11 item 4 is updated to point at the verdict either way.
5. A decision entry adopts the verdict, names what would reopen it, and cross-references DEC-071.
6. **Nothing user-visible changes in Phase A.** No migration, no API change, no frontend change. If a
   defect is found while measuring, it is repaired as a prerequisite and recorded as a deviation —
   the Sprint 028 precedent.
7. The roadmap's Sprint 031 entry is impact-reviewed against the verdict: a child entity would change
   what an importer creates, and the import boundary is drawn one sprint later.

## Required tests (TDD)

Phase A builds no feature, so its tests are the recordings and the guards that keep the finding
honest:

- **Provider recordings** under `backend/tests/fixtures/providers/`, following the existing
  convention, for every live request the measurement makes. A measurement nobody can re-run is a
  claim, not evidence.
- **A test that the flat contract still holds** — `EntryRow` has no parent column and
  `test_domain_conformance.py` is unchanged — so a Phase A that accidentally starts building is
  visible in the diff.
- **If, and only if, Phase B is authorized at the gate:** its tests are written then, and the first
  of them is a keyset test proving the cursor still cannot skip or repeat a page with child rows in
  the result set.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
git diff --check
```

Full gates because a documentation-only sprint still may not leave the tree red. The e2e, build and
container gates are **NOT REQUIRED** for a Phase A that changes no application code, and must be run
and recorded if Phase B is authorized and lands.

Plus, for every provider claimed as measured: the actual request, run live, with the response shape
summarized in the verdict and the recording committed.

## Explicit non-scope

- **Building depth.** Phase B is a separate authorization. A Phase A that ships a schema change has
  failed, whatever the schema change is.
- **A third domain.** Series and games are the domains that would exercise this, and they are epics
  after the plan (DEC-058). Phase A measures their providers; it does not register them.
- **Per-domain imports.** Sprint 031, and deliberately after this one.
- **Reopening rereads.** Product spec §10 item 4 settled that: latest dates, one score,
  `reread_count`, no `readings` table. Depth is a different question and must not be used to reopen
  a settled one.

## Commit checkpoints

1. `docs(sprint-030): measure what the providers return` (the recordings and the measurement)
2. `docs(sprint-030): cost the three shapes` (the table)
3. `docs(sprint-030): the entry-depth verdict` (the document and its decision entry)
4. final `docs(sprint-030): close sprint and hand off`

## Risks and decisions to surface

- **The gate is the point.** Phase A ends with a verdict and a question to the owner, not with an
  implementation. Ask it as `WORKFLOW.md`'s clarification policy requires: one focused question, the
  options, the trade-offs, and a recommended default.
- **The owner's hypothesis is to be tested, not assumed** (DEC-071, quoted):

  > Most scenarios can be modelled by going **one level down only** — series into seasons, books into
  > chapters if any, albums into songs, at most. And the depth available is decided by **how the
  > provider stores it**: if a TV provider returns one entry per season, no finer grain exists to
  > model. In the other direction, items can be **grouped into sets** — the individual Harry Potter
  > books as one set — and a set may be useful for things other than depth.

  It is a hypothesis with a mechanism behind it, which makes it the thing most likely to be adopted
  without checking. Check it: if a provider returns a finer grain than the hypothesis predicts, that
  is the finding.
- **The tracklist precedent cuts both ways.** It proves children can be *represented* today, cheaply.
  It proves nothing about children that carry state, which is the actual question. Do not let "we
  already do this" answer "does a child need a status".
- **TMDB and IGDB both need credentials** to measure. If either is unobtainable, that arm is a paper
  walk and must be labelled one (DEC-068), and the verdict must say what it would take to close it.
