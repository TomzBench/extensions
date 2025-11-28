//! Chunk audio, recombine, and play to verify chunking is lossless.
//!
//! Usage: `cargo run -p stt --bin play_chunks -- <audio_file>`

use std::env;
use std::io::Write;
use std::process::{Command, Stdio};

fn main() {
    let path = env::args().nth(1).unwrap_or_else(|| {
        eprintln!("Usage: play_chunks <audio_file>");
        std::process::exit(1);
    });

    let chunk_duration_ms = 10_000;
    let chunks: Vec<Vec<u8>> = stt::chunk_audio(&path, chunk_duration_ms)
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap();

    println!(
        "Chunked into {} segments ({chunk_duration_ms}ms each)",
        chunks.len()
    );

    // Concatenate all chunks
    let total_bytes: usize = chunks.iter().map(Vec::len).sum();
    let mut combined = Vec::with_capacity(total_bytes);
    for chunk in &chunks {
        combined.extend_from_slice(chunk);
    }

    println!("Recombined: {} bytes", combined.len());

    // Write to temp file for inspection
    std::fs::write("/tmp/recombined.mp3", &combined).unwrap();
    println!("Wrote to /tmp/recombined.mp3");
    println!("Playing recombined audio...\n");

    // Pipe to ffplay
    let mut child = Command::new("ffplay")
        .args([
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            "-f",
            "mp3", // Force MP3 format for concatenated stream
            "-i",
            "pipe:0",
        ])
        .stdin(Stdio::piped())
        .spawn()
        .expect("Failed to spawn ffplay - is ffmpeg installed?");

    child
        .stdin
        .take()
        .unwrap()
        .write_all(&combined)
        .expect("Failed to write to ffplay");

    child.wait().expect("Failed to wait for ffplay");

    println!("✓ Done");
}
