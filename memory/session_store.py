"""
Session context store — persists conversation turns in Redis per session.
Key schema:  session:{session_id}:history  → Redis List of JSON-encoded turns
TTL: 24 hours after last write.
"""

import json
from memory.redis_client import get_redis

SESSION_TTL = 60 * 60 * 24  # 24 hours


class SessionStore:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.key = f"session:{session_id}:history"
        self._redis = get_redis()

    async def get_history(self) -> list[dict]:
        """Retrieve all turns as a list of {role, content} dicts."""
        raw = await self._redis.lrange(self.key, 0, -1)
        return [json.loads(item) for item in raw]

    async def append_turn(self, user: str, assistant: str):
        """Append a user+assistant turn pair and refresh TTL."""
        pipe = self._redis.pipeline()
        pipe.rpush(self.key, json.dumps({"role": "user", "content": user}))
        pipe.rpush(self.key, json.dumps({"role": "assistant", "content": assistant}))
        pipe.expire(self.key, SESSION_TTL)
        await pipe.execute()

    async def clear(self):
        await self._redis.delete(self.key)

    async def close(self):
        await self._redis.aclose()
