from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import create_api_router
from app.api.websocket import create_websocket_router
from app.core.config import Settings, get_settings
from app.domain.models import ForwardingRule
from app.repositories.memory import InMemoryEventRepository, InMemoryRuleRepository
from app.services.broadcaster import ConnectionManager
from app.services.forwarding import ForwardingService
from app.services.replay import ReplayService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    event_repository = InMemoryEventRepository(settings.event_retention_limit)
    rule_repository = InMemoryRuleRepository()
    load_rules_from_config(rule_repository, settings.rules_config_path)

    forwarding_service = ForwardingService(
        relay_signing_secret=settings.relay_signing_secret
    )
    replay_service = ReplayService(
        event_repository,
        rule_repository,
        forwarding_service,
    )
    broadcaster = ConnectionManager()

    app.include_router(
        create_api_router(
            event_repository,
            rule_repository,
            forwarding_service,
            replay_service,
            broadcaster,
            settings,
        )
    )
    app.include_router(create_websocket_router(broadcaster))

    return app


def load_rules_from_config(
    repository: InMemoryRuleRepository,
    rules_config_path: str | None,
) -> None:
    if not rules_config_path:
        return
    path = Path(rules_config_path)
    if not path.exists():
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data.get("rules", []):
        repository.add(ForwardingRule(**item))


app = create_app()

