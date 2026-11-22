"""Sprint 129: refusals at the boundary leave one parseable log line each.

An operator (or fail2ban, or a log alert) needs to see guessing, lockouts and
cross-site attempts without reading request logs. Each line is JSON on stderr
and carries `category: "security"`, `event`, `client` and, where there is one,
the `username` tried — and never a password.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_security_boundary import (
    PASSWORD,
    auth_settings,
    client_for,
    install_password,
    login,
)

from book_tracker.api.auth import LoginRateLimiter
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def security_lines(output: str) -> list[dict[str, Any]]:
    lines = []
    for raw in output.splitlines():
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        if record.get("category") == "security":
            lines.append(record)
    return lines


@pytest.mark.anyio
async def test_failed_and_limited_logins_are_logged_without_the_password(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        app.state.login_limiter = LoginRateLimiter(2, 60)
        capsys.readouterr()
        async with client_for(app, "203.0.113.9") as attacker:
            assert await login(attacker, "guess-number-one") == 401
            assert await login(attacker, "guess-number-two") == 401
            assert await login(attacker, "guess-number-three") == 429
        async with client_for(app, "198.51.100.4") as owner:
            assert await login(owner) == 200
        output = capsys.readouterr().err

    events = security_lines(output)
    assert [event["event"] for event in events] == [
        "login_failed",
        "login_failed",
        "login_rate_limited",
        "login_succeeded",
    ]
    assert {event["client"] for event in events[:3]} == {"203.0.113.9"}
    assert events[3]["client"] == "198.51.100.4"
    assert all(event["username"] == "mauro" for event in events)
    assert [event["level"] for event in events] == ["warning", "warning", "warning", "info"]
    for secret in ("guess-number", PASSWORD):
        assert secret not in output


@pytest.mark.anyio
async def test_setup_code_guesses_and_cross_site_requests_are_logged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        capsys.readouterr()
        async with client_for(app, "203.0.113.9") as client:
            wrong = await client.post(
                "/api/auth/setup",
                json={"username": "x", "password": PASSWORD, "setup_code": "nope-nope"},
            )
            assert wrong.status_code == 403
            cross = await client.post(
                "/api/auth/login",
                json={"username": "mauro", "password": "x"},
                headers={"Sec-Fetch-Site": "same-site"},
            )
            assert cross.status_code == 403
        output = capsys.readouterr().err

    events = security_lines(output)
    assert [event["event"] for event in events] == [
        "setup_code_invalid",
        "cross_site_request_refused",
    ]
    assert all(event["client"] == "203.0.113.9" for event in events)
    assert events[1]["route"] == "/api/auth/login"
    assert events[1]["method"] == "POST"
    assert "nope-nope" not in output
