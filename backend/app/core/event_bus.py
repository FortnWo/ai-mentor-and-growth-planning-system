from __future__ import annotations

import logging
from collections import defaultdict
from threading import RLock
from typing import Callable

from app.core.domain_events import DomainEvent, build_domain_event


logger = logging.getLogger("ai_mentor.events")
EventHandler = Callable[[DomainEvent], None]


class EventDispatchError(RuntimeError):
    def __init__(self, event: DomainEvent, errors: list[Exception]):
        super().__init__(f"Event dispatch failed for {event.name} with {len(errors)} error(s)")
        self.event = event
        self.errors = errors


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        if not event_name:
            raise ValueError("event_name is required")

        with self._lock:
            handlers = self._handlers[event_name]
            if handler not in handlers:
                handlers.append(handler)

    def subscribers(self, event_name: str) -> list[EventHandler]:
        with self._lock:
            return list(self._handlers.get(event_name, []))

    def publish(
        self,
        *,
        event_name: str,
        user_id: int,
        payload: dict | None = None,
        trace_id: str | None = None,
        fail_fast: bool = False,
    ) -> DomainEvent:
        event = build_domain_event(
            event_name=event_name,
            user_id=user_id,
            payload=payload,
            trace_id=trace_id,
        )
        errors = self.dispatch(event, fail_fast=fail_fast)
        if errors and not fail_fast:
            logger.warning(
                "Event dispatched with handler errors event_name=%s user_id=%s trace_id=%s error_count=%s",
                event.name,
                event.user_id,
                event.trace_id,
                len(errors),
            )
        return event

    def dispatch(self, event: DomainEvent, *, fail_fast: bool = False) -> list[Exception]:
        handlers = self.subscribers(event.name)
        errors: list[Exception] = []

        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.exception(
                    "Event handler failed event_name=%s trace_id=%s handler=%s",
                    event.name,
                    event.trace_id,
                    getattr(handler, "__name__", str(handler)),
                )
                errors.append(exc)
                if fail_fast:
                    raise EventDispatchError(event, errors) from exc

        return errors


event_bus = EventBus()

