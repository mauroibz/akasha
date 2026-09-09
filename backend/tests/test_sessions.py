from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

import book_tracker.application.sessions as sessions_module
from book_tracker.application.sessions import SESSION_LIFETIME, SessionStore
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.migrations import upgrade


def engine_at(tmp_path: Path):  # type: ignore[no-untyped-def]
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    return create_engine(configured)


def test_session_create_lookup_refresh_expire_and_delete(tmp_path: Path) -> None:
    engine = engine_at(tmp_path)
    store = SessionStore(engine)
    started = datetime(2026, 9, 8, 12, tzinfo=UTC)

    created = store.create(1, user_agent="Phone browser", now=started)
    assert len(created.token) >= 43
    assert created.expires_at == started + SESSION_LIFETIME

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT token_hash, last_seen_at, expires_at, user_agent FROM sessions")
        ).one()
    assert created.token not in row.token_hash
    assert row.user_agent == "Phone browser"

    seen = store.lookup(created.token, now=started + timedelta(hours=2))
    assert seen is not None
    assert seen.user_id == 1
    assert seen.username == "admin"
    with engine.connect() as connection:
        refreshed = connection.execute(text("SELECT last_seen_at, expires_at FROM sessions")).one()
    assert refreshed.last_seen_at != row.last_seen_at
    assert refreshed.expires_at == row.expires_at

    assert store.lookup(created.token, now=started + SESSION_LIFETIME) is None
    assert store.expire(now=started + SESSION_LIFETIME) == 1

    replacement = store.create(1, now=started)
    assert store.delete(replacement.token) == 1
    assert store.lookup(replacement.token, now=started) is None

    first = store.create(1, now=started)
    second = store.create(1, now=started)
    assert store.delete_all(1) == 2
    assert store.lookup(first.token, now=started) is None
    assert store.lookup(second.token, now=started) is None


def test_missing_and_expired_lookup_pay_the_same_digest_comparison(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    engine = engine_at(tmp_path)
    store = SessionStore(engine)
    started = datetime(2024, 1, 1, tzinfo=UTC)
    expired = store.create(1, now=started)
    compared: list[tuple[int, int]] = []
    original = sessions_module.secrets.compare_digest

    def recording_compare(left: str, right: str) -> bool:
        compared.append((len(left), len(right)))
        return original(left, right)

    monkeypatch.setattr(sessions_module.secrets, "compare_digest", recording_compare)
    assert store.lookup("unknown", now=datetime.now(UTC)) is None
    assert store.lookup(expired.token, now=datetime.now(UTC)) is None
    assert compared == [(64, 64), (64, 64)]
