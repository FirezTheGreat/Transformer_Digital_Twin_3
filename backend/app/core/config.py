"""Core Application Configuration and Settings.

Manages application settings, environment configurations, and defaults for the
Distribution Transformer Digital Twin backend API.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Immutable application settings model."""

    app_name: str = Field(
        default="Distribution Transformer Digital Twin API",
        description="Application name",
    )
    app_version: str = Field(
        default="1.0.0",
        description="Application and contract version",
    )
    api_v1_prefix: str = Field(
        default="/v1",
        description="Prefix for v1 API routes",
    )
    environment: Literal["development", "test", "production"] = Field(
        default_factory=lambda: os.getenv("APP_ENV", "development"),  # type: ignore[arg-type]
        description="Execution environment",
    )
    default_asset_id: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_ASSET_ID", "TX_1000_COMM"),
        description="Default transformer asset identifier",
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        ],
        description="Allowed CORS origins",
    )
    db_path: str = Field(
        default_factory=lambda: os.getenv("DB_PATH", ":memory:"),
        description="DuckDB database file path or :memory:",
    )
    parquet_dir: str = Field(
        default_factory=lambda: os.getenv("PARQUET_DIR", "data/processed/parquet"),
        description="Parquet storage partition directory",
    )
    load_reference_kva: float = Field(
        default_factory=lambda: float(os.getenv("LOAD_REFERENCE_KVA", "142.898")),
        description="Empirical 95th percentile apparent power in kVA for relative load index",
    )
    expected_cadence_s: int = Field(
        default_factory=lambda: int(os.getenv("EXPECTED_CADENCE_S", "900")),
        description="Expected telemetry sampling interval in seconds",
    )
    evaluation_window_s: int = Field(
        default_factory=lambda: int(os.getenv("EVALUATION_WINDOW_S", "86400")),
        description="Rolling evaluation window duration in seconds",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
