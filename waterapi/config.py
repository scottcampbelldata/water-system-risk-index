"""Settings loaded from environment variables (and an optional .env file).

No secrets are hardcoded. All database credentials and runtime options are read
from the process environment, mirroring the grid-intelligence-platform pattern.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database connection (standard libpq-style names)
    pghost: str = "localhost"
    pgport: int = 5432
    pgdatabase: str = "water_risk"
    pguser: str = "water_app"
    pgpassword: str = ""

    # API runtime
    water_api_port: int = 8000
    water_log_level: str = "INFO"

    # Optional bearer token protecting GET /metrics. When empty (default) the
    # endpoint is open, which is convenient for local/portfolio use; set it in
    # production so request telemetry is not publicly readable.
    water_metrics_token: str = ""

    # Comma-separated explicit CORS origins. localhost/127.0.0.1 on any port is
    # always allowed via a regex (see api/main.py) for local development.
    water_cors_origins: str = "https://water-risk.example.com"

    # Seed file the loader ingests (relative paths resolved against repo root).
    water_seed_path: str = "data/processed/app_data.json"

    @property
    def sqlalchemy_url(self) -> str:
        return f"postgresql+psycopg://{self.pguser}:{self.pgpassword}@{self.pghost}:{self.pgport}/{self.pgdatabase}"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.water_cors_origins.split(",") if origin.strip()]

    @property
    def seed_path(self) -> Path:
        path = Path(self.water_seed_path)
        return path if path.is_absolute() else REPO_ROOT / path


settings = Settings()
