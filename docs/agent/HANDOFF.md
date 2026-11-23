# Handoff

## Where the project stands

**2026-11-23, 3.1.0 released and running on the board** (#42, tag `v3.1.0`; no migration). The owner reviewed 3.0.0 on the board and
asked for six changes (DEC-192), built as Sprints 137 (finishing records when; *Mark as read*;
the pile in rounds by creator; `/pile`, the pile as a list) and 138 (Home's module families: a
year per library, `year:<item type>`, and a module per shelf, `shelf:<id>`). No migration and
no new setting. Release notes: `docs/operations/release-notes-v3.1.md`. The project state is
`complete`; the next work is the owner's.

**Environment warning:** a local Akasha 1.5.7 container (`akasha-akasha-1`) listens on
127.0.0.1:8000, where the Playwright dev server proxies unstubbed `/api` calls; with it up,
16–17 accessibility tests fail, on `main` too. Run Playwright with
`AKASHA_E2E_BACKEND=http://127.0.0.1:9`. The repository has an old stash (`stash@{0}`,
made on `adc4de4`, the deployment line's planning); leave it.

Left from the review: Open Library bookkeeping subjects as reasons; Home's *More like this*
posters large at 1440; Model and From your library segments shown when off; a TMDB pick without
a poster; *Lately* shows imported titles as stored; a library's year without a goal and few
finishes is mostly empty space.

## Earlier state (release 3.0.0)

**2026-11-23, 3.0.0 released and running on the board.** DEC-183's line (Sprints 130–136) is
complete and merged (#41, `3ba6d31`), tagged `v3.0.0`, and the image is published. Release notes:
`docs/operations/release-notes-v3.0.md`. What the line adds over 2.9.0: Home at `/` (the
library moved to `/library`), the ranked pile, *More like this* with three sources (TMDB, a
hosted model, *From your library*), Home's *More like this*, Settings → Suggestions.
Migrations **0036–0038** are new since 2.9.0. The board upgraded 2.9.0 → 3.0.0 with
`pre-migration-20261123T071948Z`; revision 0038, counts unchanged, integrity clean. CI needed one
change: Home's 150 ms timing budget is doubled on the shared runner, which measured 228 ms
(`6786fe2`).

**Release gates, run on this tree:** `make check`; `make test` (backend 2195, Vitest 625);
full Playwright 239 passed, 2 skipped by design; `make audit` clean; `make build`;
`make smoke-container`. A copy of the board's library (2.9.0, revision 0035) upgraded under the
read-only compose with auth on: backup written, 0036–0038 applied, integrity and foreign keys
clean, counts unchanged (359 items, 345 entries, 22 attachments, 11 shelves, 2 users), restart
ran no migration. Two fixes came out of it: Up next no longer names "General" as a subject
(`a6f57e4`), and the add-dialog axe check waits for the fade (`c7a809f`).

**The owner's next steps:** the owner's feedback on 3.0.0 becomes minor releases. The live checks no key
allowed here: `ANTHROPIC_API_KEY=… uv run python ../scripts/record_model_fixtures.py` and
`GEMINI_API_KEY=… uv run python ../scripts/record_embedding_fixtures.py` from `backend/`,
rerun `tests/test_model_recommendations.py`, `tests/test_embeddings.py` and
`tests/test_library_source.py` (a real reply may name or order things differently: update the
expectations in their own commit), one *Model* round and one *From your library* in the app,
and confirm the default Gemini and OpenAI model ids.

**Embeddings settings (Sprint 136, DEC-191):** `AKASHA_RECS_EMBEDDINGS_PROVIDER` (`gemini`
default or `openai`), `_MODEL`, `_KEY` or `GEMINI_API_KEY`/`OPENAI_API_KEY`, `_URL`; 1,000
requests a day unless `AKASHA_PROVIDER_DAILY_LIMITS` says `{"embeddings": N}` — that value
replaces the whole default, so keep `"googlebooks": 900` in it. A Claude key alone does not
turn embeddings on. The first start with a key embeds the whole library over a few minutes.

**Judgement calls from the real-data walkthrough (not fixed):** Up next is five Stephen King
books (no variety rule); Open Library bookkeeping subjects ("Large type books", "Reading
Level-Grade 11") can still be named as reasons; Home's *More like this* posters are very large
at 1440; the year module is mostly empty when few finishes carry dates; the sheet shows Model
and From your library segments when neither is configured; a found TMDB pick can lack a poster.

Seen in Sprint 136's walkthrough and left (pre-existing): an add from Open Library can store a
foreign edition's title ("Bai nian gu du" for *Cien años de soledad*, `original_year` 1999) or
no creators (*The Hobbit*); `/api/auth/me` 404s with auth off (console noise); Settings lists
Model before TMDB; "Found in your providers" on every found row; MusicBrainz 503s under a burst.

## Earlier state (release 2.9.0)

**2026-11-22:** Sprints 128–129 are merged to `main` (#38, #40) and **released as v2.9.0**
(tag `v2.9.0`, notes in `docs/operations/release-notes-v2.9.md`). Migrations 0034–0035 are
new. The project state is `complete`; no sprint is planned.

Upgrade notes for the owner: new passwords need 12 characters; the first-run setup asks for
the code in `docker compose logs akasha`; compose runs the container read-only with no
capabilities and resource limits (`AKASHA_MEM_LIMIT`, `AKASHA_CPUS`, `AKASHA_PIDS_LIMIT`).
Take the 2.9.0 `compose.yaml` and image together.

Waiting on the owner (Sprint 128): a Cloudflare account, tunnel token, Access application and
policy on the real server; running the egress firewall script there; an off-host backup copy.

Known from the 2.9.0 review, not fixed: resuming an import install whose item was deleted
meanwhile writes an orphan cover and keeps the batch's staging, retried hourly
(`install_staged` catches only `CoverError`, `set_cover_path` raises `LookupError`); and
`resume_interrupted_installs` has no per-batch guard. Batches committed by 2.8.0 inside their
24 h undo window look interrupted on the first 2.9.0 start, which re-fills a cover removed
after that import.

## Earlier state (2026-10-24)

**2026-10-24:** Sprints 109–127 are completed and **released as v2.8.0** (tag
`v2.8.0`, GitHub release from `docs/operations/release-notes-v2.8.md`). The project state is `complete`; no sprint is planned. 109–121 are the house and the
history (DEC-176, DEC-178); 122–127 are the owner's first look at them in the running app
(DEC-179, mockups *A second look*, approved as recommended). Migrations 0028–0033 are new.

What 122–127 changed, by screen:

- **Shelves:** open loans stand as the first ledge, *Lent out*; `/lent` returns to Shelves.
- **Detail page:** only rows that hold a value; one question at a time about the most useful
  gap (*I don't remember* kept in `entries.unknown_fields`, migration 0033); *Lend…* among
  the actions; *Finished* while under way, opening one sheet (when, score or "Still an 8?",
  format). Starting something dates an empty start.
- **Library:** each *Now* card has *Finished*.
- **Insights:** *Play with your library* at the top: *Five minutes* (`/play/five`), the best
  of a score, an old score, the pile, *Fill in the gaps* (`/play/gaps`, `GET /api/gaps`).
- **`/deck`** is *Tidy up*: the inbox, covers, duplicates (Settings and the command bar).
- **Diary:** the goal leads; without one an invitation with three paces, with one a slot per
  thing aimed at filled by the year's covers (a bar above 24).

Waiting on the owner:

- A look at 122–127, especially Play's weight on a phone's first screen of Insights.
- DEC-178's reading of the 02/03 mockup note (Sprint 121 is one commit, `8b61b07`).
- Upgrading the board to 2.8.0 (`docs/operations/runbook.md`): six migrations (0028–0033)
  run there, with the usual backup first.
- Still open from before: trust-stated-status on import (DEC-165 point 3); real Hardcover,
  Simkl and StoryGraph exports (Sprint 099). Homelab sync is GitHub issue #31; the
  commonplace book is a v3 candidate.

## Verified

- Per sprint, as DEC-167 asks: the tests for the changed code, `make check`, the Playwright
  specs for each changed screen, and a walkthrough on a fresh `scripts/walkthrough.py`
  backend (recorded per sprint in the worklog and each Outcome).
- Once for 122–127, on 2026-10-24: `make test` — backend 1792 passed, Vitest 549 passed;
  full Playwright — 214 passed, 2 skipped (live metadata, by design); `make check`.
- Release gate for 2.8.0, 2026-10-24: the full suites above on the release tree's code, then
  `make check` and `make smoke-container` after the version surfaces moved.

## Known and left

- On a phone, Play's games fill most of Insights' first screen.
- At 390px a long place truncates beside its *Change* button on the detail page.
- After the last light of a reread the status stays *Reading* (DEC-175); *Finished* is the
  way to finish it now.
- The rank page's back link says *Library* even when opened from Insights.
- *Find a cover*: an installed cover is not taken back by *Undo* (no remove-cover endpoint).
- EPUBs without an ISBN are not enriched; only EPUB is read.
- `test_events.py::test_the_stream_carries_each_change_to_a_job` and `rescore.spec.ts` are
  timing-sensitive under full parallel load.

## Next session

No sprint is planned; 3.0.0 is prepared and waits on the owner's push, merge and tag. Run
checks under `set -o pipefail`. Walkthroughs: `uv run python ../scripts/walkthrough.py
[--replay module]` from `backend/`, vite on 5180 with `AKASHA_E2E_BACKEND` (it listens on
`localhost`); export only `TMDB_READ_TOKEN` from `.env` (it also sets `AKASHA_AUTH=on`); start a
fresh backend after backend changes; stop servers by port (`fuser -k`). Playwright ignores any
path containing `scratchpad`. `test_prune_items.py`'s unremovable-cover test fails only as root.
The board runs 2.9.0 until the owner upgrades it.
