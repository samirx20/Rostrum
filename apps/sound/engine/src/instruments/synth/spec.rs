//! A synth's settings as the schedule carries them (src/core/soundDsl/instruments/synth.ts decides them): the
//! oscillators, filter, envelopes, LFO, pitch envelope and analog character, and the envelope shapes.

use std::f64::consts::PI;

use serde::Deserialize;

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct SynthSpec {
    pub wave: String,
    pub voices: usize,
    pub detune: f64,
    pub cutoff: f64,
    pub resonance: f64,
    pub env_amount: f64,
    pub attack: f64,
    pub decay: f64,
    pub sustain: f64,
    pub release: f64,
    pub octave: f64,
    /// Seconds a note slides from the previous note's pitch (TypeScript says from where: `glide_from`).
    #[serde(default)]
    pub glide: f64,
    /// Octaves a soft note's filter closes (full velocity: the cutoff as set).
    #[serde(default)]
    pub filter_velocity: f64,
    /// Saturation after the filter: 0 clean … 10 hard.
    #[serde(default)]
    pub drive: f64,
    #[serde(default)]
    pub lfo: Option<Lfo>,
    /// The filter's own envelope (else it follows the amplitude envelope).
    #[serde(default)]
    pub filter_env: Option<Adsr>,
    /// Each note starts `semitones` above its pitch and falls to it with time constant `time` (an 808's punch).
    #[serde(default)]
    pub pitch_env: Option<PitchEnv>,
    /// Output level, dB (presets balance their sound against each other with it).
    #[serde(default)]
    pub level: f64,
    /// How far the oscillators spread across the stereo field: 1 full (a supersaw), 0 mono (a bass).
    #[serde(default = "full")]
    pub width: f64,
    /// Cents each oscillator wanders (analog.rs); every note then starts at fresh phases.
    #[serde(default)]
    pub drift: f64,
    /// Noise mixed in before the filter (0 … 1 of the oscillators' level).
    #[serde(default)]
    pub noise: f64,
    /// A sine an octave below (0 … 1 of the oscillators' level).
    #[serde(default)]
    pub sub: f64,
    /// "analog": decay and release fall exponentially; else in straight lines.
    #[serde(default)]
    pub curve: String,
}

fn full() -> f64 {
    1.0
}

#[derive(Deserialize, Clone, Debug)]
pub struct PitchEnv {
    pub semitones: f64,
    pub time: f64,
}

#[derive(Deserialize, Clone, Debug)]
pub struct Adsr {
    pub attack: f64,
    pub decay: f64,
    pub sustain: f64,
    pub release: f64,
}

/// One LFO, from the note's start: `rate` in Hz (TypeScript resolves note lengths), moving pitch
/// (cents), cutoff (octaves) and level (0…1), faded in over `delay` seconds.
#[derive(Deserialize, Clone, Debug)]
pub struct Lfo {
    pub wave: String,
    pub rate: f64,
    pub pitch: f64,
    pub cutoff: f64,
    pub amp: f64,
    pub delay: f64,
}

impl Lfo {
    pub(super) fn at(&self, t: f64) -> f64 {
        let p = (t * self.rate).fract();
        let v = match self.wave.as_str() {
            "triangle" => 1.0 - 4.0 * (p - 0.5).abs(),
            "square" => {
                if p < 0.5 {
                    1.0
                } else {
                    -1.0
                }
            }
            "saw" => 2.0 * p - 1.0,
            _ => (2.0 * PI * p).sin(),
        };
        v * if self.delay > 0.0 { (t / self.delay).min(1.0) } else { 1.0 }
    }
}

impl Adsr {
    /// The level at `t` for a note held `dur` seconds: attack, decay to sustain, release after.
    pub fn at(&self, t: f64, dur: f64) -> f64 {
        let held = |t: f64| {
            if t < self.attack {
                t / self.attack.max(1e-6)
            } else if t < self.attack + self.decay {
                1.0 - (1.0 - self.sustain) * (t - self.attack) / self.decay.max(1e-6)
            } else {
                self.sustain
            }
        };
        if t <= dur {
            held(t)
        } else {
            let from = held(dur);
            (from * (1.0 - (t - dur) / self.release.max(1e-6))).max(0.0)
        }
    }
}

impl SynthSpec {
    /// The amplitude envelope at `t` for a note held `dur` seconds.
    pub fn envelope(&self, t: f64, dur: f64) -> f64 {
        self.shaped(&Adsr { attack: self.attack, decay: self.decay, sustain: self.sustain, release: self.release }, t, dur)
    }

    /// An envelope as this spec's curve shapes it.
    pub(super) fn shaped(&self, e: &Adsr, t: f64, dur: f64) -> f64 {
        if self.curve == "analog" { crate::instruments::analog::analog_env(t, dur, e.attack, e.decay, e.sustain, e.release) } else { e.at(t, dur) }
    }
}
