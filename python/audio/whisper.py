"""Speech-to-text operators for RxPy streams."""

import asyncio
from asyncio import AbstractEventLoop
from collections import deque
from enum import StrEnum
from typing import Self

import numpy as np
from reactivex import Observable
from reactivex import operators as ops
from streams import buffer_with_count_or_complete, from_async_threadsafe
from streams.utils import Operator

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
    """Whisper transcriber with cached event loop for async operations."""

    def __init__(self, whisper: Whisper, loop: AbstractEventLoop | None = None):
        self._whisper = whisper
        self._loop = loop or asyncio.get_running_loop()

    def close(self) -> None:
        self._whisper.close()

    @classmethod
    def from_path(cls, model_path: str, loop: AbstractEventLoop | None = None) -> Self:
        return cls(Whisper(model_path), loop)

    def transcribe(self, emit_interval: int = 8000) -> Operator[AudioChunk, str]:
        """Transcribe audio chunks using Whisper with a 30s sliding window.

        Accumulates incoming chunks into a rolling buffer, emits transcriptions every
        emit_interval samples. Uses switch_map to drop in-flight transcriptions if a
        new window is ready (prevents backpressure buildup for live audio).

        Expects fixed-size chunks of CHUNK_SIZE samples (use rechunk(512) upstream).
        """
        max_chunks = WINDOW_SIZE // CHUNK_SIZE
        chunks_per_emit = -(-emit_interval // CHUNK_SIZE)  # ceiling division
        whisper = self._whisper
        loop = self._loop

        def accumulate(buf: deque[AudioChunk], chunk: AudioChunk) -> deque[AudioChunk]:
            assert len(chunk) == CHUNK_SIZE, f"Expected {CHUNK_SIZE} samples, got {len(chunk)}"
            buf.append(chunk)
            return buf

        def build_window(states: list[deque[AudioChunk]]) -> AudioChunk:
            window = np.concatenate(list(states[-1]))
            if len(window) < WINDOW_SIZE:
                window = np.pad(window, (0, WINDOW_SIZE - len(window)))
            return window

        def transcribe_window(window: AudioChunk) -> Observable[str]:
            return from_async_threadsafe(
                lambda: asyncio.to_thread(whisper.transcribe, window),
                loop,
            )

        def _operator(source: Observable[AudioChunk]) -> Observable[str]:
            seed: deque[AudioChunk] = deque(maxlen=max_chunks)
            scanned: Observable[deque[AudioChunk]] = source.pipe(ops.scan(accumulate, seed))
            buffered: Observable[list[deque[AudioChunk]]] = scanned.pipe(
                buffer_with_count_or_complete(chunks_per_emit)
            )
            windowed: Observable[AudioChunk] = buffered.pipe(ops.map(build_window))
            return windowed.pipe(ops.switch_map(transcribe_window))

        return _operator

    def transcribe_seconds(self, emit_interval: float = 0.5) -> Operator[AudioChunk, str]:
        """Transcribe audio with emit_interval in seconds."""
        # TODO since we're a class method, we should have caller "map" w/ a transcribe instead of
        # returning an observable
        return self.transcribe(int(emit_interval * SAMPLE_RATE))
