//! A drum-machine voice whose sound is data (TypeScript's kit presets decide every number:
//! src/core/soundDsl/instruments/kitPresets.ts): a pitch-swept tone (kick, tom, 808, snare body) with an
//! optional second mode, a click, band-limited noise (snare wires, clap, shaker) that can strike
//! as a burst of hand claps, and the TR-808's six square oscillators (hats, cymbals), all through
//! one envelope pair and an optional drive. `tune` scales every frequency, `decay` every time.

use serde::Deserialize;
use std::f64::consts::PI;

#[derive(Deserialize, Clone, Copy, Debug, Default)]
#[serde(rename_all = "camelCase", default)]
pub struct DrumModel {
    /// Seconds the hit lasts (× the kit's decay factor); the last 5 ms fade.
    pub length: f64,
    /// The tone: level, its pitch from `f_start` falling to `f_end` with time constant `pitch_decay`, its level's time constant.
    pub tone: f64,
    pub f_start: f64,
    pub f_end: f64,
    pub pitch_decay: f64,
    pub tone_decay: f64,
    /// A second mode at `tone2_ratio` × the pitch (a snare's shell), level `tone2`, decaying twice as fast.
    pub tone2: f64,
    pub tone2_ratio: f64,
    /// A short bright transient (the beater): level.
    pub click: f64,
    /// Noise: level, band (high-pass … low-pass, Hz), attack and decay time constants.
    pub noise: f64,
    pub noise_hp: f64,
    pub noise_lp: f64,
    pub noise_attack: f64,
    pub noise_decay: f64,
    /// Hand claps: the noise strikes `bursts` times `burst_gap` s apart before its tail.
    pub bursts: f64,
    pub burst_gap: f64,
    /// The six 808 square oscillators (metal), high-passed at `metal_hp`, on the noise envelope.
    pub metal: f64,
    pub metal_hp: f64,
    /// Saturation of the whole hit (0: clean).
    pub drive: f64,
}

/// A two-pole state-variable filter (one channel; topology-preserving, stable at any cutoff).
#[derive(Default, Clone, Copy)]
struct Svf { ic1: f64, ic2: f64 }

impl Svf {
    /// (low-pass, high-pass) of `x` at `hz`.
    fn run(&mut self, x: f64, hz: f64, sr: f64) -> (f64, f64) {
        let k = 1.3;
        let g = (PI * hz.clamp(10.0, sr * 0.45) / sr).tan();
        let a1 = 1.0 / (1.0 + g * (g + k));
        let (a2, v3) = (g * a1, x - self.ic2);
        let v1 = a1 * self.ic1 + a2 * v3;
        let v2 = self.ic2 + a2 * self.ic1 + g * a2 * v3;
        self.ic1 = 2.0 * v1 - self.ic1;
        self.ic2 = 2.0 * v2 - self.ic2;
        (v2, x - k * v1 - v2)
    }
}

const METAL: [f64; 6] = [205.3, 304.4, 369.6, 522.7, 540.0, 800.0];

pub struct DrumHit {
    m: DrumModel,
    tune: f64,
    decay: f64,
    sr: f64,
    len: usize,
    phase: [f64; 2],
    metal_phase: [f64; 6],
    seed: u64,
    filters: [Svf; 5],
}

impl DrumHit {
    pub fn new(m: &DrumModel, tune: f64, decay: f64, seed: u64, sr: f64) -> DrumHit {
        let len = (m.length * decay.max(0.05) * sr).floor() as usize;
        DrumHit { m: m.clone(), tune, decay: decay.max(0.05), sr, len, phase: [0.0; 2], metal_phase: [0.0; 6], seed: seed.wrapping_mul(0x9E37_79B9_7F4A_7C15) | 1, filters: [Svf::default(); 5] }
    }

    pub fn len(&self) -> usize {
        self.len
    }

    fn white(&mut self) -> f64 {
        // xorshift64*: deterministic per hit.
        self.seed ^= self.seed >> 12;
        self.seed ^= self.seed << 25;
        self.seed ^= self.seed >> 27;
        (self.seed.wrapping_mul(0x2545_F491_4F6C_DD1D) >> 11) as f64 / (1u64 << 53) as f64 * 2.0 - 1.0
    }

    /// The hit's sample at `i` samples after its start (mono).
    pub fn next(&mut self, i: usize) -> f64 {
        let (sr, k, d) = (self.sr, self.tune, self.decay);
        let t = i as f64 / sr;
        let m = self.m;
        let ex = move |tc: f64| if tc > 0.0 { (-t / (tc * d)).exp() } else { 0.0 };
        let mut s = 0.0;
        if m.tone > 0.0 {
            let f = k * (m.f_end + (m.f_start - m.f_end) * if m.pitch_decay > 0.0 { (-t / m.pitch_decay).exp() } else { 0.0 });
            self.phase[0] += 2.0 * PI * f / sr;
            let attack = (t / 0.0004).min(1.0);
            s += m.tone * self.phase[0].sin() * ex(m.tone_decay) * attack;
            if m.tone2 > 0.0 {
                self.phase[1] += 2.0 * PI * f * m.tone2_ratio / sr;
                s += m.tone2 * self.phase[1].sin() * ex(m.tone_decay * 0.5) * attack;
            }
        }
        let wants_noise = m.noise > 0.0 || m.click > 0.0;
        let n = if wants_noise { self.white() } else { 0.0 };
        if m.click > 0.0 {
            // The beater: bright noise for ~3 ms and a 3 kHz blip, what a phone speaker hears of a kick.
            let (_, hp) = self.filters[0].run(n, 2000.0 * k, sr);
            s += m.click * (1.6 * hp * (-t / 0.003).exp() + 0.9 * (2.0 * PI * 3000.0 * k * t).sin() * (-t / 0.0015).exp());
        }
        // The noise and metal envelope: attack, the claps' bursts, then the tail.
        let env = {
            let rise = if m.noise_attack > 0.0 { (t / m.noise_attack).min(1.0) } else { 1.0 };
            let bursts = m.bursts.max(1.0).round();
            let last = (bursts - 1.0) * m.burst_gap;
            if bursts > 1.0 && t < last {
                let local = t - (t / m.burst_gap).floor() * m.burst_gap;
                (-local / 0.0055).exp()
            } else {
                rise * if m.noise_decay > 0.0 { (-(t - last.max(0.0)) / (m.noise_decay * d)).exp() } else { 0.0 }
            }
        };
        if m.noise > 0.0 {
            let (_, hp) = self.filters[1].run(n, m.noise_hp * k, sr);
            let (lp, _) = self.filters[2].run(hp, m.noise_lp * k, sr);
            s += m.noise * lp * env;
        }
        if m.metal > 0.0 {
            let mut sq = 0.0;
            for (j, &f) in METAL.iter().enumerate() {
                self.metal_phase[j] = (self.metal_phase[j] + f * 1.6 * k / sr).fract();
                sq += if self.metal_phase[j] < 0.5 { 1.0 } else { -1.0 };
            }
            let (_, hp1) = self.filters[3].run(sq / 6.0, m.metal_hp * k, sr);
            let (_, hp2) = self.filters[4].run(hp1, m.metal_hp * k, sr);
            s += m.metal * hp2 * env;
        }
        if m.drive > 0.0 {
            s = (s * (1.0 + m.drive)).tanh() / (1.0 + m.drive).tanh();
        }
        let fade = ((self.len.saturating_sub(i)) as f64 / (0.005 * sr)).min(1.0);
        s * fade
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn render(m: &DrumModel, tune: f64) -> Vec<f64> {
        let mut h = DrumHit::new(m, tune, 1.0, 7, 44100.0);
        (0..h.len()).map(|i| h.next(i)).collect()
    }

    #[test]
    fn a_kick_settles_on_its_end_pitch_and_tune_moves_it() {
        let kick = DrumModel { length: 0.5, tone: 1.0, f_start: 180.0, f_end: 55.0, pitch_decay: 0.03, tone_decay: 0.3, ..Default::default() };
        let x = render(&kick, 1.0);
        // Zero crossings between 0.2 s and 0.4 s: 55 Hz → 22 crossings.
        let cross = |x: &[f64]| (8820..17640).filter(|&i| (x[i] > 0.0) != (x[i - 1] > 0.0)).count();
        assert!((cross(&x) as i64 - 22).abs() <= 2, "{}", cross(&x));
        assert!((cross(&render(&kick, 2.0)) as i64 - 44).abs() <= 3);
    }

    #[test]
    fn claps_strike_in_bursts_and_hits_are_deterministic() {
        let clap = DrumModel { length: 0.3, noise: 1.0, noise_hp: 900.0, noise_lp: 3000.0, noise_decay: 0.08, bursts: 3.0, burst_gap: 0.011, ..Default::default() };
        let x = render(&clap, 1.0);
        let rms = |a: usize, b: usize| (x[a..b].iter().map(|v| v * v).sum::<f64>() / (b - a) as f64).sqrt();
        // Each burst's start is louder than the gap just before the next one.
        assert!(rms(0, 100) > 2.0 * rms(380, 480));
        assert!(rms(485, 585) > 2.0 * rms(380, 480));
        assert_eq!(x, render(&clap, 1.0));
    }
}
