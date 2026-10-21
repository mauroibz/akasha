"""Every error the API returns, in the one envelope (Sprint 087; split out in 088)."""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from book_tracker.api.auth import (
    error_response,
    unauthenticated,
)
from book_tracker.api.identity import AuthenticationRequired
from book_tracker.application.library import LibraryError
from book_tracker.infrastructure.diskspace import InsufficientDiskSpace

#: The catch-all's answer and auth-off's, in the one error envelope (Sprint 087).
NOT_FOUND = {"error": {"code": "not_found", "message": "Not Found", "details": {}}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthenticationRequired)
    async def authentication_required(
        _request: Request, _error: AuthenticationRequired
    ) -> JSONResponse:
        return unauthenticated()

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, error: StarletteHTTPException) -> Response:
        """Starlette's own errors (an `HTTPException` a route raises, a 405) in the
        envelope every other error uses, so a client parses one shape (Sprint 087)."""
        try:
            phrase = HTTPStatus(error.status_code).phrase
        except ValueError:
            phrase = "Error"
        code = phrase.lower().replace(" ", "_").replace("-", "_")
        message = error.detail if isinstance(error.detail, str) and error.detail else phrase
        response = error_response(error.status_code, code, message)
        if error.headers:
            response.headers.update(error.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def request_validation_failed(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        """A body or query FastAPI refused, named field by field in the envelope."""
        fields = []
        for problem in error.errors():
            location = [str(part) for part in problem.get("loc", ())]
            if location and location[0] in {"body", "query", "path", "header", "cookie"}:
                location = location[1:] or location
            fields.append({"field": ".".join(location), "message": str(problem.get("msg", ""))})
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request is not valid",
                    "details": {"fields": fields},
                }
            },
        )

    @app.exception_handler(LibraryError)
    async def library_error(_request: object, error: LibraryError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"error": error.payload()})

    @app.exception_handler(OperationalError)
    async def database_busy(_request: object, error: OperationalError) -> JSONResponse:
        """`PRAGMA busy_timeout` (database.py) turns write contention into a wait,
        not a crash — Sprint 059's offload seam is the first thing that lets two
        real OS threads contend for this engine's write lock at all. If the wait
        still expires, the caller gets a typed, retryable error instead of a raw
        driver message. Any other `OperationalError` (a genuine bug: bad SQL, a
        missing table) is not this and must not be swallowed.
        """
        if "database is locked" not in str(error).lower():
            raise error
        busy = LibraryError(
            "library_busy",
            "The library is busy with another write; try again",
            status_code=503,
            user_message="Akasha is busy saving something else. Try again in a moment.",
        )
        return JSONResponse(status_code=busy.status_code, content={"error": busy.payload()})

    @app.exception_handler(InsufficientDiskSpace)
    async def disk_full(_request: object, error: InsufficientDiskSpace) -> JSONResponse:
        full = LibraryError(
            "insufficient_disk_space",
            str(error),
            status_code=507,
            user_message=(
                "Akasha's disk is nearly full, so this was refused before writing anything."
            ),
            action="Free up space, or ask whoever manages this server to.",
            details={"free_bytes": error.free_bytes, "minimum_bytes": error.minimum_bytes},
        )
        return JSONResponse(status_code=full.status_code, content={"error": full.payload()})
