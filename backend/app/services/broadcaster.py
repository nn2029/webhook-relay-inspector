from __future__ import annotations

from typing import Any


class ConnectionManager:
    """Small WebSocket fanout helper.

    Live updates are best-effort. The repository remains the source of truth, so
    a disconnected browser can catch up through HTTP after reconnecting.
    """

    def __init__(self) -> None:
        self.active_connections: set[Any] = set()

    async def connect(self, websocket: Any) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: Any) -> None:
        self.active_connections.discard(websocket)

    async def broadcast_json(self, payload: dict[str, Any]) -> None:
        stale_connections = []
        for websocket in self.active_connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale_connections.append(websocket)
        for websocket in stale_connections:
            self.disconnect(websocket)
