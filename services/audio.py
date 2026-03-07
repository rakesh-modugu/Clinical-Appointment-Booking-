"""
Raw audio utilities — resampling, voice activity detection (VAD), encoding.
"""

import numpy as np


def resample(audio: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample PCM audio bytes from one sample rate to another."""
    samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32)
    ratio = to_rate / from_rate
    target_length = int(len(samples) * ratio)
    resampled = np.interp(
        np.linspace(0, len(samples), target_length),
        np.arange(len(samples)),
        samples,
    ).astype(np.int16)
    return resampled.tobytes()


def is_speech(audio: bytes, threshold: float = 500.0) -> bool:
    """
    Simple energy-based Voice Activity Detection.
    Returns True if audio chunk likely contains speech.
    """
    samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32)
    rms = np.sqrt(np.mean(samples ** 2))
    return rms > threshold


def to_wav_bytes(pcm: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw PCM data in a minimal WAV header."""
    import struct, io
    bits = 16
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE", b"fmt ", 16,
        1, channels, sample_rate, byte_rate, block_align, bits,
        b"data", data_size,
    )
    return header + pcm
