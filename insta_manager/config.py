from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def default_home() -> Path:
    env = os.environ.get("INSTA_MANAGER_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".insta-manager"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    insta_manager_api_version: str = "v21.0"
    insta_manager_home: Path | None = None
    insta_manager_image_uploader: str = "catbox"
    insta_manager_oauth_redirect_uri: str = "http://127.0.0.1:8765/callback"

    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_public_base_url: str | None = None

    def home(self) -> Path:
        return (self.insta_manager_home or default_home()).expanduser().resolve()

    def registry_path(self) -> Path:
        return self.home() / "accounts.json"

    def scheduler_db_path(self) -> Path:
        return self.home() / "scheduler.sqlite"

    def ensure_home(self) -> Path:
        h = self.home()
        h.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(h, 0o700)
        except OSError:
            pass
        return h


def get_settings() -> Settings:
    return Settings()
