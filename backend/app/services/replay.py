from __future__ import annotations

from app.domain.models import ForwardingRule, ReplayResult
from app.repositories.memory import InMemoryEventRepository, InMemoryRuleRepository
from app.services.forwarding import ForwardingService


class ReplayService:
    """Replay previously captured events.

    Replays reuse the original raw body and headers, then add relay metadata in
    the forwarding layer. This keeps replay behavior close to the original
    webhook while still giving receivers enough information to deduplicate.
    """

    def __init__(
        self,
        event_repository: InMemoryEventRepository,
        rule_repository: InMemoryRuleRepository,
        forwarding_service: ForwardingService,
    ) -> None:
        self.event_repository = event_repository
        self.rule_repository = rule_repository
        self.forwarding_service = forwarding_service

    async def replay_event(
        self,
        event_id: str,
        target_rule_ids: list[str] | None = None,
        override_url: str | None = None,
    ) -> ReplayResult:
        event = self.event_repository.get(event_id)
        if not event:
            raise KeyError(f"Event {event_id} was not found")

        rules = self._resolve_rules(event_id, target_rule_ids, override_url)
        attempts = []
        for rule in rules:
            attempt = await self.forwarding_service.forward_event(event, rule)
            self.event_repository.append_delivery_attempt(event.id, attempt)
            attempts.append(attempt)

        self.event_repository.mark_replayed(event.id)
        return ReplayResult(event_id=event.id, attempts=attempts)

    def _resolve_rules(
        self,
        event_id: str,
        target_rule_ids: list[str] | None,
        override_url: str | None,
    ) -> list[ForwardingRule]:
        event = self.event_repository.get(event_id)
        if not event:
            raise KeyError(f"Event {event_id} was not found")

        if override_url:
            return [
                ForwardingRule(
                    name="Manual replay target",
                    endpoint_url=override_url,
                    source=event.source,
                    event_type=event.event_type,
                )
            ]
        if target_rule_ids:
            return [
                rule
                for rule_id in target_rule_ids
                if (rule := self.rule_repository.get(rule_id)) is not None
            ]
        return self.forwarding_service.matching_rules(
            event, self.rule_repository.list()
        )

