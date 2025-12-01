"""Tests for STT transcribe operator."""

import asyncio

import numpy as np
import reactivex as rx

from audio.stt import CHUNK_SIZE, Transcriber
from audio.types import AudioChunk


def chunk(value: float = 0.0) -> AudioChunk:
    """Create a 512-sample chunk filled with value."""
    return np.full(CHUNK_SIZE, value, dtype=np.float32)


class MockWhisper:
    """Mock Whisper that returns text based on first sample value."""

    def __init__(self, responses: dict[float, str] | None = None):
        self._responses = responses or {}
        self.calls: list[AudioChunk] = []

    def transcribe(self, samples: AudioChunk) -> str:
        self.calls.append(samples)
        key = round(float(samples[0]), 1)
        return self._responses.get(key, "")

    def close(self) -> None:
        pass


def test_transcriber_accumulates_chunks_and_emits() -> None:
    """Transcriber buffers chunks and emits transcription.

    Note: switch_map drops in-flight transcriptions when new windows arrive.
    With synchronous emission, only the last window's transcription completes.
    """
    whisper = MockWhisper({0.0: "hello world"})
    loop = asyncio.new_event_loop()

    # emit_interval=1024 with CHUNK_SIZE=512 means emit every 2 chunks
    transcriber = Transcriber(whisper, loop)
    operator = transcriber.transcribe(emit_interval=1024)

    results: list[str] = []
    errors: list[Exception] = []
    # 2 chunks = 1 window emission
    chunks = [chunk(0.0) for _ in range(2)]

    def run_test() -> None:
        async def async_test() -> None:
            done = asyncio.Event()
            rx.of(*chunks).pipe(operator).subscribe(
                on_next=lambda t: results.append(t),
                on_error=lambda e: errors.append(e),
                on_completed=lambda: done.set(),
            )
            await asyncio.wait_for(done.wait(), timeout=5.0)

        loop.run_until_complete(async_test())

    run_test()
    loop.close()

    assert not errors, f"Errors: {errors}"
    assert len(results) == 1
    assert results[0] == "hello world"
    assert len(whisper.calls) == 1
