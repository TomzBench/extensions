"""Tests for rechunk operator using marble testing."""

from typing import Any

import numpy as np
from reactivex.testing.marbles import marbles_testing

from audio.rechunk import rechunk
from audio.types import AudioChunk

type Lookup = dict[str | float, Any]


def arr(*values: float) -> AudioChunk:
    """Helper to create float32 arrays."""
    return np.array(values, dtype=np.float32)


def test_rechunk_exact_fit() -> None:
    """Test rechunk with input that divides evenly into chunk_size."""
    with marbles_testing() as (start, cold, _hot, exp):
        # 2 samples per emission, chunk_size=4, so 2 emissions = 1 output chunk
        # Source: -a-b-c-(d,|)  (a@1, b@3, c@5, d,complete@7)
        # Output emits when buffer fills: x@3 (after b), y@7 (after d)
        a = arr(1.0, 2.0)
        b = arr(3.0, 4.0)
        c = arr(5.0, 6.0)
        d = arr(7.0, 8.0)
        out1 = arr(1.0, 2.0, 3.0, 4.0)
        out2 = arr(5.0, 6.0, 7.0, 8.0)

        lookup: Lookup = {"a": a, "b": b, "c": c, "d": d, "x": out1, "y": out2}

        # rx marbles has broken type annotations (args appear required but have defaults)
        source = cold("-a-b-c-(d,|)", lookup)  # type: ignore[call-arg]
        expected = exp("---x---(y,|)", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(rechunk(chunk_size=4)))
        assert result == expected


def test_rechunk_with_remainder() -> None:
    """Test rechunk with remainder that gets zero-padded on completion."""
    with marbles_testing() as (start, cold, _hot, exp):
        # 2 samples per emission, chunk_size=4
        # 3 emissions = 6 samples = 1 full chunk (4) + 2 remainder -> padded
        # Source: -a-b-c-|  (a@1, b@3, c@5, complete@7)
        # Output: x@3, (y,|)@7 - flush and complete are simultaneous
        a = arr(1.0, 2.0)
        b = arr(3.0, 4.0)
        c = arr(5.0, 6.0)
        out1 = arr(1.0, 2.0, 3.0, 4.0)
        out2 = arr(5.0, 6.0, 0.0, 0.0)  # zero-padded tail

        lookup: Lookup = {"a": a, "b": b, "c": c, "x": out1, "y": out2}

        source = cold("-a-b-c-|", lookup)  # type: ignore[call-arg]
        expected = exp("---x---(y,|)", lookup)  # type: ignore[call-arg]
        result = start(source.pipe(rechunk(chunk_size=4)))
        assert result == expected


def test_rechunk_all_remainder() -> None:
    """Test rechunk when all input is smaller than chunk_size."""
    with marbles_testing() as (start, cold, _hot, exp):
        # Source: -a-|  (a@1, complete@3)
        # Output: (x,|)@3 - flush and complete are simultaneous
        a = arr(1.0, 2.0)
        out = arr(1.0, 2.0, 0.0, 0.0)  # zero-padded

        lookup: Lookup = {"a": a, "x": out}

        source = cold("-a-|", lookup)  # type: ignore[call-arg]
        expected = exp("---(x,|)", lookup)  # type: ignore[call-arg]
        result = start(source.pipe(rechunk(chunk_size=4)))
        assert result == expected


def test_rechunk_empty() -> None:
    """Test rechunk with empty source emits nothing."""
    with marbles_testing() as (start, cold, _hot, exp):
        source = cold("-|", None)  # type: ignore[call-arg]
        expected = exp("-|", None)  # type: ignore[call-arg]

        result = start(source.pipe(rechunk(chunk_size=4)))
        assert result == expected
