"""Configuration types for audio pipeline."""

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

from audio.whisper import WhisperModel


class LogLevel(IntEnum):
    """Log levels mirroring Python's logging module."""

    NOTSET = logging.NOTSET
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass(frozen=True)
class TunableVad:
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


@dataclass(frozen=True)
class TunableWhisperModel:
    """Whisper model selection."""

    model: WhisperModel = WhisperModel.SMALL_EN


@dataclass(frozen=True)
class TunableDevice:
    """Audio input device selection."""

    device_id: int | None = None  # None = system default


type Tunable = TunableVad | TunableWhisperModel | TunableDevice

# Presets for common use cases
VAD_SENTENCE = TunableVad(attack=0.8, decay=0.3, start=0.6, stop=0.4)
VAD_PARAGRAPH = TunableVad(attack=0.8, decay=0.2, start=0.6, stop=0.3)
VAD_STORY = TunableVad(attack=0.8, decay=0.1, start=0.5, stop=0.2)

WHISPER_TINY_EN = TunableWhisperModel(WhisperModel.TINY_EN)
WHISPER_BASE_EN = TunableWhisperModel(WhisperModel.BASE_EN)
WHISPER_SMALL_EN = TunableWhisperModel()  # default
WHISPER_MEDIUM_EN = TunableWhisperModel(WhisperModel.MEDIUM_EN)
WHISPER_LARGE_V3_TURBO = TunableWhisperModel(WhisperModel.LARGE_V3_TURBO)


@dataclass(frozen=True)
class AppConfig:
    """Static application configuration."""

    # Environment
    log_level: LogLevel = LogLevel.INFO
    model_cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "whisper")

    # Credentials (future cloud fallback)
    api_key: str | None = None

    # Initial tunable defaults
    whisper_model: TunableWhisperModel = field(default_factory=lambda: WHISPER_SMALL_EN)
    vad_options: TunableVad = field(default_factory=lambda: VAD_SENTENCE)
    device_id: int | None = None
