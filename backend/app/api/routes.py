from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.signatures import verify_hmac_signature
from app.domain.models import (
    EventStatus,
    ForwardingRule,
    WebhookEvent,
    parse_json_body,
)
from app.repositories.memory import InMemoryEventRepository, InMemoryRuleRepository
from app.services.broadcaster import ConnectionManager
from app.services.forwarding import ForwardingService
from app.services.replay import ReplayService


class RulePayload(BaseModel):
    name: str
    endpoint_url: str
    source: str | None = None
    event_type: str | None = None
    header_matches: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    max_retries: int = 2
    timeout_seconds: float = 5.0


class RulePatch(BaseModel):
    name: str | None = None
    endpoint_url: str | None = None
    source: str | None = None
    event_type: str | None = None
    header_matches: dict[str, str] | None = None
    enabled: bool | None = None
    max_retries: int | None = None
    timeout_seconds: float | None = None


class ReplayPayload(BaseModel):
    target_rule_ids: list[str] | None = None
    override_url: str | None = None


def infer_event_type(headers: dict[str, str], payload: Any | None) -> str | None:
    lowered = {key.lower(): value for key, value in headers.items()}
    header_type = (
        lowered.get("x-event-type")
        or lowered.get("x-github-event")
        or lowered.get("x-webhook-event")
    )
    if header_type:
        return header_type
    if isinstance(payload, dict):
        value = payload.get("type") or payload.get("event") or payload.get("event_type")
        if value:
            return str(value)
    return None


def create_api_router(
    event_repository: InMemoryEventRepository,
    rule_repository: InMemoryRuleRepository,
    forwarding_service: ForwardingService,
    replay_service: ReplayService,
    broadcaster: ConnectionManager,
    settings: Settings,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/webhooks/{source}")
    async def receive_webhook(
        source: str,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        raw_body = await request.body()
        headers = dict(request.headers)
        query_params = dict(request.query_params)
        payload = parse_json_body(raw_body)
        signature_valid: bool | None = None

        if settings.webhook_signing_secret:
            signature_header = (
                headers.get("x-webhook-signature")
                or headers.get("x-hub-signature-256")
                or headers.get("stripe-signature")
            )
            timestamp_header = headers.get("x-webhook-timestamp")
            signature_valid = verify_hmac_signature(
                settings.webhook_signing_secret,
                raw_body,
                signature_header,
                timestamp_header=timestamp_header,
                require_timestamp=bool(timestamp_header),
            )

        event = WebhookEvent(
            source=source,
            method=request.method,
            path=request.url.path,
            headers=headers,
            query_params=query_params,
            raw_body=raw_body,
            json_payload=payload,
            event_type=infer_event_type(headers, payload),
            signature_valid=signature_valid,
            status=(
                EventStatus.REJECTED
                if signature_valid is False
                else EventStatus.RECEIVED
            ),
        )
        event_repository.add(event)
        await broadcaster.broadcast_json(
            {"type": "event.received", "event": event.to_dict()}
        )

        if signature_valid is False:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        matched_rules = forwarding_service.matching_rules(
            event, rule_repository.list()
        )
        for rule in matched_rules:
            background_tasks.add_task(_forward_and_record, event, rule)

        return {
            "event_id": event.id,
            "matched_rules": len(matched_rules),
            "signature_valid": signature_valid,
        }

    async def _forward_and_record(
        event: WebhookEvent,
        rule: ForwardingRule,
    ) -> None:
        attempt = await forwarding_service.forward_event(event, rule)
        updated_event = event_repository.append_delivery_attempt(event.id, attempt)
        await broadcaster.broadcast_json(
            {
                "type": "delivery.updated",
                "event": updated_event.to_dict() if updated_event else event.to_dict(),
                "attempt": attempt.to_dict(),
            }
        )

    @router.get("/events")
    async def list_events(
        limit: int = 50,
        source: str | None = None,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        events = event_repository.list(
            limit=limit,
            source=source,
            event_type=event_type,
        )
        return {"events": [event.to_dict() for event in events]}

    @router.get("/events/{event_id}")
    async def get_event(event_id: str) -> dict[str, Any]:
        event = event_repository.get(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return event.to_dict()

    @router.post("/events/{event_id}/replay")
    async def replay_event(
        event_id: str,
        payload: ReplayPayload,
    ) -> dict[str, Any]:
        try:
            result = await replay_service.replay_event(
                event_id,
                target_rule_ids=payload.target_rule_ids,
                override_url=payload.override_url,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Event not found") from None

        event = event_repository.get(event_id)
        await broadcaster.broadcast_json(
            {
                "type": "event.replayed",
                "event": event.to_dict() if event else None,
                "result": result.to_dict(),
            }
        )
        return result.to_dict()

    @router.get("/rules")
    async def list_rules() -> dict[str, Any]:
        return {"rules": [rule.to_dict() for rule in rule_repository.list()]}

    @router.post("/rules", status_code=201)
    async def create_rule(payload: RulePayload) -> dict[str, Any]:
        rule = ForwardingRule(**payload.model_dump())
        rule_repository.add(rule)
        await broadcaster.broadcast_json(
            {"type": "rule.created", "rule": rule.to_dict()}
        )
        return rule.to_dict()

    @router.patch("/rules/{rule_id}")
    async def update_rule(rule_id: str, payload: RulePatch) -> dict[str, Any]:
        changes = payload.model_dump(exclude_unset=True)
        rule = rule_repository.update(rule_id, **changes)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        await broadcaster.broadcast_json(
            {"type": "rule.updated", "rule": rule.to_dict()}
        )
        return rule.to_dict()

    @router.delete("/rules/{rule_id}", status_code=204)
    async def delete_rule(rule_id: str) -> None:
        if not rule_repository.delete(rule_id):
            raise HTTPException(status_code=404, detail="Rule not found")
        await broadcaster.broadcast_json({"type": "rule.deleted", "rule_id": rule_id})

    return router

