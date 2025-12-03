"""Tests for switch_resource."""

from typing import Any
from unittest.mock import Mock

import reactivex as rx
from reactivex.testing.marbles import marbles_testing

from streams.switch_resource import switch_resource

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
