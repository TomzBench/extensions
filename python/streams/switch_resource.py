"""Switch-map with resource cleanup for RxPy pipelines."""

from collections.abc import Callable
from typing import Protocol

from reactivex import Observable
from reactivex import operators as ops

from streams.utils import Operator


class Closeable(Protocol):
    def close(self) -> None: ...


def switch_resource[T, R: Closeable](
    observable_factory: Callable[[R], Observable[T]],
) -> Operator[R, T]:
    """Switch-map over resources with automatic cleanup.

    For each resource emitted, creates an inner observable via observable_factory.
    When a new resource arrives, the previous inner observable is disposed and
    the previous resource is closed.

    Ensures cleanup via resource.close() on switch, complete, error, or dispose.
    """

    def _operator(source: Observable[R]) -> Observable[T]:
        def create_inner(resource: R) -> Observable[T]:
            return observable_factory(resource).pipe(ops.finally_action(resource.close))

        return source.pipe(ops.switch_map(create_inner))

    return _operator
