"use client";
import { useCallback, useEffect, useRef, useState } from "react";

interface AudioStreamState {
    frequencyData: Uint8Array | null;
    amplitude: number;
    start: () => Promise<void>;
    stop: () => void;
    sendChunk: (ws: WebSocket) => void;
}

/**
 * Captures microphone input, exposes frequency data for visualisation,
 * and allows sending raw PCM chunks over a WebSocket.
 */
export function useAudioStream(): AudioStreamState {
    const [frequencyData, setFrequencyData] = useState<Uint8Array | null>(null);
    const [amplitude, setAmplitude] = useState(0);
    const streamRef = useRef<MediaStream | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);
    const rafRef = useRef<number>(0);
    const chunksRef = useRef<Float32Array[]>([]);

    const start = useCallback(async () => {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;

        const ctx = new AudioContext({ sampleRate: 16000 });
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyserRef.current = analyser;

        const processor = ctx.createScriptProcessor(4096, 1, 1);
        processor.onaudioprocess = (e) => {
            chunksRef.current.push(e.inputBuffer.getChannelData(0).slice());
        };
        processorRef.current = processor;

        source.connect(analyser);
        analyser.connect(processor);
        processor.connect(ctx.destination);

        const data = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
            analyser.getByteFrequencyData(data);
            setFrequencyData(new Uint8Array(data));
            const rms = Math.sqrt(data.reduce((s, v) => s + v * v, 0) / data.length) / 255;
            setAmplitude(rms);
            rafRef.current = requestAnimationFrame(tick);
        };
        tick();
    }, []);

    const stop = useCallback(() => {
        cancelAnimationFrame(rafRef.current);
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        chunksRef.current = [];
        setFrequencyData(null);
        setAmplitude(0);
    }, []);

    const sendChunk = useCallback((ws: WebSocket) => {
        if (!chunksRef.current.length || ws.readyState !== WebSocket.OPEN) return;
        const chunk = chunksRef.current.splice(0, chunksRef.current.length);
        const merged = new Float32Array(chunk.reduce((a, b) => a + b.length, 0));
        let offset = 0;
        chunk.forEach((c) => { merged.set(c, offset); offset += c.length; });
        ws.send(merged.buffer);
    }, []);

    useEffect(() => () => stop(), [stop]);

    return { frequencyData, amplitude, start, stop, sendChunk };
}
