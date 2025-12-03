"""Tests for STT transcribe operator."""

import threading
from unittest.mock import MagicMock

import numpy as np
import reactivex as rx

from audio._stt import Whisper
from audio.types import AudioChunk
from audio.whisper import CHUNK_SIZE, Transcriber


def chunk(value: float = 0.0) -> AudioChunk:
    """Create a 512-sample chunk filled with value."""
    return np.full(CHUNK_SIZE, value, dtype=np.float32)


def mock_whisper(responses: dict[float, str] | None = None) -> MagicMock:
    """Create a mock Whisper that returns text based on first sample value."""
    responses = responses or {}
    mock = MagicMock(spec=Whisper)
    mock.calls = []

    def transcribe(samples: AudioChunk) -> str:
        mock.calls.append(samples)
        key = round(float(samples[0]), 1)
        return responses.get(key, "")

    mock.transcribe.side_effect = transcribe
    return mock


def test_transcriber_accumulates_chunks_and_emits() -> None:
    """Transcriber buffers chunks and emits transcription.

    Note: switch_map drops in-flight transcriptions when new windows arrive.
    With synchronous emission, only the last window's transcription completes.
    """
    whisper = mock_whisper({0.0: "hello world"})

    # emit_interval=1024 with CHUNK_SIZE=512 means emit every 2 chunks
    transcriber = Transcriber(whisper)
    operator = transcriber.transcribe(emit_interval=1024)

    results: list[str] = []
    errors: list[Exception] = []
    done = threading.Event()
    # 2 chunks = 1 window emission
    chunks = [chunk(0.0) for _ in range(2)]

    rx.of(*chunks).pipe(operator).subscribe(
        on_next=lambda t: results.append(t),
        on_error=lambda e: errors.append(e),
        on_completed=done.set,
    )

    done.wait(timeout=5.0)

    assert not errors, f"Errors: {errors}"
    assert len(results) == 1
    assert results[0] == "hello world"
    assert len(whisper.calls) == 1
