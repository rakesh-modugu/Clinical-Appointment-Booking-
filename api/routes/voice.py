"""
WebSocket endpoint for real-time audio streaming.
Receives raw audio chunks, runs STT→LLM→TTS pipeline, and streams audio back.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.agent import VoiceAgent

router = APIRouter()


@router.websocket("/voice/{session_id}")
async def voice_stream(websocket: WebSocket, session_id: str):
    await websocket.accept()
    agent = VoiceAgent(session_id=session_id)
    try:
        while True:
            audio_chunk: bytes = await websocket.receive_bytes()
            response_audio = await agent.process_chunk(audio_chunk)
            if response_audio:
                await websocket.send_bytes(response_audio)
    except WebSocketDisconnect:
        await agent.cleanup()
