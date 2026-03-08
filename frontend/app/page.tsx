"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type AgentState = "idle" | "listening" | "thinking" | "speaking";

interface Message {
    id: number;
    role: "user" | "agent";
    content: string;
    timestamp: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function generateUUID(): string {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
}

function now(): string {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const STATE_CONFIG: Record<AgentState, { label: string; color: string; dot: string }> = {
    idle: { label: "Idle", color: "text-slate-400", dot: "bg-slate-400" },
    listening: { label: "Listening", color: "text-indigo-400", dot: "bg-indigo-400" },
    thinking: { label: "Thinking", color: "text-amber-400", dot: "bg-amber-400" },
    speaking: { label: "Speaking", color: "text-emerald-400", dot: "bg-emerald-400" },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function VoiceAgentPage() {
    const sessionId = useRef<string>(generateUUID());
    const wsRef = useRef<WebSocket | null>(null);
    const mediaRecRef = useRef<MediaRecorder | null>(null);
    const audioCtxRef = useRef<AudioContext | null>(null);
    const msgCounter = useRef(0);

    const [connected, setConnected] = useState(false);
    const [recording, setRecording] = useState(false);
    const [agentState, setAgentState] = useState<AgentState>("idle");
    const [messages, setMessages] = useState<Message[]>([]);
    const [error, setError] = useState<string | null>(null);

    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll transcript
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // ---------------------------------------------------------------------------
    // WebSocket
    // ---------------------------------------------------------------------------

    const connectWS = useCallback(() => {
        const ws = new WebSocket(
            `ws://127.0.0.1:8000/ws/voice/${sessionId.current}`
        );
        ws.binaryType = "arraybuffer";
        wsRef.current = ws;

        ws.onopen = () => {
            setConnected(true);
            setError(null);
            addMessage("agent", "Connected. Say hi to get started.");
        };

        ws.onclose = () => {
            setConnected(false);
            setRecording(false);
            setAgentState("idle");
        };

        ws.onerror = () => {
            setError("WebSocket error — is the backend running?");
            setConnected(false);
        };

        ws.onmessage = async (event) => {
            // Binary → audio bytes from TTS
            if (event.data instanceof ArrayBuffer) {
                setAgentState("speaking");
                await playAudioBuffer(event.data);
                setAgentState("listening");
                return;
            }

            // Text → JSON control message
            try {
                const msg = JSON.parse(event.data as string);

                if (msg.type === "transcript") {
                    addMessage(msg.role === "user" ? "user" : "agent", msg.text ?? "");
                } else if (msg.type === "agent_state") {
                    setAgentState(msg.state as AgentState);
                } else if (msg.type === "error") {
                    setError(msg.message);
                }
            } catch {
                // Not JSON — ignore
            }
        };
    }, []);

    // ---------------------------------------------------------------------------
    // Audio playback
    // ---------------------------------------------------------------------------

    async function playAudioBuffer(buffer: ArrayBuffer) {
        if (!audioCtxRef.current) {
            audioCtxRef.current = new AudioContext();
        }
        const ctx = audioCtxRef.current;
        try {
            const decoded = await ctx.decodeAudioData(buffer.slice(0));
            const source = ctx.createBufferSource();
            source.buffer = decoded;
            source.connect(ctx.destination);
            source.start();
        } catch {
            // Incomplete chunk — skip
        }
    }

    function addMessage(role: "user" | "agent", content: string) {
        setMessages((prev) => [
            ...prev,
            { id: ++msgCounter.current, role, content, timestamp: now() },
        ]);
    }

    // ---------------------------------------------------------------------------
    // Microphone + MediaRecorder
    // ---------------------------------------------------------------------------

    async function startRecording() {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            setError("Not connected to backend.");
            return;
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
            });

            const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
            mediaRecRef.current = recorder;

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
                    wsRef.current.send(e.data);
                }
            };

            recorder.start(250); // send a chunk every 250ms
            setRecording(true);
            setAgentState("listening");
            setError(null);
        } catch {
            setError("Microphone access denied.");
        }
    }

    function stopRecording() {
        mediaRecRef.current?.stop();
        mediaRecRef.current?.stream.getTracks().forEach((t) => t.stop());
        mediaRecRef.current = null;
        setRecording(false);
        setAgentState("idle");

        // Signal end of speech to backend
        wsRef.current?.send(JSON.stringify({ type: "end_utterance" }));
    }

    function endSession() {
        wsRef.current?.send(JSON.stringify({ type: "end_session" }));
        wsRef.current?.close();
        setMessages([]);
        setAgentState("idle");
    }

    // ---------------------------------------------------------------------------
    // UI
    // ---------------------------------------------------------------------------

    const stateConf = STATE_CONFIG[agentState];

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center px-4 py-10 font-sans">

            {/* Header */}
            <div className="w-full max-w-2xl mb-8">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Voice AI Agent</h1>
                        <p className="text-sm text-slate-400 mt-0.5">Clinical Appointment Booking</p>
                    </div>

                    {/* Status badge */}
                    <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-full px-4 py-1.5 text-sm">
                        <span
                            className={`w-2 h-2 rounded-full animate-pulse ${connected ? stateConf.dot : "bg-red-500"
                                }`}
                        />
                        <span className={connected ? stateConf.color : "text-red-400"}>
                            {connected ? stateConf.label : "Disconnected"}
                        </span>
                    </div>
                </div>

                {/* Session ID */}
                <p className="text-xs text-slate-600 mt-2 font-mono">
                    session: {sessionId.current}
                </p>
            </div>

            {/* Transcript */}
            <div className="w-full max-w-2xl flex-1 bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-col gap-3 overflow-y-auto min-h-[380px] max-h-[480px]">
                {messages.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-slate-600 text-sm">
                        Connect and press "Start Speaking" to begin.
                    </div>
                ) : (
                    messages.map((m) => (
                        <div
                            key={m.id}
                            className={`flex flex-col gap-1 ${m.role === "user" ? "items-end" : "items-start"
                                }`}
                        >
                            <span className="text-[11px] text-slate-500 capitalize">
                                {m.role} · {m.timestamp}
                            </span>
                            <div
                                className={`max-w-sm px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${m.role === "user"
                                        ? "bg-indigo-600 text-white rounded-br-sm"
                                        : "bg-slate-800 text-slate-100 rounded-bl-sm"
                                    }`}
                            >
                                {m.content}
                            </div>
                        </div>
                    ))
                )}
                <div ref={bottomRef} />
            </div>

            {/* Error */}
            {error && (
                <div className="w-full max-w-2xl mt-3 bg-red-950 border border-red-800 text-red-300 text-sm rounded-xl px-4 py-2.5">
                    ⚠ {error}
                </div>
            )}

            {/* Controls */}
            <div className="w-full max-w-2xl mt-5 flex flex-col gap-3">

                {/* Connect / End Row */}
                <div className="flex gap-3">
                    {!connected ? (
                        <button
                            onClick={connectWS}
                            className="flex-1 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-medium py-3 rounded-xl transition-colors duration-150"
                        >
                            Connect to Agent
                        </button>
                    ) : (
                        <button
                            onClick={endSession}
                            className="flex-1 bg-slate-800 hover:bg-slate-700 active:bg-slate-900 text-slate-300 font-medium py-3 rounded-xl transition-colors duration-150 border border-slate-700"
                        >
                            End Session
                        </button>
                    )}
                </div>

                {/* Mic button */}
                {connected && (
                    <button
                        onMouseDown={startRecording}
                        onMouseUp={stopRecording}
                        onTouchStart={startRecording}
                        onTouchEnd={stopRecording}
                        disabled={!connected}
                        className={`w-full py-4 rounded-xl font-semibold text-base transition-all duration-150 select-none
              ${recording
                                ? "bg-rose-600 hover:bg-rose-500 text-white scale-[0.98] shadow-inner"
                                : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg"
                            }`}
                    >
                        {recording ? "🔴  Release to Send" : "🎙  Hold to Speak"}
                    </button>
                )}
            </div>

            {/* Footer */}
            <p className="mt-8 text-xs text-slate-700">
                Hold the mic button while speaking · Release to send · Audio plays automatically
            </p>
        </div>
    );
}
