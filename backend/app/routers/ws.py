import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt
import redis.asyncio as aioredis
from app.config import settings

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self._listener_task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        # Start shared Redis listener on first connection
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._redis_listener())

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def _redis_listener(self):
        """Single shared Redis pub/sub listener that broadcasts to ALL connected clients."""
        redis_client = aioredis.from_url(settings.REDIS_URL)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("job_updates")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await self.broadcast(data)
                    except Exception:
                        pass
                # Stop if no more clients
                if not self.active:
                    break
        finally:
            await pubsub.unsubscribe("job_updates")
            await redis_client.aclose()


manager = ConnectionManager()


def verify_ws_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub") is not None
    except JWTError:
        return False


@router.websocket("/ws/jobs")
async def websocket_jobs(ws: WebSocket, token: str = Query(default="")):
    if not verify_ws_token(token):
        await ws.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(ws)

    try:
        # Keep connection alive by listening for client messages
        while True:
            try:
                await ws.receive_text()
            except WebSocketDisconnect:
                break
    finally:
        manager.disconnect(ws)
