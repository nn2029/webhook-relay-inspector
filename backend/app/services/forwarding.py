from __future__ import annotations

import time
from typing import Protocol

from app.core.signatures import compute_hmac_signature
from app.domain.models import (
    DeliveryAttempt,
    DeliveryStatus,
    ForwardingRule,
    WebhookEvent,
    normalize_headers,
)


class HttpResponse(Protocol):
    status_code: int


class AsyncHttpPoster(Protocol):
    async def post(
        self,
        url: str,
        *,
        content: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse:
        ...


class HttpxPoster:
    async def post(
        self,
        url: str,
        *,
        content: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse:
        import httpx

        async with httpx.AsyncClient() as client:
            return await client.post(
                url, content=content, headers=headers, timeout=timeout
            )


HOP_BY_HOP_HEADERS = {
    "accept-encoding",
    "connection",
    "content-length",
    "host",
    "transfer-encoding",
}


class ForwardingService:
    """Matches rules and delivers webhooks to downstream endpoints.

    Retries are bounded and synchronous inside this service for the MVP. A
    production version should move attempts into a durable queue with exponential
    backoff, dead-letter handling, and an idempotency key carried through every
    attempt.
    """

    def __init__(
        self,
        http_client: AsyncHttpPoster | None = None,
        relay_signing_secret: str | None = None,
    ) -> None:
        self.http_client = http_client or HttpxPoster()
        self.relay_signing_secret = relay_signing_secret

    def matching_rules(
        self, event: WebhookEvent, rules: list[ForwardingRule]
    ) -> list[ForwardingRule]:
        return [rule for rule in rules if self.rule_matches_event(rule, event)]

    def rule_matches_event(self, rule: ForwardingRule, event: WebhookEvent) -> bool:
        if not rule.enabled:
            return False
        if rule.source and rule.source != event.source:
            return False
        if rule.event_type and rule.event_type != event.event_type:
            return False

        event_headers = normalize_headers(event.headers)
        expected_headers = normalize_headers(rule.header_matches)
        for key, expected in expected_headers.items():
            if event_headers.get(key) != expected:
                return False
        return True

    async def forward_event(
        self, event: WebhookEvent, rule: ForwardingRule
    ) -> DeliveryAttempt:
        headers = self._forward_headers(event)
        status_code: int | None = None
        error: str | None = None
        started = time.perf_counter()
        final_attempt_number = 0

        # max_retries means "retries after the first try", so +1 total tries.
        for attempt_number in range(1, rule.max_retries + 2):
            final_attempt_number = attempt_number
            headers["x-relay-attempt"] = str(attempt_number)
            try:
                response = await self.http_client.post(
                    rule.endpoint_url,
                    content=event.raw_body,
                    headers=headers,
                    timeout=rule.timeout_seconds,
                )
                status_code = response.status_code
                error = None
                if 200 <= status_code < 300:
                    break
                error = f"Endpoint returned HTTP {status_code}"
                if status_code < 500:
                    break
            except Exception as exc:  # pragma: no cover - exercised by integrations
                error = str(exc)

        duration_ms = (time.perf_counter() - started) * 1000
        status = (
            DeliveryStatus.SUCCESS
            if status_code is not None and 200 <= status_code < 300
            else DeliveryStatus.FAILED
        )
        return DeliveryAttempt(
            event_id=event.id,
            rule_id=rule.id,
            endpoint_url=rule.endpoint_url,
            status=status,
            status_code=status_code,
            error=error,
            attempt_number=final_attempt_number,
            duration_ms=round(duration_ms, 2),
        )

    def _forward_headers(self, event: WebhookEvent) -> dict[str, str]:
        headers = {
            key: value
            for key, value in event.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS
        }
        headers["x-relay-event-id"] = event.id
        headers["x-relay-source"] = event.source
        if event.event_type:
            headers["x-relay-event-type"] = event.event_type
        if self.relay_signing_secret:
            headers["x-relay-signature"] = compute_hmac_signature(
                self.relay_signing_secret, event.raw_body
            )
        return headers

