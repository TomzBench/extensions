"""Thread-safe async-to-Observable bridge for RxPy."""

import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Awaitable, Callable

import reactivex
from reactivex import Observable
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase
from reactivex.disposable import Disposable


def from_async_threadsafe[T](
    coro: Callable[[], Awaitable[T]],
    loop: AbstractEventLoop,
) -> Observable[T]:
    """Convert a zero-arg async callable into a single-emission Observable.

    Thread-safe variant that can be subscribed from any thread (e.g., audio callbacks).
    Requires an explicit event loop reference since get_running_loop() won't work
    from non-asyncio threads.

    Example:
        >>> loop = asyncio.get_running_loop()
        >>> obs = from_async_threadsafe(lambda: fetch("https://example.com"), loop)
        >>> # Can be subscribed from audio thread
    """

    def subscribe(obs: ObserverBase[T], _scheduler: SchedulerBase | None = None) -> DisposableBase:
        async def run() -> None:
            try:
                result = await coro()
                obs.on_next(result)
                obs.on_completed()
            except asyncio.CancelledError as e:
                obs.on_error(Exception(e))  # propagate to subscriber
            except Exception as e:
                obs.on_error(e)

        future = asyncio.run_coroutine_threadsafe(run(), loop)

        def dispose() -> None:
            future.cancel()

        return Disposable(dispose)

    return reactivex.create(subscribe)
