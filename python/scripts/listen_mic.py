#!/usr/bin/env python3
"""Test program to listen to mic and transcribe speech."""

import asyncio
import signal
import sys

from audio.rechunk import rechunk
from audio.silero import SileroVADModel
from audio.stream import listen_to_mic
from audio.stt import with_whisper
from audio.vad import vad_sentence
from reactivex import operators as ops
from reactivex.subject import Subject
from scripts.download_whisper import get_model_path


async def main() -> int:
    model_path = str(get_model_path("small.en"))
    vad = SileroVADModel()
    stop: Subject[bool] = Subject()

    print("Listening... (Ctrl+C to stop)")

    done = asyncio.Event()
    with_whisper(
        model_path,
        lambda t: listen_to_mic().pipe(
            rechunk(512),
            vad_sentence(vad),
            t.transcribe_seconds(0.5),
            ops.repeat(),
            ops.take_until(stop),
        ),
    ).subscribe(
        on_next=lambda text: print(f"> {text}"),
        on_error=lambda e: print(f"Error: {e}", file=sys.stderr),
        on_completed=done.set,
    )

    asyncio.get_running_loop().add_signal_handler(signal.SIGINT, lambda: stop.on_next(True))
    await done.wait()
    print("Done.")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
