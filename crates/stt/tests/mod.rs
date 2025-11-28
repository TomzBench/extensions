use std::io::Cursor;
use std::path::Path;

use symphonia::core::formats::FormatOptions;
use symphonia::core::io::{MediaSourceStream, MediaSourceStreamOptions};
use symphonia::core::meta::MetadataOptions;
use symphonia::core::probe::Hint;

use stt::chunk_audio;

const SOURCE_FILE: &str = "tests/.fixtures/dQw4w9WgXcQ.mp3";
const SOURCE_DURATION_MS: u64 = 213_072; // From ffprobe

/// Calculate expected chunk count for a given duration.
#[allow(clippy::cast_possible_truncation)]
fn expected_chunk_count(chunk_duration_ms: u64) -> usize {
    SOURCE_DURATION_MS.div_ceil(chunk_duration_ms) as usize
}

/// Collect chunks, unwrapping any errors.
fn collect_chunks(path: &Path, chunk_duration_ms: u64) -> Vec<Vec<u8>> {
    chunk_audio(path, chunk_duration_ms)
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap()
}

/// Get duration in milliseconds from in-memory audio data using symphonia.
fn get_duration_ms(data: &[u8]) -> Option<u64> {
    let cursor = Cursor::new(data.to_vec());
    let mss = MediaSourceStream::new(Box::new(cursor), MediaSourceStreamOptions::default());

    let mut hint = Hint::new();
    hint.with_extension("mp3");

    let probed = symphonia::default::get_probe()
        .format(
            &hint,
            mss,
            &FormatOptions::default(),
            &MetadataOptions::default(),
        )
        .ok()?;

    let track = probed.format.default_track()?;
    let n_frames = track.codec_params.n_frames?;
    let sample_rate = track.codec_params.sample_rate?;

    Some((n_frames * 1000) / u64::from(sample_rate))
}

/// Verify chunk is valid audio that can be probed.
fn is_valid_audio(data: &[u8]) -> bool {
    get_duration_ms(data).is_some()
}

/// Assert all chunks have expected durations within tolerance.
fn assert_chunk_durations(chunks: &[Vec<u8>], target_ms: u64) {
    const TOLERANCE: u64 = 500;

    for (i, chunk) in chunks.iter().enumerate() {
        let duration = get_duration_ms(chunk).expect("chunk should be valid audio");

        if i < chunks.len() - 1 {
            // Non-final chunks: target ± tolerance
            assert!(
                (target_ms - TOLERANCE..=target_ms + TOLERANCE).contains(&duration),
                "Chunk {i} duration {duration}ms not in range {}..={}ms",
                target_ms - TOLERANCE,
                target_ms + TOLERANCE
            );
        } else {
            // Final chunk: ≤ target + tolerance (remainder)
            assert!(
                duration <= target_ms + TOLERANCE,
                "Final chunk duration {duration}ms exceeds {}ms",
                target_ms + TOLERANCE
            );
        }
    }
}

// --- Chunk Count Tests ---

#[test]
fn test_chunk_count_10s() {
    let chunks = collect_chunks(Path::new(SOURCE_FILE), 10_000);
    assert_eq!(chunks.len(), expected_chunk_count(10_000)); // 22
}

#[test]
fn test_chunk_count_30s() {
    let chunks = collect_chunks(Path::new(SOURCE_FILE), 30_000);
    assert_eq!(chunks.len(), expected_chunk_count(30_000)); // 8
}

#[test]
fn test_chunk_count_60s() {
    let chunks = collect_chunks(Path::new(SOURCE_FILE), 60_000);
    assert_eq!(chunks.len(), expected_chunk_count(60_000)); // 4
}

// --- Duration Validation Tests ---

#[test]
fn test_chunk_durations_10s() {
    let chunks = collect_chunks(Path::new(SOURCE_FILE), 10_000);
    assert_chunk_durations(&chunks, 10_000);
}

#[test]
fn test_chunk_durations_30s() {
    let chunks = collect_chunks(Path::new(SOURCE_FILE), 30_000);
    assert_chunk_durations(&chunks, 30_000);
}

// --- Validity Tests ---

#[test]
fn test_all_chunks_are_valid_audio() {
    let chunks = collect_chunks(Path::new(SOURCE_FILE), 30_000);

    for (i, chunk) in chunks.iter().enumerate() {
        assert!(is_valid_audio(chunk), "Chunk {i} is not valid audio");
    }
}

// --- Coverage Test ---

#[test]
fn test_total_duration_coverage() {
    let chunks = collect_chunks(Path::new(SOURCE_FILE), 30_000);

    let total_duration: u64 = chunks.iter().filter_map(|c| get_duration_ms(c)).sum();

    // Total should be within 1s of source duration (frame alignment tolerance)
    let diff = total_duration.abs_diff(SOURCE_DURATION_MS);
    assert!(
        diff < 1000,
        "Total duration {total_duration}ms differs from source {SOURCE_DURATION_MS}ms by {diff}ms"
    );
}
