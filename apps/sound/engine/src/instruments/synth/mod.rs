//! The synth voice (src/core/soundDsl/instruments/synth.ts decides its settings): band-limited oscillators
//! (PolyBLEP saw / square, triangle, sine), several of them detuned around the pitch and spread
//! across the stereo field, through a resonant low-pass (a TPT state-variable filter) whose cutoff
//! the envelope sweeps by `env_amount` octaves, shaped by an ADSR amplitude envelope. Optional:
//! a filter envelope of its own (the acid squelch), velocity opening the filter, glide from the
//! previous note (portamento), an LFO on pitch / cutoff / level, and drive (saturation) after the filter.
//! Analog character (analog.rs, off unless asked): drift, noise, a sub oscillator, exponential envelopes.

pub mod spec;
#[cfg(test)]
mod tests;

use std::f64::consts::PI;

use spec::SynthSpec;

/// The PolyBLEP correction for a discontinuity at phase 0 (phase `p` in 0..1, increment `dt`).
fn blep(p: f64, dt: f64) -> f64 {
    if p < dt {
        let x = p / dt;
        2.0 * x - x * x - 1.0
    } else if p > 1.0 - dt {
        let x = (p - 1.0) / dt;
        x * x + 2.0 * x + 1.0
    } else {
        0.0
    }
}

fn osc(wave: &str, p: f64, dt: f64) -> f64 {
    match wave {
        "sine" => (2.0 * PI * p).sin(),
        "triangle" => 1.0 - 4.0 * (p - 0.5).abs(),
        "square" => {
            let naive = if p < 0.5 { 1.0 } else { -1.0 };
            naive + blep(p, dt) - blep((p + 0.5) % 1.0, dt)
        }
        _ => 2.0 * p - 1.0 - blep(p, dt), // saw
    }
}

/// A phase in 0..1 that no other index's is related to (splitmix64 of the index).
fn unrelated(k: u64) -> f64 {
    let mut z = k.wrapping_add(1).wrapping_mul(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    (z ^ (z >> 31)) as f64 / u64::MAX as f64
}

/// A note's seed from its start sample and pitch (Hz): a score's note and the same note played live
/// (started at the frame it was heard and recorded) take the same drift, starting phases and noise.
pub fn note_seed(start: u64, freq: f64) -> u64 {
    start << 8 ^ (freq * 16.0) as u64
}

pub struct SynthVoice {
    spec: SynthSpec,
    sr: f64,
    dur: f64,
    gain: f64,
    velocity: f64,
    /// The oscillators' summed level (their weights' root sum of squares): drive saturates relative to it.
    norm: f64,
    /// Gliding: the previous note's pitch over this one's.
    glide_from: Option<f64>,
    /// The note's own glide, vibrato and shape.
    expression: Option<crate::instruments::expression::Expression>,
    oscs: Vec<(f64, f64, f64, f64)>, // phase, increment, gain left, gain right
    ic: [[f64; 2]; 2],               // filter state per channel
    analog: Option<crate::instruments::analog::Analog>,
}

impl SynthVoice {
    pub fn new(spec: &SynthSpec, freq: f64, dur: f64, velocity: f64, pan: f64, sr: f64) -> SynthVoice {
        let n = spec.voices.max(1);
        let f = freq * 2f64.powf(spec.octave);
        // Evenly spaced detunes with evenly spaced starting phases line the oscillators up on one
        // harmonic after another as they drift (a comb sweeping up the series: a "laser" on held
        // notes). So the spacing is uneven (|u|^1.5, as hardware supersaws do) and each oscillator
        // starts at an unrelated phase (a hash of its index: the same every render).
        let oscs = (0..n)
            .map(|k| {
                let u = if n > 1 { k as f64 / (n - 1) as f64 - 0.5 } else { 0.0 };
                let cents = u.signum() * (2.0 * u.abs()).powf(1.5) * 0.5 * spec.detune;
                let spread = (pan + u * 1.6 * spec.width).clamp(-1.0, 1.0);
                let a = (spread + 1.0) * PI / 4.0;
                let phase = if n > 1 { unrelated(k as u64) } else { 0.0 };
                // The centre oscillators louder than the outer ones, so the fundamental never cancels out.
                let weight = 1.0 - 0.45 * (2.0 * u.abs());
                (phase, f * 2f64.powf(cents / 1200.0) / sr, a.cos() * weight, a.sin() * weight)
            })
            .collect();
        // Loudness of uncorrelated oscillators adds as power: normalise by the weights' root sum of squares.
        let power: f64 = (0..n).map(|k| { let u = if n > 1 { k as f64 / (n - 1) as f64 - 0.5 } else { 0.0 }; (1.0 - 0.45 * (2.0 * u.abs())).powi(2) }).sum();
        SynthVoice { spec: spec.clone(), sr, dur, gain: velocity * 0.32 / power.sqrt() * 10f64.powf(spec.level / 20.0), velocity, norm: power.sqrt(), glide_from: None, expression: None, oscs, ic: [[0.0; 2]; 2], analog: None }.seeded(0)
    }

    /// The note's own seed (its start and pitch): an analog voice's drift and starting phases.
    pub fn seeded(mut self, seed: u64) -> SynthVoice {
        self.analog = crate::instruments::analog::Analog::new(self.spec.drift, self.spec.noise, self.spec.sub, self.oscs.len(), seed);
        if let Some(a) = &self.analog {
            for (k, o) in self.oscs.iter_mut().enumerate() {
                o.0 = a.phase(k, o.0);
            }
        }
        self
    }

    /// The note slides from `from` Hz to its own pitch `to` over the spec's glide time.
    pub fn gliding_from(mut self, from: f64, to: f64) -> SynthVoice {
        if self.spec.glide > 0.0 && from > 0.0 && to > 0.0 {
            self.glide_from = Some(from / to);
        }
        self
    }

    /// The note's own expression (glide, vibrato, shape) on top of the spec's.
    pub fn with_expression(mut self, e: Option<crate::instruments::expression::Expression>) -> SynthVoice {
        self.expression = e;
        self
    }

    /// A held note (played live, length unknown) ends at sample `i`: its release starts there.
    pub fn release(&mut self, i: usize) {
        self.dur = i as f64 / self.sr;
    }

    /// Samples the voice sounds for: the note and its release.
    pub fn len(&self) -> usize {
        ((self.dur + self.spec.release) * self.sr).ceil() as usize
    }

    pub fn next(&mut self, i: usize) -> (f64, f64) {
        let t = i as f64 / self.sr;
        let env = self.spec.envelope(t, self.dur);
        let lfo = self.spec.lfo.as_ref().map(|l| (l.at(t), l));
        // Pitch: the glide (straight in log pitch over the glide time), then the LFO's vibrato.
        let mut ratio = match self.glide_from {
            Some(r0) if t < self.spec.glide => r0.powf(1.0 - t / self.spec.glide),
            _ => 1.0,
        };
        if let Some((v, l)) = lfo {
            ratio *= 2f64.powf(l.pitch * v / 1200.0);
        }
        if let Some(e) = &self.expression {
            ratio *= e.ratio(t);
        }
        if let Some(p) = &self.spec.pitch_env {
            ratio *= 2f64.powf(p.semitones * (-t / p.time.max(1e-4)).exp() / 12.0);
        }
        let (mut l, mut r) = (0.0, 0.0);
        for (k, o) in self.oscs.iter_mut().enumerate() {
            let inc = o.1 * ratio * self.analog.as_ref().map_or(1.0, |a| a.ratio(k, t));
            let s = osc(&self.spec.wave, o.0, inc);
            l += s * o.2;
            r += s * o.3;
            o.0 = (o.0 + inc) % 1.0;
        }
        if let Some(a) = self.analog.as_mut() {
            let f = self.oscs.first().map_or(0.0, |o| o.1) * ratio * self.sr;
            let x = a.extra(f, self.sr, 0.7 * self.norm);
            l += x;
            r += x;
        }
        // The cutoff rides its envelope by env_amount octaves, the LFO and the note's velocity.
        let fenv = self.spec.filter_env.as_ref().map_or(env, |e| self.spec.shaped(e, t, self.dur));
        let octaves = self.spec.env_amount * fenv + lfo.map_or(0.0, |(v, l)| l.cutoff * v) + self.spec.filter_velocity * (self.velocity - 1.0);
        let fc = (self.spec.cutoff * 2f64.powf(octaves)).clamp(20.0, self.sr * 0.45);
        let g = (PI * fc / self.sr).tan();
        let k = 2.0 - 1.96 * self.spec.resonance.clamp(0.0, 1.0);
        let a1 = 1.0 / (1.0 + g * (g + k));
        let a2 = g * a1;
        let a3 = g * a2;
        let mut out = [l, r];
        for (ch, v0) in out.iter_mut().enumerate() {
            let [ic1, ic2] = &mut self.ic[ch];
            let v3 = *v0 - *ic2;
            let v1 = a1 * *ic1 + a2 * v3;
            let v2 = *ic2 + a2 * *ic1 + a3 * v3;
            *ic1 = 2.0 * v1 - *ic1;
            *ic2 = 2.0 * v2 - *ic2;
            *v0 = v2;
        }
        if self.spec.drive > 0.0 {
            let g = 1.0 + self.spec.drive;
            for v in out.iter_mut() {
                *v = (g * *v / self.norm).tanh() / g.tanh() * self.norm;
            }
        }
        let level = env * self.gain * self.expression.as_ref().map_or(1.0, |e| e.gain(t, self.dur)) * lfo.map_or(1.0, |(v, l)| 1.0 - l.amp * (0.5 - 0.5 * v));
        (out[0] * level, out[1] * level)
    }
}
