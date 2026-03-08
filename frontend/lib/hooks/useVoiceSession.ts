"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { createVoiceSocket, type VoiceEvent } from "@/lib/socket";
import { api } from "@/lib/api";

interface Turn {
    role: "user" | "assistant";
    content: string;
    timestamp: string;
}

/**
 * Manages the full WebSocket voice session lifecycle:
 * start session → open socket → stream events → end session on cleanup.
 */
export function useVoiceSession() {
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [turns, setTurns] = useState<Turn[]>([]);
    const [agentState, setAgentState] = useState<string>("idle");
    const wsRef = useRef<WebSocket | null>(null);

    const startSession = useCallback(async () => {
        const { session_id } = await api.post<{ session_id: string }>("/api/sessions/start", {});
        setSessionId(session_id);

        wsRef.current = createVoiceSocket(session_id, (event: VoiceEvent) => {
            if (event.type === "transcript") {
                setTurns((prev) => [...prev, { ...event, timestamp: new Date().toISOString() }]);
            } else if (event.type === "state") {
                setAgentState(event.state);
            }
        });
    }, []);

    const endSession = useCallback(async () => {
        wsRef.current?.close();
        if (sessionId) {
            await api.post(`/api/sessions/${sessionId}/end`, {});
        }
        setSessionId(null);
        setTurns([]);
        setAgentState("idle");
    }, [sessionId]);

    useEffect(() => () => { wsRef.current?.close(); }, []);

    return { sessionId, turns, agentState, startSession, endSession };
}
