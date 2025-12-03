"""Tests for filter_instance_start_with operator."""

from dataclasses import dataclass
from typing import Any

from reactivex.testing.marbles import marbles_testing

from streams.filter_instance_start_with import filter_instance_start_with

type Lookup = dict[str | float, Any]


@dataclass
class Cat:
    name: str


@dataclass
class Dog:
    name: str


def test_filter_instance_start_with_emits_default_then_filters() -> None:
    """Emits default immediately, then filters to matching instances."""
    with marbles_testing() as (start, cold, _hot, exp):
        default_cat = Cat(name="default")
        other_cat = Cat(name="other")
        dog = Dog(name="rover")

        lookup: Lookup = {"d": default_cat, "a": dog, "b": other_cat, "x": other_cat}

        source = cold("-a-b-|", lookup)  # type: ignore[call-arg]
        expected = exp("d--x-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(filter_instance_start_with(default_cat)))
        assert result == expected
