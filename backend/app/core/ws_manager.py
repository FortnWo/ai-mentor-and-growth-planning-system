import asyncio
import json
from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # maps user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # event loop used to schedule cross-thread notifications
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        conns = self.active_connections.setdefault(user_id, set())
        conns.add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        conns = self.active_connections.get(user_id)
        if not conns:
            return
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            # cleanup empty entry
            self.active_connections.pop(user_id, None)

    async def send_personal_message(self, user_id: int, message: dict) -> None:
        conns = list(self.active_connections.get(user_id, []))
        if not conns:
            return
        payload = json.dumps(message, default=str)
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                # on error, try to clean up connection
                try:
                    self.disconnect(user_id, ws)
                except Exception:
                    pass


# single global manager
manager = ConnectionManager()
