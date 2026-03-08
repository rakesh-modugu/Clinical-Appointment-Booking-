"""
voice.py — WebSocket route for real-time bi-directional voice streaming.
==========================================================================

Concurrency Model
-----------------
Two asyncio Tasks run concurrently for each connected client:

  ┌─────────────────────────────────────────────────────────────────────┐
  │  Task A: _reader  (frontend → server)                               │
  │  Reads raw PCM audio frames from the WebSocket and enqueues them    │
  │  into the VoiceAgent's audio queue (which feeds Deepgram STT).       │
  │  Also handles JSON control messages (e.g., {"type": "end_session"}). │
  ├─────────────────────────────────────────────────────────────────────┤
  │  Task B: _writer  (server → frontend)                               │
  │  Reads audio bytes from an asyncio.Queue populated by the agent's   │
  │  TTS callback and sends them as binary WebSocket frames.            │
  └─────────────────────────────────────────────────────────────────────┘

The two tasks run via `asyncio.gather`, so the write path is never blocked
by the read path. This is critical: TTS audio chunks can be sent to the
client while more audio is still arriving from the microphone.

Message Protocol (frontend ↔ backend)
--------------------------------------
  INBOUND  (frontend → backend)
    - Binary frame          : Raw PCM audio bytes (16kHz, 16-bit mono)
    - JSON text frame       : Control message, e.g.
        {"type": "start_session", "session_id": "<uuid>"}
        {"type": "end_session"}

  OUTBOUND (backend → frontend)
    - Binary frame          : Raw MP3/audio bytes from TTS
    - JSON text frame       : Status events, e.g.
        {"type": "transcript",  "text": "...", "is_final": true}
        {"type": "agent_state", "state": "thinking" | "speaking" | "idle"}
        {"type": "error",       "message": "..."}
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

from core.agent import VoiceAgent
from memory.redis_client import delete_session_context, save_session_context

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _send_json(ws: WebSocket, payload: dict) -> None:
    """Send a JSON control message if the socket is still open."""
    if ws.client_state == WebSocketState.CONNECTED:
        try:
            await ws.send_json(payload)
        except Exception as exc:
            logger.debug("JSON send failed (client likely disconnected): %s", exc)


async def _send_audio(ws: WebSocket, audio_bytes: bytes) -> None:
    """Send binary audio frame if the socket is still open."""
    if ws.client_state == WebSocketState.CONNECTED:
        try:
            await ws.send_bytes(audio_bytes)
        except Exception as exc:
            logger.debug("Audio send failed (client likely disconnected): %s", exc)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/voice/{session_id}")
async def voice_stream(websocket: WebSocket, session_id: str) -> None:
    """
    Persistent bi-directional WebSocket for one voice session.

    Path parameter
    --------------
    session_id : UUID string — the caller must generate this before connecting
                 and use the same ID to retrieve Redis session context. The
                 frontend should POST /api/sessions/start first to obtain it.

    Connection lifecycle
    --------------------
    1. Accept the WebSocket.
    2. Initialise a `VoiceAgent` for this session and start the STT loop.
    3. Launch concurrent _reader / _writer asyncio Tasks.
    4. On disconnect (graceful or abrupt), cancel both tasks and call
       agent.cleanup() to drain the Deepgram stream and write final state.
    """
    await websocket.accept()
    logger.info("WebSocket accepted. session=%s  client=%s", session_id, websocket.client)

    # Queue that bridges the _tts_callback (agent side) to the _writer task
    outbound_audio_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)

    async def _tts_audio_callback(audio_chunk: bytes) -> None:
        """Called by VoiceAgent for each TTS audio frame — enqueue for _writer."""
        try:
            outbound_audio_q.put_nowait(audio_chunk)
        except asyncio.QueueFull:
            logger.warning("Outbound audio queue full — dropping TTS frame. session=%s", session_id)

    # Initialise and start the agent
    agent = VoiceAgent(session_id=session_id)
    await agent.start(on_audio_out=_tts_audio_callback)

    # Seed Redis context for this session
    await save_session_context(session_id, {
        "session_id":           session_id,
        "patient_id":           None,
        "current_intent":       "greeting",
        "pending_confirmation": False,
        "extracted_entities": {
            "doctor_name":     None,
            "specialization":  None,
            "preferred_date":  None,
            "preferred_time":  None,
            "appointment_id":  None,
        },
        "conversation_state":   [],
        "language":             "English",
    }, ttl_seconds=3600)

    await _send_json(websocket, {"type": "agent_state", "state": "listening"})

    # -----------------------------------------------------------------------
    # Task A: Reader — frontend → agent (audio + control messages)
    # -----------------------------------------------------------------------
    async def _reader() -> None:
        try:
            while True:
                message = await websocket.receive()

                # Binary frame → raw PCM audio chunk
                if "bytes" in message and message["bytes"]:
                    await agent.send_audio(message["bytes"])

                # Text frame → JSON control message
                elif "text" in message and message["text"]:
                    try:
                        ctrl = json.loads(message["text"])
                    except json.JSONDecodeError:
                        logger.warning("Malformed control message. session=%s", session_id)
                        continue

                    msg_type = ctrl.get("type", "")

                    if msg_type == "end_session":
                        logger.info("Client requested session end. session=%s", session_id)
                        return   # Exit reader → triggers cleanup in the outer scope

                    elif msg_type == "set_language":
                        lang = ctrl.get("language", "English")
                        from memory.redis_client import update_session_field
                        await update_session_field(session_id, "language", lang)
                        logger.info("Language updated to %s. session=%s", lang, session_id)

                    elif msg_type == "ping":
                        await _send_json(websocket, {"type": "pong"})

                    else:
                        logger.debug("Unknown control type: %s. session=%s", msg_type, session_id)

        except WebSocketDisconnect:
            logger.info("Client disconnected. session=%s", session_id)
        except Exception as exc:
            logger.error("Reader task error. session=%s  error=%s", session_id, exc)

    # -----------------------------------------------------------------------
    # Task B: Writer — agent audio → frontend
    # -----------------------------------------------------------------------
    async def _writer() -> None:
        try:
            while True:
                # Block until the next TTS audio chunk is ready
                audio_chunk = await outbound_audio_q.get()
                await _send_audio(websocket, audio_chunk)
        except asyncio.CancelledError:
            # Flush remaining audio before shutting down
            while not outbound_audio_q.empty():
                try:
                    chunk = outbound_audio_q.get_nowait()
                    await _send_audio(websocket, chunk)
                except asyncio.QueueEmpty:
                    break
        except Exception as exc:
            logger.error("Writer task error. session=%s  error=%s", session_id, exc)

    # -----------------------------------------------------------------------
    # Run reader and writer concurrently
    # -----------------------------------------------------------------------
    reader_task = asyncio.create_task(_reader(), name=f"reader-{session_id}")
    writer_task = asyncio.create_task(_writer(), name=f"writer-{session_id}")

    try:
        # Wait for the reader to exit (client disconnect or end_session)
        await reader_task
    except Exception as exc:
        logger.error("Unhandled session error. session=%s  error=%s", session_id, exc)
    finally:
        # Cancel writer (it will flush remaining audio in its CancelledError handler)
        writer_task.cancel()
        try:
            await asyncio.wait_for(writer_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        # Graceful agent teardown
        await agent.cleanup()

        # Remove Redis context (explicit delete > waiting for TTL)
        await delete_session_context(session_id)

        # Close the WebSocket cleanly if still open
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)

        logger.info("Session fully closed. session=%s", session_id)
