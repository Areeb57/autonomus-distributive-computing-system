"""
Application configuration loaded from environment variables.

Uses pydantic-settings to validate and type-check all configuration values.
Defaults are suitable for local development with docker-compose PostgreSQL.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — every setting can be overridden via env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "DEBUG"

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://adc:adc_dev_password@localhost:5432/adc_db"

    # ── Security ─────────────────────────────────────────────────────────
    secret_key: str = "CHANGE_ME_generate_a_random_secret_key"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    token_algorithm: str = "HS256"

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: str | List[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Storage ──────────────────────────────────────────────────────────
    storage_root: Path = Path("./storage")
    upload_max_size_mb: int = 10240

    # ── Machine Identity ─────────────────────────────────────────────────
    machine_key_algorithm: str = "Ed25519"
    pairing_code_expiry_seconds: int = 300
    pairing_max_attempts: int = 5

    # ── Heartbeat and Leases ─────────────────────────────────────────────
    heartbeat_interval_seconds: int = 30
    heartbeat_timeout_seconds: int = 90
    lease_duration_seconds: int = 300

    # ── Resource Defaults ────────────────────────────────────────────────
    default_cpu_budget_percent: int = 50
    default_ram_budget_gb: int = 4
    default_storage_budget_gb: int = 20

    # ── Training ─────────────────────────────────────────────────────────
    execution_backend: str = "subprocess"
    checkpoint_interval_steps: int = 500
    max_training_runtime_hours: int = 48

    # ── WebSocket ────────────────────────────────────────────────────────
    ws_heartbeat_interval: int = 15
    ws_max_message_size: int = 1_048_576

    # ── Logging ──────────────────────────────────────────────────────────
    log_format: str = "json"
    log_file: Path = Path("./storage/logs/adc.log")
    log_rotation_mb: int = 50
    log_retention_count: int = 5

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def datasets_dir(self) -> Path:
        return self.storage_root / "datasets"

    @property
    def packages_dir(self) -> Path:
        return self.storage_root / "packages"

    @property
    def checkpoints_dir(self) -> Path:
        return self.storage_root / "checkpoints"

    @property
    def logs_dir(self) -> Path:
        return self.storage_root / "logs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call)."""
    return Settings()
