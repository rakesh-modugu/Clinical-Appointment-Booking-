/**
 * Browser-side audio helpers: WAV encoding and PCM buffer utilities.
 */

/** Encode a Float32Array (PCM samples) to a 16-bit WAV Blob. */
export function float32ToWavBlob(samples: Float32Array, sampleRate = 16000): Blob {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    const writeStr = (offset: number, s: string) =>
        [...s].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));

    const pcm = new Int16Array(samples.length);
    samples.forEach((s, i) => { pcm[i] = Math.max(-1, Math.min(1, s)) * 0x7fff; });

    writeStr(0, "RIFF");
    view.setUint32(4, 36 + pcm.byteLength, true);
    writeStr(8, "WAVE");
    writeStr(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, "data");
    view.setUint32(40, pcm.byteLength, true);
    new Int16Array(buffer, 44).set(pcm);

    return new Blob([buffer], { type: "audio/wav" });
}

/** Play raw MP3/audio bytes received from the TTS service. */
export async function playAudioBytes(data: ArrayBuffer): Promise<void> {
    const ctx = new AudioContext();
    const decoded = await ctx.decodeAudioData(data);
    const source = ctx.createBufferSource();
    source.buffer = decoded;
    source.connect(ctx.destination);
    source.start();
}
