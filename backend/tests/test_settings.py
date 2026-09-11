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


def test_trusted_identity_header_requires_an_explicit_peer_allowlist() -> None:
    with pytest.raises(ValidationError, match="authentication bypass"):
        Settings(auth="on", trusted_proxy_header="Tailscale-User-Login")


def test_trusted_identity_settings_are_inert_when_authentication_is_off() -> None:
    configured = Settings(
        auth="off",
        trusted_proxy_header="Tailscale-User-Login",
        trusted_header_autocreate=True,
    )

    assert configured.trusted_proxy_header == "Tailscale-User-Login"
    assert configured.trusted_header_autocreate is True


def _env_example_names() -> set[str]:
    """Every AKASHA_* and validation-alias variable named in .env.example.

    Commented lines count: an opt-in setting is documented as `# NAME=value`,
    and a reader who cannot find a setting in this file cannot set it.
    """
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
    names: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if not stripped or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        if name.startswith("AKASHA_") or name in {
            "GOOGLE_BOOKS_API_KEY",
            "TMDB_READ_TOKEN",
            "USER_AGENT_CONTACT",
            "TZ",
            "LOG_LEVEL",
        }:
            names.add(name)
    return names


def _settings_env_names() -> set[str]:
    """Every environment variable Settings actually reads."""
    from book_tracker.config import Settings

    names: set[str] = set()
    for field_name, field in Settings.model_fields.items():
        alias = field.validation_alias
        if alias is not None:
            names.add(str(alias))
        else:
            names.add(f"AKASHA_{field_name.upper()}")
    return names


# Compose-side interpolation names configure the deployment and never reach the
# process; they are absent from Settings by design and excluded here.
COMPOSE_SIDE = {
    "AKASHA_BIND",
    "AKASHA_PORT",
    "AKASHA_VERSION",
    "AKASHA_DATA_VOLUME",
    "AKASHA_BACKUP_VOLUME",
    "AKASHA_LOG_MAX_SIZE",
    "AKASHA_LOG_MAX_FILE",
}
# Read by scripts/backup.sh from the process environment, not by the app.
SCRIPT_SIDE = {"BACKUP_RETENTION"}
# Read by compose to locate the mounts; not application settings.
MOUNT_SIDE = {"CALIBRE_DIR", "DATA_DIR", "BACKUP_DIR"}
# Container-fixed or host-only paths the image sets; documented in .env.example
# as deliberately not overridable through this file.
IMAGE_FIXED = {
    "AKASHA_DATA_DIR",
    "AKASHA_CALIBRE_DIR",
    "AKASHA_BACKUP_DIR",
    "AKASHA_DATABASE_URL",
    "AKASHA_ENVIRONMENT",
    "AKASHA_STATIC_DIR",
}


def test_every_env_example_setting_is_accepted_by_settings() -> None:
    documented = _env_example_names() - COMPOSE_SIDE - SCRIPT_SIDE - MOUNT_SIDE
    accepted = _settings_env_names()
    missing = sorted(documented - accepted)
    assert not missing, f".env.example names settings the application ignores: {missing}"


def test_no_setting_is_missing_from_env_example() -> None:
    accepted = _settings_env_names()
    documented = _env_example_names()
    undocumented = sorted(accepted - documented - IMAGE_FIXED)
    assert not undocumented, (
        f"Settings accepts variables .env.example never mentions: {undocumented}"
    )
