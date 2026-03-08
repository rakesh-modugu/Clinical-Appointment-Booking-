"use client";
import { useEffect, useRef } from "react";

interface Props {
    frequencyData: Uint8Array | null;
}

/**
 * Real-time frequency bar visualizer using Canvas API.
 * Pass frequencyData from an AnalyserNode to animate bars.
 */
export function AudioVisualizer({ frequencyData }: Props) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !frequencyData) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const barWidth = canvas.width / frequencyData.length;
        frequencyData.forEach((value, i) => {
            const barHeight = (value / 255) * canvas.height;
            ctx.fillStyle = `hsl(${240 + (i / frequencyData.length) * 80}, 80%, 60%)`;
            ctx.fillRect(i * barWidth, canvas.height - barHeight, barWidth - 1, barHeight);
        });
    }, [frequencyData]);

    return (
        <canvas
            ref={canvasRef}
            width={400}
            height={80}
            className="w-full rounded-lg bg-gray-900"
        />
    );
}
