//! Speech-to-text module with audio processing utilities.

pub mod chunker;

pub use chunker::{chunk_audio, AudioChunks, ChunkError};
