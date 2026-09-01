# Contributing

Issues and pull requests are welcome. This file is the short version; the map of everything is
[`docs/README.md`](docs/README.md).

> **Adding a new domain** — games, films, board games, anything that is not books or albums — has its
> own guide: **[`docs/guides/adding-a-domain.md`](docs/guides/adding-a-domain.md)**. Start there
> rather than here. It exists so you never have to reverse-engineer how albums were built.

## Set up

You need Node 22, npm, and [`uv`](https://docs.astral.sh/uv/). `uv` installs Python 3.12 itself.

```bash
make bootstrap
cp .env.example .env      # set USER_AGENT_CONTACT to a real address

make dev-backend          # terminal 1 — API at http://localhost:8000
make dev-frontend         # terminal 2 — UI at http://localhost:5173
```

## The gates

Run these before opening a pull request. They are strict on purpose — this project once closed
thirteen sprints green on a product that did not work, and every gate below exists because of a
specific failure that got past the ones before it (DEC-024, DEC-025 in `docs/decisions.md`).

```bash
make check                       # format, lint, types, project state, OpenAPI drift
make test                        # 469 backend, 130 frontend
cd frontend && npm run test:e2e  # 86 browser tests, dev server and a real production build
cd .. && make smoke-container    # healthcheck, non-root, persistence, restore, graceful SIGTERM
```

`make smoke-container` is not optional theatre: it has caught failures — a broken module path inside
the image, an asset chunk that was built but never served — that no unit test, type check or browser
test could see.

## How the code is organised

```text
backend/src/book_tracker/
├── api/             # thin FastAPI routers and error mapping
├── application/     # use cases and transaction boundaries
├── domain/          # spec.py: what a domain is · registry.py: which ones exist
├── domains/         # one package per domain — book/, album/
├── infrastructure/  # SQLAlchemy, provider HTTP, covers, jobs
└── main.py          # app factory, lifespan, static SPA mount
```

The rule that matters: **the shared layers never branch on which domain they are holding.** A layer
that needs domain-specific behaviour asks the registry for a declaration. `if item_type == "book"` is
the thing to catch in review.

## Rules that are not style preferences

- **Never re-record a provider fixture to make a test pass.** `backend/tests/fixtures/providers/`
  holds pinned real API responses. Re-recording one turns a regression test into a rubber stamp
  (DEC-025).
- **A mock substituted for the unit under test does not prove that unit.** Mock the transport;
  replay a recorded response.
- **Never weaken, skip or delete a test to get green**, and never fabricate command output.
- **Imported user data is never overwritten by synchronisation.** Explicit refresh is the only
  overwrite path, and it is confirmed.
- **Migrations are the only schema-change path**, and a migration must never import the live
  registry — it is history, and history does not change when a domain is added.
- **Internal names are permanent.** The package stays `book_tracker` and the core entities stay
  `items`/`entries` regardless of product branding. User-facing copy is the only thing that follows
  the brand.
- **Passing tests are not evidence that a flow works.** Run the application against realistic data
  and use the thing you changed.

## Commit messages

One tag, one title, a blank line, then the body:

```text
[TAG] Title in the imperative, no trailing full stop

Why this changed, and anything the diff cannot say for itself. Wrap at 100
columns. Reference decisions as DEC-NNN and sprints as "Sprint NNN" so both
stay greppable.
```

The tag is mandatory, uppercase, and one of:

| Tag | For |
|---|---|
| `[ADD]` | A new capability that did not exist before |
| `[MOD]` | A change to behaviour that already existed |
| `[FIX]` | A defect repair. Say what was broken, not just what you changed |
| `[REF]` | Restructuring with no behaviour change. If behaviour changed, it is not a `[REF]` |
| `[DOCS]` | Documentation, specs, sprint files, decisions, the roadmap |
| `[TEST]` | Tests only. A test added alongside a change ships in that change's commit instead |
| `[BUILD]` | Dependencies, the container, CI, Makefile targets, generated contracts |
| `[CHORE]` | Repository housekeeping with no product effect — ignore rules, file moves, cleanup |

Nothing else. A change that seems to need a new tag is usually two commits.

Rules that follow from the table:

- **One tag per commit**, so a commit that would need two is doing two things. Split it.
- **`[REF]` means the tests do not change.** A refactor whose tests had to be edited changed
  behaviour, and belongs under `[MOD]` or `[FIX]` where a reviewer will look for it.
- **The title says what, the body says why.** The diff already says how, and a body that narrates the
  diff is wasted.
- **No attribution trailers.** No `Co-Authored-By`, no generated-with notice, no tool signature —
  this applies to human and agent commits alike.

Examples:

```text
[ADD] Read series from Wikidata on a five-class instance-of filter
[FIX] Stop the backfill re-queueing deliberately coverless movies
[REF] Promote the poster URL builder to shared infrastructure
[DOCS] Close sprint 049 and hand off
```

**Commits made before 2026-08-31 use Conventional Commits** (`feat(sprint-048): …`). They are history
and are not rewritten; the table above applies to everything after it.

## Pull requests

If your change alters a contract — an API shape, a schema, a product behaviour — update the spec it
contradicts in the same pull request, and add an entry to [`docs/decisions.md`](docs/decisions.md)
explaining the choice. Decisions are append-only: supersede an old entry, never edit it.

## If you are an AI agent

Read [`AGENTS.md`](AGENTS.md) first. It is the binding protocol for sessions that change this
repository — one sprint at a time, test-driven, with a walkthrough gate and an atomic handoff — and
it overrides this file wherever the two differ.
