//! PyO3 bindings for the `stt` audio chunking library.

use numpy::{PyArray1, PyArrayMethods};
use pyo3::prelude::*;
use stt::{chunk_audio, Whisper};

/// Python wrapper for `AudioChunks` iterator.
#[pyclass(name = "AudioChunks")]
pub struct PyAudioChunks(stt::AudioChunks);

#[pymethods]
impl PyAudioChunks {
    #[new]
    fn new(path: &str, chunk_duration_ms: u64) -> PyResult<Self> {
        let chunks = chunk_audio(path, chunk_duration_ms)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        Ok(Self(chunks))
    }

    fn __iter__(slf: PyRef<Self>) -> PyRef<Self> {
        slf
    }

    fn __next__(&mut self) -> PyResult<Option<Vec<u8>>> {
        match self.0.next() {
            Some(Ok(bytes)) => Ok(Some(bytes)),
            Some(Err(e)) => Err(PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string())),
            None => Ok(None),
        }
    }
}

/// Whisper speech-to-text context.
#[pyclass(name = "Whisper")]
pub struct PyWhisper(Whisper);

#[pymethods]
impl PyWhisper {
    #[new]
    fn new(model_path: &str) -> PyResult<Self> {
        let whisper = Whisper::new(model_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        Ok(Self(whisper))
    }

    /// Transcribe audio samples (16kHz mono f32, up to 30s).
    fn transcribe(&self, samples: &Bound<'_, PyArray1<f32>>) -> PyResult<String> {
        let samples = unsafe { samples.as_slice()? };
        self.0
            .transcribe(samples)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
    }

    /// Explicitly close the context.
    fn close(&mut self) {
        self.0.close();
    }

    /// Check if context is open.
    fn is_open(&self) -> bool {
        self.0.is_open()
    }

    fn __enter__(slf: PyRef<Self>) -> PyRef<Self> {
        slf
    }

    #[pyo3(signature = (_exc_type=None, _exc_value=None, _traceback=None))]
    fn __exit__(
        &mut self,
        _exc_type: Option<&Bound<'_, PyAny>>,
        _exc_value: Option<&Bound<'_, PyAny>>,
        _traceback: Option<&Bound<'_, PyAny>>,
    ) -> bool {
        self.close();
        false
    }
}

#[pymodule]
fn _stt(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyAudioChunks>()?;
    m.add_class::<PyWhisper>()?;
    Ok(())
}
