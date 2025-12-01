"""
Asyncio wrappers around creating audio sources.  For example, download an audio file from youtube or
listen to the mic.

Many of these sources have hard dependencies that are not injected. (YT-DLP, sounddevice, etc). In
When testing complicated RxPy flows, use marbles - and observable pipes should have an abstract
interface.
"""

import asyncio
import contextlib
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import reactivex as rx
import sounddevice as sd  # type: ignore[import-untyped]
from numpy.typing import NDArray
from reactivex import operators as ops
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase
from reactivex.disposable import Disposable
from reactivex.observable import Observable
from reactivex.scheduler import NewThreadScheduler
from streams import from_async
from yt_dlp import YoutubeDL
from yt_dlp.utils import YoutubeDLError

from audio._stt import AudioChunks
from audio.exceptions import AudioExtractionError

if TYPE_CHECKING:
    from yt_dlp import _Params

type AudioStream = NDArray[np.float32]


def safe_cleanup(tmpdir: tempfile.TemporaryDirectory) -> Callable:
    def do_cleanup() -> None:
        with contextlib.suppress(OSError):
            tmpdir.cleanup()

    return do_cleanup


def download_audio(url: str, format: str = "mp3") -> Observable[tuple[str, list[bytes]]]:
    def create_source(_scheduler: SchedulerBase | None) -> Observable[tuple[str, list[bytes]]]:
        tmpdir = tempfile.TemporaryDirectory()

        def fetch() -> Path:
            opts: _Params = {
                "format": "bestaudio/best",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": format}],
                "outtmpl": str(Path(tmpdir.name) / "%(id)s"),
                "quiet": True,
            }
            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return Path(tmpdir.name) / f"{info['id']}.{format}"
            except YoutubeDLError as e:
                raise AudioExtractionError(str(e)) from e

        return from_async(lambda: asyncio.to_thread(fetch)).pipe(
            ops.map(lambda path: (format, list(AudioChunks(str(path), 30_000)))),
            ops.finally_action(safe_cleanup(tmpdir)),
        )

    return rx.defer(create_source)


def listen_to_mic(device: int | None = None) -> Observable[AudioStream]:
    """Create an observable that emits audio samples from a microphone."""

    def subscribe(
        obs: ObserverBase[AudioStream], _sched: SchedulerBase | None = None
    ) -> DisposableBase:
        def callback(data: AudioStream, _fr: int, _time: object, _status: object) -> None:
            obs.on_next(data.copy())

        # NOTE - might need to implement resample to 16Khz, (default is usually 44.1khz or 48khz).
        #        sd resamples if device supports it. Supposedly most modern devices support
        stream = sd.InputStream(device=device, callback=callback, channels=1, samplerate=16000)
        stream.start()

        def dispose() -> None:
            stream.stop()
            stream.close()

        return Disposable(dispose)

    # callback runs on system audio thread, observe_on switches to new thread for downstream
    return rx.create(subscribe).pipe(ops.observe_on(NewThreadScheduler()))
