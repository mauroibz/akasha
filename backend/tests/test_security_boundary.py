"""The request boundary under public exposure (Sprint 128, DEC-180).

Each test here failed against `12705c9`: the audit's proofs of concept, kept as
regression tests (F2, F3, F4, F9, F10, F11, F12, F13, F18, F21).
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.api.auth import (
    COOKIE_NAME,
    SECURE_COOKIE_NAME,
    LoginRateLimiter,
)
from book_tracker.application.passwords import hash_password
from book_tracker.application.sessions import SessionStore
from book_tracker.config import Settings
from book_tracker.main import create_app

PASSWORD = "a private library password"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def auth_settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        user_agent_contact="test@example.invalid",
        auth="on",
        **overrides,
    )


def install_password(app: object, password: str = PASSWORD) -> None:
    credential = hash_password(password)
    with app.state.engine.begin() as connection:  # type: ignore[attr-defined]
        connection.execute(
            text(
                "UPDATE users SET username = 'mauro', display_name = 'Mauro', "
                "password_hash = :digest, password_salt = :salt WHERE id = 1"
            ),
            {"digest": credential.digest, "salt": credential.salt},
        )


def client_for(
    app: object, peer: str = "127.0.0.1", base_url: str = "http://test"
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app, client=(peer, 3210)),  # type: ignore[arg-type]
        base_url=base_url,
    )


async def login(client: httpx.AsyncClient, password: str = PASSWORD, **headers: str) -> int:
    response = await client.post(
        "/api/auth/login", json={"username": "mauro", "password": password}, headers=headers
    )
    return response.status_code


# F2 ------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "host", ["x/api/health/?", "x/api/health/live?", "x/assets/a.js?", "x/api/auth/me?"]
)
async def test_a_forged_host_header_cannot_skip_the_boundary(tmp_path: Path, host: str) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        async with client_for(app) as client:
            for path in ("/api/entries", "/api/search?q=x", "/openapi.json"):
                response = await client.get(path, headers={"Host": host})
                assert response.status_code == 401, (host, path, response.text)


# F18 -----------------------------------------------------------------------


@pytest.mark.anyio
async def test_metrics_and_provider_health_need_a_session_with_auth_on(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path, metrics="on"))
    async with app.router.lifespan_context(app):
        install_password(app)
        with app.state.engine.begin() as connection:
            credential = hash_password("bruno's private password")
            connection.execute(
                text(
                    "INSERT INTO users (username,password_hash,password_salt,is_admin,"
                    "created_at,updated_at) VALUES ('bruno',:d,:s,0,'2026-01-01','2026-01-01')"
                ),
                {"d": credential.digest, "s": credential.salt},
            )
        async with client_for(app) as client:
            assert (await client.get("/metrics")).status_code == 401
            assert (await client.get("/api/health/providers")).status_code == 401
            assert (await client.get("/api/health/live")).status_code == 200
            ready = await client.get("/api/health/ready")
            assert ready.status_code == 200
            assert "free_bytes" not in ready.text

            response = await client.post(
                "/api/auth/login",
                json={"username": "bruno", "password": "bruno's private password"},
            )
            assert response.status_code == 200
            assert (await client.get("/metrics")).status_code == 403
            assert (await client.get("/api/health/providers")).status_code == 200

        async with client_for(app) as admin:
            assert await login(admin) == 200
            metrics = await admin.get("/metrics")
            assert metrics.status_code == 200
            assert "akasha_jobs" in metrics.text


# F3 / F10 / F21 limiter ----------------------------------------------------


@pytest.mark.anyio
async def test_a_limited_client_learns_nothing_and_every_guess_counts(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    clock = [100.0]
    async with app.router.lifespan_context(app):
        install_password(app)
        app.state.login_limiter = LoginRateLimiter(3, 60, clock=lambda: clock[0])
        async with client_for(app, "203.0.113.9") as attacker:
            for _ in range(3):
                assert await login(attacker, "wrong guess one") == 401
            # The right password from the limited client answers exactly like a
            # wrong one: 429, nothing about correctness.
            assert await login(attacker) == 429
            clock[0] += 30
            for _ in range(3):
                assert await login(attacker, "wrong guess two") == 429
            # The first three failures have left the window, but the guesses made
            # while limited were counted: an attacker who keeps hammering stays out.
            clock[0] += 31
            assert await login(attacker) == 429
            clock[0] += 61
            assert await login(attacker) == 200


@pytest.mark.anyio
async def test_the_owner_still_signs_in_while_another_client_is_refused(tmp_path: Path) -> None:
    app = create_app(
        auth_settings(
            tmp_path,
            client_ip_header="CF-Connecting-IP",
            trusted_proxy_peers=["172.18.0.0/16"],
        )
    )
    async with app.router.lifespan_context(app):
        install_password(app)
        app.state.login_limiter = LoginRateLimiter(3, 300)
        # Behind the tunnel every request comes from cloudflared's address; the
        # header names the real client.
        async with client_for(app, "172.18.0.5") as tunnel:
            for _ in range(5):
                await login(tunnel, "wrong", **{"CF-Connecting-IP": "198.51.100.7"})
            assert await login(tunnel, PASSWORD, **{"CF-Connecting-IP": "198.51.100.7"}) == 429
            assert await login(tunnel, PASSWORD, **{"CF-Connecting-IP": "192.0.2.44"}) == 200


@pytest.mark.anyio
async def test_the_client_header_is_ignored_from_an_untrusted_peer(tmp_path: Path) -> None:
    app = create_app(
        auth_settings(
            tmp_path,
            client_ip_header="CF-Connecting-IP",
            trusted_proxy_peers=["172.18.0.0/16"],
        )
    )
    async with app.router.lifespan_context(app):
        install_password(app)
        app.state.login_limiter = LoginRateLimiter(3, 300)
        async with client_for(app, "203.0.113.9") as direct:
            for index in range(3):
                # A rotating forged header does not buy a fresh bucket.
                await login(direct, "wrong", **{"CF-Connecting-IP": f"192.0.2.{index}"})
            assert await login(direct, PASSWORD, **{"CF-Connecting-IP": "192.0.2.200"}) == 429


def test_distributed_guessing_is_bounded_per_username() -> None:
    limiter = LoginRateLimiter(2, 60, clock=lambda: 0.0)
    for client in range(10):
        assert not limiter.limited("mauro", f"10.0.0.{client}")
        limiter.fail("mauro", f"10.0.0.{client}")
        limiter.fail("mauro", f"10.0.0.{client}")
    # 20 failures from 10 clients reach the username-wide cap (10 x maximum).
    assert limiter.limited("mauro", "10.0.0.250")
    assert not limiter.limited("someone-else", "10.0.0.250")


def test_one_client_spraying_usernames_is_capped() -> None:
    limiter = LoginRateLimiter(2, 60, clock=lambda: 0.0)
    for index in range(limiter.client_maximum):
        limiter.fail(f"user{index}", "10.0.0.1")
    assert limiter.limited("fresh-name", "10.0.0.1")
    assert not limiter.limited("fresh-name", "10.0.0.2")


def test_limiter_memory_is_bounded_and_checks_create_nothing() -> None:
    clock = [0.0]
    limiter = LoginRateLimiter(5, 10, clock=lambda: clock[0], max_keys=50)
    for index in range(500):
        assert not limiter.limited(f"user{index}", f"10.0.{index // 256}.{index % 256}")
    assert limiter.key_count() == 0
    for index in range(500):
        limiter.fail(f"user{index}", f"10.0.{index // 256}.{index % 256}")
    assert limiter.key_count() <= 50
    clock[0] += 11
    limiter.limited("user499", "10.0.1.243")
    limiter.prune()
    assert limiter.key_count() == 0


@pytest.mark.anyio
async def test_change_password_guesses_are_rate_limited(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        app.state.login_limiter = LoginRateLimiter(2, 300)
        async with client_for(app) as client:
            assert await login(client) == 200
            for _ in range(2):
                wrong = await client.patch(
                    "/api/auth/password",
                    json={"current_password": "not it", "new_password": "a new long password"},
                )
                assert wrong.status_code == 401
            limited = await client.patch(
                "/api/auth/password",
                json={"current_password": PASSWORD, "new_password": "a new long password"},
            )
            assert limited.status_code == 429


# F4 ------------------------------------------------------------------------


@pytest.mark.anyio
async def test_setup_needs_the_code_printed_in_the_server_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        code = app.state.setup_code
        assert isinstance(code, str) and len(code) >= 12
        output = capsys.readouterr().err
        assert f"Akasha setup code: {code}" in output
        async with client_for(app) as client:
            me = (await client.get("/api/auth/me")).json()
            assert me["setup_required"] is True
            body = {"username": "mauro", "password": PASSWORD}
            missing = await client.post("/api/auth/setup", json=body)
            assert missing.status_code == 403
            assert missing.json()["error"]["code"] == "setup_code_invalid"
            wrong = await client.post("/api/auth/setup", json={**body, "setup_code": "nope"})
            assert wrong.status_code == 403
            with app.state.engine.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT count(*) FROM users WHERE password_hash IS NOT NULL")
                    ).scalar_one()
                    == 0
                )
            right = await client.post("/api/auth/setup", json={**body, "setup_code": code})
            assert right.status_code == 200


@pytest.mark.anyio
async def test_a_configured_setup_token_is_used_and_not_logged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(auth_settings(tmp_path, setup_token="operator-chosen-setup-code"))
    async with app.router.lifespan_context(app):
        assert "operator-chosen-setup-code" not in capsys.readouterr().err
        async with client_for(app) as client:
            response = await client.post(
                "/api/auth/setup",
                json={
                    "username": "mauro",
                    "password": PASSWORD,
                    "setup_code": "operator-chosen-setup-code",
                },
            )
            assert response.status_code == 200


@pytest.mark.anyio
async def test_setup_code_guesses_are_rate_limited(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        app.state.login_limiter = LoginRateLimiter(2, 300)
        async with client_for(app) as client:
            body = {"username": "mauro", "password": PASSWORD}
            for _ in range(2):
                response = await client.post("/api/auth/setup", json={**body, "setup_code": "x"})
                assert response.status_code == 403
            response = await client.post(
                "/api/auth/setup", json={**body, "setup_code": app.state.setup_code}
            )
            assert response.status_code == 429


@pytest.mark.anyio
async def test_no_setup_code_when_the_library_is_already_claimed(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path, admin_username="mauro", admin_password=PASSWORD))
    async with app.router.lifespan_context(app):
        assert app.state.setup_code is None


# F11 -----------------------------------------------------------------------


@pytest.mark.anyio
async def test_new_passwords_need_twelve_characters(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        code = app.state.setup_code
        async with client_for(app) as client:
            short = await client.post(
                "/api/auth/setup",
                json={"username": "mauro", "password": "eleven char", "setup_code": code},
            )
            assert short.status_code == 422
            assert (
                await client.post(
                    "/api/auth/setup",
                    json={"username": "mauro", "password": PASSWORD, "setup_code": code},
                )
            ).status_code == 200
            for method, path, body in (
                ("POST", "/api/users", {"username": "bruno", "password": "short"}),
                ("PATCH", "/api/users/1", {"password": "short"}),
                (
                    "PATCH",
                    "/api/auth/password",
                    {"current_password": PASSWORD, "new_password": "short"},
                ),
            ):
                response = await client.request(method, path, json=body)
                assert response.status_code == 422, (method, path)
        # An existing short password still signs in.
        install_password(app, "old")
        async with client_for(app) as client:
            assert await login(client, "old") == 200


# F9 ------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("auth", ["on", "off"])
async def test_cross_site_unsafe_requests_are_refused(tmp_path: Path, auth: str) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid", auth=auth)
    )
    async with app.router.lifespan_context(app):
        install_password(app)
        async with client_for(app, base_url="http://akasha.example") as client:
            body = {"manual": {"item_type": "book", "title": "Rayuela"}, "idempotency_key": "r"}
            for headers in (
                {"Sec-Fetch-Site": "same-site"},
                {"Sec-Fetch-Site": "cross-site"},
                {"Origin": "http://evil.example.com"},
                {"Origin": "null"},
            ):
                response = await client.post("/api/entries", json=body, headers=headers)
                assert response.status_code == 403, headers
                assert response.json()["error"]["code"] == "cross_site_request"
            refused_login = await client.post(
                "/api/auth/login",
                json={"username": "mauro", "password": PASSWORD},
                headers={"Sec-Fetch-Site": "cross-site"},
            )
            assert refused_login.status_code == 403
            # Reads stay reachable cross-site (a link to the app still works).
            reads = await client.get("/api/health/live", headers={"Sec-Fetch-Site": "cross-site"})
            assert reads.status_code == 200
            if auth == "on":
                assert await login(client, PASSWORD, **{"Sec-Fetch-Site": "same-origin"}) == 200
            for headers in (
                {"Sec-Fetch-Site": "same-origin"},
                {"Sec-Fetch-Site": "none"},
                {"Origin": "http://akasha.example"},
                {},
            ):
                title = f"Rayuela {sorted(headers.items())}"
                response = await client.post(
                    "/api/entries",
                    json={
                        "manual": {"item_type": "book", "title": title},
                        "idempotency_key": title,
                    },
                    headers=headers,
                )
                assert response.status_code in {200, 201}, (headers, response.text)


# F12 -----------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_secure_cookie_carries_the_host_prefix(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path, cookie_secure=True))
    async with app.router.lifespan_context(app):
        install_password(app)
        async with client_for(app, base_url="https://akasha.example") as client:
            response = await client.post(
                "/api/auth/login", json={"username": "mauro", "password": PASSWORD}
            )
            cookie = response.headers["set-cookie"]
            assert cookie.startswith(f"{SECURE_COOKIE_NAME}=")
            assert "; Secure" in cookie and "; Path=/" in cookie and "Domain" not in cookie
            assert (await client.get("/api/entries")).status_code == 200
        # A legacy-named cookie planted by a sibling subdomain is not a session
        # when the app runs Secure.
        token = SessionStore(app.state.engine).create(1).token
        async with client_for(app, base_url="https://akasha.example") as planted:
            planted.cookies.set(COOKIE_NAME, token)
            assert (await planted.get("/api/entries")).status_code == 401


@pytest.mark.anyio
async def test_plain_http_keeps_the_legacy_cookie_name(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        async with client_for(app) as client:
            response = await client.post(
                "/api/auth/login", json={"username": "mauro", "password": PASSWORD}
            )
            assert response.headers["set-cookie"].startswith(f"{COOKIE_NAME}=")
            assert (await client.get("/api/entries")).status_code == 200


@pytest.mark.anyio
async def test_startup_warns_when_the_cookie_may_go_out_without_secure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app(auth_settings(tmp_path))
    with caplog.at_level(logging.WARNING):
        async with app.router.lifespan_context(app):
            pass
    assert "AKASHA_COOKIE_SECURE" in caplog.text

    caplog.clear()
    app = create_app(auth_settings(tmp_path / "secure", cookie_secure=True))
    with caplog.at_level(logging.WARNING):
        async with app.router.lifespan_context(app):
            pass
    assert "AKASHA_COOKIE_SECURE" not in caplog.text


# F21 sessions --------------------------------------------------------------


@pytest.mark.anyio
async def test_changing_the_password_rotates_the_session_and_ends_the_others(
    tmp_path: Path,
) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        other = SessionStore(app.state.engine).create(1)
        async with client_for(app) as client:
            assert await login(client) == 200
            old_token = client.cookies[COOKIE_NAME]
            response = await client.patch(
                "/api/auth/password",
                json={"current_password": PASSWORD, "new_password": "a brand new password"},
            )
            assert response.status_code == 204
            new_token = response.cookies[COOKIE_NAME]
            assert new_token != old_token
            assert (await client.get("/api/entries")).status_code == 200
        assert SessionStore(app.state.engine).lookup(old_token) is None
        assert SessionStore(app.state.engine).lookup(other.token) is None


@pytest.mark.anyio
async def test_login_discards_a_presented_session(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        planted = SessionStore(app.state.engine).create(1)
        async with client_for(app) as client:
            response = await client.post(
                "/api/auth/login",
                json={"username": "mauro", "password": PASSWORD},
                cookies={COOKIE_NAME: planted.token},
            )
            assert response.status_code == 200
            assert response.cookies[COOKIE_NAME] != planted.token
        assert SessionStore(app.state.engine).lookup(planted.token) is None


@pytest.mark.anyio
async def test_session_lifetime_is_configurable(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path, session_days=7))
    async with app.router.lifespan_context(app):
        install_password(app)
        async with client_for(app) as client:
            response = await client.post(
                "/api/auth/login", json={"username": "mauro", "password": PASSWORD}
            )
            assert f"Max-Age={7 * 86400}" in response.headers["set-cookie"]
        with app.state.engine.connect() as connection:
            created, expires = connection.execute(
                text("SELECT created_at, expires_at FROM sessions")
            ).one()
        assert expires[:10] > created[:10]
        from book_tracker.application.sessions import parse_timestamp

        assert (parse_timestamp(expires) - parse_timestamp(created)).days == 7


# F13 -----------------------------------------------------------------------


@pytest.mark.anyio
async def test_every_response_carries_the_security_headers(tmp_path: Path) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Akasha</title>", encoding="utf-8")
    (static / "app.js").write_text("console.log(1)", encoding="utf-8")
    app = create_app(auth_settings(tmp_path, static_dir=static))
    async with app.router.lifespan_context(app):
        install_password(app)
        async with client_for(app) as client:
            shell = await client.get("/books/1")
            api = await client.get("/api/entries")
            asset = await client.get("/app.js")
        for response in (shell, api, asset):
            headers = response.headers
            assert headers["x-content-type-options"] == "nosniff"
            assert headers["x-frame-options"] == "DENY"
            assert headers["referrer-policy"] == "no-referrer"
            assert headers["cross-origin-opener-policy"] == "same-origin"
            assert "camera=()" in headers["permissions-policy"]
            csp = headers["content-security-policy"]
            assert "script-src 'self';" in csp
            assert "frame-ancestors 'none'" in csp
            assert "strict-transport-security" not in headers
        assert api.headers["cache-control"] == "no-store"
        assert shell.headers["cache-control"] == "no-cache"

    async with app.router.lifespan_context(app):
        async with client_for(app, base_url="https://akasha.example") as client:
            response = await client.get("/api/health/live")
        assert response.headers["strict-transport-security"] == "max-age=31536000"


# F2 docs -------------------------------------------------------------------


@pytest.mark.anyio
async def test_interactive_docs_are_off_with_auth_on(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        async with client_for(app) as client:
            assert await login(client) == 200
            assert (await client.get("/openapi.json")).status_code == 200
            for path in ("/docs", "/redoc"):
                assert (await client.get(path)).status_code == 404, path
