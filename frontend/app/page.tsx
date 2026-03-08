"use client";

import { useEffect, useRef, useState, useCallback } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────
type ConnectionStatus = "idle" | "connecting" | "connected" | "disconnected" | "error";
type AgentStatus = "idle" | "listening" | "thinking" | "speaking";

interface Message {
    id: string;
    role: "user" | "agent";
    text: string;
    timestamp: Date;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function generateUUID(): string {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function StatusDot({ status }: { status: ConnectionStatus }) {
    const colors: Record<ConnectionStatus, string> = {
        idle: "bg-slate-500",
        connecting: "bg-yellow-400 animate-pulse",
        connected: "bg-emerald-400",
        disconnected: "bg-red-400",
        error: "bg-red-600 animate-pulse",
    };
    const labels: Record<ConnectionStatus, string> = {
        idle: "Idle",
        connecting: "Connecting…",
        connected: "Connected",
        disconnected: "Disconnected",
        error: "Error",
    };
    return (
        <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${colors[status]}`} />
            <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                {labels[status]}
            </span>
        </div>
    );
}

function SoundWave({ active }: { active: boolean }) {
    if (!active) return null;
    return (
        <div className="flex items-center gap-1 h-10">
            {[...Array(7)].map((_, i) => (
                <div key={i} className="sound-bar" style={{ height: "8px" }} />
            ))}
        </div>
    );
}

function OrbButton({
    agentStatus,
    isRecording,
    onToggle,
    disabled,
}: {
    agentStatus: AgentStatus;
    isRecording: boolean;
    onToggle: () => void;
    disabled: boolean;
}) {
    const label =
        agentStatus === "listening"
            ? "Listening…"
            : agentStatus === "thinking"
                ? "Thinking…"
                : agentStatus === "speaking"
                    ? "Speaking…"
                    : "Tap to speak";

    return (
        <div className="flex flex-col items-center gap-4">
            <button
                onClick={onToggle}
                disabled={disabled}
                aria-label={label}
                className={`
          relative w-28 h-28 rounded-full 
          flex items-center justify-center
          transition-all duration-300 select-none
          ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer glow-button"}
          ${isRecording ? "animate-pulse-ring" : "animate-float"}
        `}
                style={{
                    background: isRecording
                        ? "linear-gradient(135deg, #ef4444, #b91c1c)"
                        : "linear-gradient(135deg, #6366f1, #8b5cf6)",
                }}
            >
                {/* Mic icon */}
                <svg
                    className="w-10 h-10 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.8}
                >
                    {isRecording ? (
                        // Stop square
                        <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
                    ) : (
                        // Microphone
                        <>
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M12 1a3 3 0 0 1 3 3v8a3 3 0 0 1-6 0V4a3 3 0 0 1 3-3z"
                            />
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4M8 22h8"
                            />
                        </>
                    )}
                </svg>
            </button>
            <p
                className="text-sm font-medium tracking-wide"
                style={{ color: "var(--text-secondary)" }}
            >
                {label}
            </p>
            <SoundWave active={agentStatus === "listening" || agentStatus === "speaking"} />
        </div>
    );
}

function ChatBubble({ message }: { message: Message }) {
    const isUser = message.role === "user";
    return (
        <div
            className={`flex animate-fade-in-up ${isUser ? "justify-end" : "justify-start"}`}
        >
            {!isUser && (
                <div
                    className="w-8 h-8 rounded-full flex items-center justify-center mr-2 flex-shrink-0"
                    style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
                >
                    <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
                        <path
                            fillRule="evenodd"
                            d="M4 5a2 2 0 012-2v1a1 1 0 102 0V3a2 2 0 012 2v6a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm9.707 5.707a1 1 0 00-1.414-1.414L11 10.586V7a1 1 0 10-2 0v3.586l-1.293-1.293a1 1 0 00-1.414 1.414l3 3a1 1 0 001.414 0l3-3z"
                            clipRule="evenodd"
                        />
                    </svg>
                </div>
            )}
            <div
                className={`
          max-w-xs lg:max-w-sm px-4 py-3 rounded-2xl text-sm leading-relaxed
          ${isUser ? "rounded-tr-sm" : "rounded-tl-sm"}
        `}
                style={{
                    background: isUser
                        ? "linear-gradient(135deg, #6366f1, #8b5cf6)"
                        : "var(--bg-card)",
                    border: isUser ? "none" : "1px solid var(--border-color)",
                    color: "var(--text-primary)",
                }}
            >
                {message.text}
                <p
                    className="text-xs mt-1 opacity-60"
                    style={{ color: isUser ? "#e0e7ff" : "var(--text-secondary)" }}
                >
                    {message.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                    })}
                </p>
            </div>
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function VoiceAgentPage() {
    // Session ID: only generated client-side after mount to prevent hydration errors
    const [mounted, setMounted] = useState(false);
    const [sessionId, setSessionId] = useState<string>("");

    const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("idle");
    const [agentStatus, setAgentStatus] = useState<AgentStatus>("idle");
    const [isRecording, setIsRecording] = useState(false);
    const [messages, setMessages] = useState<Message[]>([]);
    const [currentTranscript, setCurrentTranscript] = useState("");

    const wsRef = useRef<WebSocket | null>(null);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const audioQueueRef = useRef<ArrayBuffer[]>([]);
    const isPlayingRef = useRef(false);
    const streamRef = useRef<MediaStream | null>(null);
    const chatBottomRef = useRef<HTMLDivElement>(null);

    // ── Mount: generate session ID client-side only ──────────────────────────
    useEffect(() => {
        setMounted(true);
        setSessionId(generateUUID());
    }, []);

    // ── Auto-scroll chat ─────────────────────────────────────────────────────
    useEffect(() => {
        chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // ── AudioContext: lazily init ────────────────────────────────────────────
    function getAudioContext(): AudioContext {
        if (!audioContextRef.current) {
            audioContextRef.current = new (window.AudioContext ||
                (window as unknown as { webkitAudioContext: typeof AudioContext })
                    .webkitAudioContext)();
        }
        return audioContextRef.current;
    }

    // ── TTS Playback queue ───────────────────────────────────────────────────
    const playNextInQueue = useCallback(async () => {
        if (isPlayingRef.current || audioQueueRef.current.length === 0) return;
        isPlayingRef.current = true;
        setAgentStatus("speaking");

        const buffer = audioQueueRef.current.shift()!;
        const ctx = getAudioContext();

        try {
            const decoded = await ctx.decodeAudioData(buffer);
            const source = ctx.createBufferSource();
            source.buffer = decoded;
            source.connect(ctx.destination);
            source.onended = () => {
                isPlayingRef.current = false;
                if (audioQueueRef.current.length > 0) {
                    playNextInQueue();
                } else {
                    setAgentStatus("idle");
                }
            };
            source.start(0);
        } catch {
            isPlayingRef.current = false;
            setAgentStatus("idle");
        }
    }, []);

    // ── WebSocket connection ─────────────────────────────────────────────────
    const connectWebSocket = useCallback(() => {
        if (!sessionId) return;
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        setConnectionStatus("connecting");
        const ws = new WebSocket(`ws://127.0.0.1:8000/ws/voice/${sessionId}`);
        ws.binaryType = "arraybuffer";
        wsRef.current = ws;

        ws.onopen = () => {
            setConnectionStatus("connected");
            addMessage("agent", "Hello! I'm your clinical appointment assistant. How can I help you today?");
        };

        ws.onmessage = (event) => {
            if (typeof event.data === "string") {
                // JSON control messages
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === "transcript") {
                        setCurrentTranscript(msg.text ?? "");
                    } else if (msg.type === "transcript_final") {
                        if (msg.text) addMessage("user", msg.text);
                        setCurrentTranscript("");
                        setAgentStatus("thinking");
                    } else if (msg.type === "llm_response") {
                        if (msg.text) addMessage("agent", msg.text);
                    } else if (msg.type === "tts_start") {
                        setAgentStatus("speaking");
                    } else if (msg.type === "tts_end") {
                        setAgentStatus("idle");
                    } else if (msg.type === "error") {
                        addMessage("agent", `⚠️ ${msg.message}`);
                    }
                } catch {
                    // non-JSON string, ignore
                }
            } else if (event.data instanceof ArrayBuffer) {
                // Raw TTS audio chunk — queue and play
                audioQueueRef.current.push(event.data.slice(0));
                playNextInQueue();
            }
        };

        ws.onerror = () => setConnectionStatus("error");
        ws.onclose = () => {
            setConnectionStatus("disconnected");
            setIsRecording(false);
            setAgentStatus("idle");
        };
    }, [sessionId, playNextInQueue]);

    // ── Disconnect ───────────────────────────────────────────────────────────
    const disconnectWebSocket = useCallback(() => {
        stopRecording();
        wsRef.current?.close();
        wsRef.current = null;
        audioQueueRef.current = [];
        isPlayingRef.current = false;
        setConnectionStatus("idle");
        setAgentStatus("idle");
    }, []);

    // ── Start recording ──────────────────────────────────────────────────────
    const startRecording = useCallback(async () => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = stream;

            const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
                ? "audio/webm;codecs=opus"
                : "audio/webm";

            const recorder = new MediaRecorder(stream, { mimeType });
            mediaRecorderRef.current = recorder;

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
                    wsRef.current.send(e.data);
                }
            };

            recorder.start(250); // 250ms chunks for low latency
            setIsRecording(true);
            setAgentStatus("listening");

            // Notify server we started listening
            wsRef.current?.send(JSON.stringify({ type: "start_listening" }));
        } catch (err) {
            console.error("Microphone access denied:", err);
            addMessage("agent", "⚠️ Microphone access was denied. Please allow microphone access and try again.");
        }
    }, []);

    // ── Stop recording ───────────────────────────────────────────────────────
    const stopRecording = useCallback(() => {
        if (mediaRecorderRef.current?.state !== "inactive") {
            mediaRecorderRef.current?.stop();
        }
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        mediaRecorderRef.current = null;
        setIsRecording(false);

        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "stop_listening" }));
        }
        setAgentStatus("thinking");
    }, []);

    // ── Toggle mic ───────────────────────────────────────────────────────────
    const handleToggle = useCallback(() => {
        if (connectionStatus !== "connected") return;
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    }, [connectionStatus, isRecording, startRecording, stopRecording]);

    // ── Utility: add message to chat ─────────────────────────────────────────
    function addMessage(role: "user" | "agent", text: string) {
        setMessages((prev) => [
            ...prev,
            { id: generateUUID(), role, text, timestamp: new Date() },
        ]);
    }

    // ── Cleanup on unmount ───────────────────────────────────────────────────
    useEffect(() => {
        return () => {
            disconnectWebSocket();
            audioContextRef.current?.close();
        };
    }, [disconnectWebSocket]);

    // ── Don't render until client-side to avoid hydration mismatch ───────────
    if (!mounted) return null;

    const isConnected = connectionStatus === "connected";

    return (
        <div
            className="min-h-screen flex flex-col"
            style={{ background: "var(--bg-primary)" }}
        >
            {/* ── Header ─────────────────────────────────────────────────────── */}
            <header
                className="glass-card mx-4 mt-4 px-6 py-4 flex items-center justify-between"
                style={{ borderRadius: "16px" }}
            >
                <div className="flex items-center gap-3">
                    <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center"
                        style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
                    >
                        <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path
                                fillRule="evenodd"
                                d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z"
                                clipRule="evenodd"
                            />
                        </svg>
                    </div>
                    <div>
                        <h1 className="font-bold text-lg gradient-text">Clinical Voice AI</h1>
                        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                            Appointment Booking Agent
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <StatusDot status={connectionStatus} />
                    {sessionId && (
                        <span
                            className="text-xs font-mono px-2 py-1 rounded-lg hidden sm:block"
                            style={{
                                background: "var(--bg-secondary)",
                                color: "var(--text-secondary)",
                            }}
                        >
                            {sessionId.slice(0, 8)}…
                        </span>
                    )}
                </div>
            </header>

            {/* ── Main content ───────────────────────────────────────────────── */}
            <main className="flex-1 flex flex-col lg:flex-row gap-4 p-4 max-w-6xl mx-auto w-full">
                {/* Left panel: Orb + controls */}
                <div className="lg:w-80 flex flex-col gap-4">
                    {/* Orb card */}
                    <div className="glass-card p-8 flex flex-col items-center gap-6">
                        <OrbButton
                            agentStatus={agentStatus}
                            isRecording={isRecording}
                            onToggle={handleToggle}
                            disabled={!isConnected}
                        />

                        {/* Live transcript */}
                        {currentTranscript && (
                            <div
                                className="w-full px-4 py-3 rounded-xl text-sm italic text-center"
                                style={{
                                    background: "var(--bg-secondary)",
                                    color: "var(--text-secondary)",
                                    borderLeft: "3px solid var(--accent-primary)",
                                }}
                            >
                                "{currentTranscript}"
                            </div>
                        )}
                    </div>

                    {/* Connect / Disconnect button */}
                    <button
                        onClick={isConnected ? disconnectWebSocket : connectWebSocket}
                        disabled={connectionStatus === "connecting"}
                        className={`
              w-full py-3 px-6 rounded-xl font-semibold text-sm
              transition-all duration-300
              ${connectionStatus === "connecting" ? "opacity-50 cursor-not-allowed" : ""}
            `}
                        style={{
                            background: isConnected
                                ? "rgba(239, 68, 68, 0.15)"
                                : "linear-gradient(135deg, #6366f1, #8b5cf6)",
                            color: isConnected ? "#ef4444" : "#fff",
                            border: isConnected ? "1px solid rgba(239,68,68,0.3)" : "none",
                            boxShadow: isConnected
                                ? "none"
                                : "0 0 20px rgba(99,102,241,0.3)",
                        }}
                    >
                        {connectionStatus === "connecting"
                            ? "Connecting…"
                            : isConnected
                                ? "Disconnect"
                                : "Connect to Agent"}
                    </button>

                    {/* Info card */}
                    <div
                        className="glass-card p-4 text-xs flex flex-col gap-2"
                        style={{ color: "var(--text-secondary)" }}
                    >
                        <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
                            How to use
                        </p>
                        <p>1. Click <strong>Connect to Agent</strong></p>
                        <p>2. Tap the orb and speak your request</p>
                        <p>3. Tap again to stop and send</p>
                        <p>4. The agent will respond in audio + text</p>
                    </div>
                </div>

                {/* Right panel: Chat history */}
                <div className="flex-1 glass-card flex flex-col min-h-[500px] lg:min-h-0">
                    <div
                        className="px-6 py-4 border-b flex items-center gap-2"
                        style={{ borderColor: "var(--border-color)" }}
                    >
                        <svg
                            className="w-4 h-4"
                            style={{ color: "var(--accent-primary)" }}
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                            />
                        </svg>
                        <h2 className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
                            Conversation
                        </h2>
                        <span
                            className="ml-auto text-xs px-2 py-0.5 rounded-full"
                            style={{
                                background: "var(--bg-secondary)",
                                color: "var(--text-secondary)",
                            }}
                        >
                            {messages.length} messages
                        </span>
                    </div>

                    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
                        {messages.length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center text-center gap-3">
                                <div
                                    className="w-16 h-16 rounded-full flex items-center justify-center"
                                    style={{ background: "var(--bg-secondary)" }}
                                >
                                    <svg
                                        className="w-8 h-8"
                                        style={{ color: "var(--accent-primary)" }}
                                        fill="none"
                                        viewBox="0 0 24 24"
                                        stroke="currentColor"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={1.5}
                                            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                                        />
                                    </svg>
                                </div>
                                <p className="font-medium" style={{ color: "var(--text-secondary)" }}>
                                    No messages yet
                                </p>
                                <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                                    Connect to the agent and start speaking
                                </p>
                            </div>
                        ) : (
                            messages.map((msg) => <ChatBubble key={msg.id} message={msg} />)
                        )}
                        <div ref={chatBottomRef} />
                    </div>

                    {/* Status bar */}
                    <div
                        className="px-6 py-3 border-t flex items-center gap-2"
                        style={{
                            borderColor: "var(--border-color)",
                            color: "var(--text-secondary)",
                        }}
                    >
                        {agentStatus === "thinking" && (
                            <>
                                <div className="flex gap-1">
                                    {[0, 150, 300].map((delay) => (
                                        <span
                                            key={delay}
                                            className="w-2 h-2 rounded-full animate-bounce"
                                            style={{
                                                background: "var(--accent-primary)",
                                                animationDelay: `${delay}ms`,
                                            }}
                                        />
                                    ))}
                                </div>
                                <span className="text-xs">Agent is thinking…</span>
                            </>
                        )}
                        {agentStatus === "speaking" && (
                            <>
                                <SoundWave active />
                                <span className="text-xs ml-2">Agent is speaking…</span>
                            </>
                        )}
                        {agentStatus === "listening" && (
                            <span className="text-xs">🎙️ Listening to you…</span>
                        )}
                        {agentStatus === "idle" && isConnected && (
                            <span className="text-xs">Ready — tap the orb to speak</span>
                        )}
                        {!isConnected && (
                            <span className="text-xs">Not connected</span>
                        )}
                    </div>
                </div>
            </main>

            {/* ── Footer ─────────────────────────────────────────────────────── */}
            <footer
                className="text-center py-4 text-xs"
                style={{ color: "var(--text-secondary)" }}
            >
                Clinical Voice AI Agent &nbsp;·&nbsp; Session:{" "}
                <span className="font-mono">{sessionId.slice(0, 8)}</span>
            </footer>
        </div>
    );
}
