//! Synthesized sound effects and material foley: a port of src/engine/sound/schedule/sfxFoley.ts
//! (renderSfxFoleyClip), and recorded library takes played like tape (library/librarySample.ts).

pub mod ambience;
mod foley;
pub mod kit;
mod presets;
pub mod speech;

use std::f64::consts::{PI, SQRT_2};

use crate::mix::schedule::{Material, Pcm};
use crate::instruments::voices::fast_noise;

const TAU: f64 = 2.0 * PI;

/// A state-variable filter (topology-preserving, stable at any cutoff): (low, band, high) of `x` at
/// `hz`, damping `q` (2 = gentle, 0.3 = sharp). The ambience beds and the social-video kit share it.
#[derive(Default, Clone, Copy)]
pub(crate) struct Svf { ic1: f64, ic2: f64 }
impl Svf {
    pub(crate) fn run(&mut self, x: f64, hz: f64, q: f64, sr: f64) -> (f64, f64, f64) {
        let g = (PI * hz.clamp(20.0, sr * 0.45) / sr).tan();
        let a1 = 1.0 / (1.0 + g * (g + q));
        let (a2, v3) = (g * a1, x - self.ic2);
        let v1 = a1 * self.ic1 + a2 * v3;
        let v2 = self.ic2 + a2 * self.ic1 + g * a2 * v3;
        self.ic1 = 2.0 * v1 - self.ic1;
        self.ic2 = 2.0 * v2 - self.ic2;
        (v2, v1, x - q * v1 - v2)
    }
}

/// Seeded noise (xorshift), the same every render.
pub(crate) struct Rng(pub(crate) u64);
impl Rng {
    /// Uniform in 0 … 1.
    pub(crate) fn u(&mut self) -> f64 {
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        (self.0.wrapping_mul(0x2545_F491_4F6C_DD1D) >> 11) as f64 / (1u64 << 53) as f64
    }
    /// Uniform in -1 … 1.
    pub(crate) fn n(&mut self) -> f64 {
        self.u() * 2.0 - 1.0
    }
}

pub struct Sfx<'a> {
    pub preset: &'a str,
    pub material: Option<&'a Material>,
    pub duration: f64,
    pub volume: f64,
    pub pitch: f64,
    pub pan_from: f64,
    pub pan_to: f64,
}

/// Adds the effect into the clip buffers from sample 0.
pub fn render_sfx(p: &Sfx, left: &mut [f32], right: &mut [f32], sr: f64) {
    let dur = p.duration.max(0.03);
    let len = left.len().min((dur * sr).floor() as usize);
    let pitch = 2f64.powf(p.pitch / 12.0);
    if p.material.is_none() && crate::sfx::ambience::PRESETS.contains(&p.preset) {
        let n = left.len().min(len);
        crate::sfx::ambience::render(p.preset, dur, sr, |i, l, r| {
            if i < n {
                let a = (p.pan_from.clamp(-1.0, 1.0) + 1.0) * PI / 4.0;
                left[i] += (l * a.cos() * SQRT_2 * p.volume) as f32;
                right[i] += (r * a.sin() * SQRT_2 * p.volume) as f32;
            }
        });
        return;
    }
    if p.material.is_none() && crate::sfx::kit::PRESETS.contains(&p.preset) {
        let n = left.len().min(len);
        // Each preset's level, set so the set sits together (a click near −6 dBFS, an impact's body near −4).
        let trim = match p.preset { "impact" | "boom" | "hit" | "hitHard" => 0.7, "riser" | "uplifter" => 0.65, "click" | "tap" | "tick" | "key" => 0.7, "ding" | "chime" | "notification" | "success" => 1.3, _ => 1.0 };
        crate::sfx::kit::render(p.preset, dur, pitch, sr, |i, u, l, r| {
            let (l, r) = (l * trim, r * trim);
            if i < n {
                let pan = (p.pan_from + (p.pan_to - p.pan_from) * u).clamp(-1.0, 1.0);
                let a = (pan + 1.0) * PI / 4.0;
                left[i] += (l * a.cos() * p.volume) as f32;
                right[i] += (r * a.sin() * p.volume) as f32;
            }
        });
        return;
    }
    let (mut ph, mut lp) = ((0.0f64, 0.0f64), 0.0f64);
    let preset = p.preset;
    for i in 0..len {
        let t = i as f64 / sr;
        let u = (t / dur).min(1.0);
        let n = fast_noise(i as f64);
        lp = lp * 0.82 + n * 0.18;
        let (sig_l, sig_r) = match p.material {
            Some(m) => foley::material(m, preset, t, u, n, lp, pitch, dur),
            None => presets::synth(preset, &mut ph, t, u, n, lp, pitch, dur, sr),
        };
        let pan = (p.pan_from + (p.pan_to - p.pan_from) * u).clamp(-1.0, 1.0);
        let a = (pan + 1.0) * PI / 4.0;
        left[i] += (sig_l * a.cos() * p.volume) as f32;
        right[i] += (sig_r * a.sin() * p.volume) as f32;
    }
}

/// JavaScript's Math.round (halves round up).
pub fn js_round(x: f64) -> f64 {
    (x + 0.5).floor()
}

/// A library take (stereo PCM) read at `2^(pitch/12)` speed, panned, with a 10 ms fade at its cut.
pub fn render_sample(pcm: &Pcm, duration: f64, volume: f64, pitch: f64, pan_from: f64, pan_to: f64, left: &mut [f32], right: &mut [f32], sr: f64) -> Result<(), String> {
    let src = pcm.read()?;
    let frames = pcm.frames;
    let rate = 2f64.powf(pitch / 12.0);
    let natural = if duration > 0.0 { duration } else { frames as f64 / sr / rate };
    let len = left.len().min((natural * sr).floor() as usize).min(((frames as f64 - 1.0) / rate).floor().max(0.0) as usize);
    let at = |k: usize, c: usize| src[k * 2 + c] as f64;
    for i in 0..len {
        let pos = i as f64 * rate;
        let k = pos.floor() as usize;
        let f = pos - k as f64;
        let l = at(k, 0) + (at(k + 1, 0) - at(k, 0)) * f;
        let r = at(k, 1) + (at(k + 1, 1) - at(k, 1)) * f;
        let pan = (pan_from + (pan_to - pan_from) * (i as f64 / len.max(1) as f64)).clamp(-1.0, 1.0);
        let a = (pan + 1.0) * PI / 4.0;
        let g = ((len - i) as f64 / (0.01 * sr)).min(1.0) * volume * SQRT_2;
        left[i] += (l * a.cos() * g) as f32;
        right[i] += (r * a.sin() * g) as f32;
    }
    Ok(())
}
