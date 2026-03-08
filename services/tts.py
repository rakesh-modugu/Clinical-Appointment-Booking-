"""
Text-to-Speech service wrapper.
Supports ElevenLabs (primary) with Azure TTS as fallback.
"""

import httpx
from core.config import settings

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel


async def synthesize(text: str, voice_id: str = DEFAULT_VOICE_ID) -> bytes:
    """
    Convert text to speech audio bytes using ElevenLabs.
    Returns raw MP3 audio bytes ready to stream over WebSocket.
    """
    url = f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content
