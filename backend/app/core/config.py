from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Webhook Relay & Inspector"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    webhook_signing_secret: str | None = None
    relay_signing_secret: str | None = None
    event_retention_limit: int = 1000
    rules_config_path: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        return cls(
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            cors_origins=tuple(
                origin.strip() for origin in origins.split(",") if origin.strip()
            ),
            webhook_signing_secret=os.getenv("WEBHOOK_SIGNING_SECRET") or None,
            relay_signing_secret=os.getenv("RELAY_SIGNING_SECRET") or None,
            event_retention_limit=int(os.getenv("EVENT_RETENTION_LIMIT", "1000")),
            rules_config_path=os.getenv("RULES_CONFIG_PATH") or None,
        )


def get_settings() -> Settings:
    return Settings.from_env()

