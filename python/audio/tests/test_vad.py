"""Tests for VAD gate operator."""

from typing import Any
from unittest.mock import Mock

import numpy as np
import reactivex as rx
from reactivex.testing.marbles import marbles_testing

from audio.config import TunableVad
from audio.types import AudioChunk
from audio.vad import vad_gate, while_speaking

type Lookup = dict[str | float, Any]

INSTANT = TunableVad(attack=1.0, decay=1.0, start=0.6, stop=0.3)
SLOW_DECAY = TunableVad(attack=1.0, decay=0.5, start=0.6, stop=0.3)


def arr(*values: float) -> AudioChunk:
    return np.array(values, dtype=np.float32)


def mock_vad(probs: dict[float, float]) -> Mock:
    """Create a mock VAD model that returns probability based on first sample value."""

    def side_effect(chunk: AudioChunk) -> float:
        key = round(float(chunk[0]), 1)
        return probs.get(key, 0.0)

    return Mock(side_effect=side_effect)


def test_while_speaking_is_silent() -> None:
    """Silence filtered and completion happens"""
    with marbles_testing() as (start, cold, _hot, exp):
        tune = TunableVad(start=0.5, stop=0.5)
        lookup: Lookup = {"a": 0.4}
        src = cold("  -a-a-a-a|", lookup)  # type: ignore[call-arg]
        expect = exp("--------|", lookup)  # type: ignore[call-arg]
        result = start(src.pipe(while_speaking(rx.of(tune))))
        assert result == expect


def test_while_speaking_starts_and_stops() -> None:
    """Silence filtered some values start and then stops with completion"""
    with marbles_testing() as (start, cold, _hot, exp):
        lookup: Lookup = {"a": 0.0, "b": 0.1, "c": 0.2, "d": 0.3, "e": 0.4, "f": 0.5, "g": 0.6}
        tune = cold(" t", {"t": TunableVad(start=0.5, stop=0.2)})  # type: ignore[call-arg]
        src = cold("  a-b-c-d-e-f-g-f-e-d-c-b-a  ", lookup)  # type: ignore[call-arg]
        expect = exp("----------f-g-f-e-d-(c,|)", lookup)  # type: ignore[call-arg]
        result = start(src.pipe(while_speaking(tune)))
        assert result == expect


def test_vad_gate_filters_silence_emits_speech() -> None:
    """Silence filtered, speech emitted, completes on speech stop."""
    with marbles_testing() as (start, cold, _hot, exp):
        model = mock_vad({0.9: 0.9, 0.1: 0.1})
        silence = arr(0.1, 0.1)
        speech = arr(0.9, 0.9)

        lookup_in: Lookup = {"a": silence, "b": speech, "c": speech, "d": silence}
        lookup_out: Lookup = {"x": speech, "y": speech, "z": silence}

        source = cold("-a-b-c-d-|", lookup_in)  # type: ignore[call-arg]
        expected = exp("---x-y-(z,|)", lookup_out)  # type: ignore[call-arg]

        result = start(source.pipe(vad_gate(model, rx.of(INSTANT))))
        assert result == expected


def test_vad_gate_slow_decay_delays_stop() -> None:
    """Slow decay keeps speaking through brief silence."""
    with marbles_testing() as (start, cold, _hot, exp):
        # decay=0.5: avg drops slowly
        # speech(0.9) -> avg=0.9, speaking
        # silence(0.1) -> avg=0.5*0.1 + 0.5*0.9 = 0.5, still > stop(0.3)
        # silence(0.1) -> avg=0.5*0.1 + 0.5*0.5 = 0.3, at threshold
        # silence(0.1) -> avg=0.5*0.1 + 0.5*0.3 = 0.2, < stop, completes
        model = mock_vad({0.9: 0.9, 0.1: 0.1})
        speech = arr(0.9, 0.9)
        silence = arr(0.1, 0.1)

        lookup_in: Lookup = {"a": speech, "b": silence, "c": silence, "d": silence}

        source = cold("-a-b-c-d-|", lookup_in)  # type: ignore[call-arg]
        expected = exp("-a-b-c-(d,|)", lookup_in)  # type: ignore[call-arg]

        result = start(source.pipe(vad_gate(model, rx.of(SLOW_DECAY))))
        assert result == expected


def test_vad_gate_completes_on_source_complete() -> None:
    """Completes normally if source completes while speaking."""
    with marbles_testing() as (start, cold, _hot, exp):
        model = mock_vad({0.9: 0.9})
        speech = arr(0.9, 0.9)
        lookup: Lookup = {"a": speech}

        source = cold("-a-a-|", lookup)  # type: ignore[call-arg]
        expected = exp("-a-a-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(vad_gate(model, rx.of(INSTANT))))
        assert result == expected


def test_vad_gate_empty_source() -> None:
    """Empty source completes without emission."""
    with marbles_testing() as (start, cold, _hot, exp):
        model = mock_vad({})

        source = cold("-|", None)  # type: ignore[call-arg]
        expected = exp("-|", None)  # type: ignore[call-arg]

        result = start(source.pipe(vad_gate(model, rx.of(INSTANT))))
        assert result == expected


def test_vad_gate_all_silence() -> None:
    """All silence emits nothing."""
    with marbles_testing() as (start, cold, _hot, exp):
        model = mock_vad({0.1: 0.1})
        silence = arr(0.1, 0.1)
        lookup: Lookup = {"a": silence}

        source = cold("-a-a-a-|", lookup)  # type: ignore[call-arg]
        expected = exp("-------|", None)  # type: ignore[call-arg]

        result = start(source.pipe(vad_gate(model, rx.of(INSTANT))))
        assert result == expected
