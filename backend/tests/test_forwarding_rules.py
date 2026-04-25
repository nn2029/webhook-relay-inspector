import unittest

from app.domain.models import ForwardingRule, WebhookEvent, parse_json_body
from app.repositories.memory import InMemoryEventRepository, InMemoryRuleRepository
from app.services.forwarding import ForwardingService
from app.services.replay import ReplayService


def make_event() -> WebhookEvent:
    body = b'{"type":"order.created","id":"evt_1"}'
    return WebhookEvent(
        source="stripe",
        method="POST",
        path="/webhooks/stripe",
        headers={"x-event-type": "order.created", "x-tenant": "demo"},
        query_params={},
        raw_body=body,
        json_payload=parse_json_body(body),
        event_type="order.created",
        signature_valid=True,
    )


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeClient:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.calls = []

    async def post(self, url: str, *, content: bytes, headers: dict, timeout: float):
        self.calls.append(
            {
                "url": url,
                "content": content,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return FakeResponse(self.status_code)


class ForwardingRuleTests(unittest.TestCase):
    def test_matches_source_event_type_and_headers(self) -> None:
        event = make_event()
        service = ForwardingService(http_client=FakeClient())
        matching = ForwardingRule(
            name="Stripe orders",
            endpoint_url="https://example.test/webhook",
            source="stripe",
            event_type="order.created",
            header_matches={"X-Tenant": "demo"},
        )
        wrong_type = ForwardingRule(
            name="Invoices",
            endpoint_url="https://example.test/webhook",
            source="stripe",
            event_type="invoice.paid",
        )
        disabled = ForwardingRule(
            name="Disabled",
            endpoint_url="https://example.test/webhook",
            enabled=False,
        )

        self.assertEqual(
            service.matching_rules(event, [matching, wrong_type, disabled]),
            [matching],
        )


class ReplayServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_replay_forwards_to_matching_rules_and_records_attempt(self) -> None:
        event_repo = InMemoryEventRepository()
        rule_repo = InMemoryRuleRepository()
        event = event_repo.add(make_event())
        rule = rule_repo.add(
            ForwardingRule(
                name="Orders",
                endpoint_url="https://receiver.test/orders",
                source="stripe",
                event_type="order.created",
            )
        )
        fake_client = FakeClient()
        forwarding = ForwardingService(
            http_client=fake_client,
            relay_signing_secret="relay-secret",
        )
        replay = ReplayService(event_repo, rule_repo, forwarding)

        result = await replay.replay_event(event.id)

        self.assertEqual(len(result.attempts), 1)
        self.assertEqual(result.attempts[0].rule_id, rule.id)
        self.assertEqual(len(event_repo.get(event.id).delivery_attempts), 1)
        self.assertEqual(fake_client.calls[0]["url"], "https://receiver.test/orders")
        self.assertEqual(fake_client.calls[0]["content"], event.raw_body)
        self.assertIn("x-relay-event-id", fake_client.calls[0]["headers"])
        self.assertIn("x-relay-signature", fake_client.calls[0]["headers"])


if __name__ == "__main__":
    unittest.main()

