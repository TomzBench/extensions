# Config (injectable?)
# VadOptions - Tunable
# WhisperModel - Tunable
# Device (ie int or str) - Tunable

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import dataclass
from functools import partial

import reactivex.operators as ops
from reactivex import Observable
from streams import filter_instance_start_with
from streams.switch_resource import switch_resource
from streams.utils import Operator

from audio.config import AppConfig, Tunable, TunableDevice, TunableVad, TunableWhisperModel
from audio.rechunk import rechunk
from audio.silero import SileroVADModel
from audio.stream import listen_to_mic
from audio.vad import VADModel, vad_gate
from audio.whisper import SAMPLE_RATE, Transcriber
from audio.window import window_chunks


@dataclass
class RecorderDependencies:
    vad: Callable[[], VADModel] = SileroVADModel
    whisper: Transcriber | None = None
    executor: Executor | None = None


def recorder(
    maybe_cfg: AppConfig | None = None,
    maybe_deps: RecorderDependencies | None = None,
) -> Operator[Tunable, str]:
    cfg = maybe_cfg or AppConfig()
    deps = maybe_deps or RecorderDependencies()
    vad_model = deps.vad()

    def operator(obs: Observable[Tunable]) -> Observable[str]:
        # Get our tunable parameters
        obs_vad: Observable[TunableVad] = obs.pipe(filter_instance_start_with(cfg.vad_options))
        obs_device: Observable[TunableDevice] = obs.pipe(filter_instance_start_with(cfg.device))
        obs_whisper: Observable[TunableWhisperModel] = obs.pipe(
            filter_instance_start_with(cfg.whisper_model)
        )

        def make_transcriber(t: TunableWhisperModel) -> Transcriber:
            return Transcriber.from_path(cfg.model_cache_dir / t.model, deps.executor)

        def make_transcribe_pipeline(dev: int | None, transcriber: Transcriber) -> Observable[str]:
            emit_interval = int(0.5 * SAMPLE_RATE)  # TODO add emit interval to cfg
            return listen_to_mic(dev).pipe(
                rechunk(512),
                vad_gate(vad_model, obs_vad),
                window_chunks(emit_interval=emit_interval),
                ops.switch_map(transcriber.transcribe),
                ops.repeat(),
            )

        def make_device_pipeline(dev: TunableDevice) -> Observable[str]:
            return obs_whisper.pipe(
                ops.map(make_transcriber),
                switch_resource(partial(make_transcribe_pipeline, dev.device_id)),
            )

        return obs_device.pipe(ops.switch_map(make_device_pipeline))

    return operator
