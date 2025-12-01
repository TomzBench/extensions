"""Tests for audio stream processing."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio.stream import download_audio

FIXTURES_DIR = Path(__file__).parent / ".fixtures"
VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.asyncio
@patch("audio.stream.tempfile.TemporaryDirectory")
@patch("audio.stream.YoutubeDL")
async def test_download_audio_emits_chunked_audio(
    mock_ydl_class: MagicMock, mock_tmpdir: MagicMock
) -> None:
    """Test that download_audio extracts and chunks audio."""
    # Setup TemporaryDirectory to point to fixtures
    mock_tmpdir.return_value.name = str(FIXTURES_DIR)
    mock_tmpdir.return_value.cleanup = MagicMock()

    # Setup YoutubeDL mock
    mock_ydl = MagicMock()
    mock_ydl_class.return_value = mock_ydl
    mock_ydl.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {"id": VIDEO_ID}

    results: list[tuple[str, list[bytes]]] = []
    completed: list[bool] = []
    errors: list[Exception] = []

    obs = download_audio(f"https://www.youtube.com/watch?v={VIDEO_ID}")
    obs.subscribe(
        on_next=results.append,
        on_completed=lambda: completed.append(True),
        on_error=errors.append,
    )

    await asyncio.sleep(0.1)

    assert errors == [], f"Unexpected error: {errors}"
    assert len(results) == 1
    assert results[0][0] == "mp3"
    assert len(results[0][1]) > 0  # Real chunks from fixture
    assert completed == [True]
    mock_ydl.extract_info.assert_called_once()
