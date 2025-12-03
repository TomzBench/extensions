#!/usr/bin/env python3
"""Test program to listen to mic and transcribe speech."""

import asyncio
import signal
import sys

from audio import recorder
from reactivex import operators as ops
from reactivex.subject import Subject


async def main() -> int:
    stop: Subject[bool] = Subject()

    print("Listening... (Ctrl+C to stop)")

    done = asyncio.Event()
    tunables = Subject()
    stt = recorder()
    stt(tunables).pipe(ops.take_until(stop)).subscribe(
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
