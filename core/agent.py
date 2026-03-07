"""
Core AI agent loop: orchestrates STT → LLM → TTS per audio chunk.
"""

from services.stt import transcribe
from services.llm import generate_response
from services.tts import synthesize
from memory.session_store import SessionStore


class VoiceAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.store = SessionStore(session_id)

    async def process_chunk(self, audio_chunk: bytes) -> bytes | None:
        """
        Full pipeline for one audio chunk:
        1. STT  — bytes → text transcript
        2. LLM  — text + context → response text
        3. TTS  — response text → audio bytes
        """
        transcript = await transcribe(audio_chunk)
        if not transcript:
            return None

        history = await self.store.get_history()
        response_text = await generate_response(transcript, history)

        await self.store.append_turn(user=transcript, assistant=response_text)

        audio_response = await synthesize(response_text)
        return audio_response

    async def cleanup(self):
        """Called on WebSocket disconnect — persist and close session."""
        await self.store.close()
