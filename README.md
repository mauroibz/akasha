# Akasha Book Tracker

Akasha is a self-hosted, keyboard-first personal book rating and triage app. It tracks opinions, not ebook files, and v1 has no authentication: deploy it only on a trusted LAN.

## Local setup

Requirements: Docker, Node 22, npm, and `uv`. `uv` installs the required Python 3.12 runtime automatically.

```bash
make bootstrap
cp .env.example .env
make dev-backend   # terminal 1, API at http://localhost:8000
make dev-frontend  # terminal 2, UI at http://localhost:5173
```

The first backend startup creates the local `data/` directories and applies the foundation Alembic migration. Sprint 001 intentionally seeds no book-domain rows.

## Quality and build commands

```bash
make format       # apply backend/frontend formatting
make check        # format check, lint, types, project state, OpenAPI drift
make test         # backend and frontend behavior tests
make build        # Python wheel and production SPA
make openapi      # regenerate frontend/openapi.json
make migrate      # explicitly upgrade the configured database
cd frontend && npm run test:e2e  # Chromium library/keyboard browser checks
```

## Container

Set a real contact address for future provider requests, then build and start the single production container:

```bash
cp .env.example .env
docker compose up --build
```

Compose persists `${DATA_DIR:-./data}` at `/data`. The image serves the SPA and API on port 8000, runs as a non-root user, contains no Node runtime, and uses `/api/health/ready` for health checks. The Calibre read-only mount is enabled in Sprint 008.

Run the repeatable image proof with `make smoke-container`; it builds the image, checks readiness and SPA routing, recreates the container over persistent data, confirms the process is non-root, and verifies Node is absent.

## Repository guidance

Coding agents start with [AGENTS.md](AGENTS.md). Product behavior is canonical in [the product spec](docs/specs/product-spec.md), while implementation contracts live in [the technical spec](docs/specs/technical-spec.md).
