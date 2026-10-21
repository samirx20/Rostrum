//! CLAP plugins (S4) through clack-host (MIT / Apache-2.0): the user's installed plugins, found in
//! the standard folders, listed with their parameters, and rendered offline like any other voice —
//! an instrument plays a clip's notes, an effect processes a track — in fixed 256-sample blocks,
//! with notes and parameters as sample-timed events. Preview plays the same render export writes.
//! A plugin's saved state (plugins/params.rs) is loaded before it plays; automated parameters follow
//! their envelopes (`Automation`); a person tweaks a plugin in its own window (plugins/session.rs).

pub mod render;
#[cfg(windows)]
pub mod session;
#[cfg(test)]
mod tests;

use std::path::{Path, PathBuf};

use clack_extensions::params::{ParamInfoBuffer, ParamInfoFlags, PluginParams};
use clack_extensions::state::PluginState;
use clack_host::prelude::*;
use serde::Deserialize;

struct Shared;
impl<'a> SharedHandler<'a> for Shared {
    fn request_restart(&self) {}
    fn request_process(&self) {}
    fn request_callback(&self) {}
}
struct Host;
impl HostHandlers for Host {
    type Shared<'a> = Shared;
    type MainThread<'a> = ();
    type AudioProcessor<'a> = ();
}

fn host_info() -> Result<HostInfo, String> {
    HostInfo::new("Rostrum", "Rostrum", "https://rostrum.studio", env!("CARGO_PKG_VERSION")).map_err(|e| format!("{e:?}"))
}

/// The folders CLAP plugins are installed in (the CLAP spec's, per user and per machine; CLAP_PATH first).
pub fn folders() -> Vec<PathBuf> {
    let mut out: Vec<PathBuf> = std::env::var_os("CLAP_PATH").map(|p| std::env::split_paths(&p).collect()).unwrap_or_default();
    if let Some(local) = std::env::var_os("LOCALAPPDATA") {
        out.push(Path::new(&local).join("Programs").join("Common").join("CLAP"));
    }
    if let Some(common) = std::env::var_os("COMMONPROGRAMFILES") {
        out.push(Path::new(&common).join("CLAP"));
    }
    out
}

/// Every plugin in the CLAP files there: what it is and its parameters.
pub fn scan() -> Vec<serde_json::Value> {
    let mut out = vec![];
    for dir in folders() {
        let Ok(files) = std::fs::read_dir(&dir) else { continue };
        for f in files.flatten().map(|e| e.path()).filter(|p| p.extension().is_some_and(|x| x.eq_ignore_ascii_case("clap"))) {
            match describe(&f) {
                Ok(list) => out.extend(list),
                Err(e) => out.push(serde_json::json!({ "format": "clap", "path": f.to_string_lossy(), "error": e })),
            }
        }
    }
    out
}

/// The unit a parameter's display text ends in, when it is one of the common ones ("-60.0 dB" → "dB").
fn unit_of(text: &str) -> Option<&'static str> {
    let t = text.trim();
    ["dB", "Hz", "kHz", "ms", "%", "s"].into_iter().find(|u| t.strip_suffix(u).is_some_and(|n| n.trim_end().ends_with(|c: char| c.is_ascii_digit())))
}

/// The plugins in one CLAP file (what `scan` lists for each file; the contract's `plugins` request).
pub fn describe(path: &Path) -> Result<Vec<serde_json::Value>, String> {
    let entry = unsafe { PluginEntry::load(path) }.map_err(|e| format!("cannot load: {e:?}"))?;
    let factory = entry.get_plugin_factory().ok_or("no plugin factory")?;
    let info = host_info()?;
    let mut out = vec![];
    for d in factory.plugin_descriptors() {
        let Some(id) = d.id() else { continue };
        let features: Vec<String> = d.features().map(|f| f.to_string_lossy().into_owned()).collect();
        let kind = if features.iter().any(|f| f == "instrument") { "instrument" } else { "effect" };
        let mut instance = PluginInstance::<Host>::new(|_| Shared, |_| (), &entry, id, &info).map_err(|e| format!("{e:?}"))?;
        let mut params = vec![];
        let mut handle = instance.plugin_handle();
        if let Some(p) = handle.get_extension::<PluginParams>() {
            let mut buf = ParamInfoBuffer::new();
            for i in 0..p.count(&mut handle) {
                if let Some(pi) = p.get_info(&mut handle, i, &mut buf) {
                    let mut q = serde_json::json!({ "id": pi.id.get(), "name": String::from_utf8_lossy(pi.name), "module": String::from_utf8_lossy(pi.module), "min": pi.min_value, "max": pi.max_value, "default": pi.default_value });
                    if pi.flags.intersects(ParamInfoFlags::IS_STEPPED | ParamInfoFlags::IS_ENUM) {
                        q["stepped"] = true.into();
                    }
                    // CLAP has no unit field: read one off the plugin's own text for its lowest value ("-60.0 dB").
                    let mut text = [0u8; 64];
                    if let Some(u) = p.value_to_text(&handle, pi.id, pi.min_value, &mut text).ok().and_then(|t| unit_of(&String::from_utf8_lossy(t))) {
                        q["unit"] = u.into();
                    }
                    params.push(q);
                }
            }
        }
        let has_window = handle.get_extension::<clack_extensions::gui::PluginGui>().is_some();
        out.push(serde_json::json!({
            "format": "clap", "path": path.to_string_lossy(), "id": id.to_string_lossy(), "hasWindow": has_window,
            "name": d.name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(),
            "vendor": d.vendor().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(),
            "kind": kind, "features": features, "params": params,
        }));
    }
    Ok(out)
}

/// A plugin as the schedule names it: its file, its id in that file, its saved state (base64 of
/// the plugin's own bytes) and parameter values (id, plain value or an envelope over song time).
#[derive(Deserialize, Clone, Debug)]
pub struct PluginSpec {
    /// "clap" or "vst3".
    #[serde(default = "clap_format")]
    pub format: String,
    pub path: String,
    pub id: String,
    #[serde(default)]
    pub params: Vec<(u32, crate::mix::schedule::Param)>,
    #[serde(default)]
    pub state: Option<String>,
    /// Song time (seconds) at the start of what it renders: an instrument's clip start (envelopes are in song time).
    #[serde(default)]
    pub at: f64,
    /// A track's controller lanes (R24), sent as MIDI: CC 0…127 or the pitch wheel. CLAP only.
    #[serde(default)]
    pub cc: Vec<CcLane>,
}

/// One controller lane: `cc` 0…127 (1 mod wheel, 7 volume, 11 expression, 64 sustain …) or 128 the pitch wheel;
/// `points` (song seconds, value: 0…1, the pitch wheel -1…1), straight lines between, held before and after.
#[derive(Deserialize, Clone, Debug)]
pub struct CcLane {
    pub cc: u16,
    pub points: Vec<[f64; 2]>,
}

/// How often (samples) a moving lane is sent again.
const CC_STEP: usize = 64;

impl CcLane {
    /// Its three MIDI bytes at song second `t` (channel 1).
    pub fn midi(&self, t: f64) -> [u8; 3] {
        let v = crate::instruments::expression::lane_at(&self.points, t);
        if self.cc >= 128 {
            let b = ((v.clamp(-1.0, 1.0) + 1.0) * 8192.0).round().clamp(0.0, 16383.0) as u16;
            [0xE0, (b & 0x7f) as u8, (b >> 7) as u8]
        } else {
            [0xB0, self.cc as u8, (v.clamp(0.0, 1.0) * 127.0).round() as u8]
        }
    }
}

/// The lanes' MIDI messages in the block [pos, pos + n) of a render starting at song second `at`: the value at the
/// render's start, then every CC_STEP samples where its bytes change. `last` keeps what each lane last sent.
pub fn cc_events(lanes: &[CcLane], last: &mut Vec<Option<[u8; 3]>>, at: f64, sr: f64, pos: usize, n: usize) -> Vec<(u32, [u8; 3])> {
    last.resize(lanes.len(), None);
    let mut out = vec![];
    for (k, lane) in lanes.iter().enumerate() {
        for o in (0..n).filter(|o| (pos + o) % CC_STEP == 0 || *o == 0) {
            let bytes = lane.midi(at + (pos + o) as f64 / sr);
            if last[k] != Some(bytes) {
                last[k] = Some(bytes);
                out.push((o as u32, bytes));
            }
        }
    }
    out.sort_by_key(|e| e.0);
    out
}

fn clap_format() -> String {
    "clap".into()
}

/// Loads a saved state (base64) into a plugin, before it is activated.
pub fn load_state(handle: &mut PluginMainThreadHandle, state: &str) -> Result<(), String> {
    let bytes = crate::plugins::params::unbase64(state)?;
    let ext = handle.get_extension::<PluginState>().ok_or("it cannot load a saved state (no CLAP state extension)")?;
    ext.load(handle, &mut bytes.as_slice()).map_err(|_| "it refused its saved state".to_string())
}

/// The plugin's state as it is now (base64 of its own bytes).
pub fn save_state(handle: &mut PluginMainThreadHandle) -> Result<String, String> {
    let ext = handle.get_extension::<PluginState>().ok_or("it cannot save its state (no CLAP state extension)")?;
    let mut bytes = vec![];
    ext.save(handle, &mut bytes).map_err(|_| "it would not save its state".to_string())?;
    Ok(crate::plugins::params::base64(&bytes))
}

/// A note for an instrument plugin: start and end (samples), MIDI key, velocity 0..1.
pub struct Note {
    pub start: usize,
    pub end: usize,
    pub key: u16,
    pub velocity: f64,
}
