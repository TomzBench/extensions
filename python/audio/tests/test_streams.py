"""Tests for audio stream processing."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from audio.stream import download_audio

FIXTURES_DIR = Path(__file__).parent / ".fixtures"
VIDEO_ID = "dQw4w9WgXcQ"


def test_download_audio_emits_chunked_audio():
    """Test that download_audio extracts and chunks audio."""
    fixture_path = FIXTURES_DIR / f"{VIDEO_ID}.mp3"

    # Patch extract_audio to return fixture path instead of downloading
    with patch("audio.stream.extract_audio", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = fixture_path

        results: list[tuple[str, bytes]] = []
        completed: list[bool] = []

        obs = download_audio(f"https://www.youtube.com/watch?v={VIDEO_ID}")
        obs.subscribe(
            on_next=results.append,
            on_completed=lambda: completed.append(True),
        )

        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))

        mock_extract.assert_called_once()
        assert len(results) == 1
        assert results[0][0] == "mp3"
        assert len(results[0][1]) > 0
        assert completed == [True]
