from __future__ import annotations

from collections import deque
from threading import RLock

from app.domain.models import (
    DeliveryAttempt,
    EventStatus,
    ForwardingRule,
    WebhookEvent,
)


class InMemoryEventRepository:
    """Thread-safe event store with count-based retention.

    The methods mirror the database operations this service would keep in SQL:
    insert once, find by idempotency key, append delivery attempts, list newest,
    and prune old rows. The storage is still process-local; the boundary is the
    part worth demonstrating.
    """

    def __init__(self, retention_limit: int = 1000) -> None:
        self.retention_limit = retention_limit
        self._events: dict[str, WebhookEvent] = {}
        self._idempotency_index: dict[str, str] = {}
        self._order: deque[str] = deque()
        self._lock = RLock()

    def add(self, event: WebhookEvent) -> WebhookEvent:
        saved, _ = self.add_if_new(event)
        return saved

    def add_if_new(self, event: WebhookEvent) -> tuple[WebhookEvent, bool]:
        with self._lock:
            if event.idempotency_key:
                existing_id = self._idempotency_index.get(event.idempotency_key)
                if existing_id and existing_id in self._events:
                    return self._events[existing_id], False

            if event.id not in self._events:
                self._order.append(event.id)
            self._events[event.id] = event
            if event.idempotency_key:
                self._idempotency_index[event.idempotency_key] = event.id
            self._prune_locked()
            return event, True

    def get(self, event_id: str) -> WebhookEvent | None:
        with self._lock:
            return self._events.get(event_id)

    def list(
        self,
        limit: int = 50,
        source: str | None = None,
        event_type: str | None = None,
    ) -> list[WebhookEvent]:
        with self._lock:
            events = [self._events[event_id] for event_id in reversed(self._order)]
            if source:
                events = [event for event in events if event.source == source]
            if event_type:
                events = [event for event in events if event.event_type == event_type]
            return events[:limit]

    def append_delivery_attempt(
        self, event_id: str, attempt: DeliveryAttempt
    ) -> WebhookEvent | None:
        with self._lock:
            event = self._events.get(event_id)
            if not event:
                return None
            event.delivery_attempts.append(attempt)
            if attempt.status.value == "success":
                event.status = EventStatus.FORWARDED
            elif attempt.status.value == "failed":
                event.status = EventStatus.FORWARD_FAILED
            return event

    def mark_replayed(self, event_id: str) -> WebhookEvent | None:
        with self._lock:
            event = self._events.get(event_id)
            if not event:
                return None
            event.replay_count += 1
            event.status = EventStatus.REPLAYED
            return event

    def _prune_locked(self) -> None:
        while len(self._order) > self.retention_limit:
            oldest_id = self._order.popleft()
            event = self._events.pop(oldest_id, None)
            if event and event.idempotency_key:
                self._idempotency_index.pop(event.idempotency_key, None)


class InMemoryRuleRepository:
    """In-memory forwarding rule store with a database-friendly contract."""

    def __init__(self) -> None:
        self._rules: dict[str, ForwardingRule] = {}
        self._lock = RLock()

    def add(self, rule: ForwardingRule) -> ForwardingRule:
        with self._lock:
            self._rules[rule.id] = rule
            return rule

    def get(self, rule_id: str) -> ForwardingRule | None:
        with self._lock:
            return self._rules.get(rule_id)

    def list(self) -> list[ForwardingRule]:
        with self._lock:
            return list(self._rules.values())

    def update(self, rule_id: str, **changes: object) -> ForwardingRule | None:
        with self._lock:
            rule = self._rules.get(rule_id)
            if not rule:
                return None
            for key, value in changes.items():
                if hasattr(rule, key) and value is not None:
                    setattr(rule, key, value)
            return rule

    def delete(self, rule_id: str) -> bool:
        with self._lock:
            return self._rules.pop(rule_id, None) is not None
