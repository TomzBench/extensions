from dataclasses import dataclass

import reactivex as rx
import sounddevice as sd  # type: ignore[import-untyped]
from reactivex import Observable
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase
from reactivex.disposable import Disposable
from reactivex.scheduler import NewThreadScheduler

from audio.stream import ops
from audio.types import AudioStream, DeviceMeta


def query_input_device(device: int | None = None) -> DeviceMeta:
    """Query sounddevice for input device metadata."""
    return sd.query_devices(device, kind="input")  # type: ignore[no-any-return]


@dataclass
class AudioSource:
    device_id: int | None
    device_name: str
    meta: DeviceMeta
    stream: Observable[AudioStream]


def audio_stream(device: int | None = None) -> AudioSource:
    def subscribe(
        obs: ObserverBase[AudioStream], _sched: SchedulerBase | None = None
    ) -> DisposableBase:
        def callback(data: AudioStream, _fr: int, _time: object, _status: object) -> None:
            obs.on_next(data.copy())

        # NOTE - might need to implement resample to 16Khz, (default is usually 44.1khz or 48khz).
        #        sd resamples if device supports it. Supposedly most modern devices support
        stream = sd.InputStream(device=device, callback=callback, channels=1, samplerate=16000)
        stream.start()

        def dispose() -> None:
            stream.stop()
            stream.close()

        return Disposable(dispose)

    # callback runs on system audio thread, observe_on switches to new thread for downstream
    observable = rx.create(subscribe).pipe(ops.observe_on(NewThreadScheduler()))
    meta = query_input_device(device)
    return AudioSource(
        device_id=meta["index"],
        device_name=meta["name"],
        meta=meta,
        stream=observable,
    )
