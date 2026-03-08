/**
 * WebSocket client — creates and manages the voice session socket.
 * Exposes typed helpers for sending audio and listening to server events.
 */

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

export type VoiceEvent =
    | { type: "transcript"; role: "user" | "assistant"; content: string }
    | { type: "audio"; data: ArrayBuffer }
    | { type: "state"; state: "listening" | "thinking" | "speaking" | "idle" }
    | { type: "error"; message: string };

export function createVoiceSocket(
    sessionId: string,
    onEvent: (event: VoiceEvent) => void
): WebSocket {
    const ws = new WebSocket(`${WS_URL}/voice/${sessionId}`);

    ws.binaryType = "arraybuffer";

    ws.onmessage = (msg) => {
        if (msg.data instanceof ArrayBuffer) {
            onEvent({ type: "audio", data: msg.data });
        } else {
            try {
                onEvent(JSON.parse(msg.data) as VoiceEvent);
            } catch {
                console.error("Unrecognised WS message", msg.data);
            }
        }
    };

    ws.onerror = () => onEvent({ type: "error", message: "WebSocket error" });

    return ws;
}
