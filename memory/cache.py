"""
General-purpose TTL cache for LLM responses and embeddings.
Avoids redundant LLM calls for identical inputs within the TTL window.
Key schema:  cache:{namespace}:{hash(key)}  → JSON value string
"""

import hashlib
import json
from memory.redis_client import get_redis

DEFAULT_TTL = 60 * 10  # 10 minutes


async def cache_get(namespace: str, key: str) -> dict | None:
    """Return cached value for key, or None on miss."""
    redis = get_redis()
    hashed = hashlib.sha256(key.encode()).hexdigest()
    raw = await redis.get(f"cache:{namespace}:{hashed}")
    return json.loads(raw) if raw else None


async def cache_set(namespace: str, key: str, value: dict, ttl: int = DEFAULT_TTL):
    """Store value in cache with a TTL."""
    redis = get_redis()
    hashed = hashlib.sha256(key.encode()).hexdigest()
    await redis.setex(f"cache:{namespace}:{hashed}", ttl, json.dumps(value))


async def cache_invalidate(namespace: str, key: str):
    """Remove a specific cache entry."""
    redis = get_redis()
    hashed = hashlib.sha256(key.encode()).hexdigest()
    await redis.delete(f"cache:{namespace}:{hashed}")
