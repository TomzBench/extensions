"""Silero VAD wrapper using silero-vad-lite (ONNX)."""

from silero_vad_lite import SileroVAD

from audio.types import AudioChunk

SAMPLE_RATE = 16000
WINDOW_SIZE = 512  # 32ms at 16kHz


class SileroVADModel:
    """Silero VAD model wrapper that satisfies the VADModel protocol."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self._vad = SileroVAD(sample_rate=sample_rate)

    @property
    def window_size(self) -> int:
        """Required chunk size in samples."""
        return int(self._vad.window_size_samples)

    def __call__(self, chunk: AudioChunk) -> float:
        """Return speech probability for the given audio chunk."""
        return float(self._vad.process(memoryview(chunk.data)))
