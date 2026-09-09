"""Opaque, revocable server-side sessions (DEC-146, Sprint 077)."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text

SESSION_LIFETIME = timedelta(days=400)
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
                        "SELECT sessions.id, sessions.token_hash, sessions.expires_at, "
                        "users.id AS user_id, users.username, users.display_name, users.is_admin "
                        "FROM sessions JOIN users ON users.id = sessions.user_id "
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

        with self.engine.begin() as connection:
            connection.execute(
                text("UPDATE sessions SET last_seen_at = :seen WHERE id = :id"),
                {"seen": timestamp(current), "id": row["id"]},
            )
        return SessionIdentity(
            session_id=str(row["id"]),
            user_id=int(row["user_id"]),
            username=str(row["username"]),
            display_name=(str(row["display_name"]) if row["display_name"] is not None else None),
            is_admin=bool(row["is_admin"]),
        )

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
