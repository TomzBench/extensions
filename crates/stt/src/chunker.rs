//! Core audio chunking implementation.
//!
//! Uses `FFmpeg` library (via `ffmpeg-next` crate) for audio segmentation.
//! No subprocess calls - pure Rust FFI integration.

use std::path::{Path, PathBuf};
use std::ptr;
use std::sync::OnceLock;

extern crate ffmpeg_next as ffmpeg;

use ffmpeg::codec::packet::Packet;
use ffmpeg::format::context::Input;
use ffmpeg::{ffi, format, media, Rational};

/// Error type for audio chunking operations.
#[derive(Debug)]
pub enum ChunkError {
    FileNotFound(PathBuf),
    FfmpegError(String),
}

impl std::fmt::Display for ChunkError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ChunkError::FileNotFound(p) => write!(f, "File not found: {}", p.display()),
            ChunkError::FfmpegError(e) => write!(f, "FFmpeg error: {e}"),
        }
    }
}

impl std::error::Error for ChunkError {}

impl From<ffmpeg::Error> for ChunkError {
    fn from(e: ffmpeg::Error) -> Self {
        ChunkError::FfmpegError(e.to_string())
    }
}

// --- RAII Wrappers for FFmpeg resources ---

/// RAII wrapper for `AVIOContext` dynamic buffer.
struct DynBuffer(*mut ffi::AVIOContext);

impl DynBuffer {
    /// Allocate a new dynamic buffer for in-memory I/O.
    fn new() -> Result<Self, ChunkError> {
        let mut ptr: *mut ffi::AVIOContext = ptr::null_mut();
        let ret = unsafe { ffi::avio_open_dyn_buf(&raw mut ptr) };
        if ret < 0 {
            return Err(ChunkError::FfmpegError(format!(
                "Failed to open dynamic buffer: {ret}"
            )));
        }
        Ok(Self(ptr))
    }

    /// Get raw pointer for attaching to format context.
    fn as_ptr(&self) -> *mut ffi::AVIOContext {
        self.0
    }

    /// Close buffer and extract contents. Consumes self.
    fn into_bytes(self) -> Vec<u8> {
        let mut data_ptr: *mut u8 = ptr::null_mut();
        let size = unsafe { ffi::avio_close_dyn_buf(self.0, &raw mut data_ptr) };

        let result = if size > 0 && !data_ptr.is_null() {
            let len = usize::try_from(size).unwrap_or(0);
            unsafe { std::slice::from_raw_parts(data_ptr, len).to_vec() }
        } else {
            Vec::new()
        };

        if !data_ptr.is_null() {
            unsafe { ffi::av_free(data_ptr.cast::<std::ffi::c_void>()) };
        }

        std::mem::forget(self); // Prevent Drop from closing again
        result
    }
}

impl Drop for DynBuffer {
    fn drop(&mut self) {
        if !self.0.is_null() {
            let mut data_ptr: *mut u8 = ptr::null_mut();
            unsafe {
                ffi::avio_close_dyn_buf(self.0, &raw mut data_ptr);
                if !data_ptr.is_null() {
                    ffi::av_free(data_ptr.cast::<std::ffi::c_void>());
                }
            }
        }
    }
}

/// RAII wrapper for `AVFormatContext` (output) with owned dynamic buffer.
struct OutputContext {
    ptr: *mut ffi::AVFormatContext,
    buf: std::mem::ManuallyDrop<DynBuffer>,
}

impl OutputContext {
    /// Allocate a new output format context with in-memory buffer.
    fn new(format_name: &str, buf: DynBuffer) -> Result<Self, ChunkError> {
        let mut ptr: *mut ffi::AVFormatContext = ptr::null_mut();
        let format_cstr = std::ffi::CString::new(format_name)
            .map_err(|e| ChunkError::FfmpegError(format!("Invalid format name: {e}")))?;

        let ret = unsafe {
            ffi::avformat_alloc_output_context2(
                &raw mut ptr,
                ptr::null_mut(),
                format_cstr.as_ptr(),
                ptr::null(),
            )
        };

        if ret < 0 || ptr.is_null() {
            return Err(ChunkError::FfmpegError(format!(
                "Failed to allocate output context: {ret}"
            )));
        }

        // Attach buffer to context
        unsafe {
            (*ptr).pb = buf.as_ptr();
            (*ptr).flags |= ffi::AVFMT_FLAG_CUSTOM_IO;
        }

        Ok(Self {
            ptr,
            buf: std::mem::ManuallyDrop::new(buf),
        })
    }

    /// Add a new stream and copy codec parameters from input.
    fn add_stream(
        &self,
        stream_params: &ffmpeg::codec::Parameters,
    ) -> Result<ffi::AVRational, ChunkError> {
        let out_stream = unsafe { ffi::avformat_new_stream(self.ptr, ptr::null()) };

        if out_stream.is_null() {
            return Err(ChunkError::FfmpegError(
                "Failed to create output stream".to_string(),
            ));
        }

        let ret =
            unsafe { ffi::avcodec_parameters_copy((*out_stream).codecpar, stream_params.as_ptr()) };

        if ret < 0 {
            return Err(ChunkError::FfmpegError(format!(
                "Failed to copy codec parameters: {ret}"
            )));
        }

        // Reset codec_tag to avoid format incompatibility
        unsafe {
            (*(*out_stream).codecpar).codec_tag = 0;
        }

        Ok(unsafe { (*out_stream).time_base })
    }

    /// Write the container header.
    fn write_header(&mut self) -> Result<&mut Self, ChunkError> {
        let ret = unsafe { ffi::avformat_write_header(self.ptr, ptr::null_mut()) };
        if ret < 0 {
            return Err(ChunkError::FfmpegError(format!(
                "Failed to write header: {ret}"
            )));
        }
        Ok(self)
    }

    /// Write a packet to the output.
    fn write_packet(&mut self, pkt: &mut ffi::AVPacket) -> Result<(), ChunkError> {
        let ret = unsafe { ffi::av_interleaved_write_frame(self.ptr, &raw mut *pkt) };
        if ret < 0 {
            return Err(ChunkError::FfmpegError(format!(
                "Failed to write packet: {ret}"
            )));
        }
        Ok(())
    }

    /// Write packets with timestamp conversion.
    fn write_packets(
        &mut self,
        packets: &[Packet],
        in_time_base: Rational,
        out_time_base: ffi::AVRational,
    ) -> Result<&mut Self, ChunkError> {
        for packet in packets {
            let mut pkt = ffi::AVPacket {
                buf: ptr::null_mut(),
                pts: packet.pts().unwrap_or(ffi::AV_NOPTS_VALUE),
                dts: packet.dts().unwrap_or(ffi::AV_NOPTS_VALUE),
                data: packet
                    .data()
                    .map_or(ptr::null_mut(), |d| d.as_ptr().cast_mut()),
                size: i32::try_from(packet.size()).unwrap_or(i32::MAX),
                stream_index: 0,
                flags: packet.flags().bits(),
                side_data: ptr::null_mut(),
                side_data_elems: 0,
                duration: packet.duration(),
                pos: -1,
                opaque: ptr::null_mut(),
                opaque_ref: ptr::null_mut(),
                time_base: ffi::AVRational {
                    num: in_time_base.numerator(),
                    den: in_time_base.denominator(),
                },
            };

            // Rescale timestamps to output time base
            unsafe {
                ffi::av_packet_rescale_ts(&raw mut pkt, pkt.time_base, out_time_base);
            }
            pkt.time_base = out_time_base;

            // Replace AV_NOPTS_VALUE duration with 0 after rescaling to avoid FFmpeg warnings
            if pkt.duration == ffi::AV_NOPTS_VALUE {
                pkt.duration = 0;
            }

            self.write_packet(&mut pkt)?;
        }

        Ok(self)
    }

    /// Write the container trailer.
    fn write_trailer(&mut self) -> Result<&mut Self, ChunkError> {
        let ret = unsafe { ffi::av_write_trailer(self.ptr) };
        if ret < 0 {
            return Err(ChunkError::FfmpegError(format!(
                "Failed to write trailer: {ret}"
            )));
        }
        Ok(self)
    }

    /// Close buffer and extract contents. Consumes self.
    fn into_bytes(mut self) -> Vec<u8> {
        // Detach buffer from format context before consuming
        unsafe { (*self.ptr).pb = ptr::null_mut() };

        // Free format context
        unsafe { ffi::avformat_free_context(self.ptr) };
        self.ptr = ptr::null_mut();

        // Take ownership of buffer and extract bytes
        let buf = unsafe { std::mem::ManuallyDrop::take(&mut self.buf) };
        let result = buf.into_bytes();

        std::mem::forget(self);
        result
    }
}

impl Drop for OutputContext {
    fn drop(&mut self) {
        // Detach buffer before freeing format context
        if !self.ptr.is_null() {
            unsafe {
                (*self.ptr).pb = ptr::null_mut();
                ffi::avformat_free_context(self.ptr);
            }
        }
        // Manually drop the buffer
        unsafe { std::mem::ManuallyDrop::drop(&mut self.buf) };
    }
}

// --- Public API ---

/// Iterator over audio chunks.
///
/// Uses `FFmpeg` library to segment audio files, producing chunks that match
/// the output of `ffmpeg -f segment -segment_time <duration> -c copy`.
pub struct AudioChunks {
    path: PathBuf,
    chunk_duration_ms: u64,
    input: Input,
    audio_stream_index: usize,
    time_base: Rational,
    stream_params: ffmpeg::codec::Parameters,
    chunk_duration_tb: i64,
    current_packets: Vec<Packet>,
    chunk_start_pts: Option<i64>,
    exhausted: bool,
    format_name: String,
}

/// Initialize `FFmpeg` once per process.
fn init_ffmpeg() -> Result<(), ChunkError> {
    static INIT: OnceLock<Result<(), String>> = OnceLock::new();

    INIT.get_or_init(|| ffmpeg::init().map_err(|e| e.to_string()))
        .clone()
        .map_err(ChunkError::FfmpegError)
}

impl AudioChunks {
    fn new(path: PathBuf, chunk_duration_ms: u64) -> Result<Self, ChunkError> {
        if !path.exists() {
            return Err(ChunkError::FileNotFound(path));
        }

        init_ffmpeg()?;

        let input = format::input(&path)?;

        // Find audio stream
        let audio_stream = input
            .streams()
            .best(media::Type::Audio)
            .ok_or_else(|| ChunkError::FfmpegError("No audio stream found".to_string()))?;

        let audio_stream_index = audio_stream.index();
        let time_base = audio_stream.time_base();
        let stream_params = audio_stream.parameters();

        // Determine output format from extension
        let format_name = path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("mp3")
            .to_string();

        // Convert chunk duration to time base units
        // chunk_duration_tb = (ms / 1000) * (den / num)
        #[allow(clippy::cast_possible_wrap)]
        let chunk_duration_tb = (chunk_duration_ms as i64 * i64::from(time_base.denominator()))
            / (1000 * i64::from(time_base.numerator()));

        Ok(Self {
            path,
            chunk_duration_ms,
            input,
            audio_stream_index,
            time_base,
            stream_params,
            chunk_duration_tb,
            current_packets: Vec::new(),
            chunk_start_pts: None,
            exhausted: false,
            format_name,
        })
    }

    #[must_use]
    pub fn path(&self) -> &PathBuf {
        &self.path
    }

    #[must_use]
    pub fn chunk_duration_ms(&self) -> u64 {
        self.chunk_duration_ms
    }

    /// Finalize current chunk and return its bytes.
    fn finalize_chunk(&mut self) -> Result<Option<Vec<u8>>, ChunkError> {
        if self.current_packets.is_empty() {
            return Ok(None);
        }

        let packets = std::mem::take(&mut self.current_packets);
        self.chunk_start_pts = None;

        let buf = DynBuffer::new()?;
        let mut octx = OutputContext::new(&self.format_name, buf)?;
        let out_time_base = octx.add_stream(&self.stream_params)?;

        octx.write_header()?
            .write_packets(&packets, self.time_base, out_time_base)?
            .write_trailer()?;

        let bytes = octx.into_bytes();
        Ok(if bytes.is_empty() { None } else { Some(bytes) })
    }
}

impl Iterator for AudioChunks {
    type Item = Result<Vec<u8>, ChunkError>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.exhausted {
            return None;
        }

        loop {
            let Some((stream, packet)) = self.input.packets().next() else {
                // End of file - finalize remaining packets
                self.exhausted = true;
                return self.finalize_chunk().transpose();
            };

            // Skip non-audio streams
            if stream.index() != self.audio_stream_index {
                continue;
            }

            let pts = packet.pts().unwrap_or(0);

            // Initialize chunk start PTS
            if self.chunk_start_pts.is_none() {
                self.chunk_start_pts = Some(pts);
            }

            let chunk_start = self.chunk_start_pts.unwrap();

            // Check if packet exceeds chunk boundary
            let at_boundary =
                pts - chunk_start >= self.chunk_duration_tb && !self.current_packets.is_empty();

            if at_boundary {
                // Finalize current chunk before starting new one
                match self.finalize_chunk() {
                    Ok(Some(bytes)) => {
                        self.chunk_start_pts = Some(pts);
                        self.current_packets.push(packet);
                        return Some(Ok(bytes));
                    }
                    Ok(None) => {
                        self.chunk_start_pts = Some(pts);
                    }
                    Err(e) => {
                        self.exhausted = true;
                        return Some(Err(e));
                    }
                }
            }

            self.current_packets.push(packet);
        }
    }
}

/// Chunk an audio file into segments of the specified duration.
///
/// # Arguments
/// * `path` - Path to the audio file
/// * `chunk_duration_ms` - Duration of each chunk in milliseconds
///
/// # Example
/// ```ignore
/// for chunk in stt::chunk_audio("audio.mp3", 30_000)? {
///     // process chunk bytes
/// }
/// ```
pub fn chunk_audio(
    path: impl AsRef<Path>,
    chunk_duration_ms: u64,
) -> Result<AudioChunks, ChunkError> {
    AudioChunks::new(path.as_ref().to_path_buf(), chunk_duration_ms)
}
