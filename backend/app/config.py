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

    # House trades: Stock Watcher-shaped JSON. The original bucket is defunct
    # (verified July 2026) — point this at any live mirror with the same row
    # schema. Senate uses the official efdsearch.senate.gov directly.
    house_data_url: str = (
        "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com"
        "/data/all_transactions.json"
    )

    scoring_config_path: Path = BACKEND_DIR / "scoring.yaml"

    # Opt-in AI analysis of 10-K filings. Leave empty to disable the feature
    # entirely (the rest of the app stays 100% free/keyless). Costs money per
    # analysis — see README.
    anthropic_api_key: str = ""
    analysis_model: str = "claude-opus-4-8"

    # Daily auto-refresh (ingest all sources + rescore + alert detection).
    auto_refresh_enabled: bool = True
    auto_refresh_hour: int = 7  # local server time

    # Optional alert push: POSTs a JSON superset {title, body, text, content,
    # ticker, kind} that Slack ("text"), Discord ("content"), ntfy and generic
    # webhook receivers all understand. Empty = in-app alerts only.
    alert_webhook_url: str = ""

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
