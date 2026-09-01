.PHONY: bootstrap dev format lint typecheck test check migrate build openapi openapi-check smoke-container

UV_ENV = UV_CACHE_DIR=/tmp/akasha-uv-cache

bootstrap:
	cd backend && $(UV_ENV) uv sync --python 3.12 --all-groups
	cd frontend && npm ci

dev:
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals."

.PHONY: dev-backend dev-frontend
dev-backend:
	cd backend && BOOK_TRACKER_DATA_DIR=../data USER_AGENT_CONTACT=local@example.invalid $(UV_ENV) uv run uvicorn book_tracker.main:app --reload

dev-frontend:
	cd frontend && npm run dev

format:
	cd backend && $(UV_ENV) uv run ruff format .
	cd backend && $(UV_ENV) uv run ruff check --fix .
	cd frontend && npm run format

lint:
	cd backend && $(UV_ENV) uv run ruff format --check .
	cd backend && $(UV_ENV) uv run ruff check .
	cd frontend && npm run format:check
	cd frontend && npm run lint

typecheck:
	cd backend && $(UV_ENV) uv run mypy
	cd frontend && npm run typecheck

test:
	cd backend && $(UV_ENV) uv run pytest --cov=book_tracker --cov-report=term-missing
	cd frontend && npm test

# The coverage report on demand: `make test` already carries the flags, so this
# is for a session that wants the number (and the missing-lines table) without
# running the frontend suite. A focused run without coverage costs 26 s less
# (DEC-114).
coverage:
	cd backend && $(UV_ENV) uv run pytest --cov=book_tracker --cov-report=term-missing

openapi:
	cd backend && $(UV_ENV) uv run python ../scripts/export_openapi.py

openapi-check:
	cd backend && $(UV_ENV) uv run python ../scripts/export_openapi.py --check
	cd frontend && npm run api:check

check: lint typecheck openapi-check
	python scripts/validate_project.py

migrate:
	cd backend && $(UV_ENV) uv run alembic upgrade head

build:
	cd backend && $(UV_ENV) uv build
	cd frontend && npm run build

smoke-container:
	bash scripts/smoke_container.sh
