# Handoff — Sprint 058 is ready: an image you pull, not a build you run

Sprint 057 (the names sprint, DEC-119) is complete and committed: the pydantic env prefix is
`AKASHA_` (clean break, no alias — an operator's old `BOOK_TRACKER_*` variables are ignored
from v1.5.1 on), the API title is "Akasha", and every version surface reads 1.5.1. v1.5.1 now
carries Sprints 056 + 057 and is **still untagged** — the owner's call. `docs/agent/state.json`
reads `ready` with `058` active. The `book_tracker` package itself is untouched; DEC-042 and
the internal-names invariant stand.

The next move is ordinary: execute Sprint 058 with the protocol in `/AGENTS.md`.

## What Sprint 058 must not get wrong

- **A compose service carrying both `image:` and `build:` builds silently when the image is
  absent** — the failure this sprint exists to remove. The local build moves to its own
  overlay; compose points at the registry.
- **Three steps need the owner's GitHub account** — workflow package-write permission,
  pushing the tag, package visibility. They are written out with expected results in the
  sprint file: surface them, don't improvise them.
- **The smoke test must keep building locally and keep its hermetic `COMPOSE_ENV_FILES`
  harness and random port.** Its env names are `AKASHA_*` now (Sprint 057); the scratchpad
  invocation in TESTING.md uses `AKASHA_INCLUDE_SCRATCHPAD`.
- **Sprint 058 declares the narrowed gate** (validator + `make check` + smoke) as long as its
  diff stays confined to deployment/CI configuration and docs — one file under `backend/src/`
  withdraws it.
- The walkthrough scripts print `AKASHA_DATA_DIR=...` now; old scratchpad flows with the old
  names are dead.

## Verified at Sprint 057's close

`make test` 1186 + 194 green; `make check` green; `make smoke-container` exit 0 on the frozen
tree (title/version asserted through the served OpenAPI); validator green. Fifteen local
commits on main, nothing tagged or pushed.

## After Sprint 058

059 (event loop, v1.5.4) is gated measurement-first; 060 (storage, v1.5.5) owes the full gate.

## Private data and operational constraints

Unchanged. `exports/` is the owner's private source archive, gitignored whole, read-only
walkthrough input. Secrets, databases, uploaded imports and covers are never committed. v1
has no auth and stays LAN-only; Calibre is opened read-only. No pushing unless asked.
