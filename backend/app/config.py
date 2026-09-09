"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """Locate the directory holding `data/` and `models/`.

    The depth differs between environments: running locally the backend lives at
    `<repo>/backend`, while in Docker `backend/` *is* the working directory, so
    a hard-coded `parents[n]` resolves correctly in one and not the other.
    Walking up until both directories are found works in both.
    """
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "data").is_dir() and (candidate / "models").is_dir():
            return candidate
    # Nothing found (a bare checkout); fall back to the repository layout.
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _find_project_root()

# Explicit overrides win. Docker sets them so the data and model volumes can be
# mounted outside the source tree: nesting a volume inside the bind-mounted
# source directory makes Docker create empty stub directories on the host.
DATA_DIR = Path(os.getenv("DATA_DIR") or PROJECT_ROOT / "data")
MODEL_DIR = Path(os.getenv("MODEL_DIR") or PROJECT_ROOT / "models")


class Settings(BaseSettings):
    """Runtime settings. Every value can be overridden by an env var."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Kirana-IQ"
    app_version: str = "0.1.0"
    environment: str = "development"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "kirana_iq"
    postgres_user: str = "kirana"
    postgres_password: str = "kirana"

    # Comma-separated list of origins allowed to call the API.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Inventory policy -------------------------------------------------
    # Every threshold below is a business decision, not a law, so all of them
    # are environment-configurable.

    # Stock cover at or below this many days is CRITICAL regardless of lead time.
    critical_cover_days: float = 2.0
    # Cover within lead_time + this buffer is MEDIUM risk.
    medium_cover_buffer_days: float = 3.0
    # Cover above this is flagged as possible overstock.
    overstock_cover_days: float = 30.0
    # Extra days of demand to hold beyond the supplier lead time.
    safety_days: int = 3
    # Service-level multiplier for safety stock. 1.28 ~ 90% service level.
    service_level_z: float = 1.28

    # --- Anomaly detection ------------------------------------------------
    # Days of recent demand compared against the baseline window before it.
    anomaly_recent_days: int = 7
    anomaly_baseline_days: int = 28
    # A change must clear BOTH gates to be reported: a relative move this large,
    # and a statistically unusual one. Percentage alone fires constantly on
    # low-volume products; z-score alone flags trivial moves on steady ones.
    anomaly_min_change: float = 0.25
    anomaly_min_zscore: float = 2.0
    # Slow movers: products selling below this fraction of catalogue average.
    slow_moving_threshold: float = 0.25

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
