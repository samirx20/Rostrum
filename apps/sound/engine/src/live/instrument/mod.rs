//! A playable instrument (S3): notes played live (a MIDI keyboard, the app's keyboard, a test) on
//! the same voices a score renders — the synth voice, the SoundFont sampler, the drum kit. TypeScript
//! resolves the instrument (src/engine/sound/live/liveInstrument.ts); this plays it. Events apply at the
//! start of the next block, and every note is recorded at the frame it was heard, so a recording
//! lands where the player heard it. Built-in named instruments shape a note by its length (known in
//! a score, not while a key is held), so they are refused live rather than sounding different.
//! SFZ instruments play from samples decoded up front (sfz.rs `preload`); a layered instrument
//! plays each layer as an instrument of its own (layers.rs). Past MAX_VOICES the oldest released
//! voice (else the oldest) is stolen with a 5 ms fade, never cut.

mod keys;
mod source;
#[cfg(test)]
mod tests;

use std::sync::mpsc::{Receiver, Sender};

use serde::Deserialize;

use crate::instruments::sampler::SamplerSpec;
use crate::instruments::synth::spec::SynthSpec;
use crate::instruments::synth::SynthVoice;

#[derive(Deserialize, Clone, Debug)]
pub struct LiveSpec {
    #[serde(default)]
    pub synth: Option<SynthSpec>,
    #[serde(default)]
    pub sampler: Option<SamplerSpec>,
    /// A drum kit: MIDI key → the kit's voice (TypeScript's map, liveInstrument.ts LIVE_DRUM_KEYS).
    #[serde(default)]
    pub drums: Option<std::collections::HashMap<String, String>>,
    /// Each voice's tuning, decay, level and one-shot (TypeScript's kitVoice).
    #[serde(default)]
    pub kit: std::collections::HashMap<String, KitVoice>,
    /// An SFZ articulation (a sampled instrument: sfz.rs), played from its preloaded samples.
    #[serde(default)]
    pub sfz: Option<crate::instruments::sfz::SfzSpec>,
    /// A layered instrument: each layer an instrument of its own (layers.rs).
    #[serde(default)]
    pub layers: Option<Vec<crate::live::layers::LiveLayer>>,
    /// A plugin instrument (plugins/live.rs): the document's plugin, state and fixed values.
    #[serde(default)]
    pub plugin: Option<crate::plugins::clap::PluginSpec>,
    /// Where its activated processor will be (set by the main thread that opened it).
    #[serde(skip)]
    pub slot: Option<crate::plugins::live::Slot>,
    #[serde(default = "one")]
    pub volume: f64,
}
fn one() -> f64 {
    1.0
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct KitVoice {
    pub tune: f64,
    pub decay: f64,
    pub level: f64,
    #[serde(default)]
    pub sample: Option<crate::mix::schedule::Pcm>,
    /// The one-shot's own rate (it plays at the device's).
    #[serde(default)]
    pub sample_rate: Option<f64>,
    /// A kit preset's synthesized hit (drumsynth.rs).
    #[serde(default)]
    pub model: Option<crate::instruments::drumsynth::DrumModel>,
}

#[derive(Clone, Copy, Debug)]
pub enum Event {
    On { key: u8, velocity: f64, at: f64 },
    Off { key: u8 },
}

pub enum Report {
    /// A finished note: frames since the stream started.
    Note { key: u8, velocity: f64, start: u64, end: u64 },
    /// A note-on reached the speaker `latency` seconds after its event.
    Heard { key: u8, latency: f64, queue: f64 },
    /// A key the drum kit has no voice for.
    Ignored { key: u8 },
    /// Something could not play (a one-shot that cannot be read).
    Failed { what: String },
}

enum Kind {
    Synth(SynthSpec),
    Sampler(rustysynth::Synthesizer, i32),
    Drums(std::collections::HashMap<String, String>, std::collections::HashMap<String, KitVoice>),
    /// Regions, their preloaded samples, legato, how often each key has been struck (round robin), and the half steps
    /// the file's keys sit above the key played (SfzSpec key_offset).
    Sfz(std::sync::Arc<Vec<crate::instruments::sfz::Region>>, std::collections::HashMap<std::path::PathBuf, std::sync::Arc<crate::instruments::sfz::Sample>>, bool, std::collections::HashMap<u8, u32>, i8),
    Layers(Vec<crate::live::layers::Layer>),
    Plugin(crate::plugins::live::PluginVoice),
}

/// A sounding synth note or drum hit: its voice, the sample it is at, the key holding it.
enum Playing {
    Synth { key: u8, voice: SynthVoice, i: usize, held: bool },
    Drum { voice: crate::instruments::voices::Voice, i: usize },
    Sfz { key: u8, voice: crate::instruments::sfz::SfzVoice },
}

impl Playing {
    /// The next frame, or None once the voice has finished.
    fn tick(&mut self) -> Option<(f64, f64)> {
        match self {
            Playing::Synth { voice, i, .. } => {
                if *i >= voice.len() {
                    return None;
                }
                *i += 1;
                Some(voice.next(*i - 1))
            }
            Playing::Drum { voice, i } => {
                if *i >= voice.len {
                    return None;
                }
                *i += 1;
                Some(voice.next(*i - 1))
            }
            Playing::Sfz { voice, .. } => voice.next().map(|(l, r)| (l as f64, r as f64)),
        }
    }
    fn held(&self) -> bool {
        match self {
            Playing::Synth { held, .. } => *held,
            Playing::Sfz { voice, .. } => voice.held(),
            Playing::Drum { .. } => false,
        }
    }
}

pub struct Instrument {
    kind: Kind,
    rate: f64,
    volume: f32,
    playing: Vec<Playing>,
    /// Stolen voices fading out: frames of the fade left.
    stolen: Vec<(Playing, u32)>,
    events: Receiver<Event>,
    reports: Sender<Report>,
    /// Keys down: (key, velocity, frame it started).
    down: Vec<(u8, f64, u64)>,
    /// Note-ons in the block just written: (key, event time) — `heard` turns them into latencies.
    pending: Vec<(u8, f64, f64)>,
    scratch: (Vec<f32>, Vec<f32>),
    /// The last note played: where a gliding synth slides from.
    last_freq: Option<f64>,
}

const MAX_VOICES: usize = 64;

impl Instrument {
    pub fn new(spec: &LiveSpec, rate: u32, events: Receiver<Event>, reports: Sender<Report>) -> Result<Instrument, String> {
        if spec.plugin.is_some() {
            let others = spec.synth.is_some() || spec.sampler.is_some() || spec.drums.is_some() || spec.sfz.is_some() || spec.layers.is_some();
            // Its session is opened on the main thread (live/perform.rs, live/play.rs); a plugin inside a layered instrument has none.
            let slot = spec.slot.clone().filter(|_| !others).ok_or("a plugin instrument plays live on its own (not as a layer, not with another instrument)")?;
            return Ok(Instrument::with_kind(Kind::Plugin(crate::plugins::live::PluginVoice::new(slot)), spec, rate, events, reports));
        }
        let kind = match (&spec.synth, &spec.sampler, &spec.drums, &spec.sfz, &spec.layers) {
            (Some(s), None, None, None, None) => Kind::Synth(s.clone()),
            (None, Some(s), None, None, None) => {
                let (synth, ch) = crate::instruments::sampler::synthesizer(s, rate as f64)?;
                Kind::Sampler(synth, ch)
            }
            (None, None, Some(keys), None, None) => Kind::Drums(keys.clone(), spec.kit.clone()),
            (None, None, None, Some(s), None) => {
                if s.swell {
                    return Err(format!("{}: a swell shapes each note by its length (known in a score, not while a key is held); play the plain articulation live", s.file));
                }
                let (regions, samples) = crate::instruments::sfz::preload(&s.file)?;
                Kind::Sfz(regions, samples, s.legato, Default::default(), s.key_offset)
            }
            (None, None, None, None, Some(layers)) => Kind::Layers(layers.iter().map(|l| crate::live::layers::Layer::new(l, rate)).collect::<Result<_, String>>()?),
            _ => return Err("a live instrument is exactly one of { synth }, { sampler }, { drums: { key: voice } }, { sfz }, { layers } or { plugin }".into()),
        };
        Ok(Instrument::with_kind(kind, spec, rate, events, reports))
    }

    fn with_kind(kind: Kind, spec: &LiveSpec, rate: u32, events: Receiver<Event>, reports: Sender<Report>) -> Instrument {
        Instrument { kind, rate: rate as f64, volume: spec.volume as f32, playing: Vec::with_capacity(MAX_VOICES), stolen: vec![], events, reports, down: vec![], pending: vec![], scratch: (vec![], vec![]), last_freq: None }
    }
}
