//! A layered instrument played live (cinematic.* presets, `{ layers }`): each layer is an instrument
//! of its own with what src/core/soundDsl/instruments/layers.ts gives it in the mix — a velocity gate and curve,
//! a transpose, an onset delay with a seeded jitter, its gain and pan (the track's equal-power law)
//! and its inserts (livefx.rs). The mix plays each layer as a track; live, the same layers sum here.

use std::sync::mpsc::{channel, Sender};

use serde::Deserialize;

use crate::live::instrument::{Event, Instrument, LiveSpec};
use crate::fx::livefx::LiveFx;

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct LiveLayer {
    pub name: String,
    pub instrument: LiveSpec,
    pub gain: f64,
    pub pan: f64,
    pub delay_ms: f64,
    pub jitter_ms: f64,
    pub velocity: [f64; 2],
    pub min_velocity: f64,
    pub transpose: i32,
    #[serde(default)]
    pub effects: Vec<crate::mix::schedule::Effect>,
}

pub struct Layer {
    spec: LiveLayer,
    inst: Instrument,
    tx: Sender<Event>,
    fx: LiveFx,
    /// Events waiting for their delay: (frame due, event).
    queue: Vec<(u64, Event)>,
    /// Keys sounding on this layer (struck key → the key it plays), so a release finds a transposed note.
    down: Vec<(u8, u8)>,
    strikes: u64,
    gains: [f32; 2],
    scratch: Vec<f32>,
    l: Vec<f32>,
    r: Vec<f32>,
}

impl Layer {
    pub fn new(spec: &LiveLayer, rate: u32) -> Result<Layer, String> {
        let who = |e: String| format!("layer \"{}\": {e}", spec.name);
        let (tx, rx) = channel();
        // The layer's own reports (heard, notes) are the parent's to make: its channel is dropped.
        let (rtx, _) = channel();
        let inst = Instrument::new(&LiveSpec { volume: 1.0, ..spec.instrument.clone() }, rate, rx, rtx).map_err(who)?;
        let fx = LiveFx::new(&spec.effects, rate as f64).map_err(who)?;
        let a = (spec.pan.clamp(-1.0, 1.0) + 1.0) * std::f64::consts::PI / 4.0;
        let g = spec.gain * std::f64::consts::SQRT_2;
        Ok(Layer { spec: spec.clone(), inst, tx, fx, queue: vec![], down: vec![], strikes: 0, gains: [(g * a.cos()) as f32, (g * a.sin()) as f32], scratch: vec![], l: vec![], r: vec![] })
    }

    /// The layer's onset delay for a strike: its delay plus a seeded jitter (−1 … 1 of `jitterMs`).
    fn delay(&self, frame: u64, rate: f64) -> u64 {
        let j = crate::instruments::voices::fast_noise(self.strikes as f64 * 7.31 + self.spec.delay_ms);
        frame + (((self.spec.delay_ms + self.spec.jitter_ms * j).max(0.0)) / 1000.0 * rate) as u64
    }

    pub fn on(&mut self, key: u8, velocity: f64, frame: u64, rate: f64) {
        self.strikes += 1;
        if velocity < self.spec.min_velocity {
            return;
        }
        let [lo, hi] = self.spec.velocity;
        let to = (key as i32 + self.spec.transpose).clamp(0, 127) as u8;
        self.down.retain(|d| d.0 != key);
        self.down.push((key, to));
        let due = self.delay(frame, rate);
        self.queue.push((due, Event::On { key: to, velocity: (lo + (hi - lo) * velocity).clamp(0.0, 1.0), at: 0.0 }));
    }

    pub fn off(&mut self, key: u8, frame: u64, rate: f64) {
        if let Some(i) = self.down.iter().position(|d| d.0 == key) {
            let (_, to) = self.down.remove(i);
            let due = frame + (self.spec.delay_ms / 1000.0 * rate) as u64;
            self.queue.push((due, Event::Off { key: to }));
        }
    }

    #[cfg(test)]
    pub fn voices(&self) -> usize {
        self.inst.voices()
    }

    /// Adds this block of the layer into `out` (stereo interleaved, first frame `start`).
    pub fn fill(&mut self, out: &mut [f32], start: u64) {
        let frames = out.len() / 2;
        let end = start + frames as u64;
        let mut k = 0;
        while k < self.queue.len() {
            if self.queue[k].0 < end {
                let _ = self.tx.send(self.queue.remove(k).1);
            } else {
                k += 1;
            }
        }
        self.scratch.clear();
        self.scratch.resize(out.len(), 0.0);
        crate::live::wasapi::Source::fill(&mut self.inst, &mut self.scratch, start);
        self.l.clear();
        self.r.clear();
        self.l.extend(self.scratch.iter().step_by(2));
        self.r.extend(self.scratch.iter().skip(1).step_by(2));
        self.fx.process(&mut self.l, &mut self.r);
        for f in 0..frames {
            out[f * 2] += self.l[f] * self.gains[0];
            out[f * 2 + 1] += self.r[f] * self.gains[1];
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::live::instrument::{Event, Instrument, LiveSpec};
    use crate::live::wasapi::Source;

    fn block_peaks(inst: &mut Instrument, etx: &std::sync::mpsc::Sender<Event>, blocks: usize, on_at: usize) -> Vec<f32> {
        let mut out = vec![];
        for b in 0..blocks {
            if b == on_at {
                etx.send(Event::On { key: 60, velocity: 0.9, at: 0.0 }).unwrap();
            }
            let mut block = vec![0f32; 288];
            inst.fill(&mut block, (b * 144) as u64);
            out.push(block.iter().fold(0f32, |m, v| m.max(v.abs())));
        }
        out
    }

    #[test]
    fn layers_sound_together_with_their_delay_gate_and_inserts() {
        let synth = r#"{"synth":{"wave":"saw","voices":1,"detune":0,"cutoff":3000,"resonance":0.1,"envAmount":0,"attack":0.001,"decay":0.1,"sustain":0.8,"release":0.05,"octave":0}}"#;
        let spec: LiveSpec = serde_json::from_str(&format!(
            r#"{{"layers":[{{"name":"a","instrument":{synth},"gain":1,"pan":-0.2,"delayMs":0,"jitterMs":0,"velocity":[0,1],"minVelocity":0,"transpose":0,"effects":[{{"type":"eq","bands":[{{"shape":"lowpass","freq":1500,"gain":0,"q":0.707}}]}}]}},
                {{"name":"b","instrument":{synth},"gain":0.5,"pan":0.2,"delayMs":30,"jitterMs":0,"velocity":[0.5,0.8],"minVelocity":0,"transpose":12}},
                {{"name":"gated","instrument":{synth},"gain":1,"pan":0,"delayMs":0,"jitterMs":0,"velocity":[0,1],"minVelocity":0.95,"transpose":0}}],"volume":0.8}}"#
        ))
        .unwrap();
        let (etx, erx) = std::sync::mpsc::channel();
        let (rtx, _rrx) = std::sync::mpsc::channel();
        let mut inst = Instrument::new(&spec, 48000, erx, rtx).unwrap();
        let peaks = block_peaks(&mut inst, &etx, 40, 2);
        assert_eq!(peaks[1], 0.0);
        assert!(peaks[3] > 0.01, "the first layer sounds at once");
        // Two layers once the 30 ms (10 blocks of 3 ms) delay has passed; the gated one never (velocity 0.9 < 0.95).
        assert_eq!(inst.voices(), 2);
        let bad: LiveSpec = serde_json::from_str(&format!(r#"{{"layers":[{{"name":"x","instrument":{synth},"gain":1,"pan":0,"delayMs":0,"jitterMs":0,"velocity":[0,1],"minVelocity":0,"transpose":0,"effects":[{{"type":"delay","time":0.25,"feedback":0.3,"mix":0.2,"pingPong":false,"damp":6000}}]}}]}}"#)).unwrap();
        let (_e, erx) = std::sync::mpsc::channel();
        let (rtx, _r) = std::sync::mpsc::channel();
        let err = Instrument::new(&bad, 48000, erx, rtx).err().unwrap();
        assert!(err.contains("layer \"x\"") && err.contains("delay"), "{err}");
    }
}
