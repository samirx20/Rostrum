//! A plugin instrument played live (`rostrum live`, the transport's overdub `rostrum play --track`):
//! the same session code as the plugin's window (session.rs: clap/session.rs / vst3/session.rs),
//! opened with the document's state, preset and fixed parameter values, without a window. The
//! session lives on the main thread (CLAP and VST3 want their main-thread calls there: activation,
//! idle callbacks, closing); the audio thread plays the activated processor from a shared slot.

use std::sync::{Arc, Mutex};

use crate::plugins::session::{Note, Proc, Session, SessionSpec};

/// The activated processor, shared between the main thread (activates, closes) and the audio thread (plays).
#[derive(Clone, Default)]
pub struct Slot(pub Arc<Mutex<Option<Box<dyn Proc>>>>);

impl std::fmt::Debug for Slot {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("Slot")
    }
}

/// The main-thread half.
pub struct LivePlugin {
    session: Box<dyn Session>,
    slot: Slot,
}

impl LivePlugin {
    pub fn open(spec: &crate::plugins::clap::PluginSpec) -> Result<LivePlugin, String> {
        let session = crate::plugins::session::open(&SessionSpec { plugin: spec.clone(), effect: false, preset: None, title: None, input: None })?;
        Ok(LivePlugin { session, slot: Slot::default() })
    }

    /// What the instrument plays from (LiveSpec `slot`).
    pub fn slot(&self) -> Slot {
        self.slot.clone()
    }

    /// Activates at the stream's rate; the audio thread hears it from the next block.
    pub fn activate(&mut self, rate: u32) -> Result<(), String> {
        let proc = self.session.activate(rate as f64, 8192)?;
        *self.slot.0.lock().map_err(|_| "the plugin's slot was poisoned")? = Some(proc);
        Ok(())
    }

    /// Main-thread work the plugin asked for (call every few milliseconds).
    pub fn idle(&mut self) {
        crate::plugins::window::pump_messages();
        self.session.idle(None);
    }

    /// Deactivates and closes (after the stream has stopped).
    pub fn close(mut self) {
        let proc = self.slot.0.lock().ok().and_then(|mut s| s.take());
        self.session.close(proc);
    }
}

/// The audio-thread half: notes gathered for the next block, the plugin's output added.
pub struct PluginVoice {
    slot: Slot,
    notes: Vec<Note>,
    bufs: [Vec<f32>; 4],
}

impl PluginVoice {
    pub fn new(slot: Slot) -> PluginVoice {
        PluginVoice { slot, notes: vec![], bufs: Default::default() }
    }

    pub fn on(&mut self, key: u8, velocity: f64) {
        self.notes.push((0, key, velocity.max(1e-3)));
    }

    pub fn off(&mut self, key: u8) {
        self.notes.push((0, key, 0.0));
    }

    /// Adds the plugin's block into `out` (interleaved stereo). An error drops the plugin (it is reported once).
    pub fn fill(&mut self, out: &mut [f32]) -> Result<(), String> {
        let frames = out.len() / 2;
        for b in self.bufs.iter_mut() {
            b.clear();
            b.resize(frames, 0.0);
        }
        let notes = std::mem::take(&mut self.notes);
        let Ok(mut slot) = self.slot.0.lock() else { return Ok(()) };
        let Some(p) = slot.as_mut() else { return Ok(()) }; // not activated yet
        let [il, ir, ol, or] = &mut self.bufs;
        if let Err(e) = p.process((il, ir), (ol, or), &notes) {
            *slot = None;
            return Err(format!("the plugin stopped: {e}"));
        }
        for f in 0..frames {
            out[f * 2] += ol[f];
            out[f * 2 + 1] += or[f];
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use crate::live::instrument::{Event, Instrument, LiveSpec};
    use crate::live::wasapi::Source;

    /// Surge XT played as a live instrument: silent until a key, sounding while held, and the note
    /// recorded where it was heard (as every live instrument).
    #[test]
    fn a_plugin_instrument_plays_live_from_the_documents_spec() {
        let Some(path) = crate::plugins::clap::folders().into_iter().map(|d| d.join("Surge XT.clap")).find(|p| p.exists()) else {
            return eprintln!("Surge XT not installed: skipped");
        };
        let mut spec: LiveSpec = serde_json::from_value(serde_json::json!({ "plugin": { "path": path.to_string_lossy(), "id": "org.surge-synth-team.surge-xt" }, "volume": 0.8 })).unwrap();
        let mut live = super::LivePlugin::open(spec.plugin.as_ref().unwrap()).unwrap();
        spec.slot = Some(live.slot());
        let (etx, erx) = std::sync::mpsc::channel();
        let (rtx, rrx) = std::sync::mpsc::channel();
        let mut inst = Instrument::new(&spec, 48000, erx, rtx).unwrap();
        live.activate(48000).unwrap();
        let mut frame = 0u64;
        let mut run = |inst: &mut Instrument, n: usize| -> f32 {
            let mut peak = 0f32;
            for _ in 0..n {
                let mut block = vec![0f32; 512];
                inst.fill(&mut block, frame);
                frame += 256;
                peak = block.iter().fold(peak, |m, s| m.max(s.abs()));
            }
            peak
        };
        assert!(run(&mut inst, 10) < 1e-4, "silent before a key");
        etx.send(Event::On { key: 60, velocity: 0.9, at: 0.0 }).unwrap();
        assert!(run(&mut inst, 40) > 0.01, "a held key sounds");
        etx.send(Event::Off { key: 60 }).unwrap();
        run(&mut inst, 2);
        drop(inst);
        live.close();
        let notes: Vec<_> = rrx.try_iter().filter_map(|r| if let crate::live::instrument::Report::Note { key, start, end, .. } = r { Some((key, start, end)) } else { None }).collect();
        assert_eq!(notes, vec![(60, 2560, 2560 + 40 * 256)]);
    }

    #[test]
    fn a_plugin_inside_layers_or_without_its_session_is_refused() {
        let (_e, erx) = std::sync::mpsc::channel();
        let (rtx, _r) = std::sync::mpsc::channel();
        let spec: LiveSpec = serde_json::from_value(serde_json::json!({ "plugin": { "path": "x.clap", "id": "x" } })).unwrap();
        assert!(Instrument::new(&spec, 48000, erx, rtx).is_err());
    }
}
