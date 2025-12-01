"""Utility functions for bridging async/await and RxPy observables."""

import asyncio
from asyncio import AbstractEventLoop, Task
from collections.abc import Awaitable, Callable

import reactivex
from reactivex import Observable
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase
from reactivex.disposable import Disposable

type Operator[T, U] = Callable[[Observable[T]], Observable[U]]


def _disposer[T](task: Task[T]) -> Disposable:
    def dispose() -> None:
        if task.cancel():
            # TODO log task was succesfully cancelled
            pass
        else:
            # TODO warn task is no longer running
            pass

    return Disposable(dispose)


def from_async[T](
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

        # use run_coroutine_threadsafe to schedule from any thread
        future = asyncio.run_coroutine_threadsafe(run(), loop)

        def dispose() -> None:
            future.cancel()

        return Disposable(dispose)

    return reactivex.create(subscribe)


def buffer_with_count_or_complete[T](count: int) -> Operator[T, list[T]]:
    """Buffer items into lists of size count, emitting partial buffer on complete."""

    def _operator(source: Observable[T]) -> Observable[list[T]]:
        def subscribe(
            observer: ObserverBase[list[T]], scheduler: SchedulerBase | None = None
        ) -> DisposableBase:
            buffer: list[T] = []

            def on_next(item: T) -> None:
                buffer.append(item)
                if len(buffer) >= count:
                    observer.on_next(buffer.copy())
                    buffer.clear()

            def on_completed() -> None:
                if buffer:
                    observer.on_next(buffer.copy())
                observer.on_completed()

            return source.subscribe(
                on_next=on_next,
                on_error=observer.on_error,
                on_completed=on_completed,
                scheduler=scheduler,
            )

        return reactivex.create(subscribe)

    return _operator


def take_while_inclusive[T](predicate: Callable[[T], bool]) -> Operator[T, T]:
    """Like take_while but includes the first element that fails the predicate."""

    def _operator(source: Observable[T]) -> Observable[T]:
        def subscribe(
            observer: ObserverBase[T], scheduler: SchedulerBase | None = None
        ) -> DisposableBase:
            def on_next(item: T) -> None:
                if predicate(item):
                    observer.on_next(item)
                else:
                    observer.on_next(item)
                    observer.on_completed()

            return source.subscribe(
                on_next=on_next,
                on_error=observer.on_error,
                on_completed=observer.on_completed,
                scheduler=scheduler,
            )

        return reactivex.create(subscribe)

    return _operator
