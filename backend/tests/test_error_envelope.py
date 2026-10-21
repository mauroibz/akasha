"""Every error the API returns is one envelope (Sprint 087, production-grade proposal R5).

Three shapes used to reach the browser: the `{"error": {code, message, details}}`
envelope, `{"detail": "Not Found"}` from the catch-all and the auth-off routes, and
FastAPI's own `HTTPException` and 422 bodies. Each client parser had to guess which
one it was holding. These are the four sources that did not use the envelope.
"""

from pathlib import Path
from typing import Any

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _envelope(body: Any) -> dict[str, Any]:
    assert set(body) == {"error"}, body
    error = body["error"]
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["details"], dict)
    return error


async def _call(tmp_path: Path, method: str, path: str, **kwargs: Any) -> httpx.Response:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        return await client.request(method, path, **kwargs)


@pytest.mark.anyio
async def test_an_unknown_api_path_is_a_not_found_envelope(tmp_path: Path) -> None:
    response = await _call(tmp_path, "GET", "/api/nonexistent")
    assert response.status_code == 404
    assert _envelope(response.json())["code"] == "not_found"


@pytest.mark.anyio
async def test_an_auth_route_with_auth_off_is_a_not_found_envelope(tmp_path: Path) -> None:
    response = await _call(tmp_path, "GET", "/api/auth/me")
    assert response.status_code == 404
    assert _envelope(response.json())["code"] == "not_found"


@pytest.mark.anyio
async def test_an_http_exception_raised_by_a_route_is_an_envelope(tmp_path: Path) -> None:
    # `require_auth_mode` raises Starlette's HTTPException when auth is off.
    response = await _call(tmp_path, "GET", "/api/users")
    assert response.status_code == 404
    assert _envelope(response.json())["code"] == "not_found"


@pytest.mark.anyio
async def test_a_malformed_body_is_a_validation_envelope_naming_the_field(
    tmp_path: Path,
) -> None:
    response = await _call(tmp_path, "POST", "/api/shelves", json={"nmae": "Typo"})
    assert response.status_code == 422
    error = _envelope(response.json())
    assert error["code"] == "validation_error"
    assert [field["field"] for field in error["details"]["fields"]] == ["name"]
    assert all(field["message"] for field in error["details"]["fields"])


def test_the_contract_documents_the_envelope_for_validation_errors(tmp_path: Path) -> None:
    """FastAPI documents its own 422 body on every route that takes input. The
    contract has to say what is actually returned, or the generated client of
    Sprint 088 would type a shape the server no longer sends."""
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    schema = app.openapi()
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    shelves = schema["paths"]["/api/shelves"]["post"]["responses"]["422"]
    assert shelves["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
