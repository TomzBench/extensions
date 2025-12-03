"""Tests for from_thread operator."""

import threading

from streams.from_thread import from_thread


def test_from_thread_emits_result() -> None:
    """Runs blocking callable in thread and emits result."""
    results: list[str] = []
    done = threading.Event()

    from_thread(lambda: "hello").subscribe(
        on_next=results.append,
        on_completed=done.set,
    )

    done.wait(timeout=1.0)
    assert results == ["hello"]


def test_from_thread_emits_error() -> None:
    """Propagates exceptions to on_error."""
    errors: list[Exception] = []
    done = threading.Event()

    def fail() -> str:
        raise ValueError("boom")

    def on_error(e: Exception) -> None:
        errors.append(e)
        done.set()

    from_thread(fail).subscribe(on_error=on_error)

    done.wait(timeout=1.0)
    assert len(errors) == 1
    assert "boom" in str(errors[0])
