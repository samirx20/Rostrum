//! A bowed solo voice by DDSP (differentiable digital signal processing): the line's pitch and
//! loudness curves, made from its notes, drive a learned decoder (ddsp_net.rs) whose outputs play a
//! harmonic oscillator bank (one sine per harmonic, each at its learned level) plus filtered noise
//! (the bow's hiss), then the room the model learned. Nothing is played back: the sound is synthesized
//! from the curves, so it follows any pitch, glide, vibrato and dynamic exactly. One line: a note that
//! starts before the last one ends (legato) is slurred to — the pitch glides, the bow keeps moving.

use std::sync::OnceLock;

use super::ddsp_net::Decoder;
use super::{Note, Rng};
use crate::instruments::pan_gains;

static VIOLIN: &[u8] = include_bytes!("../../../data/ddsp/violin.ddsp");

pub fn violin() -> Result<&'static Decoder, String> {
    static D: OnceLock<Result<Decoder, String>> = OnceLock::new();
    D.get_or_init(|| Decoder::load(VIOLIN)).as_ref().map_err(|e| e.clone())
}

/// Control frames per second (the model's).
pub const FPS: f64 = 300.0;
/// A slur's glide (s), a lifted bow's release (s to fall 1/e), a fresh bow stroke's attack (s, soft → hard).
const GLIDE: f64 = 0.065;
const RELEASE: f64 = 0.07;
const ATTACK: (f64, f64) = (0.11, 0.035);

/// The line's pitch (Hz) and loudness (dB) at each frame from `t0` seconds into the clip.
pub fn curves(d: &Decoder, notes: &[Note], t0: f64, frames: usize, sr: f64) -> (Vec<f64>, Vec<f64>) {
    let s = &d.stats;
    let floor = s.ld_min + 4.0;
    let level = |v: f64| s.ld_p10 - 2.0 + (s.ld_p95 + 1.0 - s.ld_p10 + 2.0) * v.clamp(0.0, 1.0).powf(0.9);
    let (mut f0, mut ld) = (Vec::with_capacity(frames), Vec::with_capacity(frames));
    let mut last_f = notes.first().map_or(440.0, |n| n.freq);
    for k in 0..frames {
        let t = t0 + k as f64 / FPS;
        // The sounding note: the latest one started (a monophonic line).
        let i = notes.iter().rposition(|n| n.start as f64 / sr <= t);
        let Some(i) = i else {
            f0.push(last_f);
            ld.push(floor);
            continue;
        };
        let n = &notes[i];
        let (start, end) = (n.start as f64 / sr, (n.start + n.len) as f64 / sr);
        let into = t - start;
        let prev = i.checked_sub(1).map(|j| &notes[j]).filter(|p| (p.start + p.len) as f64 / sr >= start - 0.02);
        let mut f = n.freq * n.expression.map_or(1.0, |e| e.ratio(into));
        let mut amp = 10f64.powf((level(n.velocity) + 20.0 * n.expression.map_or(1.0, |e| e.gain(into, end - start)).max(1e-4).log10()) / 20.0);
        match prev {
            Some(p) => {
                let u = (into / GLIDE).clamp(0.0, 1.0);
                let u = u * u * (3.0 - 2.0 * u);
                f = (p.freq.ln() * (1.0 - u) + f.ln() * u).exp();
                // The bow changes direction or the finger lands: a small dip, never silence.
                let from = 10f64.powf(level(p.velocity) / 20.0);
                amp = from * (1.0 - u) + amp * u;
                amp *= 1.0 - 0.18 * (1.0 - (2.0 * u - 1.0).abs());
            }
            None => {
                let a = ATTACK.0 + (ATTACK.1 - ATTACK.0) * n.velocity.clamp(0.0, 1.0);
                let u = (into / a).clamp(0.0, 1.0);
                amp *= 1.0 - (1.0 - u).powi(3);
            }
        }
        if t > end {
            amp *= (-(t - end) / RELEASE).exp();
        }
        last_f = f;
        f0.push(f);
        ld.push((20.0 * amp.max(1e-12).log10()).max(floor));
    }
    (f0, ld)
}

/// `ssig`: the decoder's output scaling (2·σ(x)^ln10 + 1e-7), as it was trained.
fn ssig(x: f32) -> f64 {
    2.0 * (1.0 / (1.0 + (-x as f64).exp())).powf(std::f64::consts::LN_10) + 1e-7
}

/// The decoder's frames as sound at `sr`: harmonics (Chebyshev recurrence: one sine and a few
/// multiply-adds per harmonic per sample) and filtered noise (seeded white noise, its STFT scaled by
/// the bands).
pub fn synthesize(d: &Decoder, f0: &[f64], out: &[Vec<f32>], seed: u64, sr: f64) -> Vec<f64> {
    let nh = d.harmonics;
    let nyq = (sr / 2.0).min(d.sr / 2.0);
    let frames: Vec<(Vec<f64>, Vec<f64>)> = out.iter().zip(f0).map(|(o, &f)| {
        let amp = ssig(o[0]);
        let mut h: Vec<f64> = (0..nh).map(|k| if f * (k + 1) as f64 >= nyq { 0.0 } else { ssig(o[1 + k]) }).collect();
        let sum: f64 = h.iter().sum::<f64>().max(1e-7);
        h.iter_mut().for_each(|v| *v *= amp / sum);
        (h, o[1 + nh..].iter().map(|&x| ssig(x - 5.0)).collect())
    }).collect();
    let len = (f0.len() as f64 / FPS * sr) as usize;
    let at = |k: f64| -> (usize, usize, f64) {
        let i = (k.floor() as usize).min(f0.len() - 1);
        (i, (i + 1).min(f0.len() - 1), k - k.floor())
    };
    let mut sig = vec![0.0; len];
    let mut phase = 0.0f64;
    for (n, s) in sig.iter_mut().enumerate() {
        let (i, j, fr) = at(n as f64 / sr * FPS);
        let f = f0[i] + (f0[j] - f0[i]) * fr;
        phase = (phase + 2.0 * std::f64::consts::PI * f / sr) % (2.0 * std::f64::consts::PI);
        let (s1, c2) = (phase.sin(), 2.0 * phase.cos());
        let (mut prev, mut cur, mut acc) = (0.0, s1, 0.0);
        let (hi, hj) = (&frames[i].0, &frames[j].0);
        for k in 0..nh {
            acc += (hi[k] + (hj[k] - hi[k]) * fr) * cur;
            let next = c2 * cur - prev;
            prev = cur;
            cur = next;
        }
        *s = acc;
    }
    let mut rng = Rng::new(seed);
    let white: Vec<f32> = (0..len).map(|_| rng.next() as f32).collect();
    let (n, hop) = (512, 128);
    let mut spec = crate::analysis::stft::forward(&white, n, hop);
    let bands = d.bands as f64;
    for fi in 0..spec.re.len() {
        let (i, j, fr) = at((crate::analysis::stft::frame_time(fi, n, hop, sr).max(0.0)) * FPS);
        for k in 0..=n / 2 {
            let pos = k as f64 * sr / n as f64 / (d.sr / 2.0) * (bands - 1.0);
            let g = if pos > bands - 1.0 { 0.0 } else {
                let (b0, bf) = (pos.floor() as usize, pos - pos.floor());
                let b1 = (b0 + 1).min(d.bands - 1);
                let band = |fr_: &Vec<f64>| fr_[b0] * (1.0 - bf) + fr_[b1] * bf;
                band(&frames[i].1) * (1.0 - fr) + band(&frames[j].1) * fr
            };
            spec.scale(fi, k, g);
        }
    }
    let noise = crate::analysis::stft::inverse(&spec, len);
    sig.iter().zip(&noise).map(|(h, n)| h + *n as f64).collect()
}

/// The learned room (`d.sr`), read at `sr`.
fn room(d: &Decoder, sr: f64) -> Vec<f64> {
    let len = (d.ir.len() as f64 * sr / d.sr) as usize;
    (0..len).map(|i| {
        let x = i as f64 * d.sr / sr;
        let (k, fr) = (x.floor() as usize, x - x.floor());
        let a = d.ir[k] as f64;
        let b = d.ir.get(k + 1).copied().unwrap_or(0.0) as f64;
        if k == 0 { 0.0 } else { (a + (b - a) * fr) * d.sr / sr }
    }).collect()
}

pub fn render(notes: &[Note], left: &mut [f32], right: &mut [f32], sr: f64) -> Result<(), String> {
    let Some(first) = notes.first() else { return Ok(()) };
    let d = violin()?;
    let t0 = (first.start as f64 / sr - 0.02).max(0.0);
    let end = notes.iter().map(|n| (n.start + n.len) as f64 / sr).fold(0.0, f64::max) + 0.6;
    let frames = ((end - t0) * FPS).ceil() as usize + 1;
    let (f0, ld) = curves(d, notes, t0, frames, sr);
    let out = d.run(&f0, &ld);
    let dry = synthesize(d, &f0, &out, first.start as u64 ^ 0xD5D5, sr);
    let x: Vec<f32> = dry.iter().map(|&v| v as f32).collect();
    let wet = crate::fx::convolve::convolve(&x, &room(d, sr));
    let (gl, gr) = pan_gains(first.pan, 1.0);
    let start = (t0 * sr) as usize;
    for i in 0..wet.len().max(dry.len()) {
        let k = start + i;
        if k >= left.len() {
            break;
        }
        let s = (dry.get(i).copied().unwrap_or(0.0) + wet.get(i).copied().unwrap_or(0.0)) * LEVEL;
        left[k] = (left[k] as f64 + s * gl) as f32;
        right[k] = (right[k] as f64 + s * gr) as f32;
    }
    Ok(())
}

/// The model's level (VSCO's recordings are quiet) up to the other instruments'.
const LEVEL: f64 = 2.5;
