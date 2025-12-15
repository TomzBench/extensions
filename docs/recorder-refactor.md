# Recorder Refactor Notes

## Problem

`listen_to_mic` has a hidden dependency on `sd.InputStream`. Currently we inject
`device_id` as a tunable, but the actual stream creation is internal to stt.py.
This limits testability and flexibility.

## Solution: Full Dependency Injection

Instead of passing device IDs, inject the audio stream directly. The recorder
should receive an `Observable[AudioChunk]` (or `Observable[AudioSource]`) and
have no knowledge of sounddevice.

### Benefits

1. **Full DI** - stt.py has no knowledge of sounddevice
2. **Testable** - can inject mock audio streams for tests
3. **Flexible** - can swap to different audio sources (file, network, etc.)

## Design

Wrap stream with metadata for logging/observability:

```python
@dataclass
class AudioSource:
    device_id: int | None
    device_name: str
    stream: Observable[AudioStream]
```

`Observable[AudioSource]` emits new source on device change. Gives hook points
for logging device switches, correlating issues with specific devices, etc.

## Implementation Plan

1. Create `AudioSource` class in `audio/source.py`
2. Remove `TunableDevice` from `config.py` (no longer needed)
3. Change `recorder()` signature:
   - First argument: `Observable[AudioSource]` (the audio stream)
   - Other tunables (VAD, model) remain in config as before
4. Caller is responsible for creating `AudioSource` observable from device
   selection UI

## Type Aliases

Consider renaming for clarity:

- `AudioStream` - arbitrary length chunks (raw from mic)
- `AudioChunk` - padded 512 samples (post-rechunk, VAD-compatible)

Not enforced by type system but clarifies intent at a glance.

## Observable[Observable[T]] Pattern

This pattern appears in RxPy with `window`, `group_by`, etc., but is typically
immediately flattened. For our case, wrapping in `AudioSource` is cleaner than
raw `Observable[Observable[AudioChunk]]`.
