"""Tests for Transcriber."""

import threading
from unittest.mock import MagicMock

import numpy as np

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


def test_transcriber_transcribes_window() -> None:
    """Transcriber transcribes a single audio window."""
    whisper = mock_whisper({1.0: "hello world"})
    transcriber = Transcriber(whisper)

    window = np.full(CHUNK_SIZE * 2, 1.0, dtype=np.float32)

    results: list[str] = []
    done = threading.Event()

    transcriber.transcribe(window).subscribe(
        on_next=results.append,
        on_completed=done.set,
    )

    done.wait(timeout=5.0)

    assert results == ["hello world"]
    assert len(whisper.calls) == 1
