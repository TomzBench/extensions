//! Speech-to-text module with audio processing utilities.

pub mod chunker;
pub mod whisper;

pub use chunker::{chunk_audio, AudioChunks, ChunkError};
pub use whisper::{Whisper, WhisperError};
