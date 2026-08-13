FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend-build
WORKDIR /build/backend
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev --no-editable && uv build

FROM python:3.12-slim AS runtime
ENV PATH=/opt/venv/bin:$PATH \
    BOOK_TRACKER_DATA_DIR=/data \
    BOOK_TRACKER_BACKUP_DIR=/backups \
    BOOK_TRACKER_STATIC_DIR=/app/static \
    BOOK_TRACKER_ENVIRONMENT=production \
    PYTHONUNBUFFERED=1
RUN groupadd --system --gid 10001 akasha && useradd --system --uid 10001 --gid akasha --home /app akasha
WORKDIR /app
COPY --from=backend-build /opt/venv /opt/venv
COPY --from=backend-build /build/backend/alembic.ini /app/alembic.ini
COPY --from=backend-build /build/backend/alembic /app/alembic
COPY --from=frontend-build /build/frontend/dist /app/static
RUN mkdir -p /data /backups && chown -R akasha:akasha /app /data /backups
USER 10001:10001
EXPOSE 8000
# uvicorn is PID 1 under the exec-form CMD below, so SIGTERM reaches it directly
# and it runs its own graceful shutdown. Compose adds `init: true` on top.
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=2)"]
CMD ["uvicorn", "book_tracker.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
