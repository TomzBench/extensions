# Config (injectable?)
# VadOptions - Tunable
# WhisperModel - Tunable
# Device (ie int or str) - Tunable

from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import dataclass

import reactivex.operators as ops
from reactivex import Observable
from streams import filter_instance_start_with
from streams.switch_resource import switch_resource
from streams.utils import Operator

from audio.config import AppConfig, Tunable, TunableVad, TunableWhisperModel
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
        def make_transcriber(t: TunableWhisperModel) -> Transcriber:
            return Transcriber.from_path(str(cfg.model_cache_dir / t.model), deps.executor)

        def make_pipeline(transcriber: Transcriber) -> Observable[str]:
            emit_interval = int(0.5 * SAMPLE_RATE)  # TODO add emit interval to cfg
            return listen_to_mic(cfg.device_id).pipe(
                rechunk(512),
                vad_gate(vad_model, vad_opts_obs),
                window_chunks(emit_interval=emit_interval),
                ops.switch_map(transcriber.transcribe),
                ops.repeat(),
            )

        vad_opts_obs: Observable[TunableVad] = obs.pipe(
            filter_instance_start_with(cfg.vad_options),
        )
        transcribers: Observable[Transcriber] = obs.pipe(
            filter_instance_start_with(cfg.whisper_model),
            ops.map(make_transcriber),
        )
        return transcribers.pipe(switch_resource(make_pipeline))

    return operator
