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
- **Your opinions, protected.** Score, status, dates, reread count, notes and shelves.
  Nothing you wrote is ever overwritten by a metadata refresh — that is an invariant
  the test suite enforces, not a promise.
- **Keyboard triage.** Work through a backlog with `j`/`k` to move, digits to score,
  letters to set status, `Enter` to accept.
- **Imports with a preview and an undo.** Goodreads CSV and a read-only Calibre
  library. You see exactly what will happen before it happens, and you can reverse it
  after.
- **Background enrichment.** A durable job queue fills in metadata and covers, retries
  failures, and survives a restart.
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
| `DATA_DIR` | `./data` | Database and covers |
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
a live WAL database), archives covers and import metadata, writes checksums, verifies
itself with `PRAGMA integrity_check`, and keeps the last `BACKUP_RETENTION` nights.

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

Issues and pull requests are welcome. Two things worth knowing first:

- Read [`AGENTS.md`](AGENTS.md) — it governs how changes are made here, and the test
  and verification gates are strict on purpose.
- Provider fixtures in `backend/tests/fixtures/providers/` are pinned recordings of
  real API responses. **Never re-record one to make a test pass** — that turns a
  regression test into a rubber stamp.

## License

[GNU AGPL v3](LICENSE). You may run, modify and share Akasha freely, including inside
an institution. If you redistribute it or run a modified version as a network service,
you must publish your source under the same licence.

For redistribution or hosting **without** those obligations, a separate commercial
licence is available — see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).
