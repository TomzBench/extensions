"""Speech-to-text transcriber wrapping whisper.cpp."""

from concurrent.futures import Executor
from enum import StrEnum
from typing import Self

from reactivex import Observable
from streams import from_thread

from audio._stt import Whisper
from audio.types import AudioChunk


class WhisperModel(StrEnum):
    """Available Whisper GGML models."""

    TINY = "ggml-tiny.bin"
    TINY_EN = "ggml-tiny.en.bin"
    BASE = "ggml-base.bin"
    BASE_EN = "ggml-base.en.bin"
    SMALL = "ggml-small.bin"
    SMALL_EN = "ggml-small.en.bin"
    MEDIUM = "ggml-medium.bin"
    MEDIUM_EN = "ggml-medium.en.bin"
    LARGE_V1 = "ggml-large-v1.bin"
    LARGE_V2 = "ggml-large-v2.bin"
    LARGE_V3 = "ggml-large-v3.bin"
    LARGE_V3_TURBO = "ggml-large-v3-turbo.bin"


SAMPLE_RATE = 16000
WINDOW_SIZE = SAMPLE_RATE * 30  # 30s Whisper window
CHUNK_SIZE = 512


class Transcriber:
    """Whisper transcriber with optional thread pool for blocking operations."""

    def __init__(self, whisper: Whisper, executor: Executor | None = None):
        self._whisper = whisper
        self._executor = executor

    def close(self) -> None:
        self._whisper.close()

    @classmethod
    def from_path(cls, model_path: str, executor: Executor | None = None) -> Self:
        return cls(Whisper(model_path), executor)

    def transcribe(self, window: AudioChunk) -> Observable[str]:
        """Transcribe a single audio window (up to 30s of 16kHz audio)."""
        return from_thread(lambda: self._whisper.transcribe(window), self._executor)
