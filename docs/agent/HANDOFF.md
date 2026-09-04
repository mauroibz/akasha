# Handoff — Sprint 068 closed; Sprint 069 is next

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "069"`,
`active_sprint_status: "ready"`. Plan revision 37; `FINAL_SPRINT` in
`scripts/validate_project.py` is 70. `docs/sprints/069-a-door-out-of-the-app.md`'s own
`Status` is `ready`. Sprint 070 stays `planned` behind it.

## What just happened

Two proposals (`docs/export-proposal.md`, `docs/ui-cohesion-proposal.md`) and Sprints
068–072 had been drafted by an earlier session and left uncommitted. Committed as-is
after checking them against `scripts/validate_project.py`. The owner then accepted the
export line as **DEC-135**, scheduled as Sprints 068–070; the UI-cohesion line
(071–072) stays proposed and unaccepted.

**[Sprint 068 — Export the way we import](../sprints/068-export-the-way-we-import.md)**
closed. Export now has the shape import already has: `domain/exports.py` declares the
`ExportView` protocol and `ExportRow` (the neutral row a view is handed), plus a
generic `table` CSV view built per domain from that domain's own `Domain` object —
every registered domain, not only book, can now leave in a format another application
opens. `GoodreadsExportView`/`EXPORT` moved into `domains/book/goodreads.py`, beside
the reader of the same file, byte-identical to the pre-sprint `export_csv`.
`application/export.py`'s shared walk (`iter_export_rows`/`stream_export_view`) removed
the last item-type branch in a shared layer. New: `GET /api/exports` (the
declarations, entry counts included) and `GET /api/export/{view}?type=<domain>`.
`?format=csv` is now an alias of the `goodreads` view, proven byte-identical rather
than merely left unchanged.

**Read the sprint's own Outcome before touching export again** — two implementation
decisions it had to resolve, not corrections of a wrong reading like DEC-134 was, but
worth knowing before extending the surface in 069/070:

1. **`table` is registered as one instance per domain**, not one shared instance across
   all five (`REGISTERED_EXPORTS` in `registry.py` has six entries: `goodreads` plus
   five `table`s). `GET /api/exports` therefore lists six rows, not two — dispatch on
   `GET /api/export/{view}?type=<domain>` is what disambiguates same-named views across
   domains, and `name` is unique **within** one domain's `EXPORTS_BY_DOMAIN` tuple, not
   across the whole registry.
2. **`type` on `GET /api/export/{view}` is a required query parameter.**

## Current numbers

- Backend **1,352** tests (was 1,333). Frontend unchanged at **243** — this sprint
  touched no `.tsx` file, confirmed against the diff. `make check` green.
  `docs/decisions.md` ends at **DEC-135**.
- No new benchmark numbers — Sprint 068 touched no query the benchmark suite measures.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — still
  outstanding, unrelated to this sprint, needs the owner's own container. Neither 066,
  067 nor 068's own walkthroughs discharge it.
- **The 390px domain-radiogroup overflow** (DEC-134). Still real, still unfixed, still
  not urgent.
- Cutting the `v1.6.0` and/or `v1.7.0` tags.
- **DEC-133's open product question** (album ranking ordering `Label` ahead of
  `Artists`) — still the owner's call.
- **Series' export target is still undecided** — proposal §2.3 flags it as the one open
  product question in the export line, and Sprint 070 is where it gets measured or
  recorded as "the `table` floor is the answer for series," per DEC-088/DEC-127's
  precedent of measuring rather than guessing.

## Branch and authorization

On **`main`**, committed directly (matching how this session's own docs commits and
recent Sprint 066/067 work landed) — **nothing pushed**. Three commits for Sprint 068:
`bf86712`, `7c93377`, `c358e66`, each independently green. Authorization does not carry
forward: this session was asked to work the active sprint and did exactly that. It does
not extend to pushing, merging, or any remote action.

## What export is, in one paragraph

`GET /api/export` is unchanged: the lossless, entity-shaped JSON, every domain, streamed
in keyset batches. Beside it, a registered `ExportView` (`domain/exports.py`) is the
export analogue of an `Importer`: it declares `name`/`label`/`item_types`/`media_type`/
`lossless`/`filename`/`guide`/`help_url`/`carries` and a `write(rows)` that receives one
`ExportRow` at a time from the shared walk in `application/export.py`, holding no
session and writing no SQL. `domain/registry.py`'s `REGISTERED_EXPORTS`/
`EXPORTS_BY_DOMAIN`/`find_export_view` are derived from what views declare, the same
shape `IMPORTERS_BY_DOMAIN` already has. `GET /api/exports` renders every declaration
with a live entry count; `GET /api/export/{view}?type=<domain>` streams one, 404 through
the standard envelope for an unknown view or a domain a view does not carry.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- The domain radiogroup on `/insights` overflows at 390px with five real domains
  (DEC-134).

## Version

Unchanged at `1.7.0`. Sprint 068 added OpenAPI surface (`GET /api/exports`,
`GET /api/export/{view}`) but did not bump the version — that decision belongs to
whoever closes the export line (069, or 070 if 070 ships), the way 066/067 bumped
together rather than sprint-by-sprint.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. **The owner's own instance runs
on this host at `127.0.0.1:8000`** — this sprint's walkthrough used a throwaway backend
on an ephemeral port against a fresh `/tmp` data directory precisely to avoid it, and
removed both at close. Do not point a walkthrough at `:8000` without asking.
