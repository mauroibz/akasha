"""Whose request this is (Sprint 076).

The resolver is the one place that decides who a request belongs to, and it
answers with a value rather than a lookup. `AKASHA_AUTH` accepts exactly one
value in v1 (`off`, enforced in `Settings`), so every request belongs to the
seeded user — and these tests pin that the constant names the migration's own
row, not an invention.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from book_tracker.api.identity import CurrentUser, Principal
from book_tracker.config import Settings
from book_tracker.main import create_app


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_principal_without_acting_user_is_own_effective_user() -> None:
    assert Principal(user_id=7, username="ada", is_admin=False).effective_user_id == 7


def test_principal_with_acting_user_touches_their_rows() -> None:
    """Impersonation is Sprint 080, but the field that carries it exists now:
    once filled, "whose rows" follows it, and no caller can be surprised."""
    principal = Principal(user_id=7, username="ada", is_admin=True, acting_as=3)
    assert principal.effective_user_id == 3


@pytest.mark.anyio
async def test_off_auth_resolves_to_the_seeded_user(tmp_path: Path) -> None:
    """The resolver runs as a real FastAPI dependency — the shape every route
    gets it in, including the 213 `create_app(` call sites that never pass a
    user of their own."""
    app = create_app(settings(tmp_path))
    received: list[Principal] = []

    @app.get("/_identity_probe")
    async def probe(user: CurrentUser) -> dict[str, int]:
        received.append(user)
        return {"user_id": user.user_id}

    async with app.router.lifespan_context(app):
        response = TestClient(app).get("/_identity_probe")

    assert response.status_code == 200
    assert response.json() == {"user_id": 1}
    (principal,) = received
    assert principal.username == "admin"
    assert principal.is_admin is True
    assert principal.acting_as is None


@pytest.mark.anyio
async def test_resolver_names_the_migrations_own_row(tmp_path: Path) -> None:
    """The answer is not an invented constant: it names the user the Sprint
    075 migration actually wrote (renamed `admin` at DEC-147). A drift between
    the resolver and the seed fails here before it leaks into a row."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        with app.state.engine.connect() as connection:
            row = connection.execute(
                text("SELECT username, is_admin FROM users WHERE id = 1")
            ).one()
    assert row.username == "admin"
    assert bool(row.is_admin) is True


def test_no_hardcoded_user_outside_the_resolver() -> None:
    """Deliberately crude (the sprint's own word): grep every backend source
    file for the three shapes a hardcoded user wears. `api/identity.py` is the
    one file allowed to say `user_id=1`, because it is the one place allowed
    to decide who a request belongs to. Anything else means the pattern came
    back through a site the resolver never passes."""
    src_root = Path(__file__).resolve().parent.parent / "src" / "book_tracker"
    resolver_file = (src_root / "api" / "identity.py").resolve()
    pattern = re.compile(r"\buser_id\b\s*(?::\s*int\s*)?=\s*1\b|\buser_id\b\s*==\s*1\b")

    offenders: list[str] = []
    for py in sorted(src_root.rglob("*.py")):
        if py.resolve() == resolver_file:
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.relative_to(src_root)}:{lineno}: {line.strip()}")

    assert not offenders, "\n".join(
        ["a hardcoded user reappeared outside api/identity.py:"] + offenders
    )
