//! PyO3 bindings for the `stt` audio chunking library.

use pyo3::prelude::*;
use stt::chunk_audio;

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

#[pymodule]
fn _stt(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyAudioChunks>()?;
    Ok(())
}
