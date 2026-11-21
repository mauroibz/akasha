"""Sprint 128 containment settings: Docker secrets and the Cloudflare Access gate (DEC-180)."""

import warnings
from pathlib import Path

import pytest
from pydantic import ValidationError

from book_tracker import config
from book_tracker.config import Settings


def _secrets(tmp_path: Path, **files: str) -> Path:
    directory = tmp_path / "secrets"
    directory.mkdir()
    for name, value in files.items():
        (directory / name).write_text(value + "\n", encoding="utf-8")
    return directory


def test_secrets_directory_supplies_prefixed_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`/run/secrets/akasha_admin_password` is read the way `AKASHA_ADMIN_PASSWORD` is."""
    monkeypatch.delenv("AKASHA_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("AKASHA_ADMIN_USERNAME", raising=False)
    secrets = _secrets(
        tmp_path, akasha_admin_username="owner", akasha_admin_password="correct horse battery"
    )
    monkeypatch.setattr(config, "SECRETS_DIR", secrets)

    configured = Settings(data_dir=tmp_path)

    assert configured.admin_username == "owner"
    assert configured.admin_password is not None
    # A trailing newline from `echo ... > file` is not a character of the password.
    assert configured.admin_password.get_secret_value() == "correct horse battery"


def test_secrets_directory_uses_the_alias_for_unprefixed_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TMDB_READ_TOKEN", raising=False)
    monkeypatch.setattr(config, "SECRETS_DIR", _secrets(tmp_path, tmdb_read_token="tok-123"))

    assert Settings(data_dir=tmp_path).tmdb_read_token == "tok-123"


def test_environment_wins_over_a_secret_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TMDB_READ_TOKEN", "from-env")
    monkeypatch.setattr(config, "SECRETS_DIR", _secrets(tmp_path, tmdb_read_token="from-file"))

    assert Settings(data_dir=tmp_path).tmdb_read_token == "from-env"


def test_missing_secrets_directory_is_silent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """pydantic-settings warns about a configured directory that does not exist."""
    monkeypatch.setattr(config, "SECRETS_DIR", tmp_path / "absent")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Settings(data_dir=tmp_path)

    assert [str(warning.message) for warning in caught] == []


def test_cloudflare_access_is_off_by_default(tmp_path: Path) -> None:
    configured = Settings(data_dir=tmp_path)

    assert configured.cf_access_team_domain is None
    assert configured.cf_access_aud is None


def test_cloudflare_access_settings_are_set_together(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="together"):
        Settings(data_dir=tmp_path, cf_access_team_domain="team.cloudflareaccess.com")
    with pytest.raises(ValidationError, match="together"):
        Settings(data_dir=tmp_path, cf_access_aud="a" * 64)


def test_cloudflare_access_team_domain_is_normalised_to_a_host(tmp_path: Path) -> None:
    configured = Settings(
        data_dir=tmp_path,
        cf_access_team_domain="https://Team.CloudflareAccess.com/",
        cf_access_aud="abc123",
    )

    assert configured.cf_access_team_domain == "team.cloudflareaccess.com"


@pytest.mark.parametrize(
    "domain",
    ["team.cloudflareaccess.com/evil", "user@team.example", "team example.com", "", "http://x.y"],
)
def test_cloudflare_access_team_domain_must_be_a_bare_host(tmp_path: Path, domain: str) -> None:
    with pytest.raises(ValidationError, match="AKASHA_CF_ACCESS_TEAM_DOMAIN"):
        Settings(data_dir=tmp_path, cf_access_team_domain=domain, cf_access_aud="abc123")


def test_cloudflare_access_reads_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AKASHA_CF_ACCESS_TEAM_DOMAIN", "team.cloudflareaccess.com")
    monkeypatch.setenv("AKASHA_CF_ACCESS_AUD", "abc123")

    configured = Settings(data_dir=tmp_path)

    assert configured.cf_access_team_domain == "team.cloudflareaccess.com"
    assert configured.cf_access_aud == "abc123"


def test_blank_cloudflare_access_settings_mean_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The lockout recovery in the runbook turns the check off with `VAR=` on the command line."""
    monkeypatch.setenv("AKASHA_CF_ACCESS_TEAM_DOMAIN", "")
    monkeypatch.setenv("AKASHA_CF_ACCESS_AUD", "  ")

    configured = Settings(data_dir=tmp_path)

    assert configured.cf_access_team_domain is None
    assert configured.cf_access_aud is None


ROOT = Path(__file__).resolve().parents[2]


def test_the_image_does_not_hand_its_code_to_the_application_user() -> None:
    """F20: a process that can write /app turns a file-write bug into code execution."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "chown -R" not in dockerfile
    assert "chown akasha:akasha /data /data/tmp /backups" in dockerfile
    assert "TMPDIR=/data/tmp" in dockerfile
    assert "PYTHONDONTWRITEBYTECODE=1" in dockerfile
    assert '"--no-server-header"' in dockerfile
    command = [line for line in dockerfile.splitlines() if line.startswith("CMD ")][-1]
    assert "proxy-headers" not in command
    assert "forwarded-allow-ips" not in command
    # Sprint 129: a bound on how long open responses may hold up a stop, well inside
    # compose's stop_grace_period, so a stop never ends in SIGKILL mid-job.
    assert '"--timeout-graceful-shutdown", "10"' in command


def test_compose_contains_the_container() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    for line in (
        "read_only: true",
        "- /tmp:size=64m,mode=1777,noexec,nosuid,nodev",
        "cap_drop: [ALL]",
        '- "no-new-privileges:true"',
        "mem_limit: ${AKASHA_MEM_LIMIT:-",
        "cpus: ${AKASHA_CPUS:-",
        "pids_limit: ${AKASHA_PIDS_LIMIT:-",
    ):
        assert line in compose, line


def test_the_public_overlay_publishes_nothing_and_forces_the_exposure_conditions() -> None:
    overlay = (ROOT / "compose.public.yaml").read_text(encoding="utf-8")

    assert "ports: !reset []" in overlay
    for line in (
        "- AKASHA_AUTH=on",
        "- AKASHA_COOKIE_SECURE=true",
        "- AKASHA_METRICS=off",
        "- AKASHA_CLIENT_IP_HEADER=CF-Connecting-IP",
        '- AKASHA_TRUSTED_PROXY_PEERS=["172.30.10.2"]',
        "- AKASHA_SESSION_DAYS=${AKASHA_SESSION_DAYS:-30}",
        "ipv4_address: 172.30.10.2",
        "internal: true",
        "com.docker.network.bridge.name: br-akasha-eg",
    ):
        assert line in overlay, line
    assert overlay.count("enable_ipv6: false") == 3
    # The sidecar is pinned by digest, never a floating tag.
    assert "image: cloudflare/cloudflared:" in overlay
    assert "@sha256:" in overlay.split("image: cloudflare/cloudflared:", 1)[1].splitlines()[0]


def test_startup_creates_the_temporary_directory_on_the_data_volume(tmp_path: Path) -> None:
    """The image sets TMPDIR=/data/tmp; a volume from before Sprint 128 has no such folder.

    Without it, tempfile silently falls back to /tmp — a small RAM tmpfs in the read-only
    container — and a large import fails there instead of spooling to disk.
    """
    from fastapi.testclient import TestClient

    from book_tracker.main import create_app

    data = tmp_path / "data"
    with TestClient(create_app(Settings(data_dir=data))):
        assert (data / "tmp").is_dir()
