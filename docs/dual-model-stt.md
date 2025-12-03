# Dual-Model STT Architecture

## Overview

Speculative transcription using two Whisper models in parallel: a fast model for
immediate feedback and a heavy model for accuracy corrections. Similar to
speculative execution in CPUs or speculative decoding in LLMs.

```
Audio chunks (shared)
    ├──→ [Fast: tiny/base]   → Low-latency draft (grey)
    │                              ↓
    └──→ [Heavy: small/medium] → High-quality correction (solid)
                                      ↓
                              Merged output with confidence styling
```

## Motivation

| Strategy              | Latency | Accuracy | Trade-off                    |
| --------------------- | ------- | -------- | ---------------------------- |
| Single large model    | Poor    | High     | User waits                   |
| Single small model    | Good    | Lower    | Errors stick                 |
| Dual model (this)     | Good    | High     | Memory overhead, merge logic |
| Streaming ASR (cloud) | Best    | Medium   | Privacy, cost, network       |

The dual-model approach provides Deepgram-like responsiveness with Whisper-level
accuracy, running locally.

## RxPy Integration

The existing reactive architecture supports this naturally:

```python
shared = audio_chunks.pipe(ops.share())

fast_stream = shared.pipe(fast_transcriber.transcribe(emit_interval=4000))   # 0.25s
slow_stream = shared.pipe(slow_transcriber.transcribe(emit_interval=16000))  # 1.0s

merged = rx.merge(fast_stream, slow_stream).pipe(ops.scan(merge_state, seed))
```

Key operators:

- `share()` - Fork audio to both models without duplication
- `merge()` - Combine outputs into single stream
- `scan()` - Stateful merging with correction tracking
- `switch_map()` - Existing backpressure handling (slow model won't block fast)

## Window Tracking

Both models use 30s sliding windows but emit at different intervals. Track
alignment via monotonic window IDs:

```python
# Fast emits: window_id 0, 1, 2, 3, 4, 5, 6, 7, 8...
# Slow emits: window_id 0,          4,          8... (4x multiple)
```

Slow result with `window_id=8` confirms/replaces fast results covering
`window_id` in `[5, 6, 7, 8]`.

If `switch_map` drops an in-flight transcription, the counter increments before
the async call so drops are detectable.

## Threading Model

Single RxPy scheduler thread for the observable chain:

```python
listen_to_mic().pipe(
    rechunk(512),
    observe_on(NewThreadScheduler()),  # Move off audio callback thread
    ops.share(),                        # Fork here - both models on same scheduler
)
```

Whisper calls go to `asyncio.to_thread()` via `from_async_threadsafe()`, keeping
compute off the scheduler thread.

## Merging Strategies

### Option A: Timestamp-based replacement (simplest)

```python
@dataclass
class TranscriptSegment:
    text: str
    window_id: int
    confidence: Literal["draft", "confirmed"]
```

Slow emissions replace all draft segments in their coverage window.

### Option B: Diff-based patching

Use `difflib` to find changes between fast and slow outputs. Only update changed
portions, keeping stable text stable. Reduces visual flicker.

### Option C: Full replacement with animation

Slow model replaces entire fast output. UI animates grey → solid transition.
Simplest implementation, may cause more visual churn.

## Output Format

### Console

ANSI color codes for visual feedback:

- Grey/dim: draft (fast model)
- White/bright: confirmed (slow model)

### Structured Consumers

JSON with confidence metadata:

```json
{
  "text": "hello world",
  "confidence": "draft",
  "window_id": 5,
  "timestamp": 1234567890.123
}
```

Or for confirmed:

```json
{
  "text": "hello world",
  "confidence": "confirmed",
  "window_id": 8,
  "corrects_window_ids": [5, 6, 7, 8]
}
```

## Model Pairing Options

| Fast    | Heavy    | Speed Ratio | Notes               |
| ------- | -------- | ----------- | ------------------- |
| tiny    | small    | ~5x         | Good for English    |
| tiny.en | small.en | ~5x         | Best English-only   |
| base    | medium   | ~4x         | Better multilingual |

Memory overhead: ~150MB (tiny) + ~500MB (small) = ~650MB total.

## Alternative Approaches

Other strategies for achieving speculative + finalized STT output:

### Streaming ASR with Finalization

Cloud services (Deepgram, AssemblyAI, Google Cloud Speech) provide native
interim/final result streams:

```
[interim] "hello wor"
[interim] "hello world how"
[final]   "Hello world, how are you?"
```

Pros: True word-by-word streaming (~100ms latency), no merge logic needed.
Cons: Cloud dependency, privacy concerns, API costs, network latency.

### Single Model with Partial Decoding

Some Whisper forks (whisper.cpp, faster-whisper) support partial/streaming
decode - emitting tokens as they're generated:

```
[partial] "hel"
[partial] "hello"
[partial] "hello world"
[final]   "Hello world."
```

Pros: Single model, lower memory, native confidence from token probabilities.
Cons: Whisper wasn't designed for this - quality of partials varies, may require
patches or specific forks.

### Cascaded Refinement

Run fast model first, then re-run heavy model on same audio after fast
completes (sequential, not parallel):

```
Audio → [fast] → display draft → [heavy] → replace with final
```

Pros: Simpler than parallel - no merge logic, one model loaded at a time.
Cons: Heavy model starts late, longer time to final result.

### Hybrid Local + Cloud

Fast local model for immediate feedback, cloud API for corrections:

```
Audio → [local tiny] → draft
     └→ [cloud API]  → final (async, when network available)
```

Pros: Best latency (local) + best accuracy (cloud large models).
Cons: Privacy trade-off, network dependency for finals, cost.

### Confidence-Gated Single Model

Single model with token-level confidence scores. Display low-confidence tokens
as draft, high-confidence as final:

```python
for token in transcription:
    style = "final" if token.confidence > 0.9 else "draft"
```

Pros: Single model, no merge logic, natural confidence from model.
Cons: Whisper doesn't expose per-token confidence easily, requires model
modifications or post-hoc estimation.

### Why Dual-Model Parallel

We chose parallel dual-model because:

1. Fully local (privacy, no network dependency)
2. True parallel execution (fast model never blocked by heavy)
3. Clean separation (draft vs final are distinct model outputs)
4. RxPy architecture fits naturally (`share()` + `merge()`)
5. Predictable behavior (no partial decode quirks)

Trade-off is memory (~650MB for two models) and merge complexity.

## Future Enhancements

- Speculative prefill: Start transcribing during trailing silence (before VAD
  fully gates) for extra snappiness
- Sentence boundary alignment: Trigger slow model on VAD sentence completion
  rather than fixed interval
- Confidence thresholding: Skip slow model correction if fast model confidence
  is high enough

---

# Custom Tracing Layer for Whisper Logging

## Problem

`whisper.cpp` (via `whisper-rs`) is verbose during model load and transcription:

```
whisper_init_state
whisper_init_with_params
whisper_model_load
...
```

Direct bridges like `pyo3-log` or `tracing-for-pyo3-logging` acquire the GIL per
log call, which interferes with real-time audio processing.

## Solution

Custom tracing `Layer` that batches logs and flushes on our schedule:

```rust
use tracing_subscriber::Layer;
use std::sync::mpsc::Sender;

struct BatchingPyLogger {
    tx: Sender<LogEntry>,
}

impl<S> Layer<S> for BatchingPyLogger
where
    S: tracing::Subscriber,
{
    fn on_event(&self, event: &tracing::Event<'_>, _ctx: Context<'_, S>) {
        // Non-blocking send to channel (no GIL)
        let _ = self.tx.send(LogEntry::from(event));
    }
}
```

## Flush Strategy

Flush to Python between transcription windows or on a timer:

- Between `switch_map` emissions (natural pause point)
- On errors (immediate flush)
- At end of transcription session
- Periodic timer (e.g., every 5s)

## Filtering Options

Apply in the layer to reduce noise:

- Drop DEBUG/TRACE entirely
- Aggregate repeated messages: "whisper_decode called 847 times"
- Only forward WARN and above to Python

## Cargo Configuration

```toml
[dependencies]
whisper-rs = { version = "...", features = ["tracing"] }
tracing = "0.1"
tracing-subscriber = "0.3"
```

## Alternative: Suppress Entirely

If logs aren't needed, simplest option is a no-op layer or build whisper.cpp
with `-DWHISPER_NO_LOGS=1`.
