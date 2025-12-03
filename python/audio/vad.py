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

from typing import Protocol

from reactivex import Observable
from reactivex import operators as ops
from streams import take_while_inclusive
from streams.utils import Operator

from audio.config import TunableVad
from audio.types import AudioChunk


class VADModel(Protocol):
    def __call__(self, chunk: AudioChunk) -> float: ...


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


