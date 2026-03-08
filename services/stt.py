"""
Speech-to-Text service wrapper.
Supports OpenAI Whisper (cloud) and Deepgram (streaming).
"""

import openai
from core.config import settings


async def transcribe(audio_bytes: bytes, language: str = "en") -> str:
    """
    Transcribe raw audio bytes to text using OpenAI Whisper.
    audio_bytes: PCM/WAV audio data
    Returns: transcript string, or empty string if silence detected.
    """
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    # Whisper expects a file-like object; wrap bytes in a named tuple
    import io
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.wav"

    response = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language=language,
    )
    return response.text.strip()
