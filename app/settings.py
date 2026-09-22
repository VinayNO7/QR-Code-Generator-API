from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    secret: str
    database_path: Path
    token_ttl_minutes: int
    cors_origins: list[str]


def get_settings() -> Settings:
    raw_origins = os.getenv("QR_CORS_ORIGINS", "")
    return Settings(
        # A conspicuous default keeps local setup easy; production is rejected in main.py.
        secret=os.getenv("QR_API_SECRET", "development-only-change-me"),
        database_path=Path(os.getenv("QR_DATABASE_PATH", "data/qr_api.db")),
        token_ttl_minutes=int(os.getenv("QR_TOKEN_TTL_MINUTES", "1440")),
        cors_origins=[item.strip() for item in raw_origins.split(",") if item.strip()],
    )
