"""Exceptions for audio extraction operations."""


class AudioExtractionError(Exception):
    """Base exception for audio extraction errors."""


class InvalidURLError(AudioExtractionError):
    """URL is malformed or unsupported."""


class VideoUnavailableError(AudioExtractionError):
    """Video does not exist, is private, or geo-restricted."""


class DownloadError(AudioExtractionError):
    """Failed to download the media stream."""


class PostProcessingError(AudioExtractionError):
    """FFmpeg audio extraction/conversion failed."""


class OutputDirectoryError(AudioExtractionError):
    """Output directory does not exist or is not writable."""
