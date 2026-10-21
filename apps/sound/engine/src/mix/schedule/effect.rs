//! The effects a schedule names (src/core/soundDsl/effects.ts resolved every default): the inserts,
//! their parameters (a number or an envelope), spectral repairs and the tone match.

use serde::Deserialize;

/// A number, or an envelope [[seconds, value], …].
#[derive(Deserialize, Clone, Debug)]
#[serde(untagged)]
pub enum Param {
    Value(f64),
    Envelope(Vec<[f64; 2]>),
}

#[derive(Deserialize, Clone, Debug)]
pub struct EqBand {
    pub shape: String,
    pub freq: Param,
    pub gain: Param,
    pub q: Param,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(tag = "type", rename_all = "camelCase")]
pub enum Effect {
    Eq { bands: Vec<EqBand> },
    Compressor { threshold: Param, ratio: Param, attack: f64, release: f64, makeup: Param, knee: f64 },
    #[serde(rename_all = "camelCase")]
    Delay { time: f64, feedback: Param, mix: Param, ping_pong: bool, damp: f64 },
    /// `space` "freeverb.<space>": the Freeverb form, which `decay` (s, RT60), `damping` (0 … 1) and `size` (0 … 1) tune.
    Reverb { space: String, mix: Param, #[serde(default)] decay: Option<f64>, #[serde(default)] damping: Option<f64>, #[serde(default)] size: Option<f64> },
    Saturate { drive: Param, mix: Param },
    /// Tape: wow, flutter, age (0 … 1 each).
    Tape { wow: Param, flutter: Param, age: Param },
    Limiter { ceiling: f64, release: f64 },
    /// Stereo width: 0 mono, 1 as it is, 2 wider; the side under `mono_below` Hz kept as it is (stereo.rs).
    #[serde(rename_all = "camelCase")]
    Width { width: Param, mono_below: f64 },
    /// An impulse response: built in (generated) or a decoded file.
    Convolution { ir: crate::fx::convolve::Ir, mix: Param },
    /// A CLAP / VST3 effect plugin.
    Plugin { plugin: crate::plugins::clap::PluginSpec },
    /// Dialogue repair (dynamics.rs, lsar.rs, dehum.rs, dereverb.rs); TypeScript resolved every default.
    /// De-esser: the band above `freq` cut while sibilance passes `threshold` (dB), at most `range` dB.
    Deess { freq: f64, threshold: f64, range: f64 },
    /// Noise gate / downward expander: below `threshold` (dB) the level falls `ratio`:1, at most `range` dB.
    Gate { threshold: f64, ratio: f64, range: f64, attack: f64, hold: f64, release: f64 },
    /// Dialogue leveller: rides speech to `target` (LUFS, 400 ms), pauses under `floor` held.
    #[serde(rename_all = "camelCase")]
    Leveller { target: f64, max_gain: f64, max_cut: f64, speed: f64, floor: f64 },
    /// Hum removal: notches on `freq` (0: found in the clip) and its harmonics, following its drift.
    Dehum { freq: f64, harmonics: usize, width: f64 },
    /// Clipped runs (at `threshold` × the peak or above) re-drawn by AR interpolation.
    Declip { threshold: f64 },
    /// Clicks (AR-residual impulses up to `max_length` ms) interpolated away.
    #[serde(rename_all = "camelCase")]
    Declick { sensitivity: f64, max_length: f64 },
    /// Late-reverb suppression: `amount` 0 … 1, at most `reduction` dB, room decay `time` s (0: measured).
    Dereverb { amount: f64, reduction: f64, time: f64 },
}

/// A time–frequency region of a clip to remove (clip seconds, Hz), filled in from around it.
#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Repair {
    pub at: f64,
    pub duration: f64,
    pub low_hz: f64,
    pub high_hz: f64,
}

/// A tone-matching EQ curve ([Hz, dB] points, measured once on the host and stored in the document).
#[derive(Deserialize, Clone, Debug)]
pub struct CurveEq {
    pub curve: Vec<[f64; 2]>,
    /// "linear" or "minimum".
    pub phase: String,
}
