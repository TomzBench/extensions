"""Voice activity detection operators for RxPy streams.

Example:
    from audio.rechunk import rechunk
    from audio.vad import vad_sentence
    from audio.silero import SileroVADModel

    model = SileroVADModel()
    mic_observable.pipe(
        rechunk(512),
        vad_sentence(model),
    ).subscribe(
        on_next=lambda chunk: buffer.append(chunk),
        on_completed=lambda: transcribe(concat(buffer)),
    )
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from reactivex import Observable
from reactivex import operators as ops
from streams import take_while_inclusive
from streams.utils import Operator

from audio.types import AudioChunk


class VADModel(Protocol):
    def __call__(self, chunk: AudioChunk) -> float: ...


@dataclass(frozen=True)
class VadOptions:
    """Configuration for VAD gate behavior.

    Attributes:
        attack: Smoothing factor for rising signal (higher = faster response to speech)
        decay: Smoothing factor for falling signal (lower = slower response to silence)
        start: Probability threshold to start speaking
        stop: Probability threshold to stop speaking
    """

    attack: float = 0.8
    decay: float = 0.3
    start: float = 0.6
    stop: float = 0.3


# Presets for common use cases
VAD_SENTENCE = VadOptions(attack=0.8, decay=0.3, start=0.6, stop=0.4)
VAD_PARAGRAPH = VadOptions(attack=0.8, decay=0.2, start=0.6, stop=0.3)
VAD_STORY = VadOptions(attack=0.8, decay=0.1, start=0.5, stop=0.2)


def _make_smoother(attack: float, decay: float) -> Callable[[float], float]:
    """Asymmetric EMA smoother."""
    avg = 0.0

    def update(prob: float) -> float:
        nonlocal avg
        alpha = attack if prob > avg else decay
        avg = alpha * prob + (1 - alpha) * avg
        return avg

    return update


def _make_hysteresis(start: float, stop: float) -> Callable[[float], bool]:
    """Stateful hysteresis function."""
    speaking = False

    def update(prob: float) -> bool:
        nonlocal speaking
        if not speaking and prob > start:
            speaking = True
        elif speaking and prob < stop:
            speaking = False
        return speaking

    return update


def vad_gate(
    model: VADModel,
    options: VadOptions = VAD_SENTENCE,
) -> Operator[AudioChunk, AudioChunk]:
    """Gate audio chunks through VAD with configurable options."""
    smoother = _make_smoother(options.attack, options.decay)
    trigger = _make_hysteresis(options.start, options.stop)

    def is_speaking(chunk: AudioChunk) -> bool:
        return trigger(smoother(float(model(chunk))))

    def _operator(source: Observable[AudioChunk]) -> Observable[AudioChunk]:
        return source.pipe(
            ops.skip_while(lambda c: not is_speaking(c)),  # type: ignore[arg-type]
            take_while_inclusive(is_speaking),
        )

    return _operator


def vad_sentence(model: VADModel) -> Operator[AudioChunk, AudioChunk]:
    """Short pause tolerance for sentence-level detection."""
    return vad_gate(model, VAD_SENTENCE)


def vad_paragraph(model: VADModel) -> Operator[AudioChunk, AudioChunk]:
    """Medium pause tolerance for paragraph-level detection."""
    return vad_gate(model, VAD_PARAGRAPH)


def vad_story(model: VADModel) -> Operator[AudioChunk, AudioChunk]:
    """Long pause tolerance for story/monologue detection."""
    return vad_gate(model, VAD_STORY)
