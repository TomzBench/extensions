"""Type-narrowing filter operator for RxPy."""

from typing import cast

from reactivex import Observable
from reactivex import operators as ops

from streams.utils import Operator


def filter_instance[T, U](cls: type[U]) -> Operator[T, U]:
    """Filter to only items that are instances of cls, with type narrowing."""

    def _operator(source: Observable[T]) -> Observable[U]:
        filtered: Observable[T] = source.pipe(ops.filter(lambda x: isinstance(x, cls)))
        return filtered.pipe(ops.map(lambda x: cast("U", x)))

    return _operator
