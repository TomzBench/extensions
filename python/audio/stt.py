# Config (injectable?)
# VadOptions - Tunable
# WhisperModel - Tunable
# Device (ie int or str) - Tunable

from asyncio import AbstractEventLoop
from collections.abc import Callable
from dataclasses import dataclass

import reactivex as rx
import reactivex.operators as ops
from reactivex import Observable
from streams import filter_instance
from streams.switch_resource import switch_resource
from streams.utils import Operator

from audio.config import AppConfig, Tunable, TunableWhisperModel
from audio.rechunk import rechunk
from audio.silero import SileroVADModel
from audio.stream import listen_to_mic
from audio.vad import VADModel, vad_sentence
from audio.whisper import Transcriber


@dataclass
class RecorderDependencies:
    vad: Callable[[], VADModel] = SileroVADModel
    whisper: Transcriber | None = None
    loop: AbstractEventLoop | None = None


def recorder(
    maybe_cfg: AppConfig | None = None,
    maybe_deps: RecorderDependencies | None = None,
) -> Operator[Tunable, str]:
    cfg = maybe_cfg or AppConfig()
    deps = maybe_deps or RecorderDependencies()

    def operator(obs: Observable[Tunable]) -> Observable[str]:
        return rx.merge(
            rx.of(cfg.whisper_model),
            obs.pipe(filter_instance(TunableWhisperModel), ops.map(lambda x: x.model)),
        ).pipe(
            ops.map(lambda x: Transcriber.from_path(str(cfg.model_cache_dir / x), deps.loop)),
            switch_resource(
                lambda whisper: listen_to_mic(cfg.device_id).pipe(
                    rechunk(512),
                    vad_sentence(deps.vad()),  # TODO (vad gate accept Observable[TunableVad])
                    whisper.transcribe_seconds(0.5),  # TODO add emit interval to cfg
                    ops.repeat(),
                )
            ),
        )

    return operator
