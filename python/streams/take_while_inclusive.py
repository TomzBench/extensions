"""Take-while operator that includes the failing element."""

from collections.abc import Callable

import reactivex
from reactivex import Observable
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase

from streams.utils import Operator


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
