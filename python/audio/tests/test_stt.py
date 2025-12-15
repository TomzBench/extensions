"""Tests for recorder speech-to-text pipeline."""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from unittest.mock import Mock

import numpy as np
import reactivex as rx
from reactivex import Observable
from reactivex.testing.marbles import MarblesContext, marbles_testing

from audio.config import AppConfig, TunableVad, TunableWhisperModel
from audio.source import AudioSource
from audio.stt import RecorderDependencies, recorder
from audio.types import AudioChunk, DeviceMeta

type Lookup = dict[str | float, Any]

# attack=1, decay=1 means avg = prob (no smoothing)
# start=0.5, stop=0.5 means speech when prob > 0.5, silence when prob < 0.5
INSTANT_VAD = TunableVad(attack=1.0, decay=1.0, start=0.5, stop=0.5)


def chunk(value: float, size: int = 512) -> AudioChunk:
    """Create audio chunk filled with value (first sample used by mock VAD)."""
    return np.full(size, value, dtype=np.float32)


def mock_vad(probs: dict[float, float]) -> Mock:
    """VAD that returns probability based on first sample value."""

    def side_effect(c: AudioChunk) -> float:
        key = round(float(c[0]), 1)
        return probs.get(key, 0.0)

    return Mock(side_effect=side_effect)


def mock_transcriber(text: str) -> Mock:
    """Transcriber that always returns the given text."""
    transcriber = Mock()
    transcriber.transcribe = Mock(return_value=rx.of(text))
    transcriber.close = Mock()
    return transcriber


def mock_device_meta(name: str = "test") -> DeviceMeta:
    """Create DeviceMeta with sensible defaults for testing."""
    return {
        "name": name,
        "index": 0,
        "hostapi": 0,
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_low_input_latency": 0.0,
        "default_low_output_latency": 0.0,
        "default_high_input_latency": 0.0,
        "default_high_output_latency": 0.0,
        "default_samplerate": 16000.0,
    }


def make_audio_source(name: str, stream: Observable[AudioChunk]) -> AudioSource:
    """Create AudioSource with mock metadata."""
    return AudioSource(device_id=0, device_name=name, meta=mock_device_meta(), stream=stream)


@dataclass
class AudioContext:
    marbles: MarblesContext
    source: Any
    tunables: Any
    expected: Any


@contextmanager
def audio_testing(
    source: str,
    audio: str,
    tune: str,
    exp: str,
) -> Generator[AudioContext, None, None]:
    with marbles_testing() as marbles_context:
        # 0.0 = silence (prob 0), 1.0 = speech (prob 1)
        silence = chunk(0.0)
        speech = chunk(1.0)

        (start, cold, hot, expected) = marbles_context
        # TODO for each "audio source" - there is an "audio stream". Therefore source should take an
        # array audio observables
        a = cold(audio, {"s": silence, "h": speech})  # type: ignore[call-arg]
        s = cold(source, {"a": make_audio_source("t1", a)})  # type: ignore[call-arg]
        t = cold(tune, {"v": INSTANT_VAD, "w": TunableWhisperModel()})  # type: ignore[call-arg]
        e = expected(exp, {"h": "hello"})  # type: ignore[call-arg]
        try:
            yield AudioContext(
                marbles=MarblesContext(start, cold, hot, expected),
                source=s,
                tunables=t,
                expected=e,
            )
        finally:
            pass


def test_recorder_transcribes_single_utterance() -> None:
    """Single utterance 'hello': silence -> speech -> silence -> 'hello'."""
    with audio_testing(
        source="a----|",  # TODO a-----b-----c----
        audio=" s-h-s|",  #      s-h-s------------ # every h has an utterance
        #                              s-h-s------ # every h has an utterance
        #                                    s-h-s # every h has an utterance
        tune="  (vw)|",
        exp="   ----h|",
    ) as test:
        (start, _cold, _hot, _exp) = test.marbles
        source = test.source
        tunables = test.tunables
        expected = test.expected
        # 0.0 = silence (prob 0), 1.0 = speech (prob 1)
        #   silence = chunk(0.0)
        #   speech = chunk(1.0)

        #   audio_lookup: Lookup = {"s": silence, "h": speech}
        #   audio = cold("s-h-s|", audio_lookup)  # type: ignore[call-arg]

        #   # Audio stream: silence, speech, silence (ends utterance)

        #   # Source emits AudioSource then completes - drives pipeline lifecycle
        #   source_lookup: Lookup = {"a": make_audio_source("t1", audio)}
        #   source = cold("a----|", source_lookup)  # type: ignore[call-arg]

        #   # Tunables: VAD config and whisper model (both needed to start pipeline)
        #   tunable_lookup: Lookup = {"v": INSTANT_VAD, "w": TunableWhisperModel()}
        #   tunables = cold("(vw)|", tunable_lookup)  # type: ignore[call-arg]

        # Expected: "hello" emitted when utterance ends, complete when source completes
        # expected = exp("----h|", {"h": "hello"})  # type: ignore[call-arg]

        cfg = AppConfig(vad_options=INSTANT_VAD)
        # NOTE our MockTranscribers are not injected correctly, we either need recorder to be
        # injectd w/ a TranscriberFactor. Or we need TunableWhisperModels to be transcribers
        transcriber = mock_transcriber("hello")
        vad = mock_vad({0.0: 0.0, 1.0: 1.0})
        deps = RecorderDependencies(vad=lambda: vad, whisper=transcriber)

        result = start(tunables.pipe(recorder(source, cfg, deps)))
        assert result == expected
