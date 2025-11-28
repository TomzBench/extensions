"""Type stubs for audio._stt native extension."""

from collections.abc import Iterator

class AudioChunks(Iterator[bytes]):
    """Iterator over audio chunks from a file.

    Args:
        path: Path to the audio file.
        chunk_duration_ms: Duration of each chunk in milliseconds.
    """

    def __new__(cls, path: str, chunk_duration_ms: int) -> AudioChunks: ...
    def __iter__(self) -> AudioChunks: ...
    def __next__(self) -> bytes: ...
