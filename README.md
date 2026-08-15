<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/brand/source/mark-on-dark.svg">
  <img src="docs/brand/source/mark-on-light.svg" alt="" width="88" height="88">
</picture>

# Akasha

**A self-hosted book tracker that records what you thought of a book.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-fbbf24?style=flat-square)](LICENSE)
[![Self-hosted](https://img.shields.io/badge/deploy-LAN%20only-a1a1aa?style=flat-square)](SECURITY.md)
[![Python 3.12](https://img.shields.io/badge/python-3.12-a1a1aa?style=flat-square)](backend/pyproject.toml)
[![React 18](https://img.shields.io/badge/react-18-a1a1aa?style=flat-square)](frontend/package.json)

</div>

<br>

![The Akasha library](docs/brand/screenshots/library.png)

---

## What it is

Akasha is a personal library that runs on a small server in your house. One user,
no accounts, no social layer, no sharing. You add a book, give it a score out of
ten, write a note, put it on a shelf.

It exists because reading trackers optimise for other people seeing your shelves.
This one optimises for you remembering, three years later, whether a book was any
good and why. No social media features, fully offline.

> [!WARNING]
> **v1 has no authentication of any kind.** Anyone who can reach the port can read
> and change everything. Run it on a trusted LAN, never on the public internet.
> See [SECURITY.md](SECURITY.md) for the full threat model.

## What it does

- **A library that stays fast.** Ten thousand entries scroll smoothly — a virtualized
  grid and a compact table, keyset pagination, six sorts. Search and sorting are
  accent-insensitive, so `avila` finds `Ávila`.
- **Adding books.** Search Open Library and Google Books, or type a book in by hand.
  Covers are fetched once and stored locally; providers are never called while
  rendering a page you already have.
- **Your opinions, protected.** Score, status, notes, shelves, and how you own your copy
  — plus dates and a reread count for the kinds of thing that have them. Nothing you
  wrote is ever overwritten by a metadata refresh — that is an invariant the test suite
  enforces, not a promise.
- **Keyboard triage.** Work through a backlog with `j`/`k` to move, digits to score,
  letters to set status, `Enter` to accept.
- **Imports with a preview and an undo.** Goodreads CSV and a read-only Calibre
  library. You see exactly what will happen before it happens, and you can reverse it
  after.
- **Background enrichment.** A durable job queue fills in metadata and covers, retries
  failures, and survives a restart.
- **Files on a book.** Attach an epub or a PDF to an edition and download it again
  later. Stored by content, so the same file attached twice takes the space of one,
  and seven nights of backups cost about one copy rather than seven. Files are served
  as downloads and never rendered, and nothing here parses them — this is a shelf, not
  a reader.
- **Your library, exportable.** One request dumps everything as JSON, or as a
  Goodreads-shaped CSV that opens in a spreadsheet. The dump keeps what you typed and
  leaves out what the application derived, so nothing you corrected by hand is lost and
  nothing rebuilt from a cache pretends to be authoritative.
- **Accessible by default.** Twelve automated axe checks gate every change; both list
  surfaces are proper ARIA feeds.

<details>
<summary><b>A book's detail page</b></summary>

![A book detail page](docs/brand/screenshots/detail.png)

</details>

## Quick start

You need Docker with the Compose plugin. Nothing else.

```bash
git clone https://github.com/mauroibz/akasha.git
cd akasha

cp .env.example .env
$EDITOR .env                              # set USER_AGENT_CONTACT to a real address

mkdir -p data backups calibre
sudo chown -R 10001:10001 data backups    # the container runs as uid 10001

docker compose up -d
```

Open `http://localhost:8000`.

> [!IMPORTANT]
> Don't skip the `chown`. The container runs as a non-root user and cannot write into
> directories owned by anyone else. Missing it produces `attempt to write a readonly
> database`, which looks like corruption and is only permissions.

`USER_AGENT_CONTACT` is required — Open Library asks callers to identify themselves,
and startup refuses without it.

### Configuration

Everything is environment variables, all documented in [`.env.example`](.env.example).

| Variable | Default | What it does |
|---|---|---|
| `USER_AGENT_CONTACT` | *required* | Contact address sent to metadata providers |
| `GOOGLE_BOOKS_API_KEY` | *empty* | Optional. Without it, search uses Open Library alone and Spanish-language coverage is poor |
| `DATA_DIR` | `./data` | Database, covers and attached files |
| `BACKUP_DIR` | `./backups` | Backups, deliberately outside the data volume |
| `CALIBRE_DIR` | `./calibre` | Your Calibre library, mounted read-only |
| `AKASHA_PORT` | `8000` | Published port |
| `AKASHA_BIND` | `0.0.0.0` | Set to `127.0.0.1` to keep it off the network |
| `TZ` | `UTC` | Timezone |
| `LOG_LEVEL` | `INFO` | Log verbosity |

Check which providers are live:

```bash
curl -s localhost:8000/api/health/providers
```

### Backups

There is a real backup, and the restore has been tested rather than described.

```bash
# One backup now
./scripts/backup.sh

# Nightly, from the host's crontab — not from inside the container
15 3 * * *  cd /srv/akasha && ./scripts/backup.sh >> /var/log/akasha-backup.log 2>&1
```

Each run copies the database through SQLite's online backup API (never a file copy of
a live WAL database), archives covers and import metadata, hardlinks attached files so
each night does not pay for a fresh copy of them, writes checksums, verifies itself
with `PRAGMA integrity_check`, and keeps the last `BACKUP_RETENTION` nights.

Upgrades take their own backup first: if a migration has pending work against an
existing database, startup copies it before touching anything and refuses to migrate
if it cannot.

Restore, rollback and reverse-proxy guidance are in
**[the operator runbook](docs/operations/runbook.md)**.

## Development

You need Node 22, npm, and [`uv`](https://docs.astral.sh/uv/). `uv` installs Python
3.12 itself.

```bash
make bootstrap
cp .env.example .env

make dev-backend    # terminal 1 — API at http://localhost:8000
make dev-frontend   # terminal 2 — UI at http://localhost:5173
```

| Command | What it does |
|---|---|
| `make check` | Format check, lint, types, project state, OpenAPI drift |
| `make test` | Backend and frontend unit tests |
| `make format` | Apply formatting |
| `make build` | Python wheel and production SPA |
| `make migrate` | Upgrade the configured database |
| `make smoke-container` | Full container proof: healthcheck, non-root, persistence across recreation, every asset chunk, read-only Calibre, backup and restore, graceful SIGTERM |
| `npm run test:e2e` | Playwright, in `frontend/` — dev server *and* a real production build |

### Stack

FastAPI, SQLAlchemy, Alembic and SQLite on the backend. React 18, Vite, TypeScript,
Tailwind, shadcn/ui and TanStack Query on the frontend. One container, one process,
one SQLite file.

### Domains

A **domain** is a kind of thing the library holds. Books ship; albums are built and
waiting to be released. The point of the structure is that a third one — games, films,
board games — is somebody else's afternoon rather than a fork.

```text
backend/src/book_tracker/
├── api/             # thin FastAPI routers and error mapping
├── application/     # use cases and transaction boundaries
├── domain/          # spec.py: what a domain IS · registry.py: which ones EXIST
├── domains/         # one package per domain
│   ├── book/        #   declaration · Open Library + Google Books · Goodreads + Calibre
│   └── album/       #   declaration · MusicBrainz + Cover Art Archive
├── infrastructure/  # SQLAlchemy, provider HTTP, covers, jobs
└── main.py
```

A domain declares its metadata fields, its status vocabulary, its formats, its identity
rule and what it recognises in the add box. **That one declaration is served over the API
and every screen renders from it** — tabs, chips, the metadata dialog, triage hotkeys, the
detail page. There is no `if item_type == "book"` anywhere above the registry, and a
conformance suite parametrised over the registry holds every domain to the same contract
*by existing*.

Adding one costs your own package, one registry entry, provider wiring and three enum
lines. **No database migration, and no edit to another domain's files.**

→ **[How to add a domain](docs/guides/adding-a-domain.md)** · the binding contract is
[technical spec §6.6](docs/specs/technical-spec.md)

### The documentation

[`docs/README.md`](docs/README.md) is the map. Every document there says whether it is
**canonical**, **historical** or a **proposal**, so a dated file is never mistaken for
instructions.

Architecture and contracts live in [the technical spec](docs/specs/technical-spec.md);
product behaviour is canonical in [the product spec](docs/specs/product-spec.md).
Every material decision, with its reasoning, is in [`docs/decisions.md`](docs/decisions.md).

### A note on how this was built

Akasha was built by an AI coding agent working sprint by sprint under a protocol in
[`AGENTS.md`](AGENTS.md), with a human owner making the product decisions. The sprint
files, the decision log and the worklog in `docs/` are the real record of that,
including the parts that went wrong. If you are curious about what that process
actually produces, that directory is more honest than most write-ups.

## Design

The visual identity — palette, typography, the mark and how it is constructed — is in
[`docs/brand/`](docs/brand/). The short version: zinc-950 ground, a single amber
accent, Inter, and a mark drawn on Lucide's 24px grid so it sits beside the interface
icons as a sibling.

## Contributing

Issues and pull requests are welcome. **[`CONTRIBUTING.md`](CONTRIBUTING.md)** has the
setup, the gates and the rules that are not style preferences. Three things worth knowing
before you open it:

- **Adding a domain has its own guide** —
  [`docs/guides/adding-a-domain.md`](docs/guides/adding-a-domain.md). You should never
  have to reverse-engineer how albums were built.
- [`AGENTS.md`](AGENTS.md) governs how changes are made here, and the verification gates
  are strict on purpose.
- Provider fixtures in `backend/tests/fixtures/providers/` are pinned recordings of
  real API responses. **Never re-record one to make a test pass** — that turns a
  regression test into a rubber stamp.

## License

[GNU AGPL v3](LICENSE). You may run, modify and share Akasha freely, including inside
an institution. If you redistribute it or run a modified version as a network service,
you must publish your source under the same licence.

For redistribution or hosting **without** those obligations, a separate commercial
licence is available — see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).
