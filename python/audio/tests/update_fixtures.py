"""Helper scripts to fetch mock data

Usage:
    python -m audio.tests.update_fixtures
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

import yt_dlp

if TYPE_CHECKING:
    from yt_dlp import _Params

FIXTURES_DIR = Path(__file__).parent / ".fixtures"
VIDEO_ID = "dQw4w9WgXcQ"


def download_audio() -> Path:
    """Download audio fixture using yt-dlp."""
    FIXTURES_DIR.mkdir(exist_ok=True)
    output_audio = FIXTURES_DIR / f"{VIDEO_ID}.mp3"
    output_info = FIXTURES_DIR / f"{VIDEO_ID}.json"

    opts: _Params = {
        "format": "bestaudio/best",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        "outtmpl": str(FIXTURES_DIR / "%(id)s.%(ext)s"),
        "quiet": False,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        url = f"https://youtube.com/watch?v={VIDEO_ID}"
        ydl.download([url])
        info = ydl.extract_info(url)
        with open(output_info, "w") as f:
            json.dump(info, f, indent=2, default=str)

    return output_audio


if __name__ == "__main__":
    path = download_audio()
    print(f"Downloaded: {path}")
