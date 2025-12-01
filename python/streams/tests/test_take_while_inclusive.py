"""Tests for take_while_inclusive operator."""

from typing import Any

from reactivex.testing.marbles import marbles_testing

from streams import take_while_inclusive

type Lookup = dict[str | float, Any]


def test_take_while_inclusive_includes_failing_element() -> None:
    """Emits elements while predicate true, plus first failing element."""
    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"a": 1, "b": 2, "c": 3, "d": 4}

        source = cold("-a-b-c-d-|", lookup)  # type: ignore[call-arg]
        expected = exp("-a-b-(c,|)", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(take_while_inclusive(lambda x: x < 3)))  # type: ignore[operator]
        assert result == expected


def test_take_while_inclusive_all_pass() -> None:
    """All elements pass, completes with source."""
    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"a": 1, "b": 2}

        source = cold("-a-b-|", lookup)  # type: ignore[call-arg]
        expected = exp("-a-b-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(take_while_inclusive(lambda x: x < 10)))  # type: ignore[operator]
        assert result == expected


def test_take_while_inclusive_first_fails() -> None:
    """First element fails, emits it and completes."""
    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"a": 5}

        source = cold("-a-b-|", lookup)  # type: ignore[call-arg]
        expected = exp("-(a,|)", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(take_while_inclusive(lambda x: x < 3)))  # type: ignore[operator]
        assert result == expected
