"""Tests for switch_resource."""

from typing import Any
from unittest.mock import Mock

import reactivex as rx
from reactivex.testing import ReactiveTest, TestScheduler
from reactivex.testing.marbles import marbles_testing
from reactivex.testing.subscription import Subscription

from streams.switch_resource import switch_resource

on_next = ReactiveTest.on_next
on_completed = ReactiveTest.on_completed

type Lookup = dict[str | float, Any]


def test_close_called_on_complete() -> None:
    """Resource.close() is called when observable completes."""
    resource = Mock()

    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"r": resource, "a": 1, "b": 2}

        resources = cold("-r-|", lookup)  # type: ignore[call-arg]
        inner = cold("a-b-|", lookup)  # type: ignore[call-arg]
        expected = exp("-a-b-|", lookup)  # type: ignore[call-arg]

        result = start(resources.pipe(switch_resource(lambda _: inner)))
        assert result == expected

    resource.close.assert_called_once()


def test_close_called_on_error() -> None:
    """Resource.close() is called and error propagates to subscriber."""
    resource = Mock()

    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"r": resource, "a": 1}

        resources = cold("-r-|", lookup)  # type: ignore[call-arg]
        inner = cold("a-#", lookup)  # type: ignore[call-arg]
        expected = exp("-a-#", lookup)  # type: ignore[call-arg]

        result = start(resources.pipe(switch_resource(lambda _: inner)))
        assert result == expected

    resource.close.assert_called_once()


def test_subscriber_receives_on_complete() -> None:
    """Subscriber receives all values and completion."""
    resource = Mock()

    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"r": resource, "a": 1, "b": 2, "c": 3}

        resources = cold("-r-|", lookup)  # type: ignore[call-arg]
        inner = cold("a-b-c-|", lookup)  # type: ignore[call-arg]
        expected = exp("-a-b-c-|", lookup)  # type: ignore[call-arg]

        result = start(resources.pipe(switch_resource(lambda _: inner)))
        assert result == expected

    resource.close.assert_called_once()


def test_close_called_on_switch() -> None:
    """Previous resource.close() is called when new resource arrives."""
    resource1 = Mock()
    resource2 = Mock()

    with marbles_testing() as (start, cold, _hot, _exp):
        lookup: Lookup = {"r": resource1, "s": resource2, "a": 1}

        # r emits, then s emits (switching), then completes
        resources = cold("-r-s-|", lookup)  # type: ignore[call-arg]

        def make_inner(_: Mock) -> rx.Observable[int]:
            return cold("a-a-a-|", lookup)  # type: ignore[call-arg]

        start(resources.pipe(switch_resource(make_inner)))

    # Both resources should be closed: r on switch, s on complete
    resource1.close.assert_called_once()
    resource2.close.assert_called_once()


def test_close_called_on_dispose() -> None:
    """Resource.close() is called when subscriber disposes (unsubscribes).

    Uses TestScheduler to verify subscription timing - marbles don't support
    subscription/unsubscription syntax (unlike RxJS ^ and !).
    """
    resource = Mock()
    scheduler = TestScheduler()

    # Hot observable: resource at 210, values at 220, 230, 240...
    resources = scheduler.create_hot_observable(
        on_next(210, resource),
    )

    # Inner emits continuously (never completes on its own)
    inner = scheduler.create_cold_observable(
        on_next(10, "a"),
        on_next(20, "b"),
        on_next(30, "c"),
        on_next(40, "d"),
    )

    # scheduler.start subscribes at 200, disposes at 300 by default
    # So we'll receive: resource at 210, then inner starts, emitting a,b,c
    # Dispose at 300 should trigger close()
    results = scheduler.start(
        lambda: resources.pipe(switch_resource(lambda _: inner)),
        disposed=250,  # Dispose early to test unsubscribe cleanup
    )

    # Verify we received values before disposal (inner starts at 210)
    # Inner emits at 210+10=220, 210+20=230, 210+30=240
    assert results.messages == [
        on_next(220, "a"),
        on_next(230, "b"),
        on_next(240, "c"),
    ]

    # Verify subscription window: subscribed at 200, disposed at 250
    assert resources.subscriptions == [Subscription(200, 250)]

    # Key assertion: close() called on dispose (unsubscribe)
    resource.close.assert_called_once()
