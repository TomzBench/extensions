# RxPY Testing Cheat Sheet

## Marble Testing

```python
from reactivex.testing.marbles import marbles_testing

with marbles_testing() as (start, cold, hot, exp):
    source = cold("--a-b-c-|")
    expected = exp("--a-b-c-|")
    result = start(source)
    assert result == expected
```

| Symbol | Meaning                                         |
| ------ | ----------------------------------------------- |
| `-`    | Time frame (10 ticks)                           |
| `a-z`  | Value emission (use lookup dict for non-string) |
| `\|`   | Completion                                      |
| `#`    | Error                                           |
| `()`   | Simultaneous events                             |

### Marble Lookup

```python
lookup = {"a": 1, "b": MyObject()}
source = cold("--a-b-|", lookup)
```

### Limitation

Marbles **do not support subscription/unsubscription syntax** (unlike RxJS `^`
and `!`).

---

## TestScheduler

Use when you need to test subscription timing, disposal, or resource cleanup.

```python
from reactivex.testing import ReactiveTest, TestScheduler
from reactivex.testing.subscription import Subscription

on_next = ReactiveTest.on_next
on_completed = ReactiveTest.on_completed
on_error = ReactiveTest.on_error
```

### Default Timing Constants

| Constant     | Default | Meaning                   |
| ------------ | ------- | ------------------------- |
| `created`    | 100     | Observable factory called |
| `subscribed` | 200     | Subscription happens      |
| `disposed`   | 1000    | Disposal happens          |

Access via `ReactiveTest.created`, `ReactiveTest.subscribed`,
`ReactiveTest.disposed`.

### Basic Usage

```python
def test_example():
    scheduler = TestScheduler()

    source = scheduler.create_hot_observable(
        on_next(210, "a"),
        on_next(220, "b"),
        on_completed(230),
    )

    results = scheduler.start(lambda: source.pipe(...))

    assert results.messages == [
        on_next(210, "a"),
        on_next(220, "b"),
        on_completed(230),
    ]
```

### Override Timing

```python
scheduler.start(
    create_fn,
    created=50,
    subscribed=100,
    disposed=250,
)
```

---

## Hot vs Cold Observables

| Type | Timing                   | Use Case                                                   |
| ---- | ------------------------ | ---------------------------------------------------------- |
| Hot  | Absolute times           | Shared source, emissions happen regardless of subscription |
| Cold | Relative to subscription | Each subscriber gets fresh sequence                        |

```python
# Hot: emits at t=210, t=220 (absolute)
hot = scheduler.create_hot_observable(
    on_next(210, "a"),
    on_next(220, "b"),
)

# Cold: emits at subscribe+10, subscribe+20 (relative)
cold = scheduler.create_cold_observable(
    on_next(10, "a"),
    on_next(20, "b"),
)
```

---

## Testing Subscriptions

### Verify Subscription Window

```python
source = scheduler.create_hot_observable(on_next(210, "a"))

results = scheduler.start(
    lambda: source.pipe(...),
    disposed=250,
)

# Subscribed at 200 (default), disposed at 250
assert source.subscriptions == [Subscription(200, 250)]
```

### Infinite Subscription

```python
# Subscription(200) with no end = infinite (never disposed)
assert source.subscriptions == [Subscription(200)]
```

---

## Testing Disposal/Cleanup

```python
def test_close_called_on_dispose():
    resource = Mock()
    scheduler = TestScheduler()

    resources = scheduler.create_hot_observable(
        on_next(210, resource),
    )

    inner = scheduler.create_cold_observable(
        on_next(10, "a"),
        on_next(20, "b"),
    )

    results = scheduler.start(
        lambda: resources.pipe(switch_resource(lambda _: inner)),
        disposed=250,
    )

    # Verify subscription timing
    assert resources.subscriptions == [Subscription(200, 250)]

    # Verify cleanup on dispose
    resource.close.assert_called_once()
```

---

## Multiple Subscriptions

`scheduler.start()` only supports single subscription. For multiple:

```python
def test_multiple_subscriptions():
    scheduler = TestScheduler()
    source = scheduler.create_cold_observable(on_next(10, "a"))

    subs = []
    shared = source.pipe(ops.share())

    # Schedule subscriptions manually
    scheduler.schedule_relative(200, lambda *_: subs.append(shared.subscribe()))
    scheduler.schedule_relative(300, lambda *_: subs.append(shared.subscribe()))

    # Schedule disposals
    scheduler.schedule_relative(500, lambda *_: subs[1].dispose())
    scheduler.schedule_relative(600, lambda *_: subs[0].dispose())

    scheduler.start()

    assert source.subscriptions == [Subscription(200, 600)]
```

---

## Quick Reference

```python
# Imports
from reactivex.testing import ReactiveTest, TestScheduler
from reactivex.testing.marbles import marbles_testing
from reactivex.testing.subscription import Subscription

on_next = ReactiveTest.on_next
on_completed = ReactiveTest.on_completed
on_error = ReactiveTest.on_error

# Marbles (simple emission testing)
with marbles_testing() as (start, cold, hot, exp):
    result = start(cold("--a-b-|"))

# TestScheduler (subscription/disposal testing)
scheduler = TestScheduler()
source = scheduler.create_hot_observable(on_next(210, "x"))
results = scheduler.start(lambda: source, disposed=300)
assert source.subscriptions == [Subscription(200, 300)]
```
