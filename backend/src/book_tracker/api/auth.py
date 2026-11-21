"""Password login, first-run setup, and cookie policy (Sprint 077)."""

from __future__ import annotations

import hmac
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from book_tracker.api.identity import (
    SECURE_SESSION_COOKIE_NAME,
    AdminUser,
    CurrentUser,
    client_address,
    peer_is_trusted,
    request_uses_https,
    session_cookie_name,
    session_store,
    session_token,
)
from book_tracker.api.library import ErrorResponse
from book_tracker.application.library import LibraryError
from book_tracker.application.passwords import hash_password, verify_password
from book_tracker.application.sessions import (
    SESSION_COOKIE_NAME,
    SESSION_LIFETIME,
    SessionIdentity,
    timestamp,
    utc_now,
)
from book_tracker.infrastructure.offload import off_loop

COOKIE_NAME = SESSION_COOKIE_NAME
SECURE_COOKIE_NAME = SECURE_SESSION_COOKIE_NAME
#: The shortest password a new credential may have (Sprint 128, F11). Sign-in
#: keeps accepting whatever was set before, so no existing account is locked out.
MIN_PASSWORD_LENGTH = 12

__all__ = [
    "COOKIE_NAME",
    "SECURE_COOKIE_NAME",
    "LoginRateLimiter",
    "client_address",
    "peer_is_trusted",
    "request_uses_https",
]
router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])


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


NewPassword = Annotated[SecretStr, Field(min_length=MIN_PASSWORD_LENGTH, max_length=1024)]


class SetupBody(LoginBody):
    password: NewPassword
    display_name: str | None = Field(default=None, max_length=100)
    #: Printed in the server log at start (F4); without it setup answers 403.
    setup_code: SecretStr | None = Field(default=None, max_length=200)


class MeResponse(BaseModel):
    auth: str
    authenticated: bool
    setup_required: bool
    user: UserResponse | None
    acting_as: UserResponse | None


class SessionResponse(BaseModel):
    id: str
    created_at: datetime
    last_seen_at: datetime
    user_agent: str | None
    current: bool


class UserSummary(UserResponse):
    entry_count: int
    shelf_count: int


class CreateUserBody(LoginBody):
    password: NewPassword
    display_name: str | None = Field(default=None, max_length=100)
    is_admin: bool = False


class UpdateUserBody(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    is_admin: bool | None = None
    password: NewPassword | None = None


class ChangePasswordBody(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: NewPassword


class DeleteUserBody(BaseModel):
    action: Literal["transfer", "delete"]
    transfer_to_user_id: int | None = None


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


def _acting_as_response(identity: SessionIdentity) -> UserResponse | None:
    if identity.acting_as_user_id is None or identity.acting_as_username is None:
        return None
    return UserResponse(
        id=identity.acting_as_user_id,
        username=identity.acting_as_username,
        display_name=identity.acting_as_display_name,
        is_admin=bool(identity.acting_as_is_admin),
    )


def strip_untrusted_identity_header(
    request: Request, configured_header: str | None, configured_peers: list[str]
) -> None:
    """Remove an asserted identity before any inner application code can see it."""
    if not configured_header or peer_is_trusted(request, configured_peers):
        return
    target = configured_header.casefold().encode("latin-1")
    request.scope["headers"] = [
        (name, value) for name, value in request.scope.get("headers", []) if name.lower() != target
    ]


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    # `__Host-` when Secure: Path=/ and no Domain, which the browser enforces (F12).
    lifetime = getattr(request.app.state, "session_lifetime", SESSION_LIFETIME)
    response.set_cookie(
        session_cookie_name(request),
        token,
        max_age=int(lifetime.total_seconds()),
        path="/",
        secure=request_uses_https(request),
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    response.set_cookie(
        session_cookie_name(request),
        "",
        max_age=0,
        expires=0,
        path="/",
        secure=request_uses_https(request),
        httponly=True,
        samesite="lax",
    )


class LoginRateLimiter:
    """Failed password checks, counted per (username, client), username and client.

    Sprint 128 (F3, F10, F21) redesigned it around four rules:

    - a limited request is refused *before* any password is verified, so a 429
      says nothing about whether the guess was right, and it is still counted;
    - the lock that stops a guesser is the (username, client) pair, so the owner
      signing in from another address is not refused while someone else is;
    - a username-wide cap (``username_factor`` times the pair maximum) bounds a
      distributed attack, and a per-client cap bounds one client spraying names;
    - memory is bounded: checks never create a bucket, expired buckets are
      dropped, and past ``max_keys`` the oldest bucket is evicted.
    """

    def __init__(
        self,
        maximum: int,
        window_seconds: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        username_factor: int = 10,
        client_factor: int = 4,
        max_keys: int = 10_000,
    ) -> None:
        self.maximum = maximum
        self.window_seconds = window_seconds
        self.clock = clock
        self.username_maximum = maximum * username_factor
        self.client_maximum = maximum * client_factor
        self.max_keys = max_keys
        self._buckets: OrderedDict[str, deque[float]] = OrderedDict()

    def _keys(self, username: str, client: str) -> tuple[tuple[str, int], ...]:
        return (
            (f"pair:{username}\x00{client}", self.maximum),
            (f"username:{username}", self.username_maximum),
            (f"client:{client}", self.client_maximum),
        )

    def _count(self, key: str, now: float) -> int:
        bucket = self._buckets.get(key)
        if bucket is None:
            return 0
        while bucket and bucket[0] <= now - self.window_seconds:
            bucket.popleft()
        if not bucket:
            del self._buckets[key]
            return 0
        return len(bucket)

    def _record(self, key: str, limit: int, now: float) -> None:
        self._count(key, now)
        bucket = self._buckets.get(key)
        if bucket is None:
            while len(self._buckets) >= self.max_keys:
                self._buckets.popitem(last=False)
            bucket = self._buckets[key] = deque(maxlen=limit)
        else:
            self._buckets.move_to_end(key)
        bucket.append(now)

    def limited(self, username: str, client: str) -> bool:
        now = self.clock()
        return any(self._count(key, now) >= limit for key, limit in self._keys(username, client))

    def fail(self, username: str, client: str) -> None:
        now = self.clock()
        for key, limit in self._keys(username, client):
            self._record(key, limit, now)

    def refused(self, username: str, client: str) -> None:
        """Count an attempt made while limited, without verifying it.

        The pair and client buckets keep filling, so a client that keeps
        hammering stays refused; the username-wide bucket does not, so one
        refused client cannot by itself lock the owner out from everywhere.
        """
        now = self.clock()
        pair, _username, client_key = self._keys(username, client)
        for key, limit in (pair, client_key):
            self._record(key, limit, now)

    def succeed(self, username: str, client: str) -> None:
        self._buckets.pop(self._keys(username, client)[0][0], None)

    def prune(self) -> None:
        now = self.clock()
        for key in list(self._buckets):
            self._count(key, now)

    def key_count(self) -> int:
        return len(self._buckets)


#: The limiter's "username" for setup-code guesses, which no real account can
#: have (usernames are normalized visible text; this holds a NUL).
SETUP_LIMIT_KEY = "\x00setup"


def rate_limited() -> JSONResponse:
    return error_response(429, "login_rate_limited", "Too many failed login attempts")


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


def trusted_header_user(
    engine: Engine, asserted_identity: str, *, autocreate: bool
) -> dict[str, Any] | None:
    """Resolve a normalized proxy identity, optionally creating its empty account."""
    username = normalize_username(asserted_identity)
    if not username or len(username) > 100:
        return None
    existing = _lookup_user(engine, username)
    if existing is not None or not autocreate:
        return existing
    now = timestamp(utc_now())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(username,display_name,password_hash,password_salt,is_admin,"
                    "created_at,updated_at) "
                    "VALUES (:username,NULL,NULL,NULL,0,:now,:now)"
                ),
                {"username": username, "now": now},
            )
    except IntegrityError:
        # Another request from the same new device may have won the insert.
        pass
    return _lookup_user(engine, username)


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
    client = client_address(request)
    limiter: LoginRateLimiter = request.app.state.login_limiter
    # Refused before any verification, and counted: a 429 never says whether
    # the guess was right (F3).
    if limiter.limited(username, client):
        limiter.refused(username, client)
        return rate_limited()
    user = await off_loop(_lookup_user, request.app.state.engine, username)
    password_matches = await _credentials_match(user, body.password.get_secret_value())
    if not password_matches:
        limiter.fail(username, client)
        return unauthenticated()
    assert user is not None
    limiter.succeed(username, client)
    store = session_store(request)
    presented = session_token(request)
    if presented:
        # A session the browser arrived with is never carried across a sign-in:
        # it may have been planted (session fixation, F21).
        await off_loop(store.delete, presented)
    request.state.suppress_session_cookie = True
    created = await off_loop(
        store.create,
        int(user["id"]),
        user_agent=request.headers.get("user-agent"),
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
def logout(request: Request) -> Response:
    require_auth_mode(request)
    token = session_token(request)
    if token:
        session_store(request).delete(token)
    response = Response(status_code=204)
    clear_session_cookie(response, request)
    return response


@router.get(
    "/sessions",
    response_model=list[SessionResponse],
    responses={401: {"model": ErrorResponse}},
)
def list_sessions(request: Request, user: CurrentUser) -> list[SessionResponse]:
    require_auth_mode(request)
    current_session_id = getattr(request.state, "session_id", None)
    return [
        SessionResponse(
            id=session.id,
            created_at=session.created_at,
            last_seen_at=session.last_seen_at,
            user_agent=session.user_agent,
            current=session.id == current_session_id,
        )
        for session in session_store(request).list_for_user(user.user_id)
    ]


@router.delete(
    "/sessions",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={401: {"model": ErrorResponse}},
)
def logout_everywhere(request: Request, user: CurrentUser) -> Response:
    require_auth_mode(request)
    session_store(request).delete_all(user.user_id)
    request.state.suppress_session_cookie = True
    response = Response(status_code=204)
    clear_session_cookie(response, request)
    return response


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def revoke_session(session_id: str, request: Request, user: CurrentUser) -> Response:
    require_auth_mode(request)
    if session_store(request).delete_for_user(user.user_id, session_id) != 1:
        raise LibraryError("session_not_found", "Session was not found", status_code=404)
    response = Response(status_code=204)
    if session_id == getattr(request.state, "session_id", None):
        request.state.suppress_session_cookie = True
        clear_session_cookie(response, request)
    return response


@router.get("/me", response_model=MeResponse, responses={401: {"model": ErrorResponse}})
def me(request: Request) -> MeResponse:
    require_auth_mode(request)
    needs_setup = not has_credentialed_user(request.app.state.engine)
    identity = getattr(request.state, "session_identity", None)
    if not isinstance(identity, SessionIdentity):
        token = session_token(request)
        identity = session_store(request).lookup(token) if token else None
    return MeResponse(
        auth="on",
        authenticated=identity is not None,
        setup_required=needs_setup,
        user=_user_response(identity) if identity is not None else None,
        acting_as=_acting_as_response(identity) if identity is not None else None,
    )


@router.post(
    "/setup",
    response_model=UserResponse,
    responses={
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def setup(
    body: SetupBody, request: Request, response: Response
) -> UserResponse | JSONResponse:
    require_auth_mode(request)
    if await off_loop(has_credentialed_user, request.app.state.engine):
        return error_response(409, "setup_already_completed", "Initial setup is already complete")
    client = client_address(request)
    limiter: LoginRateLimiter = request.app.state.login_limiter
    if limiter.limited(SETUP_LIMIT_KEY, client):
        limiter.refused(SETUP_LIMIT_KEY, client)
        return rate_limited()
    expected = getattr(request.app.state, "setup_code", None)
    provided = body.setup_code.get_secret_value().strip() if body.setup_code else ""
    if not (
        isinstance(expected, str)
        and expected
        and hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
    ):
        limiter.fail(SETUP_LIMIT_KEY, client)
        return error_response(
            403,
            "setup_code_invalid",
            "Enter the setup code printed in the server log when Akasha started",
        )
    credential = await off_loop(hash_password, body.password.get_secret_value())
    user_id = await off_loop(
        _create_admin,
        request.app.state.engine,
        username=body.username,
        display_name=body.display_name,
        digest=credential.digest,
        salt=credential.salt,
    )
    if user_id is None:
        return error_response(409, "setup_already_completed", "Initial setup is already complete")
    request.app.state.setup_code = None
    created = await off_loop(
        session_store(request).create,
        user_id,
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, request, created.token)
    user = await off_loop(_lookup_user, request.app.state.engine, normalize_username(body.username))
    assert user is not None
    return UserResponse(
        id=user_id,
        username=str(user["username"]),
        display_name=(str(user["display_name"]) if user["display_name"] is not None else None),
        is_admin=True,
    )


def _strip_display_name(value: str | None) -> str | None:
    stripped = value.strip() if value else ""
    return stripped or None


def _user_by_id(engine: Engine, user_id: int) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT id, username, display_name, password_hash, password_salt, is_admin "
                    "FROM users WHERE id=:user_id"
                ),
                {"user_id": user_id},
            )
            .mappings()
            .one_or_none()
        )
    return dict(row) if row is not None else None


def _management_response(row: dict[str, Any]) -> UserResponse:
    return UserResponse(
        id=int(row["id"]),
        username=str(row["username"]),
        display_name=str(row["display_name"]) if row["display_name"] is not None else None,
        is_admin=bool(row["is_admin"]),
    )


@users_router.get("", response_model=list[UserSummary], responses={403: {"model": ErrorResponse}})
def list_users(request: Request, _admin: AdminUser) -> list[UserSummary]:
    require_auth_mode(request)
    with request.app.state.engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT users.id, users.username, users.display_name, users.is_admin, "
                "(SELECT count(*) FROM entries WHERE entries.user_id=users.id) entry_count, "
                "(SELECT count(*) FROM shelves WHERE shelves.user_id=users.id) shelf_count "
                "FROM users ORDER BY users.id"
            )
        ).mappings()
        return [UserSummary(**dict(row)) for row in rows]


@users_router.post(
    "",
    status_code=201,
    response_model=UserResponse,
    responses={403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def create_user(body: CreateUserBody, request: Request, _admin: AdminUser) -> UserResponse:
    require_auth_mode(request)
    username = normalize_username(body.username)
    credential = await off_loop(hash_password, body.password.get_secret_value())
    now = timestamp(utc_now())

    def persist() -> dict[str, Any]:
        try:
            with request.app.state.engine.begin() as connection:
                result = connection.execute(
                    text(
                        "INSERT INTO users (username,display_name,password_hash,password_salt,"
                        "is_admin,created_at,updated_at) VALUES "
                        "(:username,:display_name,:digest,:salt,:is_admin,:now,:now)"
                    ),
                    {
                        "username": username,
                        "display_name": _strip_display_name(body.display_name),
                        "digest": credential.digest,
                        "salt": credential.salt,
                        "is_admin": int(body.is_admin),
                        "now": now,
                    },
                )
                user_id = int(result.lastrowid or 0)
        except IntegrityError as error:
            raise LibraryError(
                "validation_error",
                "Username is already in use",
                status_code=422,
                details={"field": "username"},
            ) from error
        row = _user_by_id(request.app.state.engine, user_id)
        assert row is not None
        return row

    row = await off_loop(persist)
    return _management_response(row)


@users_router.patch(
    "/{user_id}",
    response_model=UserResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_user(
    user_id: int, body: UpdateUserBody, request: Request, _admin: AdminUser
) -> UserResponse:
    require_auth_mode(request)
    # Hashed first, on its own bounded thread: the rest is one short synchronous unit.
    credential = (
        await off_loop(hash_password, body.password.get_secret_value())
        if body.password is not None
        else None
    )

    def persist() -> dict[str, Any]:
        current = _user_by_id(request.app.state.engine, user_id)
        if current is None:
            raise LibraryError("user_not_found", "User was not found", status_code=404)
        demoting = body.is_admin is False and bool(current["is_admin"])
        if demoting:
            with request.app.state.engine.connect() as connection:
                admins = int(
                    connection.execute(
                        text("SELECT count(*) FROM users WHERE is_admin=1")
                    ).scalar_one()
                )
            if admins == 1:
                raise LibraryError(
                    "last_admin", "The last admin cannot be demoted", status_code=409
                )
        values: dict[str, Any] = {"user_id": user_id, "updated_at": timestamp(utc_now())}
        assignments: list[str] = []
        if "display_name" in body.model_fields_set:
            assignments.append("display_name=:display_name")
            values["display_name"] = _strip_display_name(body.display_name)
        if body.is_admin is not None:
            assignments.append("is_admin=:is_admin")
            values["is_admin"] = int(body.is_admin)
        if credential is not None:
            assignments.extend(("password_hash=:digest", "password_salt=:salt"))
            values.update(digest=credential.digest, salt=credential.salt)
        if assignments:
            assignments.append("updated_at=:updated_at")
            with request.app.state.engine.begin() as connection:
                connection.execute(
                    text(f"UPDATE users SET {','.join(assignments)} WHERE id=:user_id"), values
                )
            if credential is not None:
                session_store(request).clear_acting_as_for_user(user_id)
                session_store(request).delete_all(user_id)
            elif demoting:
                session_store(request).clear_acting_as_for_user(user_id)
        row = _user_by_id(request.app.state.engine, user_id)
        assert row is not None
        return row

    row = await off_loop(persist)
    return _management_response(row)


@router.patch(
    "/password",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def change_password(
    body: ChangePasswordBody, request: Request, user: CurrentUser
) -> Response | JSONResponse:
    require_auth_mode(request)
    client = client_address(request)
    limiter: LoginRateLimiter = request.app.state.login_limiter
    if limiter.limited(user.username, client):
        limiter.refused(user.username, client)
        return rate_limited()
    row = await off_loop(_user_by_id, request.app.state.engine, user.user_id)
    if not await _credentials_match(row, body.current_password.get_secret_value()):
        limiter.fail(user.username, client)
        return unauthenticated()
    credential = await off_loop(hash_password, body.new_password.get_secret_value())
    store = session_store(request)

    def persist() -> str:
        with request.app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE users SET password_hash=:digest,password_salt=:salt,updated_at=:now "
                    "WHERE id=:user_id"
                ),
                {
                    "digest": credential.digest,
                    "salt": credential.salt,
                    "now": timestamp(utc_now()),
                    "user_id": user.user_id,
                },
            )
        # Every session ends, the current one included, and the device doing
        # this gets a fresh one: a token stolen before the change is worth nothing
        # after it (F21).
        store.delete_all(user.user_id)
        return store.create(user.user_id, user_agent=request.headers.get("user-agent")).token

    new_token = await off_loop(persist)
    request.state.suppress_session_cookie = True
    response = Response(status_code=204)
    set_session_cookie(response, request, new_token)
    return response


@router.post(
    "/act-as/{user_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def start_acting_as(user_id: int, request: Request, admin: AdminUser) -> Response:
    require_auth_mode(request)
    target = _user_by_id(request.app.state.engine, user_id)
    if target is None:
        raise LibraryError("user_not_found", "User was not found", status_code=404)
    if user_id == admin.user_id:
        raise LibraryError(
            "invalid_acting_user", "Choose another person's library", status_code=422
        )
    token = session_token(request)
    if token is None or session_store(request).set_acting_as(token, user_id) != 1:
        return unauthenticated()
    return Response(status_code=204)


@router.delete(
    "/act-as",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={403: {"model": ErrorResponse}},
)
def stop_acting_as(request: Request, _admin: AdminUser) -> Response:
    require_auth_mode(request)
    token = session_token(request)
    if token is None:
        return unauthenticated()
    session_store(request).clear_acting_as(token)
    return Response(status_code=204)


def _transfer_conflict(connection: Any, user_id: int, target_id: int) -> str | None:
    duplicate_item = connection.execute(
        text(
            "SELECT 1 FROM entries source JOIN entries target ON target.item_id=source.item_id "
            "WHERE source.user_id=:source AND target.user_id=:target LIMIT 1"
        ),
        {"source": user_id, "target": target_id},
    ).first()
    if duplicate_item:
        return "Both libraries contain the same item"
    duplicate_shelf = connection.execute(
        text(
            "SELECT 1 FROM shelves source JOIN shelves target ON target.slug=source.slug "
            "WHERE source.user_id=:source AND target.user_id=:target LIMIT 1"
        ),
        {"source": user_id, "target": target_id},
    ).first()
    if duplicate_shelf:
        return "Both libraries contain the same shelf name"
    duplicate_import = connection.execute(
        text(
            "SELECT 1 FROM import_batches source JOIN import_batches target "
            "ON target.kind=source.kind AND target.fingerprint=source.fingerprint "
            "WHERE source.user_id=:source AND target.user_id=:target LIMIT 1"
        ),
        {"source": user_id, "target": target_id},
    ).first()
    return "Both libraries contain the same import" if duplicate_import else None


@users_router.delete(
    "/{user_id}",
    status_code=204,
    response_class=Response,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def delete_user(
    user_id: int,
    request: Request,
    admin: AdminUser,
    body: Annotated[DeleteUserBody, Body()],
) -> Response:
    require_auth_mode(request)
    if user_id == admin.user_id:
        raise LibraryError("self_delete", "You cannot delete yourself", status_code=409)
    if _user_by_id(request.app.state.engine, user_id) is None:
        raise LibraryError("user_not_found", "User was not found", status_code=404)
    with request.app.state.engine.begin() as connection:
        if body.action == "transfer":
            target_id = body.transfer_to_user_id
            target = _user_by_id(request.app.state.engine, target_id) if target_id else None
            if target_id is None or target_id == user_id or target is None:
                raise LibraryError(
                    "invalid_transfer",
                    "Choose another existing user to receive the library",
                    status_code=422,
                    details={"field": "transfer_to_user_id"},
                )
            conflict = _transfer_conflict(connection, user_id, target_id)
            if conflict:
                raise LibraryError("transfer_conflict", conflict, status_code=409)
            for table in (
                "entries",
                "shelves",
                "import_batches",
                "import_records",
                "import_effects",
                "jobs",
            ):
                connection.execute(
                    text(f"UPDATE {table} SET user_id=:target WHERE user_id=:source"),
                    {"target": target_id, "source": user_id},
                )
        else:
            connection.execute(text("DELETE FROM jobs WHERE user_id=:user"), {"user": user_id})
            connection.execute(
                text("DELETE FROM import_batches WHERE user_id=:user"), {"user": user_id}
            )
            connection.execute(text("DELETE FROM entries WHERE user_id=:user"), {"user": user_id})
            connection.execute(text("DELETE FROM shelves WHERE user_id=:user"), {"user": user_id})
        connection.execute(text("DELETE FROM users WHERE id=:user"), {"user": user_id})
    return Response(status_code=204)
