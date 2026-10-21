//! A synth voice's analog character (src/core/soundDsl/instruments/synth.ts names it; all off by default, so a
//! spec without these fields renders exactly as before): `drift` — each oscillator wanders a few
//! cents on its own slow, uneven curve and every note starts its oscillators at fresh phases, so no
//! two notes are copies (the "MIDI" sameness of a digital voice); `noise` — breath / air mixed in
//! before the filter; `sub` — a sine an octave under the note; `curve: "analog"` — decay and release
//! fall exponentially (as a capacitor discharges) instead of in straight lines. Seeded by the note
//! (its start sample and pitch): the same every render.

use std::f64::consts::PI;

/// splitmix64: a hash of `k` as 0 … 1.
pub fn unit(k: u64) -> f64 {
    let mut z = k.wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    (z ^ (z >> 31)) as f64 / u64::MAX as f64
}

pub struct Analog {
    /// Per oscillator: a fixed offset (cents) and two slow wanders (rate Hz, phase).
    wander: Vec<(f64, f64, f64, f64, f64)>,
    depth: f64,
    noise: f64,
    sub: f64,
    sub_phase: f64,
    rng: u64,
}

impl Analog {
    /// None when the spec asks for nothing analog (the voice is then unchanged).
    pub fn new(drift: f64, noise: f64, sub: f64, oscillators: usize, seed: u64) -> Option<Analog> {
        if drift <= 0.0 && noise <= 0.0 && sub <= 0.0 {
            return None;
        }
        let h = |k: u64| unit(seed.wrapping_mul(0x2545_F491_4F6C_DD1D).wrapping_add(k));
        let wander = (0..oscillators as u64)
            .map(|k| (h(k * 8) * 2.0 - 1.0, 0.08 + 0.4 * h(k * 8 + 1), h(k * 8 + 2) * 2.0 * PI, 0.6 + 1.6 * h(k * 8 + 3), h(k * 8 + 4) * 2.0 * PI))
            .collect();
        Some(Analog { wander, depth: drift.max(0.0), noise: noise.max(0.0), sub: sub.max(0.0), sub_phase: 0.0, rng: seed ^ 0xA076_1D64_78BD_642F })
    }

    /// Oscillator `k`'s starting phase for this note (fresh every note when drifting).
    pub fn phase(&self, k: usize, fallback: f64) -> f64 {
        if self.depth > 0.0 { self.wander[k].2 / (2.0 * PI) } else { fallback }
    }

    /// Oscillator `k`'s pitch ratio at `t` seconds: its offset (half the drift) and its wander.
    pub fn ratio(&self, k: usize, t: f64) -> f64 {
        if self.depth == 0.0 {
            return 1.0;
        }
        let (off, r1, p1, r2, p2) = self.wander[k];
        let cents = self.depth * (0.5 * off + 0.35 * (2.0 * PI * r1 * t + p1).sin() + 0.15 * (2.0 * PI * r2 * t + p2).sin());
        2f64.powf(cents / 1200.0)
    }

    /// What is mixed in before the filter at the note's frequency `f` (Hz, with its glide and vibrato): noise and the sub.
    pub fn extra(&mut self, f: f64, sr: f64, level: f64) -> f64 {
        let mut x = 0.0;
        if self.noise > 0.0 {
            self.rng ^= self.rng << 13;
            self.rng ^= self.rng >> 7;
            self.rng ^= self.rng << 17;
            x += self.noise * level * ((self.rng >> 11) as f64 / (1u64 << 53) as f64 * 2.0 - 1.0);
        }
        if self.sub > 0.0 {
            x += self.sub * level * (2.0 * PI * self.sub_phase).sin();
            self.sub_phase = (self.sub_phase + 0.5 * f / sr) % 1.0;
        }
        x
    }
}

/// An ADSR with exponential decay and release (time constants a fifth of each stage: −43 dB by its end).
pub fn analog_env(t: f64, dur: f64, a: f64, d: f64, s: f64, r: f64) -> f64 {
    let held = |t: f64| if t < a { t / a.max(1e-6) } else { s + (1.0 - s) * (-(t - a) * 5.0 / d.max(1e-4)).exp() };
    if t <= dur { held(t) } else if t - dur >= r { 0.0 } else { held(dur) * (-(t - dur) * 5.0 / r.max(1e-4)).exp() * (1.0 - (t - dur) / r.max(1e-6)).min(1.0) }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nothing_asked_is_nothing_added() {
        assert!(Analog::new(0.0, 0.0, 0.0, 3, 7).is_none());
    }

    #[test]
    fn drift_wanders_each_oscillator_differently_within_its_cents_and_differs_by_note() {
        let a = Analog::new(8.0, 0.0, 0.0, 3, 1).unwrap();
        let cents = |k: usize, t: f64| 1200.0 * a.ratio(k, t).log2();
        for k in 0..3 { for i in 0..200 { assert!(cents(k, i as f64 * 0.05).abs() <= 8.0 + 1e-9); } }
        assert!((cents(0, 1.0) - cents(1, 1.0)).abs() > 0.05);
        let b = Analog::new(8.0, 0.0, 0.0, 3, 2).unwrap();
        assert!((a.phase(0, 0.0) - b.phase(0, 0.0)).abs() > 1e-6, "a new note starts at fresh phases");
    }

    #[test]
    fn the_analog_envelope_falls_exponentially_and_ends_at_zero() {
        let lin_mid = 1.0 - 0.5 * 0.5; // a straight decay to 0.5 over 1 s, half way
        let exp_mid = analog_env(0.51, 5.0, 0.01, 1.0, 0.5, 1.0);
        assert!(exp_mid < lin_mid && exp_mid > 0.5, "{exp_mid}");
        assert_eq!(analog_env(6.5, 5.0, 0.01, 1.0, 0.5, 1.0), 0.0);
        assert!(analog_env(5.1, 5.0, 0.01, 1.0, 0.5, 1.0) < 0.5 * 0.7);
    }
}
