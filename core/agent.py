"""
agent.py — Voice orchestration with OpenAI tool-calling and streaming TTS.

Pipeline per utterance
-----------------------
  1. Build messages = [system] + history + [user]
  2. Non-streaming call to OpenAI with tools=OPENAI_TOOLS
     ├── finish_reason == "tool_calls"
     │     a. Append assistant message (with tool_calls) to messages  ← CRITICAL
     │     b. Execute each tool via execute_tool_call()
     │     c. Append {"role": "tool", "tool_call_id": ..., "content": ...}
     │     d. Second call with stream=True → final spoken reply
     └── finish_reason == "stop"
           Stream the reply directly from the first response's content
  3. Pipe streaming tokens into ElevenLabs input-streaming TTS
  4. Forward audio chunks to frontend WebSocket
  5. Persist full reply to Redis
"""

import asyncio
import base64
import json
import logging
import os
from collections.abc import AsyncGenerator
from typing import Callable, Awaitable

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from core.tools import OPENAI_TOOLS, execute_tool_call
from memory.redis_client import append_conversation_turn, get_session_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY", "")
DEEPGRAM_API_KEY    = os.getenv("DEEPGRAM_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL_ID = "eleven_turbo_v2"
LLM_MODEL           = "gpt-4o"
LLM_MAX_TOKENS      = 200

SYSTEM_PROMPT = (
    "You are a multilingual clinical appointment booking voice assistant. "
    "Help patients book, reschedule, and cancel appointments. "
    "Be concise — maximum 2 sentences per reply. "
    "Respond in the patient's language (English, Hindi, or Tamil). "
    "Always check availability before confirming a slot. "
    "Only book an appointment after the patient explicitly confirms."
)

AudioBytes   = bytes
SendCallback = Callable[[AudioBytes], Awaitable[None]]


# ---------------------------------------------------------------------------
# ElevenLabs input-streaming TTS
# ---------------------------------------------------------------------------

async def _tts_stream(
    text_gen: AsyncGenerator[str, None],
    on_audio_chunk: SendCallback,
) -> None:
    """
    Accept tokens from text_gen and stream them into the ElevenLabs
    input-streaming WebSocket. Forward every audio frame to on_audio_chunk.
    Tokens are flushed every 5 words for the best latency/quality balance.
    """
    import websockets

    ws_url = (
        f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        f"/stream-input?model_id={ELEVENLABS_MODEL_ID}&optimize_streaming_latency=4"
    )

    try:
        async with websockets.connect(
            ws_url, additional_headers={"xi-api-key": ELEVENLABS_API_KEY}
        ) as ws:
            # Beginning-of-stream
            await ws.send(json.dumps({
                "text": " ",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                "xi_api_key": ELEVENLABS_API_KEY,
            }))

            buffer = ""

            async def _flush(text: str, is_final: bool = False) -> None:
                payload: dict = {"text": text + " "}
                if is_final:
                    payload["flush"] = True
                await ws.send(json.dumps(payload))
                # Drain any audio frames that arrived
                try:
                    while True:
                        frame = await asyncio.wait_for(ws.recv(), timeout=0.05)
                        if isinstance(frame, bytes) and frame:
                            await on_audio_chunk(frame)
                        elif isinstance(frame, str):
                            msg = json.loads(frame)
                            if msg.get("audio"):
                                await on_audio_chunk(base64.b64decode(msg["audio"]))
                except asyncio.TimeoutError:
                    pass

            async for token in text_gen:
                buffer += token
                if len(buffer.split()) >= 5:
                    await _flush(buffer.strip())
                    buffer = ""

            if buffer.strip():
                await _flush(buffer.strip(), is_final=True)

            # End-of-stream signal
            await ws.send(json.dumps({"text": ""}))

            # Drain remaining audio
            try:
                async for frame in ws:
                    if isinstance(frame, bytes) and frame:
                        await on_audio_chunk(frame)
            except Exception:
                pass

    except Exception as exc:
        logger.error("ElevenLabs TTS stream error: %s", exc)


# ---------------------------------------------------------------------------
# LLM streaming reply
# ---------------------------------------------------------------------------

async def _stream_reply(
    messages: list[ChatCompletionMessageParam],
) -> AsyncGenerator[str, None]:
    """Open a GPT-4o stream and yield tokens as they arrive."""
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    try:
        async with client.chat.completions.stream(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.6,
        ) as stream:
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
    except Exception as exc:
        logger.error("LLM stream error: %s", exc)
        yield "I'm sorry, something went wrong. Please try again."


# ---------------------------------------------------------------------------
# Deepgram STT stub
# ---------------------------------------------------------------------------

async def _deepgram_stt_stream(
    audio_queue: asyncio.Queue,
    transcript_callback: Callable[[str, bool], Awaitable[None]],
) -> None:
    """
    Forward audio chunks to Deepgram STT WebSocket and fire
    transcript_callback(text, is_final) for each result.

    Real endpoint (swap in when DEEPGRAM_API_KEY is set):
        wss://api.deepgram.com/v1/listen
        ?model=nova-2-medical&language=multi
        &encoding=linear16&sample_rate=16000&channels=1
        &interim_results=true&utterance_end_ms=1000&endpointing=300
    """
    logger.info("Deepgram STT stream opened.")
    accumulated = []
    while True:
        chunk = await audio_queue.get()
        if chunk is None:
            if accumulated:
                await transcript_callback("[transcribed text from audio]", True)
            logger.info("Deepgram STT stream closed.")
            break
        accumulated.append(chunk)


# ---------------------------------------------------------------------------
# VoiceAgent
# ---------------------------------------------------------------------------

class VoiceAgent:
    """Session-scoped agent. Runs the full STT → (tool?) → LLM → TTS loop."""

    def __init__(self, session_id: str) -> None:
        self.session_id       = session_id
        self._audio_queue:     asyncio.Queue = asyncio.Queue(maxsize=500)
        self._on_audio_out:    SendCallback | None = None
        self._stt_task:        asyncio.Task | None = None
        self._active_llm_tts:  asyncio.Task | None = None

    async def start(self, on_audio_out: SendCallback) -> None:
        self._on_audio_out = on_audio_out
        self._stt_task = asyncio.create_task(
            _deepgram_stt_stream(self._audio_queue, self._on_transcript),
            name=f"stt-{self.session_id}",
        )
        logger.info("VoiceAgent started. session=%s", self.session_id)

    async def send_audio(self, chunk: bytes) -> None:
        try:
            self._audio_queue.put_nowait(chunk)
        except asyncio.QueueFull:
            logger.warning("Audio queue full — dropping chunk. session=%s", self.session_id)

    async def _on_transcript(self, text: str, is_final: bool) -> None:
        if not is_final:
            return
        logger.info("Final transcript: '%s'  session=%s", text, self.session_id)
        await append_conversation_turn(self.session_id, role="user", content=text)

        if self._active_llm_tts and not self._active_llm_tts.done():
            logger.info("Barge-in — cancelling in-flight reply. session=%s", self.session_id)
            self._active_llm_tts.cancel()

        self._active_llm_tts = asyncio.create_task(
            self._run_llm_tts(text),
            name=f"llm-tts-{self.session_id}",
        )

    async def _run_llm_tts(self, user_text: str) -> None:
        """
        Agentic reasoning loop for one utterance.

        Message sequence enforced by OpenAI's API:
          messages = [system, ...history, user]
                                   ↓  (non-streaming + tools)
          if tool_calls:
            messages.append(assistant_message_with_tool_calls)   # MUST include this
            messages.append({"role": "tool", "tool_call_id": id, "content": result})
                                   ↓  (streaming, no tools)
            final spoken reply
          else:
            stream directly
        """
        assert self._on_audio_out is not None

        context  = await get_session_context(self.session_id)
        history  = context.get("conversation_state", [])

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history[-10:],
            {"role": "user", "content": user_text},
        ]

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        # ------------------------------------------------------------------
        # Pass 1 — non-streaming, with tools
        # ------------------------------------------------------------------
        logger.info("LLM pass-1 (tool check). session=%s", self.session_id)

        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=OPENAI_TOOLS,
            tool_choice="auto",
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.6,
        )

        choice        = response.choices[0]
        finish_reason = choice.finish_reason
        assistant_msg = choice.message     # The full assistant message object

        reply_tokens: list[str] = []

        # ------------------------------------------------------------------
        # Path A — LLM wants to call a tool
        # ------------------------------------------------------------------
        if finish_reason == "tool_calls" and assistant_msg.tool_calls:

            # Step 1: Append the assistant message EXACTLY as returned
            # (This is required by OpenAI — omitting it causes a 400 error)
            messages.append(assistant_msg.model_dump(exclude_unset=False))  # type: ignore[arg-type]

            # Step 2: Execute each tool and append results
            for tc in assistant_msg.tool_calls:
                fn_name = tc.function.name

                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    logger.error("Failed to parse tool args for %s: %s", fn_name, tc.function.arguments)
                    fn_args = {}

                logger.info("Agent is calling tool: %s  args=%s", fn_name, fn_args)

                tool_result = await execute_tool_call(fn_name, fn_args)

                logger.info("Tool result [%s]: %s", fn_name, tool_result[:120])

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      str(tool_result),
                })

            # Step 3: Stream the final spoken reply with DB context baked in
            logger.info("LLM pass-2 (streaming reply after tools). session=%s", self.session_id)

            async def _after_tool_gen() -> AsyncGenerator[str, None]:
                async for token in _stream_reply(messages):
                    reply_tokens.append(token)
                    yield token

            await _tts_stream(_after_tool_gen(), self._on_audio_out)

        # ------------------------------------------------------------------
        # Path B — no tool needed, stream reply directly
        # ------------------------------------------------------------------
        else:
            logger.info("No tool needed — streaming reply directly. session=%s", self.session_id)
            direct_content = assistant_msg.content or ""

            async def _direct_gen() -> AsyncGenerator[str, None]:
                if direct_content:
                    # The first pass already has the full reply — stream word by word
                    for word in direct_content.split():
                        tok = word + " "
                        reply_tokens.append(tok)
                        yield tok
                else:
                    # Rare: content was empty, open a fresh stream
                    async for token in _stream_reply(messages):
                        reply_tokens.append(token)
                        yield token

            await _tts_stream(_direct_gen(), self._on_audio_out)

        # ------------------------------------------------------------------
        # Persist full reply to Redis
        # ------------------------------------------------------------------
        full_reply = "".join(reply_tokens)
        if full_reply:
            await append_conversation_turn(
                self.session_id, role="agent", content=full_reply
            )

        logger.info(
            "Reply complete. session=%s  chars=%d  tool_used=%s",
            self.session_id, len(full_reply), finish_reason == "tool_calls",
        )

    async def cleanup(self) -> None:
        logger.info("VoiceAgent cleanup. session=%s", self.session_id)
        await self._audio_queue.put(None)

        if self._active_llm_tts and not self._active_llm_tts.done():
            self._active_llm_tts.cancel()

        if self._stt_task:
            try:
                await asyncio.wait_for(self._stt_task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._stt_task.cancel()
