"""Tests for buffer_with_count_or_complete operator."""

from typing import Any

from reactivex.testing.marbles import marbles_testing

from streams import buffer_with_count_or_complete

type Lookup = dict[str | float, Any]


def test_buffer_emits_when_count_reached() -> None:
    """Emits buffer when count is reached."""
    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"a": 1, "b": 2, "c": 3, "d": 4, "x": [1, 2], "y": [3, 4]}

        source = cold("-a-b-c-d-|", lookup)  # type: ignore[call-arg]
        expected = exp("---x---y-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(buffer_with_count_or_complete(2)))
        assert result == expected


def test_buffer_emits_partial_on_complete() -> None:
    """Emits partial buffer on source completion."""
    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"a": 1, "b": 2, "c": 3, "x": [1, 2], "y": [3]}

        source = cold("-a-b-c-|", lookup)  # type: ignore[call-arg]
        expected = exp("---x---(y,|)", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(buffer_with_count_or_complete(2)))
        assert result == expected


def test_buffer_no_emit_on_empty_complete() -> None:
    """Does not emit empty buffer on completion."""
    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"a": 1, "b": 2, "x": [1, 2]}

        source = cold("-a-b-|", lookup)  # type: ignore[call-arg]
        expected = exp("---x-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(buffer_with_count_or_complete(2)))
        assert result == expected


def test_buffer_single_item_on_complete() -> None:
    """Single item emitted as partial buffer on complete."""
    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"a": 1, "x": [1]}

        source = cold("-a-|", lookup)  # type: ignore[call-arg]
        expected = exp("---(x,|)", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(buffer_with_count_or_complete(2)))
        assert result == expected
