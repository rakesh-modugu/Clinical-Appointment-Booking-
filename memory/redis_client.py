"""
redis_client.py — Async Redis client for short-term session context memory.

Key schema : session:<session_id>
Value      : JSON-serialised dict containing intent, language, slot state,
             conversation turns, and pending confirmation flags.
TTL        : Configurable per call; defaults to 3600s (1 hour).
             Reset on every write so active sessions never expire mid-flow.
             Deleted immediately on explicit session termination.

Failure policy
--------------
Redis is treated as a soft dependency. If the server is unreachable, all
functions log the error and return safe defaults (empty dict / False) so the
voice agent degrades gracefully rather than crashing the request.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection pool (module-level singleton — created once, reused by all calls)
# ---------------------------------------------------------------------------

_pool: aioredis.ConnectionPool = aioredis.ConnectionPool.from_url(
    "redis://localhost:6379/0",
    max_connections=20,
    decode_responses=True,       # All responses returned as str, never bytes
    socket_connect_timeout=2,    # Hard timeout so a dead Redis doesn't block requests
    socket_timeout=2,
)


def _get_client() -> aioredis.Redis:
    """Return a lightweight async Redis client backed by the shared pool."""
    return aioredis.Redis(connection_pool=_pool)


def _build_key(session_id: str) -> str:
    """Namespace all session keys under a consistent prefix."""
    return f"session:{session_id}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def save_session_context(
    session_id: str,
    context_data: dict[str, Any],
    ttl_seconds: int = 3600,
) -> bool:
    """
    Persist the full session context to Redis as a JSON string.

    Parameters
    ----------
    session_id   : Unique identifier for the voice session (UUID string).
    context_data : Arbitrary dict containing the current session state, e.g.:
                   {
                       "patient_id"          : "...",
                       "current_intent"      : "booking",
                       "language"            : "Hindi",
                       "pending_confirmation": False,
                       "extracted_entities"  : {...},
                       "conversation_state"  : [...],
                   }
    ttl_seconds  : Seconds until the key expires (default 3600).
                   The TTL is refreshed on every call, so active conversations
                   never expire mid-flow.

    Returns
    -------
    True on success, False if Redis is unavailable (caller can ignore safely).
    """
    key = _build_key(session_id)
    client = _get_client()
    try:
        serialised = json.dumps(context_data, default=str)
        await client.setex(name=key, time=ttl_seconds, value=serialised)
        logger.debug("Session context saved. key=%s ttl=%ds", key, ttl_seconds)
        return True
    except aioredis.RedisError as exc:
        logger.error(
            "Redis unavailable — could not save session context. key=%s error=%s",
            key, exc,
        )
        return False
    except (TypeError, ValueError) as exc:
        logger.error(
            "Serialisation error for session context. key=%s error=%s", key, exc
        )
        return False
    finally:
        await client.aclose()


async def get_session_context(session_id: str) -> dict[str, Any]:
    """
    Retrieve and deserialise the session context for the given session_id.

    Returns
    -------
    Parsed dict on success.
    Empty dict {}  if:
      - the key does not exist (session expired or never created), or
      - Redis is unreachable, or
      - the stored value cannot be parsed as JSON.
    """
    key = _build_key(session_id)
    client = _get_client()
    try:
        raw: str | None = await client.get(key)
        if raw is None:
            logger.debug("Session context not found. key=%s", key)
            return {}
        context = json.loads(raw)
        logger.debug("Session context retrieved. key=%s", key)
        return context
    except aioredis.RedisError as exc:
        logger.error(
            "Redis unavailable — could not retrieve session context. key=%s error=%s",
            key, exc,
        )
        return {}
    except json.JSONDecodeError as exc:
        logger.error(
            "Corrupt session context in Redis (invalid JSON). key=%s error=%s", key, exc
        )
        return {}
    finally:
        await client.aclose()


async def delete_session_context(session_id: str) -> bool:
    """
    Immediately remove the session context key from Redis.

    Call this on explicit session termination (hang-up / user says 'goodbye')
    rather than waiting for the TTL to expire — keeps Redis memory clean.

    Returns
    -------
    True if the key was deleted (or did not exist), False on Redis error.
    """
    key = _build_key(session_id)
    client = _get_client()
    try:
        await client.delete(key)
        logger.debug("Session context deleted. key=%s", key)
        return True
    except aioredis.RedisError as exc:
        logger.error(
            "Redis unavailable — could not delete session context. key=%s error=%s",
            key, exc,
        )
        return False
    finally:
        await client.aclose()


async def update_session_field(
    session_id: str,
    field: str,
    value: Any,
    ttl_seconds: int = 3600,
) -> bool:
    """
    Convenience helper: update a single top-level field in the session context
    without overwriting the entire document.

    Performs a read-modify-write cycle. Not atomic — use `save_session_context`
    for bulk updates where atomicity matters.

    Parameters
    ----------
    session_id  : Target session.
    field       : The key inside the context dict to update, e.g. "current_intent".
    value       : New value to assign.
    ttl_seconds : TTL to (re)set on the key after the write.
    """
    context = await get_session_context(session_id)
    context[field] = value
    return await save_session_context(session_id, context, ttl_seconds)


async def append_conversation_turn(
    session_id: str,
    role: str,
    content: str,
    max_turns: int = 10,
    ttl_seconds: int = 3600,
) -> bool:
    """
    Append a single conversation turn to `conversation_state` and cap the list
    at `max_turns` to bound Redis memory usage.

    Parameters
    ----------
    session_id : Target session.
    role       : "user" or "agent".
    content    : Transcript text for this turn.
    max_turns  : Maximum number of turns to retain (oldest dropped first).
    ttl_seconds: TTL to refresh on the session key.
    """
    from datetime import datetime, timezone

    context = await get_session_context(session_id)
    turns: list[dict] = context.get("conversation_state", [])

    turns.append(
        {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Trim to the most recent `max_turns` entries
    if len(turns) > max_turns:
        turns = turns[-max_turns:]

    context["conversation_state"] = turns
    return await save_session_context(session_id, context, ttl_seconds)
