"""Password login, first-run setup, and cookie policy (Sprint 077)."""

from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy import Engine, text

from book_tracker.application.passwords import hash_password, verify_password
from book_tracker.application.sessions import (
    SESSION_COOKIE_NAME,
    SESSION_LIFETIME,
    SessionIdentity,
    SessionStore,
    timestamp,
    utc_now,
)
from book_tracker.infrastructure.offload import off_loop

COOKIE_NAME = SESSION_COOKIE_NAME
router = APIRouter(prefix="/api/auth", tags=["auth"])


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    error: ErrorDetail


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None
    is_admin: bool


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=1, max_length=1024)

    @field_validator("username")
    @classmethod
    def username_has_visible_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("username must contain visible text")
        return value


class SetupBody(LoginBody):
    display_name: str | None = Field(default=None, max_length=100)


class MeResponse(BaseModel):
    auth: str
    authenticated: bool
    setup_required: bool
    user: UserResponse | None


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": {}}},
    )


def unauthenticated() -> JSONResponse:
    return error_response(401, "unauthenticated", "Authentication is required")


def setup_required() -> JSONResponse:
    return error_response(409, "setup_required", "Create the first admin before using Akasha")


def auth_is_on(request: Request) -> bool:
    return getattr(request.app.state, "auth", "off") == "on"


def require_auth_mode(request: Request) -> None:
    if not auth_is_on(request):
        raise HTTPException(status_code=404, detail="Not Found")


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def has_credentialed_user(engine: Engine) -> bool:
    with engine.connect() as connection:
        return bool(
            connection.execute(
                text("SELECT EXISTS(SELECT 1 FROM users WHERE password_hash IS NOT NULL)")
            ).scalar_one()
        )


def _user_response(identity: SessionIdentity) -> UserResponse:
    return UserResponse(
        id=identity.user_id,
        username=identity.username,
        display_name=identity.display_name,
        is_admin=identity.is_admin,
    )


def peer_is_trusted(request: Request, configured_peers: list[str]) -> bool:
    if request.client is None:
        return False
    try:
        peer = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    for configured in configured_peers:
        try:
            if peer in ipaddress.ip_network(configured, strict=False):
                return True
        except ValueError:
            continue
    return False


def request_uses_https(request: Request) -> bool:
    override = request.app.state.cookie_secure
    if override is not None:
        return bool(override)
    scheme = request.url.scheme
    forwarded = request.headers.get("x-forwarded-proto")
    if forwarded and peer_is_trusted(request, request.app.state.trusted_proxy_peers):
        scheme = forwarded.split(",", 1)[0].strip().casefold()
    return scheme == "https"


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/",
        secure=request_uses_https(request),
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    response.set_cookie(
        COOKIE_NAME,
        "",
        max_age=0,
        expires=0,
        path="/",
        secure=request_uses_https(request),
        httponly=True,
        samesite="lax",
    )


class LoginRateLimiter:
    """A per-username and per-peer fixed window for failed logins."""

    def __init__(
        self,
        maximum: int,
        window_seconds: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.maximum = maximum
        self.window_seconds = window_seconds
        self.clock = clock
        self.failures: defaultdict[str, deque[float]] = defaultdict(deque)

    def _bucket(self, key: str) -> deque[float]:
        now = self.clock()
        bucket = self.failures[key]
        while bucket and bucket[0] <= now - self.window_seconds:
            bucket.popleft()
        return bucket

    def limited(self, username: str, peer: str) -> bool:
        return any(
            len(self._bucket(key)) >= self.maximum
            for key in (f"username:{username}", f"peer:{peer}")
        )

    def username_limited(self, username: str) -> bool:
        return len(self._bucket(f"username:{username}")) >= self.maximum

    def peer_limited(self, peer: str) -> bool:
        return len(self._bucket(f"peer:{peer}")) >= self.maximum

    def fail(self, username: str, peer: str) -> None:
        now = self.clock()
        self._bucket(f"username:{username}").append(now)
        self._bucket(f"peer:{peer}").append(now)


def _lookup_user(engine: Engine, username: str) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT id, username, display_name, password_hash, password_salt, is_admin "
                    "FROM users WHERE username = :username"
                ),
                {"username": username},
            )
            .mappings()
            .one_or_none()
        )
    return dict(row) if row is not None else None


# Unknown usernames pay one real scrypt too, so they do not disclose an account
# through response timing. The value is random at process start and never valid.
_DUMMY_CREDENTIAL = hash_password("timing-only-unusable-credential")


async def _credentials_match(user: dict[str, Any] | None, password: str) -> bool:
    digest = (
        str(user["password_hash"])
        if user is not None and user["password_hash"] is not None
        else _DUMMY_CREDENTIAL.digest
    )
    salt = (
        str(user["password_salt"])
        if user is not None and user["password_salt"] is not None
        else _DUMMY_CREDENTIAL.salt
    )
    verified = await off_loop(verify_password, password, digest, salt)
    return verified and user is not None and user["password_hash"] is not None


def _create_admin(
    engine: Engine,
    *,
    username: str,
    display_name: str | None,
    digest: str,
    salt: str,
    now: datetime | None = None,
) -> int | None:
    normalized = normalize_username(username)
    if not normalized:
        return None
    current = timestamp(now or utc_now())
    with engine.begin() as connection:
        result = connection.execute(
            text(
                "UPDATE users SET username = :username, display_name = :display_name, "
                "password_hash = :digest, password_salt = :salt, is_admin = 1, "
                "updated_at = :updated_at WHERE id = 1 AND NOT EXISTS "
                "(SELECT 1 FROM users WHERE password_hash IS NOT NULL)"
            ),
            {
                "username": normalized,
                "display_name": display_name.strip() if display_name else None,
                "digest": digest,
                "salt": salt,
                "updated_at": current,
            },
        )
    return 1 if result.rowcount == 1 else None


def bootstrap_admin(engine: Engine, username: str, password: SecretStr) -> bool:
    """Create startup credentials once, never overwrite an existing password."""
    if has_credentialed_user(engine):
        return False
    credential = hash_password(password.get_secret_value())
    return (
        _create_admin(
            engine,
            username=username,
            display_name=None,
            digest=credential.digest,
            salt=credential.salt,
        )
        is not None
    )


@router.post(
    "/login",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def login(
    body: LoginBody, request: Request, response: Response
) -> UserResponse | JSONResponse:
    require_auth_mode(request)
    username = normalize_username(body.username)
    user = _lookup_user(request.app.state.engine, username)
    peer = request.client.host if request.client is not None else "unknown"
    limiter: LoginRateLimiter = request.app.state.login_limiter
    if limiter.username_limited(username) or (user is None and limiter.peer_limited(peer)):
        return error_response(429, "login_rate_limited", "Too many failed login attempts")
    password_matches = await _credentials_match(user, body.password.get_secret_value())
    if not password_matches:
        if limiter.peer_limited(peer):
            return error_response(429, "login_rate_limited", "Too many failed login attempts")
        limiter.fail(username, peer)
        return unauthenticated()
    assert user is not None
    created = SessionStore(request.app.state.engine).create(
        int(user["id"]), user_agent=request.headers.get("user-agent")
    )
    set_session_cookie(response, request, created.token)
    return UserResponse(
        id=int(user["id"]),
        username=str(user["username"]),
        display_name=(str(user["display_name"]) if user["display_name"] is not None else None),
        is_admin=bool(user["is_admin"]),
    )


@router.delete(
    "/session",
    status_code=204,
    response_class=Response,
    responses={401: {"model": ErrorResponse}},
)
async def logout(request: Request) -> Response:
    require_auth_mode(request)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        SessionStore(request.app.state.engine).delete(token)
    response = Response(status_code=204)
    clear_session_cookie(response, request)
    return response


@router.get("/me", response_model=MeResponse, responses={401: {"model": ErrorResponse}})
async def me(request: Request) -> MeResponse:
    require_auth_mode(request)
    needs_setup = not has_credentialed_user(request.app.state.engine)
    token = request.cookies.get(COOKIE_NAME)
    identity = SessionStore(request.app.state.engine).lookup(token) if token else None
    return MeResponse(
        auth="on",
        authenticated=identity is not None,
        setup_required=needs_setup,
        user=_user_response(identity) if identity is not None else None,
    )


@router.post(
    "/setup",
    response_model=UserResponse,
    responses={409: {"model": ErrorResponse}},
)
async def setup(
    body: SetupBody, request: Request, response: Response
) -> UserResponse | JSONResponse:
    require_auth_mode(request)
    credential = await off_loop(hash_password, body.password.get_secret_value())
    user_id = _create_admin(
        request.app.state.engine,
        username=body.username,
        display_name=body.display_name,
        digest=credential.digest,
        salt=credential.salt,
    )
    if user_id is None:
        return error_response(409, "setup_already_completed", "Initial setup is already complete")
    created = SessionStore(request.app.state.engine).create(
        user_id, user_agent=request.headers.get("user-agent")
    )
    set_session_cookie(response, request, created.token)
    user = _lookup_user(request.app.state.engine, normalize_username(body.username))
    assert user is not None
    return UserResponse(
        id=user_id,
        username=str(user["username"]),
        display_name=(str(user["display_name"]) if user["display_name"] is not None else None),
        is_admin=True,
    )
