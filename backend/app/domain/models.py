from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


class EventStatus(str, Enum):
    RECEIVED = "received"
    REJECTED = "rejected"
    FORWARDED = "forwarded"
    FORWARD_FAILED = "forward_failed"
    REPLAYED = "replayed"


class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DeliveryAttempt:
    """A single outbound delivery try.

    The attempt keeps the event id and attempt number so downstream receivers can
    implement idempotency. A durable version would also persist a unique
    idempotency key and retry schedule in PostgreSQL or a queue table.
    """

    event_id: str
    rule_id: str
    endpoint_url: str
    status: DeliveryStatus
    attempt_number: int
    id: str = field(default_factory=lambda: new_id("attempt"))
    status_code: int | None = None
    error: str | None = None
    duration_ms: float | None = None
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "rule_id": self.rule_id,
            "endpoint_url": self.endpoint_url,
            "status": self.status.value,
            "attempt_number": self.attempt_number,
            "status_code": self.status_code,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class WebhookEvent:
    """Captured inbound webhook.

    Raw bytes are retained for replay and signature verification. That matters
    because HMAC signatures are calculated over the exact request body, not a
    parsed/reformatted JSON representation.
    """

    source: str
    method: str
    path: str
    headers: dict[str, str]
    query_params: dict[str, str]
    raw_body: bytes
    json_payload: Any | None
    event_type: str | None = None
    signature_valid: bool | None = None
    idempotency_key: str | None = None
    id: str = field(default_factory=lambda: new_id("evt"))
    status: EventStatus = EventStatus.RECEIVED
    received_at: datetime = field(default_factory=utc_now)
    delivery_attempts: list[DeliveryAttempt] = field(default_factory=list)
    replay_count: int = 0

    @property
    def body_text(self) -> str:
        return self.raw_body.decode("utf-8", errors="replace")

    def to_dict(self) -> dict[str, Any]:
        parsed_body: Any
        if self.json_payload is not None:
            parsed_body = self.json_payload
        else:
            parsed_body = self.body_text

        return {
            "id": self.id,
            "source": self.source,
            "method": self.method,
            "path": self.path,
            "headers": self.headers,
            "query_params": self.query_params,
            "body": parsed_body,
            "body_text": self.body_text,
            "event_type": self.event_type,
            "signature_valid": self.signature_valid,
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "received_at": self.received_at.isoformat(),
            "delivery_attempts": [
                attempt.to_dict() for attempt in self.delivery_attempts
            ],
            "replay_count": self.replay_count,
        }


@dataclass
class ForwardingRule:
    """Rule deciding whether an event should be forwarded.

    Rule matching stays explicit: source, event type, and selected headers.
    That makes forwarding auditable and avoids accidentally relaying every
    inbound webhook to a sensitive endpoint.
    """

    name: str
    endpoint_url: str
    source: str | None = None
    event_type: str | None = None
    header_matches: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    max_retries: int = 2
    timeout_seconds: float = 5.0
    id: str = field(default_factory=lambda: new_id("rule"))
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "endpoint_url": self.endpoint_url,
            "source": self.source,
            "event_type": self.event_type,
            "header_matches": self.header_matches,
            "enabled": self.enabled,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ReplayResult:
    event_id: str
    attempts: list[DeliveryAttempt]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "attempt_count": len(self.attempts),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


def parse_json_body(raw_body: bytes) -> Any | None:
    if not raw_body:
        return None
    try:
        return json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
