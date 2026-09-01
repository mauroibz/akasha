from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # Per-file cap on attachments (DEC-048). Configuration rather than code, like the
    # provider budgets above: 25 MB admits an epub, a PDF scan or a comic issue while
    # refusing the audiobook and video rips that would turn this into a media server.
    # It bounds the worst single file, not the total — with no auth, anyone on the LAN
    # can still fill the disk, which is a property of v1 being LAN-only.
    attachment_max_bytes: int = 25 * 1024 * 1024
    # Below this much free space on the data volume, a write that would grow the
    # disk refuses before it starts rather than failing partway through (Sprint
    # 060). 500 MB is generous headroom above the single largest thing this
    # application writes in one call (an attachment, capped above) while staying
    # far under "normally full" for a home server's data volume — the failure
    # mode this guards against is running out entirely, not running low.
    min_free_bytes: int = 500 * 1024 * 1024
    sqlite_busy_timeout_ms: int = 5_000
    static_dir: Path | None = None

    @model_validator(mode="after")
    def derive_database_url(self) -> "Settings":
        if self.backup_dir is None:
            self.backup_dir = self.data_dir.parent / "backups"
        if self.database_url is None:
            self.database_url = f"sqlite:///{self.data_dir / 'books.db'}"
        if self.environment == "production" and not self.user_agent_contact:
            raise ValueError("USER_AGENT_CONTACT is required in production")
        return self
