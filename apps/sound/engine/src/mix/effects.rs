//! Whole-clip and whole-mix effects: glitch stutter, filter sweep and the master time warp (speed is
//! stretch/speed.rs, ducking duck.rs). A port of voiceAndWarpDsp.ts; buffers hold f32 like the TS ones did.

use std::f64::consts::{PI, SQRT_2};

use crate::mix::schedule::{FilterSweep, Glitch, TimeWarp};
use crate::sfx::js_round;

/// Repeats a grain (at the last loud syllable unless placed) with a gate, alternating pan,
/// optional bitcrush and a pitch step per repeat.
pub fn glitch(left: &mut [f32], right: &mut [f32], sr: f64, g: &Glitch) {
    let len = left.len().min(right.len());
    if len < 64 {
        return;
    }
    let stutter = g.stutter_rate.filter(|&x| x != 0.0).unwrap_or(16.0).clamp(4.0, 64.0);
    let grain = ((sr / stutter).floor() as usize).max(64);
    let repeats = g.repeats.filter(|&x| x != 0.0).unwrap_or(4.0).clamp(2.0, 24.0);
    let total = match g.duration.filter(|&x| x != 0.0) {
        Some(d) => (d * sr).floor() as usize,
        None => (grain as f64 * repeats).ceil() as usize, // i < grain × repeats, repeats may be fractional
    };
    let mut default_offset = (len as i64 - total as i64 - (0.12 * sr).floor() as i64).max(0) as usize;
    let mut i = len - 1;
    while i >= grain * 2 {
        if left[i].abs() > 0.06 {
            default_offset = i.saturating_sub(grain * 2);
            break;
        }
        i -= 1;
    }
    let start = match g.at_offset {
        Some(a) => ((a * sr).floor().max(0.0) as usize).min(len - 32),
        None => default_offset,
    };
    let end = len.min(start + grain);
    let grain_l = left[start..end].to_vec();
    let grain_r = right[start..end].to_vec();
    if grain_l.len() < 16 {
        return;
    }
    let crush = g.bitcrush.unwrap_or(0.0).clamp(0.0, 1.0);
    let hold = if crush > 0.0 { ((1.0 + crush * 10.0).floor() as usize).max(1) } else { 1 };
    let levels = if crush > 0.0 { (64.0 * (1.0 - crush * 0.75)).floor().max(8.0) } else { 0.0 };
    let spread = g.pan_spread.unwrap_or(0.55).clamp(0.0, 1.0);
    let step = g.pitch_step.unwrap_or(0.0);
    let mut i = 0;
    while i < total && start + i < len {
        let rep = i / grain;
        let pm = 2f64.powf(rep as f64 * step / 12.0);
        let local = (((i % grain) as f64 * pm / hold as f64).floor() as usize) * hold;
        let gi = (grain_l.len() - 1).min(local);
        let (mut sl, mut sr_) = (grain_l[gi] as f64, grain_r[gi] as f64);
        if levels > 0.0 {
            sl = js_round(sl * levels) / levels;
            sr_ = js_round(sr_ * levels) / levels;
        }
        let ph = (i % grain) as f64 / grain as f64;
        let fade_in = if ph < 0.08 { ph / 0.08 } else { 1.0 };
        let gate = if ph > 0.82 { ((1.0 - ph) / 0.18).max(0.0) } else { 1.0 };
        let pan = if rep % 2 == 0 { -1.0 } else { 1.0 } * spread;
        let a = (pan + 1.0) * PI / 4.0;
        left[start + i] = (sl * fade_in * gate * a.cos() * SQRT_2) as f32;
        right[start + i] = (sr_ * fade_in * gate * a.sin() * SQRT_2) as f32;
        i += 1;
    }
}

/// A one-pole low-pass whose cutoff sweeps across the clip (exponential, or linear).
pub fn filter_sweep(left: &mut [f32], right: &mut [f32], sr: f64, s: &FilterSweep) {
    let len = left.len().min(right.len());
    let f0 = s.from_hz.filter(|&x| x != 0.0).unwrap_or(400.0).clamp(80.0, 20000.0);
    let f1 = s.to_hz.filter(|&x| x != 0.0).unwrap_or(18000.0).clamp(80.0, 20000.0);
    let dt = 1.0 / sr;
    let (mut l, mut r) = (0.0f64, 0.0f64);
    for i in 0..len {
        let u = i as f64 / len as f64;
        let cut = if s.linear { f0 + (f1 - f0) * u } else { f0 * (f1 / f0).powf(u) };
        let alpha = dt / (1.0 / (2.0 * PI * cut) + dt);
        l += alpha * (left[i] as f64 - l);
        r += alpha * (right[i] as f64 - r);
        left[i] = l as f32;
        right[i] = r as f32;
    }
}

/// Bullet time on the master: each window re-reads the mix slowing (or speeding) and back, with a
/// low-pass dip and a sub drop when it slows.
/// Every channel is re-read alike; the sub drop goes to the front pair (channels 0 and 1: L and R in
/// every layout), so it survives a fold-down.
pub fn time_warps(chs: &mut [&mut [f32]], sr: f64, warps: &[TimeWarp]) {
    let len = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    if warps.is_empty() || len < 64 {
        return;
    }
    let dt = 1.0 / sr;
    for w in warps {
        let start = ((w.start * sr).floor().max(0.0) as usize).min(len - 32);
        let win = (len - start).min((w.duration.max(0.1) * sr).floor() as usize);
        if win < 32 {
            continue;
        }
        let avail_ch: Vec<Vec<f32>> = chs.iter().map(|c| c[start..len].to_vec()).collect();
        let avail = len - start;
        let r_from = w.rate_from.unwrap_or(1.0).clamp(0.2, 4.0);
        let r_to = w.rate_to.unwrap_or(0.45).clamp(0.2, 4.0);
        let min_cut = w.filter_hz.unwrap_or(620.0).max(220.0);
        let (mut cursor, mut sub_phase) = (0.0f64, 0.0f64);
        let mut lp = vec![0.0f64; chs.len()];
        for i in 0..win {
            let u = i as f64 / win as f64;
            let dip = (PI * u).sin();
            let cur = r_from + (r_to - r_from) * dip;
            let idx = cursor.floor();
            let frac = cursor - idx;
            let inside = idx >= 0.0 && (idx as usize) + 1 < avail;
            let k = idx as usize;
            let filtered = cur < 0.99 || w.filter_hz.is_some();
            let alpha = if filtered { let cut = 18000.0 * (min_cut / 18000.0).powf(dip); dt / (1.0 / (2.0 * PI * cut) + dt) } else { 0.0 };
            let mut sub = 0.0;
            if w.sub_drop && r_to < r_from {
                let t = i as f64 / sr;
                sub_phase += 2.0 * PI * (36.0 + 68.0 * (-t * 5.0).exp()) / sr;
                sub = (sub_phase.sin() * 1.3).tanh() * (-t * 3.2).exp() * 0.32;
            }
            for (c, (out, a)) in chs.iter_mut().zip(&avail_ch).enumerate() {
                let s = if inside { a[k] as f64 * (1.0 - frac) + a[k + 1] as f64 * frac } else { 0.0 };
                if filtered {
                    lp[c] += alpha * (s - lp[c]);
                } else {
                    lp[c] = s;
                }
                out[start + i] = (lp[c] + if c < 2 { sub } else { 0.0 }) as f32;
            }
            cursor += cur;
        }
    }
}
