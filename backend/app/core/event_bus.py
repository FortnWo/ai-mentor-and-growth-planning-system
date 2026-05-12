from collections import defaultdict
from threading import RLock
from typing import Any, Callable

from sqlalchemy.orm import Session

EventPayload = dict[str, Any]
EventHandler = Callable[[Session, EventPayload], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._handlers[event_name]
            if handler not in handlers:
                handlers.append(handler)

    def publish(self, db: Session, event_name: str, payload: EventPayload) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event_name, []))

        for handler in handlers:
            handler(db, payload)


event_bus = EventBus()
