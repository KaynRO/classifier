import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis
from app.config import settings

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

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


manager = ConnectionManager()


@router.websocket("/ws/jobs")
async def websocket_jobs(ws: WebSocket):
    await manager.connect(ws)

    # Subscribe to Redis pub/sub for job updates
    redis_client = aioredis.from_url(settings.REDIS_URL)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("job_updates")

    try:
        async def listen_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await ws.send_json(data)
                    except Exception:
                        pass

        async def listen_client():
            while True:
                try:
                    await ws.receive_text()
                except WebSocketDisconnect:
                    break

        # Run both listeners concurrently
        await asyncio.gather(listen_redis(), listen_client(), return_exceptions=True)

    finally:
        manager.disconnect(ws)
        await pubsub.unsubscribe("job_updates")
        await redis_client.aclose()
