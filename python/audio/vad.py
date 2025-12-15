"""Voice activity detection operators for RxPy streams.

Example:
    from audio.rechunk import rechunk
    from audio.vad import vad_gate
    from audio.silero import SileroVADModel

    model = SileroVADModel()
    mic_observable.pipe(
        rechunk(512),
        vad_gate(model, config_observable),
    ).subscribe(
        on_next=lambda chunk: buffer.append(chunk),
        on_completed=lambda: transcribe(concat(buffer)),
    )
"""

from collections.abc import Callable
from typing import Protocol

from reactivex import Observable
from reactivex import operators as ops
from streams import take_while_inclusive
from streams.utils import Operator

from audio.config import TunableVad
from audio.types import AudioChunk


class VADModel(Protocol):
    def __call__(self, chunk: AudioChunk) -> float: ...


def while_speaking(tunable: Observable[TunableVad]) -> Operator[float, float]:
    def _operator(source: Observable[float]) -> Observable[float]:
        speaking = False

        def is_silent(pair: tuple[float, TunableVad]) -> bool:
            nonlocal speaking
            (avr, opts) = pair
            if not speaking and avr >= opts.start:
                speaking = True
            elif speaking and avr <= opts.stop:
                speaking = False
            return not speaking

        def is_speaking(pair: tuple[float, TunableVad]) -> bool:
            return not is_silent(pair)

        def get_prob(pair: tuple[float, TunableVad]) -> float:
            return pair[0]

        return source.pipe(
            ops.with_latest_from(tunable),
            ops.skip_while(is_silent),
            take_while_inclusive(is_speaking),
            ops.map(get_prob),
        )

    return _operator


def while_speaking_range(
    tunable: Observable[TunableVad],
) -> Callable[[Observable[float]], tuple[Observable[float], Observable[float]]]:
    """Return (start, stop) observables that emit first/last prob of utterance."""

    def _operator(source: Observable[float]) -> tuple[Observable[float], Observable[float]]:
        tunable_shared: Observable[TunableVad] = tunable.pipe(ops.share())
        start: Observable[float] = source.pipe(while_speaking(tunable_shared), ops.first())
        stop: Observable[float] = source.pipe(while_speaking(tunable_shared), ops.last())

        return (start, stop)

    return _operator


def vad_gate(
    model: VADModel,
    options_obs: Observable[TunableVad],
) -> Operator[AudioChunk, AudioChunk]:
    """Gate audio chunks through VAD with dynamically tunable options."""

    def _operator(source: Observable[AudioChunk]) -> Observable[AudioChunk]:
        avg = 0.0
        speaking = False

        def process(pair: tuple[AudioChunk, TunableVad]) -> tuple[AudioChunk, bool]:
            nonlocal avg, speaking
            chunk, opts = pair

            prob = float(model(chunk))
            alpha = opts.attack if prob > avg else opts.decay
            avg = alpha * prob + (1 - alpha) * avg

            if not speaking and avg > opts.start:
                speaking = True
            elif speaking and avg < opts.stop:
                speaking = False

            return (chunk, speaking)

        def is_silent(pair: tuple[AudioChunk, bool]) -> bool:
            return not pair[1]

        def is_speaking(pair: tuple[AudioChunk, bool]) -> bool:
            return pair[1]

        def get_chunk(pair: tuple[AudioChunk, bool]) -> AudioChunk:
            return pair[0]

        processed: Observable[tuple[AudioChunk, bool]] = source.pipe(
            ops.with_latest_from(options_obs),
            ops.map(process),
        )
        skipped: Observable[tuple[AudioChunk, bool]] = processed.pipe(
            ops.skip_while(is_silent),
            take_while_inclusive(is_speaking),
        )
        return skipped.pipe(ops.map(get_chunk))

    return _operator
