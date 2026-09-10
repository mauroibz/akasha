"""Opaque, revocable server-side sessions (DEC-146, Sprint 077)."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text

SESSION_LIFETIME = timedelta(days=400)
# A busy library can make dozens of authenticated reads for one screen. One
# durable refresh per device per day keeps annual-login semantics without
# turning all of those reads into SQLite writes.
SESSION_REFRESH_INTERVAL = timedelta(days=1)
SESSION_COOKIE_NAME = "akasha_session"
_MISSING_TOKEN_HASH = "0" * 64


def utc_now() -> datetime:
    return datetime.now(UTC)


def timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()


@dataclass(frozen=True, slots=True)
class CreatedSession:
    id: str
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    session_id: str
    user_id: int
    username: str
    display_name: str | None
    is_admin: bool
    acting_as_user_id: int | None
    acting_as_username: str | None
    acting_as_display_name: str | None
    acting_as_is_admin: bool | None
    refreshed: bool = False
class SessionStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create(
        self,
        user_id: int,
        *,
        user_agent: str | None = None,
        now: datetime | None = None,
    ) -> CreatedSession:
        current = now or utc_now()
        expires_at = current + SESSION_LIFETIME
        token = secrets.token_urlsafe(32)
        session_id = secrets.token_urlsafe(18)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(id, user_id, token_hash, created_at, last_seen_at, expires_at, user_agent) "
                    "VALUES (:id, :user_id, :token_hash, :created_at, :last_seen_at, "
                    ":expires_at, :user_agent)"
                ),
                {
                    "id": session_id,
                    "user_id": user_id,
                    "token_hash": token_hash(token),
                    "created_at": timestamp(current),
                    "last_seen_at": timestamp(current),
                    "expires_at": timestamp(expires_at),
                    "user_agent": user_agent,
                },
            )
        return CreatedSession(id=session_id, token=token, expires_at=expires_at)

    def lookup(self, token: str, *, now: datetime | None = None) -> SessionIdentity | None:
        current = now or utc_now()
        digest = token_hash(token)
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT sessions.id, sessions.token_hash, sessions.last_seen_at, "
                        "sessions.expires_at, "
                        "users.id AS user_id, users.username, users.display_name, users.is_admin, "
                        "target.id AS acting_as_user_id, target.username AS acting_as_username, "
                        "target.display_name AS acting_as_display_name, "
                        "target.is_admin AS acting_as_is_admin "
                        "FROM sessions JOIN users ON users.id = sessions.user_id "
                        "LEFT JOIN users target ON target.id = sessions.acting_as_user_id "
                        "WHERE sessions.token_hash = :token_hash"
                    ),
                    {"token_hash": digest},
                )
                .mappings()
                .one_or_none()
            )

        # Both a miss and an expired hit pay the same constant-time comparison.
        candidate = str(row["token_hash"]) if row is not None else _MISSING_TOKEN_HASH
        matches = secrets.compare_digest(digest, candidate)
        if row is None or not matches or parse_timestamp(str(row["expires_at"])) <= current:
            return None

        refreshed = False
        if parse_timestamp(str(row["last_seen_at"])) <= current - SESSION_REFRESH_INTERVAL:
            with self.engine.begin() as connection:
                result = connection.execute(
                    text(
                        "UPDATE sessions SET last_seen_at = :seen, expires_at = :expires "
                        "WHERE id = :id AND last_seen_at = :previous_seen"
                    ),
                    {
                        "seen": timestamp(current),
                        "expires": timestamp(current + SESSION_LIFETIME),
                        "id": row["id"],
                        "previous_seen": row["last_seen_at"],
                    },
                )
            refreshed = result.rowcount == 1
        return SessionIdentity(
            session_id=str(row["id"]),
            user_id=int(row["user_id"]),
            username=str(row["username"]),
            display_name=(str(row["display_name"]) if row["display_name"] is not None else None),
            is_admin=bool(row["is_admin"]),
            acting_as_user_id=(
                int(row["acting_as_user_id"])
                if row["acting_as_user_id"] is not None and bool(row["is_admin"])
                else None
            ),
            acting_as_username=(
                str(row["acting_as_username"])
                if row["acting_as_username"] is not None and bool(row["is_admin"])
                else None
            ),
            acting_as_display_name=(
                str(row["acting_as_display_name"])
                if row["acting_as_display_name"] is not None and bool(row["is_admin"])
                else None
            ),
            acting_as_is_admin=(
                bool(row["acting_as_is_admin"])
                if row["acting_as_is_admin"] is not None and bool(row["is_admin"])
                else None
            ),
            refreshed=refreshed,
        )

    def set_acting_as(self, token: str, user_id: int) -> int:
        """Point exactly the cookie's session at a target user."""
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    "UPDATE sessions SET acting_as_user_id = :target WHERE token_hash = :token_hash"
                ),
                {"target": user_id, "token_hash": token_hash(token)},
            )
        return int(result.rowcount)

    def clear_acting_as(self, token: str) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    "UPDATE sessions SET acting_as_user_id = NULL "
                    "WHERE token_hash = :token_hash AND acting_as_user_id IS NOT NULL"
                ),
                {"token_hash": token_hash(token)},
            )
        return int(result.rowcount)

    def clear_acting_as_for_user(self, user_id: int) -> int:
        """End modes owned by, or aimed at, a user whose identity changed."""
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    "UPDATE sessions SET acting_as_user_id = NULL "
                    "WHERE acting_as_user_id = :user_id "
                    "OR (user_id = :user_id AND acting_as_user_id IS NOT NULL)"
                ),
                {"user_id": user_id},
            )
        return int(result.rowcount)

    def delete(self, token: str) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(
                text("DELETE FROM sessions WHERE token_hash = :token_hash"),
                {"token_hash": token_hash(token)},
            )
        return int(result.rowcount)

    def delete_all(self, user_id: int) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(
                text("DELETE FROM sessions WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
        return int(result.rowcount)

    def delete_other(self, user_id: int, current_token: str) -> int:
        """Revoke a user's other sessions while preserving the request doing it."""
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    "DELETE FROM sessions WHERE user_id = :user_id "
                    "AND token_hash != :current_token_hash"
                ),
                {"user_id": user_id, "current_token_hash": token_hash(current_token)},
            )
        return int(result.rowcount)

    def expire(self, *, now: datetime | None = None) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(
                text("DELETE FROM sessions WHERE expires_at <= :now"),
                {"now": timestamp(now or utc_now())},
            )
        return int(result.rowcount)
