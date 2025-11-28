import contextlib
import tempfile
from collections.abc import Callable
from pathlib import Path

import reactivex as rx
from reactivex import operators as ops
from reactivex.abc import SchedulerBase
from reactivex.observable import Observable
from streams import from_async

from audio._stt import AudioChunks
from audio.extract import extract_audio


def safe_cleanup(tmpdir: tempfile.TemporaryDirectory) -> Callable:
    def do_cleanup() -> None:
        with contextlib.suppress(OSError):
            tmpdir.cleanup()

    return do_cleanup


# NOTE for complicated pipeline, inject ths observable factory as a marble. This method hardcodes
# an asyncio task as a dependency and is not injected. Trivial case like this is ok. But this method
# is not suitable for marble testing. IE:
# def complicated_pipe(source: Observable[AudioBytes]) (download_audio in prod, marble in test)
def download_audio(url: str, format: str = "mp3") -> Observable[tuple[str, list[bytes]]]:
    def create_source(_scheduler: SchedulerBase | None) -> Observable[tuple[str, list[bytes]]]:
        tmpdir = tempfile.TemporaryDirectory()
        return from_async(lambda: extract_audio(url, Path(tmpdir.name), format)).pipe(
            ops.map(lambda path: (format, list(AudioChunks(str(path), 30_000)))),
            ops.finally_action(safe_cleanup(tmpdir)),
        )

    return rx.defer(create_source)
