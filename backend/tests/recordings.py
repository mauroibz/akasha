"""Replay committed provider recordings instead of mocking the unit under test.

DEC-025: substituting a mock for the provider method under test is not proof of that
method. Boundary behaviour is proven by replaying a real response captured from the
live provider. See `tests/fixtures/providers/README.md` for provenance and the exact
commands used to capture each file.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import httpx

FIXTURES = Path(__file__).parent / "fixtures" / "providers"


def recording(name: str) -> Any:
    """Return a committed recorded provider response body."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def redirect_location(name: str) -> str:
    """Return the Location header from a committed recorded redirect response."""
    for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        if key.strip().casefold() == "location":
            return value.strip()
    raise AssertionError(f"{name} has no Location header")


Route = tuple[int, Any] | tuple[int, Any, Mapping[str, str]]


def replay(
    routes: Mapping[str, Route],
    *,
    on_request: Callable[[httpx.Request], None] | None = None,
) -> httpx.MockTransport:
    """Serve recorded responses keyed by request path.

    Any path that was not recorded fails the test loudly rather than returning a
    convenient default, so a test can never pass on a response nobody captured.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if on_request is not None:
            on_request(request)
        route = routes.get(request.url.path)
        if route is None:
            raise AssertionError(f"no recording for {request.url.path}")
        status, body = route[0], route[1]
        headers = dict(route[2]) if len(route) > 2 else {}
        if body is None:
            return httpx.Response(status, headers=headers)
        if isinstance(body, bytes | str):
            return httpx.Response(status, content=body, headers=headers)
        return httpx.Response(status, json=body, headers=headers)

    return httpx.MockTransport(handler)
