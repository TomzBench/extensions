"""Buffer operator that emits partial buffers on completion."""

import reactivex
from reactivex import Observable
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase

from streams.utils import Operator


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
