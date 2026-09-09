from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.api.auth import COOKIE_NAME, LoginRateLimiter
from book_tracker.application.passwords import hash_password
from book_tracker.application.sessions import SESSION_LIFETIME, SessionStore
from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app

PASSWORD = "a private library password"
UNAUTHENTICATED = {
    "error": {
        "code": "unauthenticated",
        "message": "Authentication is required",
        "details": {},
    }
}
SETUP_REQUIRED = {
    "error": {
        "code": "setup_required",
        "message": "Create the first admin before using Akasha",
        "details": {},
    }
}


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
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE users SET username = 'mauro', display_name = 'Mauro', "
                "password_hash = :digest, password_salt = :salt WHERE id = 1"
            ),
            {"digest": credential.digest, "salt": credential.salt},
        )


def session_cookie(response: httpx.Response) -> str:
    return response.cookies[COOKIE_NAME]


@pytest.mark.anyio
async def test_auth_off_keeps_routes_absent_and_library_open(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid")
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        assert (await client.get("/api/entries")).status_code == 200
        for method, path, body in (
            ("post", "/api/auth/login", {"username": "somebody", "password": PASSWORD}),
            ("delete", "/api/auth/session", None),
            ("get", "/api/auth/me", None),
            (
                "post",
                "/api/auth/setup",
                {"username": "somebody", "password": PASSWORD},
            ),
            (
                "patch",
                "/api/auth/password",
                {"current_password": PASSWORD, "new_password": "another private password"},
            ),
            ("get", "/api/users", None),
            ("post", "/api/users", {"username": "somebody", "password": PASSWORD}),
            ("patch", "/api/users/1", {"display_name": "Somebody"}),
            ("delete", "/api/users/1", {"action": "delete"}),
        ):
            assert (await client.request(method.upper(), path, json=body)).status_code == 404


@pytest.mark.anyio
async def test_login_sets_cookie_and_wrong_password_does_not(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            wrong = await client.post(
                "/api/auth/login", json={"username": "Mauro", "password": "not it"}
            )
            assert wrong.status_code == 401
            assert wrong.json() == UNAUTHENTICATED
            assert COOKIE_NAME not in wrong.cookies
            assert (await client.get("/openapi.json")).json() == UNAUTHENTICATED

            login = await client.post(
                "/api/auth/login", json={"username": " MAURO ", "password": PASSWORD}
            )
            assert login.status_code == 200
            assert login.json()["username"] == "mauro"
            assert COOKIE_NAME in login.cookies
            assert (await client.get("/api/entries")).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["missing", "unknown", "expired", "orphaned"])
async def test_invalid_session_shapes_share_one_401(tmp_path: Path, kind: str) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        cookies: dict[str, str] = {}
        if kind == "unknown":
            cookies[COOKIE_NAME] = "not-a-real-session"
        elif kind in {"expired", "orphaned"}:
            now = datetime(2024, 1, 1, tzinfo=UTC) if kind == "expired" else datetime.now(UTC)
            created = SessionStore(app.state.engine).create(1, now=now)
            cookies[COOKIE_NAME] = created.token
            if kind == "orphaned":
                with app.state.engine.begin() as connection:
                    credential = hash_password("another user's credential")
                    connection.execute(
                        text(
                            "INSERT INTO users (id, username, password_hash, password_salt, "
                            "is_admin, created_at, updated_at) VALUES "
                            "(2, 'remaining', :digest, :salt, 0, :now, :now)"
                        ),
                        {
                            "digest": credential.digest,
                            "salt": credential.salt,
                            "now": datetime.now(UTC).isoformat(),
                        },
                    )
                    connection.execute(text("DELETE FROM users WHERE id = 1"))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test", cookies=cookies
        ) as client:
            response = await client.get("/api/entries")
        assert response.status_code == 401
        assert response.json() == UNAUTHENTICATED


@pytest.mark.anyio
async def test_logout_revokes_the_cookie(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            login = await client.post(
                "/api/auth/login", json={"username": "mauro", "password": PASSWORD}
            )
            token = session_cookie(login)
            assert (await client.delete("/api/auth/session")).status_code == 204
            client.cookies.set(COOKIE_NAME, token)
            refused = await client.get("/api/entries")
        assert refused.status_code == 401
        assert refused.json() == UNAUTHENTICATED


@pytest.mark.anyio
async def test_setup_gates_api_then_claims_the_existing_library(tmp_path: Path) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Akasha</title>", encoding="utf-8")
    app = create_app(auth_settings(tmp_path, static_dir=static))
    async with app.router.lifespan_context(app):
        created = DomainRepository(app.state.engine, 1).create_or_get_entry(
            title="Rayuela", creators=("Julio Cortázar",)
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            for method, path in (
                ("get", "/api/entries"),
                ("post", "/api/auth/login"),
                ("delete", "/api/auth/session"),
                ("get", "/api/not-a-route"),
                ("get", "/openapi.json"),
            ):
                response = await getattr(client, method)(path)
                assert response.status_code == 409, (method, path, response.text)
                assert response.json() == SETUP_REQUIRED

            assert (await client.get("/api/health/live")).status_code == 200
            me = await client.get("/api/auth/me")
            assert me.status_code == 200
            assert me.json() == {
                "auth": "on",
                "authenticated": False,
                "setup_required": True,
                "user": None,
            }
            shell = await client.get("/books/1")
            assert shell.status_code == 200
            assert "<title>Akasha</title>" in shell.text

            setup = await client.post(
                "/api/auth/setup",
                json={"username": " Mauro ", "display_name": "Mauro", "password": PASSWORD},
            )
            assert setup.status_code == 200
            assert setup.json()["username"] == "mauro"
            assert COOKIE_NAME in setup.cookies
            entries = await client.get("/api/entries", params={"status": "unsorted"})
            assert entries.status_code == 200
            assert [entry["id"] for entry in entries.json()["items"]] == [created.entry_id]


@pytest.mark.anyio
async def test_setup_twice_is_409_and_creates_nothing(tmp_path: Path) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/setup",
                json={"username": "second", "password": "another password"},
            )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "setup_already_completed"
        with app.state.engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("base_url", "cookie_secure", "forwarded", "trusted", "expected"),
    [
        ("http://test", None, None, (), False),
        ("https://test", None, None, (), True),
        ("http://test", True, None, (), True),
        ("https://test", False, None, (), False),
        ("http://test", None, "https", ("127.0.0.1",), True),
        ("http://test", None, "https", ("10.0.0.1",), False),
    ],
)
async def test_cookie_secure_policy(
    tmp_path: Path,
    base_url: str,
    cookie_secure: bool | None,
    forwarded: str | None,
    trusted: tuple[str, ...],
    expected: bool,
) -> None:
    app = create_app(
        auth_settings(
            tmp_path,
            cookie_secure=cookie_secure,
            trusted_proxy_peers=list(trusted),
        )
    )
    async with app.router.lifespan_context(app):
        install_password(app)
        headers = {"X-Forwarded-Proto": forwarded} if forwarded else {}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app, client=("127.0.0.1", 3210)),
            base_url=base_url,
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"username": "mauro", "password": PASSWORD},
                headers=headers,
            )
        cookie = response.headers["set-cookie"]
        assert ("; Secure" in cookie) is expected
        assert "; HttpOnly" in cookie
        assert "; SameSite=lax" in cookie
        assert "; Path=/" in cookie
        assert f"Max-Age={int(SESSION_LIFETIME.total_seconds())}" in cookie


@pytest.mark.anyio
async def test_login_rate_limit_refuses_then_recovers_without_blocking_valid_other_user(
    tmp_path: Path,
) -> None:
    app = create_app(auth_settings(tmp_path, login_max_failures=2, login_window_seconds=10))
    clock = [100.0]
    async with app.router.lifespan_context(app):
        install_password(app)
        app.state.login_limiter = LoginRateLimiter(2, 10, clock=lambda: clock[0])
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            for _ in range(2):
                assert (
                    await client.post(
                        "/api/auth/login", json={"username": "guess", "password": "wrong"}
                    )
                ).status_code == 401
            limited = await client.post(
                "/api/auth/login", json={"username": "guess", "password": "wrong"}
            )
            assert limited.status_code == 429
            assert limited.json()["error"]["code"] == "login_rate_limited"

            valid = await client.post(
                "/api/auth/login", json={"username": "mauro", "password": PASSWORD}
            )
            assert valid.status_code == 200

            clock[0] += 11
            recovered = await client.post(
                "/api/auth/login", json={"username": "guess", "password": "wrong"}
            )
            assert recovered.status_code == 401


@pytest.mark.anyio
async def test_password_never_reaches_logs_or_responses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(auth_settings(tmp_path))
    async with app.router.lifespan_context(app):
        install_password(app)
        logging.getLogger("auth-test").warning(
            "login failed", extra={"password": PASSWORD, "cookie": PASSWORD}
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/login", json={"username": "mauro", "password": PASSWORD + "!"}
            )
    output = capsys.readouterr().err
    assert PASSWORD not in output
    assert PASSWORD not in response.text
    assert PASSWORD not in str(app.openapi())


@pytest.mark.anyio
async def test_environment_credentials_bootstrap_once_and_can_log_in(tmp_path: Path) -> None:
    app = create_app(
        auth_settings(
            tmp_path,
            admin_username=" FirstAdmin ",
            admin_password=PASSWORD,
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            me = await client.get("/api/auth/me")
            assert me.json()["setup_required"] is False
            login = await client.post(
                "/api/auth/login",
                json={"username": "firstadmin", "password": PASSWORD},
            )
            assert login.status_code == 200
        with app.state.engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 1


def test_openapi_carries_auth_routes_and_boundary_errors(tmp_path: Path) -> None:
    schema = create_app(auth_settings(tmp_path)).openapi()
    for path in (
        "/api/auth/login",
        "/api/auth/session",
        "/api/auth/me",
        "/api/auth/setup",
    ):
        assert path in schema["paths"]
    responses = schema["paths"]["/api/entries"]["get"]["responses"]
    assert "401" in responses
    assert "409" in responses
