"""Tests for VAD gate operator."""

from typing import Any

import numpy as np
import reactivex as rx
from reactivex.testing.marbles import marbles_testing

from audio.config import TunableVad
from audio.types import AudioChunk
from audio.vad import vad_gate

type Lookup = dict[str | float, Any]

INSTANT = TunableVad(attack=1.0, decay=1.0, start=0.6, stop=0.3)
SLOW_DECAY = TunableVad(attack=1.0, decay=0.5, start=0.6, stop=0.3)


def arr(*values: float) -> AudioChunk:
    return np.array(values, dtype=np.float32)


class MockVADModel:
    """Returns probability based on first sample value (rounded)."""

    def __init__(self, probs: dict[float, float]) -> None:
        self._probs = probs

    def __call__(self, chunk: AudioChunk) -> float:
        key = round(float(chunk[0]), 1)
        return self._probs.get(key, 0.0)


def test_vad_gate_filters_silence_emits_speech() -> None:
    """Silence filtered, speech emitted, completes on speech stop."""
    with marbles_testing() as (start, cold, _hot, exp):
        model = MockVADModel({0.9: 0.9, 0.1: 0.1})
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
        model = MockVADModel({0.9: 0.9, 0.1: 0.1})
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
        model = MockVADModel({0.9: 0.9})
        speech = arr(0.9, 0.9)
        lookup: Lookup = {"a": speech}

        source = cold("-a-a-|", lookup)  # type: ignore[call-arg]
        expected = exp("-a-a-|", lookup)  # type: ignore[call-arg]

        result = start(source.pipe(vad_gate(model, rx.of(INSTANT))))
        assert result == expected


def test_vad_gate_empty_source() -> None:
    """Empty source completes without emission."""
    with marbles_testing() as (start, cold, _hot, exp):
        model = MockVADModel({})

        source = cold("-|", None)  # type: ignore[call-arg]
        expected = exp("-|", None)  # type: ignore[call-arg]

        result = start(source.pipe(vad_gate(model, rx.of(INSTANT))))
        assert result == expected


def test_vad_gate_all_silence() -> None:
    """All silence emits nothing."""
    with marbles_testing() as (start, cold, _hot, exp):
        model = MockVADModel({0.1: 0.1})
        silence = arr(0.1, 0.1)
        lookup: Lookup = {"a": silence}

        source = cold("-a-a-a-|", lookup)  # type: ignore[call-arg]
        expected = exp("-------|", None)  # type: ignore[call-arg]

        result = start(source.pipe(vad_gate(model, rx.of(INSTANT))))
        assert result == expected
