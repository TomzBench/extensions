"""Utility functions for bridging async/await and RxPy observables."""

# Helpers for converting between coroutines, futures, and observables.
# Also includes convenience functions for collecting stream results.

import asyncio
from asyncio import AbstractEventLoop, Task
from collections.abc import Awaitable, Callable
from typing import TypeVar

import reactivex
from reactivex import Observable
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase
from reactivex.disposable import Disposable

T = TypeVar("T")


def _disposer(task: Task[T]) -> Disposable:
    def dispose() -> None:
        if task.cancel():
            # TODO log task was succesfully cancelled
            pass
        else:
            # TODO warn task is no longer running
            pass

    return Disposable(dispose)


def from_async(
    coro: Callable[[], Awaitable[T]],
    maybe_loop: AbstractEventLoop | None = None,
) -> Observable[T]:
    """Convert a zero-arg async callable into a single-emission Observable.

    Example:
        >>> async def fetch(url: str) -> dict:
        ...     return {"data": "..."}
        >>> obs = from_async(lambda: fetch("https://example.com"))
        >>> obs.subscribe(on_next=print)
    """

    def subscribe(obs: ObserverBase[T], _scheduler: SchedulerBase | None = None) -> DisposableBase:
        loop = maybe_loop if maybe_loop is not None else asyncio.get_event_loop()

        async def run() -> None:
            try:
                result = await coro()
                obs.on_next(result)
                obs.on_completed()
            except asyncio.CancelledError as e:
                obs.on_error(Exception(e))  # propagate to subscriber
            except Exception as e:
                obs.on_error(e)

        task = loop.create_task(run())
        return _disposer(task)

    return reactivex.create(subscribe)
