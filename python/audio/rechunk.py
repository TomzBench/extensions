"""Audio rechunking operator for RxPy streams."""

import numpy as np
import reactivex as rx
from reactivex import Observable
from reactivex import operators as ops
from streams.utils import Operator

from audio.types import AudioChunk


def rechunk(chunk_size: int = 512) -> Operator[AudioChunk, AudioChunk]:
    """Accumulate audio into fixed-size chunks.

    Emits fixed-size chunks as they fill. On completion, emits any
    remaining samples zero-padded to chunk_size.
    """
    buffer = np.array([], dtype=np.float32)

    def process(chunk: AudioChunk) -> Observable[AudioChunk]:
        nonlocal buffer
        buffer = np.concatenate([buffer, chunk.flatten()])

        def emit_chunks() -> Observable[AudioChunk]:
            nonlocal buffer
            if len(buffer) >= chunk_size:
                out = buffer[:chunk_size]
                buffer = buffer[chunk_size:]
                return rx.of(out).pipe(ops.concat(rx.defer(lambda _: emit_chunks())))
            return rx.empty()

        return emit_chunks()

    # when our source observable is finished, we want to emit the remainder w/ pad
    def flush() -> Observable[AudioChunk]:
        nonlocal buffer
        if len(buffer) > 0:
            padded = np.zeros(chunk_size, dtype=np.float32)
            padded[: len(buffer)] = buffer
            buffer = np.array([], dtype=np.float32)
            return rx.of(padded)
        return rx.empty()

    def _operator(source: Observable[AudioChunk]) -> Observable[AudioChunk]:
        # Concat waits for "process" to finish, then we can pad the remainder
        return source.pipe(
            ops.flat_map(process),
            ops.concat(rx.defer(lambda _: flush())),
        )

    return _operator
