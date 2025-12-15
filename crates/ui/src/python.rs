//! Bridge to Python audio recorder via `pyo3`.

use pyo3::prelude::*;
use pyo3::types::{PyAnyMethods, PyDict, PyDictMethods};
use thiserror::Error;

/// Errors from Python bridge operations.
#[derive(Debug, Error)]
pub enum PythonError {
    #[error("Python error: {0}")]
    PyErr(#[from] PyErr),
}

type Result<T> = std::result::Result<T, PythonError>;

/// Audio device information.
#[derive(Debug, Clone)]
pub struct AudioDevice {
    pub index: i32,
    pub name: String,
}

/// Query available audio input devices via sounddevice.
pub fn query_devices() -> Result<Vec<AudioDevice>> {
    Python::with_gil(|py| {
        let sd = py.import_bound("sounddevice")?;
        let device_list = sd.call_method0("query_devices")?;

        // DeviceList is not a PyList, so we need to get length and index into it
        let len: usize = device_list.len()?;

        let mut inputs = Vec::new();
        for idx in 0..len {
            let device = device_list.get_item(idx)?;
            let max_input: i32 = device
                .get_item("max_input_channels")?
                .extract()
                .unwrap_or(0);

            if max_input > 0 {
                let name: String = device
                    .get_item("name")?
                    .extract()
                    .unwrap_or_default();

                inputs.push(AudioDevice {
                    index: i32::try_from(idx).unwrap_or(-1),
                    name,
                });
            }
        }

        Ok(inputs)
    })
}

/// Handle to a running recorder session.
pub struct RecorderSession {
    subject: PyObject,
    subscription: PyObject,
}

impl RecorderSession {
    /// Start a new recorder session.
    ///
    /// # Arguments
    /// * `device_id` - Audio device index (None for default)
    /// * `model` - Whisper model name (e.g., "small.en")
    /// * `vad` - VAD parameters (attack, decay, start, stop)
    /// * `on_text` - Callback for transcribed text
    pub fn start<F>(
        device_id: Option<i32>,
        model: &str,
        vad: (f32, f32, f32, f32),
        on_text: F,
    ) -> Result<Self>
    where
        F: Fn(String) + Send + 'static,
    {
        Python::with_gil(|py| {
            // Import our modules
            let rx = py.import_bound("reactivex")?;
            let config_mod = py.import_bound("audio.config")?;
            let stt_mod = py.import_bound("audio.stt")?;

            // Create config
            let tunable_device = config_mod.getattr("TunableDevice")?;
            let tunable_model = config_mod.getattr("TunableWhisperModel")?;
            let tunable_vad = config_mod.getattr("TunableVad")?;
            let whisper_model_enum = py.import_bound("audio.whisper")?.getattr("WhisperModel")?;
            let app_config = config_mod.getattr("AppConfig")?;

            // Build initial config
            let model_value = whisper_model_enum.getattr(model_to_attr(model))?;
            let initial_model = tunable_model.call1((model_value,))?;
            let initial_device = tunable_device.call((), Some(&device_kwargs(py, device_id)?))?;
            let initial_vad =
                tunable_vad.call((), Some(&vad_kwargs(py, vad.0, vad.1, vad.2, vad.3)?))?;

            let cfg_kwargs = PyDict::new_bound(py);
            cfg_kwargs.set_item("whisper_model", initial_model)?;
            cfg_kwargs.set_item("device", initial_device)?;
            cfg_kwargs.set_item("vad_options", initial_vad)?;
            let cfg = app_config.call((), Some(&cfg_kwargs))?;

            // Create subject for tunables
            let subject_cls = rx.getattr("subject")?.getattr("Subject")?;
            let subject = subject_cls.call0()?;

            // Create recorder operator and subscribe
            let recorder_fn = stt_mod.getattr("recorder")?;
            let recorder_op = recorder_fn.call1((&cfg,))?;

            // Create Python callback wrapper
            let callback = PythonCallback::new(on_text);
            let py_callback = Py::new(py, callback)?;

            // subject.pipe(recorder_op).subscribe(on_next=callback)
            let piped = subject.call_method1("pipe", (recorder_op,))?;
            let subscribe_kwargs = PyDict::new_bound(py);
            subscribe_kwargs.set_item("on_next", py_callback.getattr(py, "on_next")?)?;
            let subscription = piped.call_method("subscribe", (), Some(&subscribe_kwargs))?;

            Ok(Self {
                subject: subject.into(),
                subscription: subscription.into(),
            })
        })
    }

    /// Send a VAD tunable update.
    pub fn update_vad(&self, attack: f32, decay: f32, start: f32, stop: f32) -> Result<()> {
        Python::with_gil(|py| {
            let config_mod = py.import_bound("audio.config")?;
            let tunable_vad = config_mod.getattr("TunableVad")?;
            let vad = tunable_vad.call((), Some(&vad_kwargs(py, attack, decay, start, stop)?))?;
            self.subject.call_method1(py, "on_next", (vad,))?;
            Ok(())
        })
    }

    /// Send a device tunable update.
    pub fn update_device(&self, device_id: Option<i32>) -> Result<()> {
        Python::with_gil(|py| {
            let config_mod = py.import_bound("audio.config")?;
            let tunable_device = config_mod.getattr("TunableDevice")?;
            let device = tunable_device.call((), Some(&device_kwargs(py, device_id)?))?;
            self.subject.call_method1(py, "on_next", (device,))?;
            Ok(())
        })
    }

    /// Send a model tunable update.
    pub fn update_model(&self, model: &str) -> Result<()> {
        Python::with_gil(|py| {
            let config_mod = py.import_bound("audio.config")?;
            let tunable_model = config_mod.getattr("TunableWhisperModel")?;
            let whisper_model_enum = py.import_bound("audio.whisper")?.getattr("WhisperModel")?;
            let model_value = whisper_model_enum.getattr(model_to_attr(model))?;
            let model_obj = tunable_model.call1((model_value,))?;
            self.subject.call_method1(py, "on_next", (model_obj,))?;
            Ok(())
        })
    }
}

impl Drop for RecorderSession {
    fn drop(&mut self) {
        let result = Python::with_gil(|py| -> PyResult<()> {
            // Complete the subject
            self.subject.call_method0(py, "on_completed")?;
            // Dispose the subscription
            self.subscription.call_method0(py, "dispose")?;
            Ok(())
        });

        if let Err(e) = result {
            eprintln!("Error during RecorderSession cleanup: {e}");
        }
    }
}

/// Python callback wrapper for receiving transcriptions.
#[pyclass]
struct PythonCallback {
    callback: Box<dyn Fn(String) + Send>,
}

impl PythonCallback {
    fn new<F: Fn(String) + Send + 'static>(f: F) -> Self {
        Self {
            callback: Box::new(f),
        }
    }
}

#[pymethods]
impl PythonCallback {
    fn on_next(&self, text: String) {
        (self.callback)(text);
    }
}

fn model_to_attr(model: &str) -> &'static str {
    match model {
        "tiny.en" => "TINY_EN",
        "base.en" => "BASE_EN",
        "medium.en" => "MEDIUM_EN",
        "large-v3-turbo" => "LARGE_V3_TURBO",
        _ => "SMALL_EN", // default for "small.en" and unknown
    }
}

fn device_kwargs(py: Python<'_>, device_id: Option<i32>) -> PyResult<Bound<'_, PyDict>> {
    let kwargs = PyDict::new_bound(py);
    kwargs.set_item("device_id", device_id)?;
    Ok(kwargs)
}

fn vad_kwargs(
    py: Python<'_>,
    attack: f32,
    decay: f32,
    start: f32,
    stop: f32,
) -> PyResult<Bound<'_, PyDict>> {
    let kwargs = PyDict::new_bound(py);
    kwargs.set_item("attack", attack)?;
    kwargs.set_item("decay", decay)?;
    kwargs.set_item("start", start)?;
    kwargs.set_item("stop", stop)?;
    Ok(kwargs)
}
