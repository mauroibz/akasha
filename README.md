# Akasha Book Tracker

Akasha is a self-hosted, keyboard-first personal book rating and triage app. It tracks opinions, not ebook files, and v1 has no authentication: deploy it only on a trusted LAN.

The current application supports cached manual/provider adds plus preview-first Goodreads CSV and
read-only Calibre imports. Goodreads imports land in the inbox with status suggestions and
provisional scores. Calibre imports use native 1–10 ratings, tags as shelves, locally copied covers,
and fill-empty re-sync. Neither source overwrites existing library opinions or populated metadata.

## Local setup

Requirements: Docker, Node 22, npm, and `uv`. `uv` installs the required Python 3.12 runtime automatically.

```bash
make bootstrap
cp .env.example .env
make dev-backend   # terminal 1, API at http://localhost:8000
make dev-frontend  # terminal 2, UI at http://localhost:5173
```

The first backend startup creates the local `data/` directories and applies the foundation Alembic migration. Sprint 001 intentionally seeds no book-domain rows.

### Metadata providers

Put a Google Books API key in `.env` as `GOOGLE_BOOKS_API_KEY`. Without it the backend still runs, but search and enrichment use Open Library alone, which covers Spanish-language editions poorly. Startup logs a warning in that case, and `GET /api/health/providers` reports which providers are configured:

```bash
curl -s localhost:8000/api/health/providers   # {"providers":[…],"degraded":false}
```

Metadata and covers are filled in the background after an import. If a library was imported while enrichment was failing, re-queue it — this only fills fields that are still empty and never overwrites an edit:

```bash
curl -s -X POST localhost:8000/api/enrichment/backfill   # {"queued": 12}
```

Progress and any failure reason for a job are at `GET /api/import/jobs/{id}`.

## Quality and build commands

```bash
make format       # apply backend/frontend formatting
make check        # format check, lint, types, project state, OpenAPI drift
make test         # backend and frontend behavior tests
make build        # Python wheel and production SPA
make openapi      # regenerate frontend/openapi.json
make migrate      # explicitly upgrade the configured database
cd frontend && npm run test:e2e  # Chromium library, add, detail, import, keyboard, and mobile checks
```

## Container

Set a real contact address for future provider requests, then build and start the single production container:

```bash
cp .env.example .env
mkdir -p data backups calibre
sudo chown -R 10001:10001 data backups   # the container runs as uid 10001
docker compose up -d --build
```

Compose persists `${DATA_DIR:-./data}` at `/data` and writes backups to
`${BACKUP_DIR:-./backups}` at `/backups`, deliberately outside the data volume. The image serves
the SPA and API on port 8000, runs as a non-root user, contains no Node runtime, and uses
`/api/health/ready` for health checks. Calibre libraries are addressed by a relative folder
beneath the read-only `/calibre` mount.

Migrations run at startup and take an online backup first whenever an existing database has
pending revisions. Nightly backups are a host cron entry calling `scripts/backup.sh`; restore and
rollback are in [the operator runbook](docs/operations/runbook.md).

Run the repeatable image proof with `make smoke-container`. It builds the image, waits on the
container's own healthcheck, writes an entry through the API and reads it back after
`docker compose down && up`, fetches every emitted asset chunk, proves `/calibre` rejects writes at
the mount and in code, takes and restores a backup, and confirms a SIGTERM stop is graceful.

## Repository guidance

Coding agents start with [AGENTS.md](AGENTS.md). Product behavior is canonical in [the product spec](docs/specs/product-spec.md), while implementation contracts live in [the technical spec](docs/specs/technical-spec.md).
