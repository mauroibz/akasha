"""Password login, first-run setup, and cookie policy (Sprint 077)."""

from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from book_tracker.api.identity import AdminUser, CurrentUser
from book_tracker.api.library import ErrorResponse
from book_tracker.application.library import LibraryError
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


class SetupBody(LoginBody):
    display_name: str | None = Field(default=None, max_length=100)


class MeResponse(BaseModel):
    auth: str
    authenticated: bool
    setup_required: bool
    user: UserResponse | None
    acting_as: UserResponse | None


class UserSummary(UserResponse):
    entry_count: int
    shelf_count: int


class CreateUserBody(LoginBody):
    display_name: str | None = Field(default=None, max_length=100)
    is_admin: bool = False


class UpdateUserBody(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    is_admin: bool | None = None
    password: SecretStr | None = Field(default=None, min_length=1, max_length=1024)


class ChangePasswordBody(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(min_length=1, max_length=1024)


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
        acting_as=_acting_as_response(identity) if identity is not None else None,
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
async def list_users(request: Request, _admin: AdminUser) -> list[UserSummary]:
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
    current = _user_by_id(request.app.state.engine, user_id)
    if current is None:
        raise LibraryError("user_not_found", "User was not found", status_code=404)
    if body.is_admin is False and bool(current["is_admin"]):
        with request.app.state.engine.connect() as connection:
            admins = int(
                connection.execute(text("SELECT count(*) FROM users WHERE is_admin=1")).scalar_one()
            )
        if admins == 1:
            raise LibraryError("last_admin", "The last admin cannot be demoted", status_code=409)
    values: dict[str, Any] = {"user_id": user_id, "updated_at": timestamp(utc_now())}
    assignments: list[str] = []
    if "display_name" in body.model_fields_set:
        assignments.append("display_name=:display_name")
        values["display_name"] = _strip_display_name(body.display_name)
    if body.is_admin is not None:
        assignments.append("is_admin=:is_admin")
        values["is_admin"] = int(body.is_admin)
    if body.password is not None:
        credential = await off_loop(hash_password, body.password.get_secret_value())
        assignments.extend(("password_hash=:digest", "password_salt=:salt"))
        values.update(digest=credential.digest, salt=credential.salt)
    if assignments:
        assignments.append("updated_at=:updated_at")
        with request.app.state.engine.begin() as connection:
            connection.execute(
                text(f"UPDATE users SET {','.join(assignments)} WHERE id=:user_id"), values
            )
        if body.password is not None:
            SessionStore(request.app.state.engine).clear_acting_as_for_user(user_id)
            SessionStore(request.app.state.engine).delete_all(user_id)
        elif body.is_admin is False:
            SessionStore(request.app.state.engine).clear_acting_as_for_user(user_id)
    row = _user_by_id(request.app.state.engine, user_id)
    assert row is not None
    return _management_response(row)


@router.patch(
    "/password",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={401: {"model": ErrorResponse}},
)
async def change_password(
    body: ChangePasswordBody, request: Request, user: CurrentUser
) -> Response | JSONResponse:
    require_auth_mode(request)
    row = _user_by_id(request.app.state.engine, user.user_id)
    if not await _credentials_match(row, body.current_password.get_secret_value()):
        return unauthenticated()
    credential = await off_loop(hash_password, body.new_password.get_secret_value())
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
    token = request.cookies.get(COOKIE_NAME)
    SessionStore(request.app.state.engine).clear_acting_as_for_user(user.user_id)
    if token:
        SessionStore(request.app.state.engine).delete_other(user.user_id, token)
    return Response(status_code=204)


@router.post(
    "/act-as/{user_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def start_acting_as(user_id: int, request: Request, admin: AdminUser) -> Response:
    require_auth_mode(request)
    target = _user_by_id(request.app.state.engine, user_id)
    if target is None:
        raise LibraryError("user_not_found", "User was not found", status_code=404)
    if user_id == admin.user_id:
        raise LibraryError(
            "invalid_acting_user", "Choose another person's library", status_code=422
        )
    token = request.cookies.get(COOKIE_NAME)
    if token is None or SessionStore(request.app.state.engine).set_acting_as(token, user_id) != 1:
        return unauthenticated()
    return Response(status_code=204)


@router.delete(
    "/act-as",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={403: {"model": ErrorResponse}},
)
async def stop_acting_as(request: Request, _admin: AdminUser) -> Response:
    require_auth_mode(request)
    token = request.cookies.get(COOKIE_NAME)
    if token is None:
        return unauthenticated()
    SessionStore(request.app.state.engine).clear_acting_as(token)
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
async def delete_user(
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
