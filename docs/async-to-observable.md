# Async-to-Observable Integration in RxPY

## Core Wrapper Design

`from_async` converts async functions into cold Observables that emit once and
complete.

```python
def from_async(
    coro_fn: Callable[..., Awaitable[T]],
    *args,
    scheduler: AsyncIOScheduler | None = None,
    **kwargs,
) -> Observable[T]:
```

Other strategies for calling async wrapper

- use partial from stdlib (similar to js bind)
  - `from_async(partial(fetch_data, url, timeout=30)`
  - fetch data positional args are loaded with url and timeout=30
- use lamda
  - `from_async(lambda: fetch_data(url, timeout=30))`

Use lambda for inline usage, partial when storing/passing the bound function
around.

## Centralized Cancellation Handling

The wrapper handles cancellation so coroutines don't need boilerplate:

```python
async def run():
    try:
        result = await coro_fn(*args, **kwargs)
        observer.on_next(result)
        observer.on_completed()
    except asyncio.CancelledError as e:
        observer.on_error(e)  # Propagate to subscriber (e.g., FastAPI route)
    except Exception as e:
        observer.on_error(e)
```

- `CancelledError` propagates as `on_error` so FastAPI can map it to HTTP 499
- Coroutines using `async with` auto-cleanup via `__aexit__`
- FastAPI exception handlers remove route boilerplate for error→HTTP mapping

## Scheduler Injection for Testability

Accept optional scheduler param instead of grabbing the event loop directly.
Enables deterministic unit tests with fake/test schedulers.

## Unit Test Strategy: Fake Async

No `pytest-asyncio` needed - use pre-resolved futures:

```python
def make_resolved_future(value):
    future = asyncio.Future()
    future.set_result(value)
    return future


def test_from_async_emits_result():
    with patch("mymodule.fetch_data") as mock_fetch:
        mock_fetch.return_value = make_resolved_future({"data": "test"})

        results = []
        from_async(mock_fetch, "url").subscribe(on_next=results.append)

        assert results == [{"data": "test"}]
```

For errors: `future.set_exception(ValueError("boom"))`

## Cold vs Shared Observables

- **Default (cold)**: New task per subscription
- **Shared execution**: Wrap with `pipe(operators.share())` for multiple
  subscribers to share one task

## Testing Tiers

- **Unit tests**: Fake async with resolved futures, deterministic
- **Integration tests**: Real async with `pytest-asyncio`

## RxPY Marble Testing Limitation

Marble syntax cannot test subscriptions. For subscription timing/lifecycle
tests, use verbose `TestScheduler` with manual `scheduler.create_observer()` and
`source.subscriptions` assertions.

## Lifecycle Management

Observable is lazy:

- **Not subscribed**: No task created, nothing to clean up
- **Subscribed**: Task running, cleanup via:
  - **Resolve with value** → `on_next` + `on_completed`, task completes
  - **Resolve with error** → `on_error`, task completes
  - **Explicit cancel** → dispose → `task.cancel()` → `CancelledError` →
    `on_error`

## Batch Operations

`from_async` handles both single values and batches - `list[T]` is just a `T`:

```python
from_async(lambda: fetch_one())             # Observable[Item]
from_async(lambda: list(AudioChunker(...))) # Observable[list[bytes]]
```

Use `flat_map` to emit batch items individually:

```python
from_async(lambda: list(chunker())).pipe(
    ops.flat_map(lambda items: rx.from_iterable(items))
)
```

## Concurrency Model

Sync work runs in thread pool via `loop.run_in_executor()`:

| Scale           | Approach             | Limitation              |
| --------------- | -------------------- | ----------------------- |
| Single user     | Thread per task      | None                    |
| Few concurrent  | Thread pool          | Pool size (~32 threads) |
| Many concurrent | Needs `pyo3-asyncio` | Thread exhaustion       |

Event loop stays responsive. Multiple batches run concurrently (one thread
each).

## True Streaming (Future)

Current `from_async` emits once per subscription. True streaming (emit per chunk
as produced) requires:

- Rust async runtime (`tokio`) + `pyo3-asyncio`, or
- Python `AsyncIterator` (`__anext__`)

Future API when needed:

```python
from_async_stream(async_iterator_fn)  # Observable[T] - multiple emissions
```

## Native python .pyi type generation

We manually create the type files for our pyo3 audio binding. Should these
bindings type grow in number, evaluate `pyo3-stub-gen`
