# Config (injectable?)
# VadOptions - Tunable
# WhisperModel - Tunable
# Device (ie int or str) - Tunable

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import dataclass
from functools import partial

import reactivex as rx
import reactivex.operators as ops
from reactivex import Observable
from streams import filter_instance_start_with
from streams.switch_resource import switch_resource
from streams.utils import Operator

from audio.config import AppConfig, Tunable, TunableWhisperModel
from audio.rechunk import rechunk
from audio.silero import SileroVADModel
from audio.source import AudioSource, audio_stream
from audio.types import AudioStream
from audio.vad import VADModel, vad_gate
from audio.whisper import SAMPLE_RATE, Transcriber
from audio.window import window_chunks


@dataclass
class RecorderDependencies:
    vad: Callable[[], VADModel] = SileroVADModel
    whisper: Transcriber | None = None
    executor: Executor | None = None


def recorder(
    source: Observable[AudioSource] | None = None,
    maybe_cfg: AppConfig | None = None,
    maybe_deps: RecorderDependencies | None = None,
) -> Operator[Tunable, str]:
    cfg = maybe_cfg or AppConfig()
    deps = maybe_deps or RecorderDependencies()
    vad_model = deps.vad()

    def operator(obs: Observable[Tunable]) -> Observable[str]:
        # Get our tunable parameters
        filter_vad = filter_instance_start_with(cfg.vad_options)
        filter_whisper = filter_instance_start_with(cfg.whisper_model)
        obs_vad = obs.pipe(filter_vad)
        obs_whisper = obs.pipe(filter_whisper)

        # Get our audio source stream
        obs_source = source or rx.of(audio_stream())

        def make_transcriber(t: TunableWhisperModel) -> Transcriber:
            # TODO deps.whisper should be a Transcriber factory
            if deps.whisper is not None:
                return deps.whisper
            return Transcriber.from_path(cfg.model_cache_dir / t.model, deps.executor)

        def make_transcribe_pipeline(
            audio: Observable[AudioStream], transcriber: Transcriber
        ) -> Observable[str]:
            emit_interval = int(0.5 * SAMPLE_RATE)  # TODO add emit interval to cfg
            return audio.pipe(
                rechunk(512),
                vad_gate(vad_model, obs_vad),
                window_chunks(emit_interval=emit_interval),
                ops.switch_map(transcriber.transcribe),
                ops.repeat(),
            )

        def make_device_pipeline(src: AudioSource) -> Observable[str]:
            return obs_whisper.pipe(
                ops.map(make_transcriber),
                switch_resource(partial(make_transcribe_pipeline, src.stream)),
            )

        # Share source so we can use it for both switch_map and completion signal
        shared_source = obs_source.pipe(ops.share())
        # last() emits final item on source complete, triggering take_until
        return shared_source.pipe(
            ops.switch_map(make_device_pipeline),
            ops.take_until(shared_source.pipe(ops.last())),
        )

    return operator
