from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.broadcaster import ConnectionManager


def create_websocket_router(broadcaster: ConnectionManager) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws/events")
    async def events_socket(websocket: WebSocket) -> None:
        await broadcaster.connect(websocket)
        await websocket.send_json({"type": "socket.connected"})
        try:
            while True:
                message = await websocket.receive_text()
                if message == "ping":
                    await websocket.send_json({"type": "socket.pong"})
        except WebSocketDisconnect:
            broadcaster.disconnect(websocket)

    return router

