//! Dialogue dynamics, offline (the whole clip or track is known, so each gain curve looks ahead):
//! a split-band de-esser, a noise gate / downward expander and a dialogue leveller. Each computes
//! a gain curve from the signal, smooths it (attack ahead of the event, hold and release after),
//! then applies it to every channel alike (linked: a bed's channels share one gain curve).

use crate::fx::eq::biquad;

const DB_FLOOR: f64 = -120.0;

fn db(ms: f64) -> f64 {
    if ms > 1e-12 { 10.0 * ms.log10() } else { DB_FLOOR }
}

/// Level (dB) of `x` over a sliding mean-square window of `win` samples, per sample.
fn level(x: &[f64], win: usize) -> Vec<f64> {
    let win = win.max(1);
    let mut acc = 0.0;
    let mut out = Vec::with_capacity(x.len());
    for i in 0..x.len() {
        acc += x[i] * x[i];
        if i >= win {
            acc -= x[i - win] * x[i - win];
        }
        out.push(db(acc.max(0.0) / win.min(i + 1) as f64));
    }
    // Centred: the window's level belongs to its middle.
    let half = win / 2;
    (0..x.len()).map(|i| out[(i + half).min(x.len() - 1)]).collect()
}

/// A reduction curve (dB ≥ 0) smoothed: it reaches each peak `attack` samples early (linear ramp
/// in, look-ahead), holds `hold` samples, then falls back with time constant `release` samples.
fn smooth(target: &[f64], attack: usize, hold: usize, release: f64) -> Vec<f64> {
    let rel = (-1.0 / release.max(1.0)).exp();
    let mut out = vec![0.0; target.len()];
    let (mut g, mut held) = (0.0f64, 0usize);
    for i in 0..target.len() {
        if target[i] >= g {
            g = target[i];
            held = 0;
        } else if held < hold {
            held += 1;
        } else {
            g = target[i] + (g - target[i]) * rel;
        }
        out[i] = g;
    }
    let step = out.iter().fold(0.0f64, |m, v| m.max(*v)) / attack.max(1) as f64;
    for i in (0..out.len().saturating_sub(1)).rev() {
        out[i] = out[i].max(out[i + 1] - step);
    }
    out
}

/// De-esser: the band above `freq` (a 2nd-order high-pass, 4th order for detection) is cut while
/// its level passes `threshold` dB and is within 15 dB of the whole signal's, by up to `range` dB (ratio 3:1 above).
pub fn deess(chs: &mut [&mut [f32]], sr: f64, freq: f64, threshold: f64, range: f64) {
    let hp = biquad("highpass", freq, 0.0, 0.707, sr);
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let share = 1.0 / chs.len().max(1) as f64;
    let mid: Vec<f64> = (0..n).map(|i| chs.iter().fold(0.0, |s, c| s + c[i] as f64) * share).collect();
    let (mut z1, mut z2) = ([0.0; 2], [0.0; 2]);
    let band: Vec<f64> = mid.iter().map(|&x| hp.tick(&mut z2, hp.tick(&mut z1, x))).collect();
    let win = (sr * 0.002) as usize;
    let (bl, fl) = (level(&band, win), level(&mid, (sr * 0.01) as usize));
    // Sibilance: the high band over the threshold and within 15 dB of the whole signal's level (a bright
    // instrument under the voice, far under its lows, is left alone).
    let target: Vec<f64> = bl.iter().zip(&fl).map(|(b, f)| if *b > threshold && *b > f - 15.0 { ((b - threshold) * (2.0 / 3.0)).min(range) } else { 0.0 }).collect();
    let red = smooth(&target, (sr * 0.002) as usize, (sr * 0.005) as usize, sr * 0.04);
    for buf in chs.iter_mut() {
        let mut z = [0.0; 2];
        for i in 0..buf.len() {
            let x = buf[i] as f64;
            let h = hp.tick(&mut z, x);
            let g = 10f64.powf(-red[i] / 20.0);
            buf[i] = (x - (1.0 - g) * h) as f32;
        }
    }
}

/// Gate / expander: below `threshold` dB the signal falls `ratio`:1 (a gate from about 10:1), at
/// most `range` dB; opens `attack` ms ahead, holds `hold` ms, closes over `release` ms.
pub fn gate(chs: &mut [&mut [f32]], sr: f64, threshold: f64, ratio: f64, range: f64, attack: f64, hold: f64, release: f64) {
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let peak: Vec<f64> = (0..n).map(|i| chs.iter().fold(0.0f64, |m, c| m.max((c[i] as f64).abs()))).collect();
    let lv = level(&peak, (sr * 0.005) as usize);
    let target: Vec<f64> = lv.iter().map(|v| if *v < threshold { ((threshold - v) * (ratio - 1.0)).min(range) } else { 0.0 }).collect();
    // Opening fast is the attack: the reduction falls ahead of the sound (smooth on the inverse).
    let open: Vec<f64> = target.iter().map(|t| range - t).collect();
    let curve = smooth(&open, (attack * sr / 1000.0) as usize, (hold * sr / 1000.0) as usize, release * sr / 1000.0);
    for i in 0..n {
        let g = 10f64.powf(-(range - curve[i]).max(0.0) / 20.0) as f32;
        for c in chs.iter_mut() {
            c[i] *= g;
        }
    }
}

/// Dialogue leveller: K-weighted loudness over 400 ms (10 ms steps) ridden to `target` LUFS, up to
/// `max_gain` dB up and `max_cut` dB down; pauses (under `floor` dB, or 25 dB under the loudest
/// speech) keep the gain they had. The gain moves with time constant `speed` s, forward and back
/// (no lag), so a phrase is levelled as a whole, not pumped syllable by syllable.
/// `weights`: each channel's BS.1770 weight (bed/; stereo 1, 1).
pub fn leveller(chs: &mut [&mut [f32]], weights: &[f64], sr: f64, target: f64, max_gain: f64, max_cut: f64, speed: f64, floor: f64) {
    let mut kw: Vec<[crate::analysis::loudness::Bq; 2]> = chs.iter().map(|_| crate::analysis::loudness::k_weighting(sr)).collect();
    let hop = (sr * 0.01) as usize;
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let mut steps = vec![];
    let mut acc = 0.0;
    for i in 0..n {
        let mut s = 0.0;
        for (c, [shelf, hp]) in kw.iter_mut().enumerate() {
            let y = hp.run(shelf.run(chs[c][i] as f64));
            s += weights[c] * y * y;
        }
        acc += s;
        if (i + 1) % hop == 0 || i + 1 == n {
            steps.push(acc / hop as f64);
            acc = 0.0;
        }
    }
    let loud: Vec<f64> = (0..steps.len()).map(|s| { let w = &steps[s.saturating_sub(20)..(s + 20).min(steps.len())]; -0.691 + db(w.iter().sum::<f64>() / w.len() as f64) }).collect();
    let top = loud.iter().fold(DB_FLOOR, |m, v| m.max(*v));
    let mut gain = vec![0.0; loud.len()];
    let mut last: Option<f64> = None;
    for s in 0..loud.len() {
        if loud[s] > floor && loud[s] > top - 25.0 {
            last = Some((target - loud[s]).clamp(-max_cut, max_gain));
        }
        gain[s] = last.unwrap_or(f64::NAN);
    }
    // Before the first speech: its gain.
    let first = gain.iter().copied().find(|g| !g.is_nan()).unwrap_or(0.0);
    gain.iter_mut().filter(|g| g.is_nan()).for_each(|g| *g = first);
    let a = (-0.01 / speed.max(0.01)).exp();
    for pass in 0..2 {
        let idx: Vec<usize> = if pass == 0 { (0..gain.len()).collect() } else { (0..gain.len()).rev().collect() };
        let mut y = gain[idx[0]];
        for &s in &idx {
            y = a * y + (1.0 - a) * gain[s];
            gain[s] = y;
        }
    }
    for i in 0..n {
        let pos = i as f64 / hop as f64;
        let (k, fr) = (pos.floor() as usize, pos.fract());
        let gdb = gain[k.min(gain.len() - 1)] * (1.0 - fr) + gain[(k + 1).min(gain.len() - 1)] * fr;
        let g = 10f64.powf(gdb / 20.0) as f32;
        for c in chs.iter_mut() {
            c[i] *= g;
        }
    }
}
