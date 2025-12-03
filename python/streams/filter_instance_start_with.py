"""Type-narrowing filter operator with initial value for RxPy."""

import reactivex as rx
from reactivex import Observable

from streams.filter_instance import filter_instance
from streams.utils import Operator


def filter_instance_start_with[T, U](default: U) -> Operator[T, U]:
    """Filter to instances matching type of default, starting with default.

    Emits the default value immediately, then filters the source to only
    emit values that are instances of the same type as default.
    """

    def _operator(source: Observable[T]) -> Observable[U]:
        cls = type(default)
        return rx.merge(
            rx.of(default),
            source.pipe(filter_instance(cls)),
        )

    return _operator
