"""Audio extraction from video URLs."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YtDlpDownloadError
from yt_dlp.utils import ExtractorError, YoutubeDLError
from yt_dlp.utils import PostProcessingError as YtDlpPostProcessingError

from audio.exceptions import (
    AudioExtractionError,
    DownloadError,
    InvalidURLError,
    OutputDirectoryError,
    PostProcessingError,
    VideoUnavailableError,
)

if TYPE_CHECKING:
    from yt_dlp import _Params


def extract_audio_sync(url: str, output_dir: Path, audio_format: str = "mp3") -> Path:
    """Extract audio from a video URL using yt-dlp."""
    if not output_dir.is_dir():
        raise OutputDirectoryError(f"Output directory does not exist: {output_dir}")

    opts: _Params = {
        "format": "bestaudio/best",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": audio_format}],
        "outtmpl": str(output_dir / "%(id)s"),
        "quiet": True,
    }
    try:
        with YoutubeDL(opts) as ydl:
            # NOTE - assuming postprocessor preferredcodec will give our file a predictable
            # extension. This assumption breaks w/ exotic file formats or malicious inputs
            info = ydl.extract_info(url, download=True)
            return output_dir / f"{info['id']}.{audio_format}"
    except ExtractorError as e:
        if "Unsupported URL" in str(e):
            raise InvalidURLError(str(e)) from e
        raise VideoUnavailableError(str(e)) from e
    except YtDlpDownloadError as e:
        raise DownloadError(str(e)) from e
    except YtDlpPostProcessingError as e:
        raise PostProcessingError(str(e)) from e
    except YoutubeDLError as e:
        raise AudioExtractionError(str(e)) from e


async def extract_audio(url: str, output_dir: Path, audio_format: str = "mp3") -> Path:
    """Async wrapper for extract_audio."""
    return await asyncio.to_thread(extract_audio_sync, url, output_dir, audio_format)
