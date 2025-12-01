"""Async-to-Observable bridge for RxPy (asyncio thread only)."""

import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Awaitable, Callable

import reactivex
from reactivex import Observable
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase

from streams.utils import disposer


def from_async[T](
    coro: Callable[[], Awaitable[T]],
    maybe_loop: AbstractEventLoop | None = None,
) -> Observable[T]:
    """Convert a zero-arg async callable into a single-emission Observable.

    Must be subscribed from the asyncio thread. For subscriptions from other threads
    (e.g., audio callbacks), use from_async_threadsafe instead.
    """

    def subscribe(obs: ObserverBase[T], _scheduler: SchedulerBase | None = None) -> DisposableBase:
        loop = maybe_loop or asyncio.get_running_loop()

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
        return disposer(task)

    return reactivex.create(subscribe)
