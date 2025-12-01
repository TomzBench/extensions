"""Speech-to-text operators for RxPy streams."""

import asyncio
from asyncio import AbstractEventLoop
from collections import deque
from collections.abc import Callable

import numpy as np
import reactivex as rx
from reactivex import Observable
from reactivex import operators as ops
from reactivex.abc import SchedulerBase
from streams import buffer_with_count_or_complete, from_async_threadsafe
from streams.utils import Operator

from audio._stt import Whisper
from audio.types import AudioChunk

SAMPLE_RATE = 16000
WINDOW_SIZE = SAMPLE_RATE * 30  # 30s Whisper window
CHUNK_SIZE = 512


class Transcriber:
    """Whisper transcriber with cached event loop for async operations."""

    def __init__(self, whisper: Whisper, loop: AbstractEventLoop):
        self._whisper = whisper
        self._loop = loop

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
                lambda: asyncio.to_thread(whisper.transcribe, window), loop
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
        return self.transcribe(int(emit_interval * SAMPLE_RATE))


def with_whisper[T](
    model_path: str,
    factory: Callable[[Transcriber], Observable[T]],
    loop: AbstractEventLoop | None = None,
) -> Observable[T]:
    """Manage Whisper context lifecycle for an observable pipeline.

    Loads the model once, passes a Transcriber to factory, and ensures cleanup on
    termination. Use this to share a Whisper context across repeated subscriptions
    (e.g., with repeat()).
    """

    def create(_scheduler: SchedulerBase | None) -> Observable[T]:
        whisper = Whisper(model_path)
        transcriber = Transcriber(whisper, loop or asyncio.get_running_loop())
        return factory(transcriber).pipe(ops.finally_action(whisper.close))

    return rx.defer(create)
