# Voice AI Agent

A real-time voice AI agent system with a Python/FastAPI backend and a Next.js 14 frontend dashboard.

## Stack
- **Backend**: Python, FastAPI, WebSockets, OpenAI Whisper, ElevenLabs, LangChain, Redis, PostgreSQL
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Socket.IO

## Structure
```
voice-ai-agent/
├── backend/    # FastAPI server — STT → LLM → TTS pipeline
└── frontend/   # Next.js dashboard — real-time session UI
```

## Quick Start
See `backend/README.md` and `frontend/README.md` for individual setup guides.
