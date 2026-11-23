import re
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)

#: Docker and Compose secrets are mounted here (Sprint 128). A file is named like the
#: environment variable it replaces, in lower case: `akasha_admin_password` for
#: AKASHA_ADMIN_PASSWORD, `tmdb_read_token` for TMDB_READ_TOKEN. The environment wins
#: when both are set. Read only when the directory exists, because pydantic-settings
#: warns about a configured directory that does not.
SECRETS_DIR = Path("/run/secrets")

#: A bare DNS name: what Cloudflare calls the team domain, `<team>.cloudflareaccess.com`.
_HOSTNAME = re.compile(r"(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")


class Settings(BaseSettings):
    # DEC-119: the prefix is AKASHA_, a clean break from BOOK_TRACKER_ with no
    # alias. The two compose-side names that already carried the AKASHA_
    # spelling (AKASHA_BIND, AKASHA_PORT) now fall inside this prefix and are
    # absorbed by extra="ignore" — a test pins that.
    model_config = SettingsConfigDict(env_prefix="AKASHA_", extra="ignore")

    data_dir: Path = Path("/data")
    calibre_dir: Path = Path("/calibre")
    backup_dir: Path | None = None
    database_url: str | None = None
    google_books_api_key: str = Field(default="", validation_alias="GOOGLE_BOOKS_API_KEY")
    # Optional, and narrow: the movie domain's poster fallback for films carrying a
    # TMDB id and no IMDb id. Absent, those films stay coverless and nothing else
    # changes — the keyless primary source needs no configuration at all.
    tmdb_read_token: str = Field(default="", validation_alias="TMDB_READ_TOKEN")
    user_agent_contact: str | None = Field(default=None, validation_alias="USER_AGENT_CONTACT")
    timezone: str = Field(default="UTC", validation_alias="TZ")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    environment: str = "development"
    # Daily request budgets per provider. Configuration rather than code (DEC-045), so
    # a metered provider added later is an entry here and not a patch: override with
    # AKASHA_PROVIDER_DAILY_LIMITS as JSON. A provider absent from this mapping is
    # unmetered and never blocked. 900 rather than Google's real ~1000 is deliberate
    # headroom, because their quota resets on Pacific time and the counter uses UTC.
    provider_daily_limits: dict[str, int] = Field(default_factory=lambda: {"googlebooks": 900})
    # Daily rounds per recommendation source (Sprint 133), as JSON in
    # AKASHA_RECOMMEND_DAILY_LIMITS: `{"tmdb": 200}`. A round asks its source once,
    # so this bounds requests to the source itself; resolving candidates spends the
    # provider budgets above. A source absent here is counted and never stopped.
    recommend_daily_limits: dict[str, int] = Field(default_factory=dict)
    # Per-file cap on attachments (DEC-048). Configuration rather than code, like the
    # provider budgets above: 25 MB admits an epub, a PDF scan or a comic issue while
    # refusing the audiobook and video rips that would turn this into a media server.
    # It bounds the worst single file, not the total — with auth off, anyone on the
    # LAN can still fill the disk, and per-user quotas are deliberately not a thing
    # (DEC-146 §4) even with it on.
    attachment_max_bytes: int = 25 * 1024 * 1024
    # Below this much free space on the data volume, a write that would grow the
    # disk refuses before it starts rather than failing partway through (Sprint
    # 060). 500 MB is generous headroom above the single largest thing this
    # application writes in one call (an attachment, capped above) while staying
    # far under "normally full" for a home server's data volume — the failure
    # mode this guards against is running out entirely, not running low.
    min_free_bytes: int = 500 * 1024 * 1024
    sqlite_busy_timeout_ms: int = 5_000
    # Authentication is opt-in so every existing install remains unchanged.
    auth: Literal["off", "on"] = "off"
    #: `/metrics` in Prometheus text format (Sprint 101). Off by default: it names
    #: providers and routes, which is nobody's business on an open LAN unless asked for.
    metrics: Literal["off", "on"] = "off"
    cookie_secure: bool | None = None
    # Shared with Sprint 081's trusted identity header: a forwarded scheme is
    # authoritative only when the immediate peer is explicitly trusted.
    trusted_proxy_peers: list[str] = Field(default_factory=list)
    trusted_proxy_header: str | None = None
    trusted_header_autocreate: bool = False
    #: The header a trusted proxy names the real client in (`CF-Connecting-IP`
    #: behind Cloudflare). Honoured only when the immediate peer is one of
    #: `trusted_proxy_peers`; otherwise the socket peer is the client (Sprint 128).
    client_ip_header: str | None = None
    login_max_failures: int = Field(default=5, ge=1)
    login_window_seconds: int = Field(default=300, ge=1)
    #: How long an unused session lives; each day of use extends it (DEC-146).
    session_days: int = Field(default=400, ge=1)
    #: The one-time code first-run setup asks for (Sprint 128, F4). Unset, a
    #: random one is generated at start and printed in the server log.
    setup_token: SecretStr | None = None
    admin_username: str | None = None
    admin_password: SecretStr | None = None
    static_dir: Path | None = None
    # Cloudflare Access as a second gate (DEC-180 point 4). With both set, every request
    # must carry a valid Access JWT for this team and application, so one that bypassed
    # Access is refused even if it reaches the container. Neither set: no check.
    cf_access_team_domain: str | None = None
    cf_access_aud: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Decided per instantiation rather than in model_config, so the directory is
        # looked for when the settings are read, and only used when it is there.
        if SECRETS_DIR.is_dir():
            file_secret_settings = SecretsSettingsSource(settings_cls, secrets_dir=SECRETS_DIR)
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    @field_validator("cf_access_team_domain", "cf_access_aud", mode="before")
    @classmethod
    def blank_is_unset(cls, value: object) -> object:
        # The compose pass-through hands an empty `.env` line over as "".
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("cf_access_team_domain")
    @classmethod
    def team_domain_is_a_host(cls, value: str | None) -> str | None:
        if value is None:
            return None
        host = value.lower().removeprefix("https://").rstrip("/")
        if not _HOSTNAME.fullmatch(host):
            raise ValueError(
                "AKASHA_CF_ACCESS_TEAM_DOMAIN must be a host name such as "
                "myteam.cloudflareaccess.com"
            )
        return host

    @model_validator(mode="after")
    def validate_admin_bootstrap(self) -> "Settings":
        if (self.admin_username is None) != (self.admin_password is None):
            raise ValueError("AKASHA_ADMIN_USERNAME and AKASHA_ADMIN_PASSWORD must be set together")
        return self

    @model_validator(mode="after")
    def validate_trusted_identity_boundary(self) -> "Settings":
        if self.auth == "on" and self.trusted_proxy_header and not self.trusted_proxy_peers:
            raise ValueError(
                "AKASHA_TRUSTED_PROXY_HEADER requires AKASHA_TRUSTED_PROXY_PEERS; "
                "otherwise any direct caller could turn it into an authentication bypass"
            )
        return self

    @model_validator(mode="after")
    def validate_cloudflare_access(self) -> "Settings":
        if (self.cf_access_team_domain is None) != (self.cf_access_aud is None):
            raise ValueError(
                "AKASHA_CF_ACCESS_TEAM_DOMAIN and AKASHA_CF_ACCESS_AUD must be set together"
            )
        return self

    @model_validator(mode="after")
    def derive_database_url(self) -> "Settings":
        if self.backup_dir is None:
            self.backup_dir = self.data_dir.parent / "backups"
        if self.database_url is None:
            self.database_url = f"sqlite:///{self.data_dir / 'books.db'}"
        if self.environment == "production" and not self.user_agent_contact:
            raise ValueError("USER_AGENT_CONTACT is required in production")
        return self
