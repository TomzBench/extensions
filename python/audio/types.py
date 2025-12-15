"""Shared type definitions for audio processing."""

from typing import TypedDict

import numpy as np
from numpy.typing import NDArray


class DeviceMeta(TypedDict):
    name: str
    index: int
    hostapi: int
    max_input_channels: int
    max_output_channels: int
    default_low_input_latency: float
    default_low_output_latency: float
    default_high_input_latency: float
    default_high_output_latency: float
    default_samplerate: float


# Arbitrary length arrays of bytes from an audio source
type AudioStream = NDArray[np.float32]

# Fixed length arrays after processing. (NOTE that types are not checked, just convention)
type AudioChunk = AudioStream
