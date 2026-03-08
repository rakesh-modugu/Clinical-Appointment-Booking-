"use client";
import { useEffect, useRef } from "react";

interface Props {
    amplitude: number; // 0.0 – 1.0
    state: "idle" | "listening" | "thinking" | "speaking";
}

const STATE_COLORS: Record<Props["state"], string> = {
    idle: "#374151",
    listening: "#6366f1",
    thinking: "#f59e0b",
    speaking: "#10b981",
};

/**
 * Animated orb that pulses and changes colour based on agent state.
 * amplitude drives the scale of the pulse ring.
 */
export function VoiceOrb({ amplitude, state }: Props) {
    const color = STATE_COLORS[state];
    const scale = 1 + amplitude * 0.4;

    return (
        <div className="relative flex items-center justify-center w-32 h-32">
            {/* Pulse ring */}
            <div
                className="absolute rounded-full opacity-30 transition-transform duration-100"
                style={{
                    width: "100%",
                    height: "100%",
                    backgroundColor: color,
                    transform: `scale(${scale})`,
                }}
            />
            {/* Core orb */}
            <div
                className="relative z-10 w-20 h-20 rounded-full flex items-center justify-center shadow-lg transition-colors duration-300"
                style={{ backgroundColor: color }}
            >
                <span className="text-white text-2xl">🎙</span>
            </div>
        </div>
    );
}
