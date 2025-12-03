"""Tests for filter_instance operator."""

from dataclasses import dataclass
from typing import Any

from reactivex.testing.marbles import marbles_testing

from streams.filter_instance import filter_instance

type Lookup = dict[str | float, Any]


@dataclass
class Cat:
    name: str


@dataclass
class Dog:
    name: str


def test_filter_instance_filters_to_matching_type() -> None:
    """Filters to only instances matching the given type."""
    with marbles_testing() as (start, cold, _hot, exp):
        cat = Cat(name="whiskers")
        dog = Dog(name="rover")

        lookup: Lookup = {"a": cat, "b": dog, "c": cat, "x": cat, "y": cat}

        source = cold("-a-b-c-|", lookup)  # type: ignore[call-arg]
        expected = exp("-x---y-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(filter_instance(Cat)))
        assert result == expected
