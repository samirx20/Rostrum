//! The inserts besides EQ: a compressor linked across the channels with a soft knee, a delay (damped,
//! optionally ping-pong), a reverb insert, saturation, tape and a peak limiter.

use std::f64::consts::PI;

use super::frames;
use super::BLOCK;
use crate::bed::Layout;
use crate::fx::reverb::Reverb;
use crate::mix::schedule::Param;

/// A compressor linked across every channel (the loudest one's peak sets the gain all share).
pub(crate) fn compressor(threshold: &Param, ratio: &Param, attack_ms: f64, release_ms: f64, makeup: &Param, knee: f64, chs: &mut [&mut [f32]], sr: f64) {
    let att = (-1.0 / (attack_ms / 1000.0 * sr)).exp();
    let rel = (-1.0 / (release_ms / 1000.0 * sr)).exp();
    let mut gr = 0.0f64; // gain reduction in dB (≥ 0)
    let (mut th, mut ra, mut mk) = (threshold.at(0.0), ratio.at(0.0), makeup.at(0.0));
    let automated = threshold.automated() || ratio.automated() || makeup.automated();
    for i in 0..frames(chs) {
        if automated && i % BLOCK == 0 {
            let t = i as f64 / sr;
            (th, ra, mk) = (threshold.at(t), ratio.at(t), makeup.at(t));
        }
        let peak = (chs.iter().fold(0.0f32, |m, c| m.max(c[i].abs())) as f64).max(1e-9);
        let level = 20.0 * peak.log10();
        let over = level - th;
        // Soft knee: a quadratic blend over `knee` dB around the threshold.
        let target = if knee > 0.0 && over.abs() <= knee / 2.0 {
            (1.0 - 1.0 / ra) * (over + knee / 2.0).powi(2) / (2.0 * knee)
        } else if over > 0.0 {
            over * (1.0 - 1.0 / ra)
        } else {
            0.0
        };
        let c = if target > gr { att } else { rel };
        gr = c * gr + (1.0 - c) * target;
        let g = 10f64.powf((mk - gr) / 20.0) as f32;
        for c in chs.iter_mut() {
            c[i] *= g;
        }
    }
}

/// A delay on a left/right pair (ping-pong bounces inside the pair); a lone channel echoes itself.
pub(crate) fn delay(time: f64, feedback: &Param, mix: &Param, ping_pong: bool, damp: f64, l: &mut [f32], r: &mut [f32], sr: f64) {
    let n = ((time * sr).round() as usize).max(1);
    let mut buf = [vec![0.0f64; n], vec![0.0f64; n]];
    let mut lp = [0.0f64; 2];
    let alpha = (1.0 / sr) / (1.0 / (2.0 * PI * damp) + 1.0 / sr);
    let mut w = 0;
    for i in 0..l.len() {
        let t = i as f64 / sr;
        let (fb, m) = (feedback.at(t), mix.at(t));
        let wet = [buf[0][w], buf[1][w]];
        for ch in 0..2 {
            lp[ch] += alpha * (wet[ch] - lp[ch]);
        }
        let x = [l[i] as f64, r[i] as f64];
        if ping_pong {
            // Left feeds the right line and right the left: echoes bounce across.
            buf[0][w] = x[0] + fb * lp[1];
            buf[1][w] = fb * lp[0];
        } else {
            buf[0][w] = x[0] + fb * lp[0];
            buf[1][w] = x[1] + fb * lp[1];
        }
        l[i] = (x[0] + wet[0] * m) as f32;
        r[i] = (x[1] + wet[1] * m) as f32;
        w = (w + 1) % n;
    }
}

/// A reverb insert over the bed's mains (dsp.rs Reverb; the LFE stays dry), blended by `mix`.
pub(crate) fn reverb(space: &str, mix: &Param, shape: crate::fx::reverb::Shape, chs: &mut [&mut [f32]], layout: Layout, sr: f64) {
    let mains: Vec<usize> = (0..chs.len()).filter(|&c| chs.len() == 2 || Some(c) != layout.lfe()).collect();
    let mut rv = Reverb::shaped(space, 1.0, sr, mains.len(), shape);
    let mut y = vec![0.0; mains.len()];
    for i in 0..frames(chs) {
        let m = mix.at(i as f64 / sr);
        for (k, &c) in mains.iter().enumerate() {
            y[k] = chs[c][i] as f64;
        }
        rv.process_n(&mut y);
        for (k, &c) in mains.iter().enumerate() {
            chs[c][i] = (chs[c][i] as f64 * (1.0 - m) + y[k] * m) as f32;
        }
    }
}

pub(crate) fn saturate(drive: &Param, mix: &Param, chs: &mut [&mut [f32]], sr: f64) {
    for i in 0..frames(chs) {
        let t = i as f64 / sr;
        let (d, m) = (drive.at(t), mix.at(t));
        for buf in chs.iter_mut() {
            buf[i] = saturated(buf[i] as f64, d, m) as f32;
        }
    }
}

/// One sample through the saturator: drive `d`, wet mix `m` (the live layers use it too).
pub(crate) fn saturated(x: f64, d: f64, m: f64) -> f64 {
    x * (1.0 - m) + (d * x).tanh() / d.tanh() * m
}

/// Tape (the lo-fi sound): wow (a slow pitch drift, up to about ±15 cents) and flutter (a fast
/// waver) from a modulated delay, then saturation and a darker, thinner tone as `age` rises.
pub(crate) fn tape(wow: &Param, flutter: &Param, age: &Param, chs: &mut [&mut [f32]], sr: f64) {
    let n = frames(chs);
    let src: Vec<Vec<f32>> = chs.iter().map(|c| c.to_vec()).collect();
    let base = 0.008 * sr;
    let (mut lp, mut hp_in, mut hp_out) = (vec![0.0f64; chs.len()], vec![0.0f64; chs.len()], vec![0.0f64; chs.len()]);
    for i in 0..n {
        let t = i as f64 / sr;
        let (w, f, a) = (wow.at(t), flutter.at(t), age.at(t));
        let d = base + sr * (w * 0.0025 * (2.0 * PI * 0.55 * t).sin() + w * 0.0012 * (2.0 * PI * 0.23 * t + 1.3).sin() + f * 0.00022 * (2.0 * PI * 6.3 * t).sin());
        let pos = i as f64 - d;
        let read = |b: &[f32]| {
            if pos < 0.0 {
                return 0.0;
            }
            let k = pos.floor() as usize;
            let fr = pos - k as f64;
            b.get(k).copied().unwrap_or(0.0) as f64 * (1.0 - fr) + b.get(k + 1).copied().unwrap_or(0.0) as f64 * fr
        };
        let drive = 1.0 + 2.0 * a;
        let cut = 16000.0 * (1.0 - 0.75 * a);
        let alpha = 1.0 - (-2.0 * PI * cut / sr).exp();
        let hp_a = (-2.0 * PI * (25.0 + 70.0 * a) / sr).exp();
        for (ch, out) in chs.iter_mut().enumerate() {
            // Unity gain for quiet signals; loud ones round off.
            let x = (drive * read(&src[ch])).tanh() / drive;
            lp[ch] += alpha * (x - lp[ch]);
            // A one-pole high-pass: tape loses the deepest lows.
            hp_out[ch] = hp_a * (hp_out[ch] + lp[ch] - hp_in[ch]);
            hp_in[ch] = lp[ch];
            out[i] = hp_out[ch] as f32;
        }
    }
}

/// A peak limiter linked across every channel: the gain drops at once to keep peaks under the
/// ceiling and recovers over `release`.
pub(crate) fn limiter(ceiling_db: f64, release_ms: f64, chs: &mut [&mut [f32]], sr: f64) {
    let ceiling = 10f64.powf(ceiling_db / 20.0);
    let rel = (-1.0 / (release_ms / 1000.0 * sr)).exp();
    let mut g = 1.0f64;
    for i in 0..frames(chs) {
        let peak = (chs.iter().fold(0.0f32, |m, c| m.max(c[i].abs())) as f64).max(1e-9);
        let need = (ceiling / peak).min(1.0);
        g = if need < g { need } else { rel * g + (1.0 - rel) * need };
        for c in chs.iter_mut() {
            c[i] = ((c[i] as f64 * g).clamp(-ceiling, ceiling)) as f32;
        }
    }
}
