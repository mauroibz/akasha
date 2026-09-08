"""The switch that multiuser is still not.

Sprint 075's `AKASHA_AUTH` exists so the deployment surface can advertise what it
does not do: the word is there, the only legal value is `off`, and both the
future tense (a day when it turns on) and any other value are refused at startup.
Nothing reads it yet — refusing is its whole job this sprint.
"""

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


def test_auth_on_refuses_naming_sprint_077(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """The operator wants authentication now; the answer says when."""
    monkeypatch.setenv("AKASHA_AUTH", "on")

    with pytest.raises(ValidationError) as excinfo:
        Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")

    # A refusal the owner can act on names the sprint that will land the thing,
    # rather than stating only that the thing is not there.
    assert "sprint 077" in str(excinfo.value).casefold()


def test_auth_nonsense_is_a_validation_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """`banana` is refused by the type itself, before the Sprint-077 message applies."""
    monkeypatch.setenv("AKASHA_AUTH", "banana")

    with pytest.raises(ValidationError) as excinfo:
        Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")

    message = str(excinfo.value)
    assert "AKASHA_AUTH" in message
    assert "off" in message