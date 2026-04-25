import unittest

from app.domain.models import (
    DeliveryAttempt,
    DeliveryStatus,
    ForwardingRule,
    WebhookEvent,
)
from app.repositories.memory import InMemoryEventRepository, InMemoryRuleRepository


def make_event(event_id: str, source: str = "github") -> WebhookEvent:
    return WebhookEvent(
        id=event_id,
        source=source,
        method="POST",
        path=f"/webhooks/{source}",
        headers={},
        query_params={},
        raw_body=b"{}",
        json_payload={},
        event_type="push",
    )


class InMemoryEventRepositoryTests(unittest.TestCase):
    def test_retains_newest_events_by_limit(self) -> None:
        repository = InMemoryEventRepository(retention_limit=2)
        repository.add(make_event("evt_1"))
        repository.add(make_event("evt_2"))
        repository.add(make_event("evt_3"))

        self.assertIsNone(repository.get("evt_1"))
        self.assertEqual(
            [event.id for event in repository.list(limit=10)],
            ["evt_3", "evt_2"],
        )

    def test_add_is_idempotent_for_existing_event_id(self) -> None:
        repository = InMemoryEventRepository()
        repository.add(make_event("evt_same", source="github"))
        repository.add(make_event("evt_same", source="stripe"))

        events = repository.list(limit=10)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source, "stripe")

    def test_add_if_new_reuses_existing_event_for_idempotency_key(self) -> None:
        repository = InMemoryEventRepository()
        first = make_event("evt_first", source="stripe")
        first.idempotency_key = "stripe:evt_123"
        second = make_event("evt_second", source="stripe")
        second.idempotency_key = "stripe:evt_123"

        saved_first, created_first = repository.add_if_new(first)
        saved_second, created_second = repository.add_if_new(second)

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(saved_first.id, saved_second.id)
        self.assertEqual([event.id for event in repository.list(limit=10)], ["evt_first"])

    def test_append_delivery_attempt_updates_event_status(self) -> None:
        repository = InMemoryEventRepository()
        event = repository.add(make_event("evt_delivery"))
        attempt = DeliveryAttempt(
            event_id=event.id,
            rule_id="rule_1",
            endpoint_url="https://receiver.test",
            status=DeliveryStatus.SUCCESS,
            status_code=200,
            attempt_number=1,
        )

        repository.append_delivery_attempt(event.id, attempt)

        saved = repository.get(event.id)
        self.assertEqual(len(saved.delivery_attempts), 1)
        self.assertEqual(saved.status.value, "forwarded")


class InMemoryRuleRepositoryTests(unittest.TestCase):
    def test_rule_crud(self) -> None:
        repository = InMemoryRuleRepository()
        rule = repository.add(
            ForwardingRule(
                name="Orders",
                endpoint_url="https://receiver.test/orders",
            )
        )

        repository.update(rule.id, enabled=False, source="stripe")

        self.assertEqual(repository.get(rule.id).source, "stripe")
        self.assertFalse(repository.get(rule.id).enabled)
        self.assertTrue(repository.delete(rule.id))
        self.assertIsNone(repository.get(rule.id))


if __name__ == "__main__":
    unittest.main()
