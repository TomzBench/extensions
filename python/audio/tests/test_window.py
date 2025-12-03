"""Tests for window_chunks operator."""

from dataclasses import dataclass
from typing import Any, Self

import numpy as np
import reactivex.operators as ops
from reactivex import Observable
from reactivex.testing.marbles import marbles_testing
from streams.utils import Operator

from audio.window import window_chunks

type Lookup = dict[str | float, Any]


def chunk(value: float = 0.0, size: int = 512) -> np.ndarray:
    """Create a chunk filled with value."""
    return np.full(size, value, dtype=np.float32)


@dataclass
class Window:
    """Wrapper for comparing numpy array windows in marble tests."""

    segments: list[tuple[float, int]]  # [(value, count), ...]
    size: int

    @classmethod
    def from_array(cls, arr: np.ndarray) -> Self:
        """Wrap a numpy array for comparison."""
        return cls(_detect_segments(arr), len(arr))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Window):
            return False
        return self.segments == other.segments and self.size == other.size


def _detect_segments(arr: np.ndarray) -> list[tuple[float, int]]:
    """Detect contiguous segments of equal values in array."""
    if len(arr) == 0:
        return []
    segments: list[tuple[float, int]] = []
    current_val = float(arr[0])
    count = 1
    for val in arr[1:]:
        if np.isclose(val, current_val):
            count += 1
        else:
            segments.append((current_val, count))
            current_val = float(val)
            count = 1
    segments.append((current_val, count))
    return segments


def make_uut(
    chunk_size: int, window_size: int, emit_interval: int
) -> Operator[np.ndarray, Window]:
    """Build window_chunks pipeline with Window wrapper for testing."""
    def _operator(source: Observable[np.ndarray]) -> Observable[Window]:
        return source.pipe(
            window_chunks(chunk_size, window_size, emit_interval),
            ops.map(Window.from_array),
        )
    return _operator


def test_window_chunks_accumulates_and_emits() -> None:
    """Accumulates chunks and emits padded window at emit_interval."""
    with marbles_testing() as (start, cold, _hot, exp):
        c1, c2 = chunk(1.0), chunk(2.0)
        w1 = Window([(1.0, 512), (2.0, 512), (0.0, 1024)], 2048)
        lookup: Lookup = {"a": c1, "b": c2, "x": w1}

        source = cold("-a-b-|", lookup)  # type: ignore[call-arg]
        expected = exp("---x-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(make_uut(512, 2048, 1024)))
        assert result == expected


def test_window_chunks_emits_on_complete() -> None:
    """Emits partial window on source completion."""
    with marbles_testing() as (start, cold, _hot, exp):
        c1, c2, c3 = chunk(1.0), chunk(2.0), chunk(3.0)
        w1 = Window([(1.0, 512), (2.0, 512), (0.0, 1024)], 2048)
        w2 = Window([(1.0, 512), (2.0, 512), (3.0, 512), (0.0, 512)], 2048)
        lookup: Lookup = {"a": c1, "b": c2, "c": c3, "x": w1, "y": w2}

        source = cold("-a-b-c-|", lookup)  # type: ignore[call-arg]
        expected = exp("---x---(y,|)", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(make_uut(512, 2048, 1024)))
        assert result == expected


def test_window_chunks_slides_at_max_capacity() -> None:
    """Old chunks are dropped when window reaches max capacity."""
    with marbles_testing() as (start, cold, _hot, exp):
        c1, c2, c3, c4 = chunk(1.0), chunk(2.0), chunk(3.0), chunk(4.0)
        w1 = Window([(1.0, 512), (2.0, 512)], 1024)
        w2 = Window([(3.0, 512), (4.0, 512)], 1024)
        lookup: Lookup = {"a": c1, "b": c2, "c": c3, "d": c4, "x": w1, "y": w2}

        source = cold("-a-b-c-d-|", lookup)  # type: ignore[call-arg]
        expected = exp("---x---y-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(make_uut(512, 1024, 1024)))
        assert result == expected
