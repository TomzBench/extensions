"""Tests for from_async utility."""

import asyncio
from unittest.mock import AsyncMock

from streams import from_async


def test_from_async_emits_and_completes() -> None:
    """Test that from_async emits the resolved value and completes."""
    mock_data = {"id": 1}
    spy = AsyncMock(return_value=mock_data)

    results: list[dict] = []
    completed = []

    obs = from_async(spy)
    obs.subscribe(
        on_next=results.append,
        on_completed=lambda: completed.append(True),
    )

    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))

    spy.assert_called_once()
    assert results == [mock_data]
    assert completed == [True]


def test_from_async_emits_error() -> None:
    """Test that from_async will resolve with an error."""
    spy = AsyncMock(side_effect=ValueError("boom"))

    errors = []
    completed: list[bool] = []

    obs = from_async(spy)
    obs.subscribe(on_error=lambda e: errors.append(e))

    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))

    spy.assert_called_once()
    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)
    assert errors[0].args == ("boom",)
    assert completed == []


def test_from_async_cancellation() -> None:
    step = asyncio.Event()

    async def sem() -> int:
        await step.wait()  # Semaphore symantics, drive test w/ step.set()
        return 42  # value is never emitted

    results: list[int] = []
    obs = from_async(sem)
    subscription = obs.subscribe(on_next=results.append)

    # Start event loop (async task "sem" is in flight)
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))

    # We cancel the async "sem" task
    subscription.dispose()

    # Free our task (but our task was already aborted)
    step.set()
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))

    # because we aborted, on_next never fires
    assert results == []
