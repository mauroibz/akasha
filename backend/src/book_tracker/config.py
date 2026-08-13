from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOOK_TRACKER_", extra="ignore")

    data_dir: Path = Path("/data")
    calibre_dir: Path = Path("/calibre")
    backup_dir: Path | None = None
    database_url: str | None = None
    google_books_api_key: str = Field(default="", validation_alias="GOOGLE_BOOKS_API_KEY")
    user_agent_contact: str | None = Field(default=None, validation_alias="USER_AGENT_CONTACT")
    timezone: str = Field(default="UTC", validation_alias="TZ")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    environment: str = "development"
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
