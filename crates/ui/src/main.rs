//! Slint UI for STT tuning panel.

mod python;

use std::sync::{Arc, Mutex};

use slint::{ModelRc, SharedString, VecModel};

slint::include_modules!();

/// Model names matching `WhisperModel` enum.
const MODELS: &[&str] = &["tiny.en", "base.en", "small.en", "medium.en", "large-v3-turbo"];

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let panel = Panel::new()?;

    // Query audio devices
    let devices = python::query_devices().unwrap_or_else(|e| {
        eprintln!("Failed to query devices: {e}");
        vec![python::AudioDevice {
            index: -1,
            name: "Default".to_string(),
        }]
    });

    let device_names: Vec<SharedString> = devices.iter().map(|d| d.name.clone().into()).collect();
    let device_indices: Vec<i32> = devices.iter().map(|d| d.index).collect();

    panel.set_devices(ModelRc::new(VecModel::from(device_names.clone())));

    // Default to last device (matches sounddevice's default behavior)
    let default_device_idx = device_names.len().saturating_sub(1);
    panel.set_selected_device_index(i32::try_from(default_device_idx).unwrap_or(0));

    // Session state (None when stopped, Some when running)
    let session: Arc<Mutex<Option<python::RecorderSession>>> = Arc::new(Mutex::new(None));

    setup_toggle_recording(&panel, Arc::clone(&session), device_indices.clone());
    setup_vad_callback(&panel, Arc::clone(&session));
    setup_device_callback(&panel, Arc::clone(&session), device_indices);
    setup_model_callback(&panel, Arc::clone(&session));

    panel.run()?;

    Ok(())
}

fn setup_toggle_recording(
    panel: &Panel,
    session: Arc<Mutex<Option<python::RecorderSession>>>,
    device_indices: Vec<i32>,
) {
    let panel_weak = panel.as_weak();
    panel.on_toggle_recording(move || {
        let mut session_guard = session.lock().expect("mutex poisoned");
        let panel = panel_weak.upgrade().expect("panel dropped");

        if session_guard.is_some() {
            // Stop: drop the session
            *session_guard = None;
            panel.set_is_running(false);
        } else {
            // Start: create new session
            let device_idx = usize::try_from(panel.get_selected_device_index()).unwrap_or(0);
            let device_id = device_indices
                .get(device_idx)
                .copied()
                .and_then(|id| if id < 0 { None } else { Some(id) });

            let model_idx = usize::try_from(panel.get_selected_model_index()).unwrap_or(2);
            let model = MODELS.get(model_idx).unwrap_or(&"small.en");

            let vad = (
                panel.get_vad_attack(),
                panel.get_vad_decay(),
                panel.get_vad_start(),
                panel.get_vad_stop(),
            );

            // Capture weak handle for the callback
            let panel_weak_inner = panel.as_weak();

            match python::RecorderSession::start(device_id, model, vad, move |text| {
                let panel_weak = panel_weak_inner.clone();
                slint::invoke_from_event_loop(move || {
                    if let Some(panel) = panel_weak.upgrade() {
                        let current = panel.get_transcript();
                        let updated = if current.is_empty() {
                            text.into()
                        } else {
                            format!("{current}\n{text}").into()
                        };
                        panel.set_transcript(updated);
                    }
                })
                .ok();
            }) {
                Ok(new_session) => {
                    *session_guard = Some(new_session);
                    panel.set_is_running(true);
                }
                Err(e) => {
                    eprintln!("Failed to start recorder: {e}");
                }
            }
        }
    });
}

fn setup_vad_callback(panel: &Panel, session: Arc<Mutex<Option<python::RecorderSession>>>) {
    panel.on_vad_changed(move |attack, decay, start, stop| {
        if let Some(ref sess) = *session.lock().expect("mutex poisoned") {
            if let Err(e) = sess.update_vad(attack, decay, start, stop) {
                eprintln!("Failed to update VAD: {e}");
            }
        }
    });
}

fn setup_device_callback(
    panel: &Panel,
    session: Arc<Mutex<Option<python::RecorderSession>>>,
    device_indices: Vec<i32>,
) {
    let panel_weak = panel.as_weak();
    panel.on_device_changed(move || {
        if let Some(ref sess) = *session.lock().expect("mutex poisoned") {
            let idx = panel_weak
                .upgrade()
                .map_or(0, |p| p.get_selected_device_index());
            let idx = usize::try_from(idx).unwrap_or(0);
            let device_id = device_indices
                .get(idx)
                .copied()
                .and_then(|id| if id < 0 { None } else { Some(id) });
            if let Err(e) = sess.update_device(device_id) {
                eprintln!("Failed to update device: {e}");
            }
        }
    });
}

fn setup_model_callback(panel: &Panel, session: Arc<Mutex<Option<python::RecorderSession>>>) {
    let panel_weak = panel.as_weak();
    panel.on_model_changed(move || {
        if let Some(ref sess) = *session.lock().expect("mutex poisoned") {
            let idx = panel_weak
                .upgrade()
                .map_or(2, |p| p.get_selected_model_index());
            let idx = usize::try_from(idx).unwrap_or(2);
            let model = MODELS.get(idx).unwrap_or(&"small.en");
            if let Err(e) = sess.update_model(model) {
                eprintln!("Failed to update model: {e}");
            }
        }
    });
}
