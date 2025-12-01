"""Integration test for Whisper transcription pipeline."""

import asyncio
from pathlib import Path

import numpy as np
import pytest
import reactivex as rx
from audio.rechunk import rechunk
from audio.stt import CHUNK_SIZE, with_whisper
from scripts.download_whisper import get_model_path

FIXTURES = Path(__file__).parent / ".fixtures"


def load_raw_audio(path: Path) -> np.ndarray:
    """Load raw f32le audio file."""
    return np.fromfile(path, dtype=np.float32)


@pytest.mark.slow
def test_whisper_transcribes_prechunked_audio() -> None:
    """Integration test: Whisper transcribes pre-chunked audio."""
    model_path = str(get_model_path("base.en"))
    audio = load_raw_audio(FIXTURES / "rick_5s_16k.raw")

    # split into CHUNK_SIZE chunks
    chunks = [audio[i : i + CHUNK_SIZE] for i in range(0, len(audio), CHUNK_SIZE)]
    # pad last chunk if needed
    if len(chunks[-1]) < CHUNK_SIZE:
        chunks[-1] = np.pad(chunks[-1], (0, CHUNK_SIZE - len(chunks[-1])))

    results: list[str] = []
    errors: list[Exception] = []
    loop = asyncio.new_event_loop()

    def run_test() -> None:
        async def async_test() -> None:
            done = asyncio.Event()
            with_whisper(
                model_path,
                lambda t: rx.of(*chunks).pipe(t.transcribe_seconds(0.5)),
            ).subscribe(
                on_next=lambda text: results.append(text),
                on_error=lambda e: errors.append(e),
                on_completed=done.set,
            )
            await asyncio.wait_for(done.wait(), timeout=30.0)

        loop.run_until_complete(async_test())

    run_test()
    loop.close()

    assert not errors, f"Errors: {errors}"
    assert len(results) >= 1, "Expected at least one transcription"
    full_text = " ".join(results).lower()
    print(f"Transcribed: {full_text}")
    assert len(full_text) > 0, "Transcription was empty"


@pytest.mark.slow
def test_whisper_transcribes_with_rechunk() -> None:
    """Integration test: Whisper transcribes audio through rechunk pipeline."""
    model_path = str(get_model_path("base.en"))
    audio = load_raw_audio(FIXTURES / "rick_5s_16k.raw")

    # simulate mic-like chunks (variable size, smaller than CHUNK_SIZE)
    mic_chunks = [audio[i : i + 256] for i in range(0, len(audio), 256)]

    results: list[str] = []
    errors: list[Exception] = []
    loop = asyncio.new_event_loop()

    def run_test() -> None:
        async def async_test() -> None:
            done = asyncio.Event()
            with_whisper(
                model_path,
                lambda t: rx.of(*mic_chunks).pipe(
                    rechunk(CHUNK_SIZE),
                    t.transcribe_seconds(0.5),
                ),
            ).subscribe(
                on_next=lambda text: results.append(text),
                on_error=lambda e: errors.append(e),
                on_completed=done.set,
            )
            await asyncio.wait_for(done.wait(), timeout=30.0)

        loop.run_until_complete(async_test())

    run_test()
    loop.close()

    assert not errors, f"Errors: {errors}"
    assert len(results) >= 1, "Expected at least one transcription"
    full_text = " ".join(results).lower()
    print(f"Transcribed: {full_text}")
    assert len(full_text) > 0, "Transcription was empty"
