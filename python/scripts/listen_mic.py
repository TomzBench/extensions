#!/usr/bin/env python3
"""Test program to listen to mic and transcribe speech."""

import signal
import sys
import threading

from audio.config import Tunable
from audio.stt import recorder
from reactivex.subject import Subject


def main() -> int:
    done = threading.Event()
    tunables: Subject[Tunable] = Subject()

    print("Listening... (Ctrl+C to stop)")

    subscription = recorder()(tunables).subscribe(
        on_next=lambda text: print(f"> {text}"),
        on_error=lambda e: print(f"Error: {e}", file=sys.stderr),
        on_completed=done.set,
    )

    signal.signal(signal.SIGINT, lambda *_: subscription.dispose())
    done.wait()
    print("Done.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
