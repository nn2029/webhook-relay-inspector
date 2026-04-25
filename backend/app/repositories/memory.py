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
    """Thread-safe in-memory event store for the MVP.

    This is intentionally simple for local demos and portfolio review. The
    compromise is that events disappear on process restart and retention is only
    count-based. The repository shape mirrors what a PostgreSQL implementation
    would need later: insert, lookup, append delivery attempt, list newest, and
    prune retained events.
    """

    def __init__(self, retention_limit: int = 1000) -> None:
        self.retention_limit = retention_limit
        self._events: dict[str, WebhookEvent] = {}
        self._order: deque[str] = deque()
        self._lock = RLock()

    def add(self, event: WebhookEvent) -> WebhookEvent:
        """Add or replace an event by id without duplicating list order.

        The replacement behavior is a small idempotency guard for tests,
        retries, or future ingestion paths that may submit the same event id.
        """

        with self._lock:
            if event.id not in self._events:
                self._order.append(event.id)
            self._events[event.id] = event
            self._prune_locked()
            return event

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
            self._events.pop(oldest_id, None)


class InMemoryRuleRepository:
    """In-memory forwarding rule store.

    Rules use the same repository contract a database adapter can implement
    later. PostgreSQL would add ownership, audit history, and encryption for
    secret endpoint credentials.
    """

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

