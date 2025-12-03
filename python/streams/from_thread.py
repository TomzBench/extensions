"""Thread-pool-to-Observable bridge for RxPy (no asyncio)."""

from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor

import reactivex
from reactivex import Observable
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase
from reactivex.disposable import Disposable

# Module-level default executor (lazy init)
_default_executor: ThreadPoolExecutor | None = None


def _get_default_executor() -> ThreadPoolExecutor:
    global _default_executor
    if _default_executor is None:
        _default_executor = ThreadPoolExecutor(max_workers=4)
    return _default_executor


def from_thread[T](
    fn: Callable[[], T],
    executor: Executor | None = None,
) -> Observable[T]:
    """Run blocking callable in thread pool, emit result as Observable.

    Sync equivalent of from_async(). Runs fn() in executor, emits result.
    If executor is None, uses a module-level default ThreadPoolExecutor.
    """

    def subscribe(
        obs: ObserverBase[T],
        _scheduler: SchedulerBase | None = None,
    ) -> DisposableBase:
        def task() -> None:
            try:
                result = fn()
                obs.on_next(result)
                obs.on_completed()
            except Exception as e:
                obs.on_error(e)

        pool = executor or _get_default_executor()
        future = pool.submit(task)

        def dispose() -> None:
            future.cancel()

        return Disposable(dispose)

    return reactivex.create(subscribe)
