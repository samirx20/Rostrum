//! What a clip holds and how it is read: its content (voices, an effect, a sample, media, speech),
//! speed, glitch, filter sweep, the master's time warps, and decoded audio on disk (PCM).

use serde::Deserialize;

fn unit() -> f64 {
    1.0
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Rate {
    pub from: f64,
    pub to: Option<f64>,
    pub preserve_pitch: bool,
    /// Warp markers, [source seconds from the clip's in-point, clip seconds] sorted by clip time: the
    /// time map instead of from / to (pitch kept).
    #[serde(default)]
    pub warp: Option<Vec<[f64; 2]>>,
    /// Pitch shift (semitones; cents as fractions), the duration kept.
    #[serde(default)]
    pub semitones: f64,
    /// Formants kept in place (None: they move with the pitch), shifted by this many semitones.
    #[serde(default)]
    pub formant: Option<f64>,
    /// "voice" (PSOLA) or "music" (Signalsmith); None: the engine listens for speech.
    #[serde(default)]
    pub content: Option<String>,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Glitch {
    pub stutter_rate: Option<f64>,
    pub repeats: Option<f64>,
    pub duration: Option<f64>,
    pub at_offset: Option<f64>,
    pub bitcrush: Option<f64>,
    pub pan_spread: Option<f64>,
    pub pitch_step: Option<f64>,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct FilterSweep {
    pub from_hz: Option<f64>,
    pub to_hz: Option<f64>,
    pub linear: bool,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct TimeWarp {
    pub start: f64,
    pub duration: f64,
    pub rate_from: Option<f64>,
    pub rate_to: Option<f64>,
    pub filter_hz: Option<f64>,
    pub sub_drop: bool,
}

/// Decoded audio on disk: raw little-endian f32, `channels` interleaved.
#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Pcm {
    pub file: String,
    pub channels: usize,
    pub frames: usize,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Material {
    pub base_freq: f64,
    pub ratios: Vec<f64>,
    pub decay: f64,
    pub noise_mix: f64,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct SpeechToken {
    pub punct: bool,
    pub weight: f64,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(tag = "kind", rename_all = "camelCase")]
pub enum Content {
    /// Notes, chords and drum hits.
    Score { voices: Vec<Voice> },
    /// A synthesized effect, or a material's foley (modes resolved by TypeScript).
    #[serde(rename_all = "camelCase")]
    Sfx { preset: String, material: Option<Material>, duration: f64, volume: f64, pitch: f64, pan_from: f64, pan_to: f64 },
    /// A recorded library take, played like tape (pitch is speed).
    #[serde(rename_all = "camelCase")]
    Sample { pcm: Pcm, duration: f64, volume: f64, pitch: f64, pan_from: f64, pan_to: f64 },
    /// A media file, decoded from its in-point (`rate` on the clip says how it is read).
    Media { pcm: Pcm },
    /// Synthesized speech (mono), through the voice chain.
    #[serde(rename_all = "camelCase")]
    Speech { pcm: Pcm, pitch_ratio: f64 },
    /// No speech synthesizer: a formant voice paced by the words.
    #[serde(rename_all = "camelCase")]
    VoiceSketch { tokens: Vec<SpeechToken>, base_f0: f64 },
    /// A placeholder tone shaped by a waveform outline.
    Waveform { peaks: Vec<f64> },
    Silence,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(tag = "kind", rename_all = "camelCase")]
pub enum Voice {
    /// cut (SFZ): seconds after its start it stops, a one-shot too (a recorded kit's hit written to stop; voices::cut_len).
    #[serde(rename_all = "camelCase")]
    Note { instrument: String, #[serde(default)] synth: Option<crate::instruments::synth::spec::SynthSpec>, #[serde(default)] sampler: Option<crate::instruments::sampler::SamplerSpec>, #[serde(default)] plugin: Option<crate::plugins::clap::PluginSpec>, #[serde(default)] sfz: Option<crate::instruments::sfz::SfzSpec>, freqs: Vec<f64>, start_idx: usize, duration: f64, velocity: f64, pan: f64, #[serde(default)] glide_from: Option<f64>, #[serde(default)] expression: Option<crate::instruments::expression::Expression>, #[serde(default)] variation: Option<crate::instruments::expression::Variation>, #[serde(default)] touch: Option<Touch>, #[serde(default)] cut: Option<f64> },
    /// tune: a pitch ratio; decay: a factor of the hit's length; cut: seconds after its start it stops (fading out over its last 10 ms), however long it would ring; sample: a one-shot played instead of the synthesized hit; model: a kit preset's synthesized hit (drumsynth.rs) instead of the classic kit's.
    #[serde(rename_all = "camelCase")]
    Drum { voice: String, start_idx: usize, velocity: f64, pan: f64, #[serde(default = "unit")] tune: f64, #[serde(default = "unit")] decay: f64, #[serde(default)] cut: Option<f64>, #[serde(default)] sample: Option<Pcm>, #[serde(default)] model: Option<crate::instruments::drumsynth::DrumModel> },
}

/// How a procedural instrument's note is played (model/): 0 soft … 1 hard (mallet, pick, stick), and
/// where it is struck or plucked (0 … 1: a bar's end to its middle, a string's bridge to its middle, a head's centre to its rim).
#[derive(Deserialize, Clone, Copy, Debug, Default)]
pub struct Touch {
    #[serde(default)]
    pub hardness: Option<f64>,
    #[serde(default)]
    pub position: Option<f64>,
    /// Plucked strings: 0 rings open … 1 muted.
    #[serde(default)]
    pub damping: Option<f64>,
}

impl Pcm {
    /// The samples, `channels` interleaved; a missing or short file is an error naming it.
    pub fn read(&self) -> Result<Vec<f32>, String> {
        let bytes = std::fs::read(&self.file).map_err(|e| format!("{}: {e}", self.file))?;
        let want = self.frames * self.channels;
        if bytes.len() < want * 4 {
            return Err(format!("{}: {} samples, the schedule expects {want}", self.file, bytes.len() / 4));
        }
        Ok(crate::mix::wavio::f32_le(&bytes[..want * 4]))
    }
}
