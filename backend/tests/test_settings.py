"""Authentication settings and their safe defaults."""

import pytest
from pydantic import ValidationError

from book_tracker.config import Settings


def test_auth_unset_behaves_as_off(tmp_path) -> None:
    """A fresh install has the word but not the thing, and starts either way."""
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")

    assert configured.auth == "off"


def test_auth_off_starts(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("AKASHA_AUTH", "off")

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")

    assert configured.auth == "off"


def test_auth_on_starts(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("AKASHA_AUTH", "on")

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.auth == "on"


def test_auth_nonsense_is_a_validation_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """`banana` is refused by the type itself, before the Sprint-077 message applies."""
    monkeypatch.setenv("AKASHA_AUTH", "banana")

    with pytest.raises(ValidationError) as excinfo:
        Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")

    message = str(excinfo.value)
    assert "auth" in message
    assert "off" in message
    assert "on" in message


def test_environment_admin_credentials_must_be_set_together() -> None:
    with pytest.raises(ValidationError, match="together"):
        Settings(auth="on", admin_username="admin")
    with pytest.raises(ValidationError, match="together"):
        Settings(auth="on", admin_password="secret")
