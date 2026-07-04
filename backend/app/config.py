from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Point this at your Supabase session-pooler connection string in
    # production, e.g. postgresql+psycopg://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres
    database_url: str = f"sqlite:///{BACKEND_DIR / 'invtrack.db'}"

    # SEC asks automated clients to identify themselves: "name email".
    sec_edgar_user_agent: str = "invtrack personal research (set SEC_EDGAR_USER_AGENT)"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    scoring_config_path: Path = BACKEND_DIR / "scoring.yaml"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_scoring_config() -> dict[str, Any]:
    with open(get_settings().scoring_config_path) as f:
        return yaml.safe_load(f)
