# Handoff — Sprint 057 is ready: the names the product actually uses

Plan revision **31** (DEC-119): the owner directed the two cheap layers of the naming
assessment — the pydantic `env_prefix` becomes `AKASHA_` (**clean break, no alias**) and the
FastAPI title drops "Book Tracker". Both ship inside the still-untagged **v1.5.1**. The
deployment line renumbered: old 057/058/059 are now **058/059/060** (v1.5.3/v1.5.4/v1.5.5);
`FINAL_SPRINT` is 60. Sprint 056's closure and its evidence are untouched history.

The next move is ordinary: execute Sprint 057 with the protocol in `/AGENTS.md`.

## What Sprint 057 must not get wrong

- **The `book_tracker` package is not renamed.** DEC-042's rejection and the AGENTS.md
  internal-names invariant stand. Only the env prefix and the API title change.
- **No alias.** A `BOOK_TRACKER_*` variable in an operator's `.env` is silently ignored from
  v1.5.1 on. The release notes say so with the rename table; do not add a compat layer.
- **`AKASHA_BIND`/`AKASHA_PORT` fall inside the pydantic prefix after the flip.** They must
  stay absorbed by `extra="ignore"` — prove it in a unit test, don't assume it.
- **Full gate owed.** The diff touches `backend/src/` and `openapi.json` (a generated
  contract): validator, `make check`, `make test`, `make smoke-container`. The version surfaces
  (pyproject, package.json, main.py, openapi.json) move to **1.5.1** — forced by the title
  change, and it corrects the drift 056's release notes acknowledged.
- Historical records (closed sprints, worklog, DEC-001–118) keep `BOOK_TRACKER_` — do not
  edit them. Verify the split with grep, not by eye.
- Sprint 056's compose env boundary (explicit list, never `env_file:`) is renamed, not widened.

## Verified at Sprint 056's close (previous sprint)

`make smoke-container` exit 0 on the frozen tree; `make check` green; narrowed gate held
(no application code). Eleven local commits on main, nothing tagged or pushed. v1.5.1 is
assembled but untagged: the tag decision is the owner's, after this sprint's changes fold in.

## After Sprint 057

058 (published image, v1.5.3) carries three owner-only GitHub steps; 059 (event loop,
v1.5.4) is gated measurement-first; 060 (storage, v1.5.5) owes the full gate.

## Private data and operational constraints

Unchanged. `exports/` is the owner's private source archive, gitignored whole, read-only
walkthrough input. Secrets, databases, uploaded imports and covers are never committed. v1
has no auth and stays LAN-only; Calibre is opened read-only. No pushing unless asked.
