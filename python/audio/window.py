"""Sliding window operator for audio chunks."""

from collections import deque

import numpy as np
from reactivex import Observable
from reactivex import operators as ops
from streams import buffer_with_count_or_complete
from streams.utils import Operator

from audio.types import AudioChunk

SAMPLE_RATE = 16000
WINDOW_SIZE = SAMPLE_RATE * 30  # 30s window
CHUNK_SIZE = 512


def window_chunks(
    chunk_size: int = CHUNK_SIZE,
    window_size: int = WINDOW_SIZE,
    emit_interval: int = 8000,
) -> Operator[AudioChunk, AudioChunk]:
    """Accumulate chunks into sliding window, emit every emit_interval samples.

    Collects fixed-size chunks into a rolling buffer (max window_size samples).
    Emits a padded window every emit_interval samples. Old chunks are dropped
    when the buffer exceeds capacity.
    """
    max_chunks = window_size // chunk_size
    chunks_per_emit = -(-emit_interval // chunk_size)  # ceiling division

    def _operator(source: Observable[AudioChunk]) -> Observable[AudioChunk]:
        def accumulate(buf: deque[AudioChunk], chunk: AudioChunk) -> deque[AudioChunk]:
            buf.append(chunk)
            return buf

        def build_window(states: list[deque[AudioChunk]]) -> AudioChunk:
            window = np.concatenate(list(states[-1]))
            if len(window) < window_size:
                window = np.pad(window, (0, window_size - len(window)))
            return window

        seed: deque[AudioChunk] = deque(maxlen=max_chunks)
        scanned: Observable[deque[AudioChunk]] = source.pipe(ops.scan(accumulate, seed))
        buffered: Observable[list[deque[AudioChunk]]] = scanned.pipe(
            buffer_with_count_or_complete(chunks_per_emit)
        )
        return buffered.pipe(ops.map(build_window))

    return _operator
