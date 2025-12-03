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


@dataclass
class Bird:
    name: str


def test_filter_instance_cat() -> None:
    """Filters to only Cat instances from mixed stream."""
    with marbles_testing() as (start, cold, _hot, exp):
        cat = Cat(name="whiskers")
        dog = Dog(name="rover")
        bird = Bird(name="tweety")

        lookup: Lookup = {"a": cat, "b": dog, "c": bird, "x": cat}

        source = cold("-a-b-c-|", lookup)  # type: ignore[call-arg]
        expected = exp("-x-----|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(filter_instance(Cat)))
        assert result == expected


def test_filter_instance_dog() -> None:
    """Filters to only Dog instances from mixed stream."""
    with marbles_testing() as (start, cold, _hot, exp):
        cat = Cat(name="whiskers")
        dog = Dog(name="rover")
        bird = Bird(name="tweety")

        lookup: Lookup = {"a": cat, "b": dog, "c": bird, "x": dog}

        source = cold("-a-b-c-|", lookup)  # type: ignore[call-arg]
        expected = exp("---x---|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(filter_instance(Dog)))
        assert result == expected


def test_filter_instance_bird() -> None:
    """Filters to only Bird instances from mixed stream."""
    with marbles_testing() as (start, cold, _hot, exp):
        cat = Cat(name="whiskers")
        dog = Dog(name="rover")
        bird = Bird(name="tweety")

        lookup: Lookup = {"a": cat, "b": dog, "c": bird, "x": bird}

        source = cold("-a-b-c-|", lookup)  # type: ignore[call-arg]
        expected = exp("-----x-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(filter_instance(Bird)))
        assert result == expected
