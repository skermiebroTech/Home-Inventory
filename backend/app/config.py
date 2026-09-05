"""Application settings.

Every setting reads the ``HS_`` prefixed environment variable first. If that
name is not set, it falls back to the bare name. The fallback exists because
the Unraid Community Applications template uses bare names, and the
architecture specification uses the ``HS_`` prefix. Both must work.

This module is the only place that holds the fallback logic. Do not repeat it
elsewhere. See ``.env.example`` for the full variable list.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "CHANGE_ME_TO_RANDOM_STRING"


def _alias(name: str) -> AliasChoices:
    """Return the HS_ prefixed name and the bare name, in that order."""
    return AliasChoices(f"HS_{name.upper()}", name.upper())


class Settings(BaseSettings):
    """Runtime configuration, read from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---
    secret_key: str = Field(
        default=DEFAULT_SECRET_KEY, validation_alias=_alias("secret_key")
    )
    port: int = Field(default=7850, validation_alias=_alias("port"))
    log_level: str = Field(default="info", validation_alias=_alias("log_level"))
    tz: str = Field(default="Australia/Brisbane", validation_alias=_alias("tz"))

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://homestock:homestock@postgres:5432/homestock",
        validation_alias=_alias("database_url"),
    )

    # --- Storage ---
    data_dir: Path = Field(default=Path("/data"), validation_alias=_alias("data_dir"))
    upload_dir: Path = Field(
        default=Path("/data/uploads"), validation_alias=_alias("upload_dir")
    )
    backup_dir: Path = Field(
        default=Path("/data/backups"), validation_alias=_alias("backup_dir")
    )
    config_dir: Path = Field(
        default=Path("/data/config"), validation_alias=_alias("config_dir")
    )
    static_dir: Path = Field(
        default=Path("/app/static"), validation_alias=_alias("static_dir")
    )

    # --- Authentication ---
    access_token_expire_minutes: int = Field(
        default=30, validation_alias=_alias("access_token_expire_minutes")
    )
    refresh_token_expire_days: int = Field(
        default=30, validation_alias=_alias("refresh_token_expire_days")
    )
    jwt_algorithm: str = Field(
        default="HS256", validation_alias=_alias("jwt_algorithm")
    )

    # --- Rate limits ---
    # The sign in routes are the only ones that an unknown caller can reach,
    # so they are the only ones that carry a limit. Set the value to an empty
    # string to turn the limit off.
    rate_limit_auth: str = Field(
        default="20/minute", validation_alias=_alias("rate_limit_auth")
    )

    # --- CORS ---
    cors_origins: str = Field(default="*", validation_alias=_alias("cors_origins"))

    # --- AI ---
    # The target server has no GPU. Every model runs on the CPU. Defaults are
    # chosen for CPU speed, not for accuracy. See docs/architecture.md.
    ai_enabled: bool = Field(default=True, validation_alias=_alias("ai_enabled"))
    ollama_url: str = Field(
        default="http://ollama:11434", validation_alias=_alias("ollama_url")
    )
    # moondream is 1.8B and about 1.7 GB. It is the fastest usable vision
    # model on a CPU. llava-phi3 (3.8B) is more accurate and slower.
    ollama_vision_model: str = Field(
        default="moondream", validation_alias=_alias("ollama_vision_model")
    )
    # Receipt text goes to a text model, not to the vision model. Text
    # inference on a CPU is several times faster than vision inference.
    ollama_text_model: str = Field(
        default="llama3.2:3b", validation_alias=_alias("ollama_text_model")
    )
    # CPU inference is slow. This ceiling stops a stuck request from hanging.
    ollama_timeout: int = Field(default=300, validation_alias=_alias("ollama_timeout"))
    # Seconds to hold an AI request open before it becomes a background job.
    # A request that outlives the reverse proxy timeout fails for the client.
    ai_inline_timeout: int = Field(
        default=8, validation_alias=_alias("ai_inline_timeout")
    )

    # --- OCR ---
    tesseract_cmd: str = Field(
        default="/usr/bin/tesseract", validation_alias=_alias("tesseract_cmd")
    )

    # --- Images ---
    image_max_dimension: int = Field(
        default=2000, validation_alias=_alias("image_max_dimension")
    )
    thumbnail_sizes: str = Field(
        default="200,600", validation_alias=_alias("thumbnail_sizes")
    )
    strip_exif_gps: bool = Field(
        default=True, validation_alias=_alias("strip_exif_gps")
    )

    # --- Backup ---
    backup_enabled: bool = Field(
        default=False, validation_alias=_alias("backup_enabled")
    )
    backup_cron: str = Field(
        default="0 3 * * *", validation_alias=_alias("backup_cron")
    )
    backup_retention: int = Field(
        default=7, validation_alias=_alias("backup_retention")
    )
    rclone_remote: str = Field(default="", validation_alias=_alias("rclone_remote"))

    # --- Migrations ---
    run_migrations_on_start: bool = Field(
        default=True, validation_alias=_alias("run_migrations_on_start")
    )

    @field_validator("log_level")
    @classmethod
    def _lower_log_level(cls, value: str) -> str:
        return value.lower()

    @property
    def cors_origin_list(self) -> list[str]:
        """Return the allowed CORS origins as a list."""
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def thumbnail_size_list(self) -> list[int]:
        """Return the thumbnail widths in pixels, smallest first."""
        sizes = [
            int(part.strip())
            for part in self.thumbnail_sizes.split(",")
            if part.strip()
        ]
        return sorted(sizes)

    @property
    def secret_key_is_default(self) -> bool:
        """Return True if the operator did not change the secret key."""
        return self.secret_key == DEFAULT_SECRET_KEY

    @property
    def sync_database_url(self) -> str:
        """Return the database URL with a synchronous driver.

        Alembic and ``pg_dump`` helpers need this form.
        """
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Return the settings singleton."""
    return Settings()


settings = get_settings()
