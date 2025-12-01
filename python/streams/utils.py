"""Shared utilities for RxPy stream operators."""

from asyncio import Task
from collections.abc import Callable

from reactivex import Observable
from reactivex.disposable import Disposable

type Operator[T, U] = Callable[[Observable[T]], Observable[U]]


def disposer[T](task: Task[T]) -> Disposable:
    def dispose() -> None:
        if task.cancel():
            # TODO log task was succesfully cancelled
            pass
        else:
            # TODO warn task is no longer running
            pass

    return Disposable(dispose)
