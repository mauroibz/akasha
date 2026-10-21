"""Liveness, readiness and provider configuration (split out of `create_app`, 088)."""

from typing import Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from book_tracker.domain.registry import DOMAINS
from book_tracker.infrastructure.diskspace import free_bytes
from book_tracker.migrations import schema_is_current


class ProviderStatus(BaseModel):
    name: str
    available: bool
    reason: str | None = None
    #: From the provider's own recent calls (Sprint 101): `available` says it is
    #: configured, this says whether it is answering.
    state: Literal["working", "degraded", "down"] = "working"


class ProviderHealth(BaseModel):
    providers: list[ProviderStatus]
    degraded: bool


def install_health_routes(app: FastAPI) -> None:
    @app.get("/api/health/live")
    def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/api/health/ready")
    def ready() -> JSONResponse:
        try:
            with app.state.engine.connect() as database:
                database.execute(text("SELECT 1"))
            if not schema_is_current(app.state.engine):
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "code": "schema_not_current",
                            "message": "Database migration is required",
                            "details": {},
                        }
                    },
                )
        except (SQLAlchemyError, OSError):
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "database_unavailable",
                        "message": "Database is unavailable",
                        "details": {},
                    }
                },
            )
        # Separate from the database check above on purpose: a full disk cannot
        # write, but it can still read, so it is not what "ready" means (technical
        # spec 8's shape, already used by /api/health/providers — a missing API key
        # must never make the application look down either). Still 200: Docker's
        # HEALTHCHECK only sees the status code, and restarting a container fixes
        # nothing about a full disk.
        disk_free = free_bytes(app.state.data_dir)
        return JSONResponse(
            {
                "status": "ready",
                "disk": {
                    "free_bytes": disk_free,
                    "low": disk_free < app.state.min_free_bytes,
                },
            }
        )

    @app.get("/api/health/providers", response_model=ProviderHealth)
    def provider_health() -> ProviderHealth:
        """Which metadata providers are configured, so the UI can say search is degraded.

        Deliberately separate from readiness: a missing API key must never make the
        application look down (technical spec 8).
        """
        configured_providers = getattr(app.state, "providers", {})
        catalog = getattr(app.state, "provider_catalog", configured_providers)
        # The order each domain prefers its own sources in, domains in registry order:
        # Open Library before Google Books is books' preference (product spec 4.3), and
        # a domain registered later lands after them without anything here changing.
        # Anything in the catalog no domain names still gets a row, last.
        preferred = [
            name for domain in DOMAINS.values() for name in domain.identity.source_preference
        ]
        order = list(dict.fromkeys([*preferred, *catalog]))
        observations = getattr(app.state, "provider_observations", None)
        rows = [
            ProviderStatus(
                name=name,
                available=name in configured_providers,
                state=observations.state(name) if observations is not None else "working",
                reason=(
                    None
                    if name in configured_providers
                    else getattr(catalog.get(name), "unavailable_reason", None) or "not configured"
                ),
            )
            for name in order
            if name in catalog
        ]
        return ProviderHealth(
            providers=rows,
            degraded=not all(row.available and row.state == "working" for row in rows),
        )
