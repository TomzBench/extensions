//! Whisper speech-to-text bindings.

use std::path::Path;
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

/// Error type for Whisper operations.
#[derive(Debug)]
pub enum WhisperError {
    ModelLoad(String),
    Transcription(String),
    Closed,
}

impl std::fmt::Display for WhisperError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WhisperError::ModelLoad(e) => write!(f, "Failed to load model: {e}"),
            WhisperError::Transcription(e) => write!(f, "Transcription failed: {e}"),
            WhisperError::Closed => write!(f, "Context already closed"),
        }
    }
}

impl std::error::Error for WhisperError {}

/// Whisper context for speech-to-text transcription.
pub struct Whisper {
    ctx: Option<WhisperContext>,
}

impl Whisper {
    /// Load a Whisper model from the given path.
    pub fn new(model_path: impl AsRef<Path>) -> Result<Self, WhisperError> {
        let ctx = WhisperContext::new_with_params(
            model_path.as_ref().to_str().unwrap_or_default(),
            WhisperContextParameters::default(),
        )
        .map_err(|e| WhisperError::ModelLoad(e.to_string()))?;

        Ok(Self { ctx: Some(ctx) })
    }

    /// Transcribe audio samples. Expects 16kHz mono f32, up to 30s (480,000 samples).
    pub fn transcribe(&self, samples: &[f32]) -> Result<String, WhisperError> {
        let ctx = self.ctx.as_ref().ok_or(WhisperError::Closed)?;

        let mut state = ctx
            .create_state()
            .map_err(|e| WhisperError::Transcription(e.to_string()))?;

        let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
        params.set_print_progress(false);
        params.set_print_realtime(false);
        params.set_print_timestamps(false);

        state
            .full(params, samples)
            .map_err(|e| WhisperError::Transcription(e.to_string()))?;

        let num_segments = state.full_n_segments().unwrap_or(0);
        let mut result = String::new();

        for i in 0..num_segments {
            if let Ok(text) = state.full_get_segment_text(i) {
                result.push_str(&text);
            }
        }

        Ok(result.trim().to_string())
    }

    /// Explicitly close the context, releasing resources.
    pub fn close(&mut self) {
        self.ctx = None;
    }

    /// Check if the context is still open.
    #[must_use]
    pub fn is_open(&self) -> bool {
        self.ctx.is_some()
    }
}
