//! Hum removal: mains hum (50 / 60 Hz) and its harmonics. The fundamental is found in the clip — a
//! long spectrum (0.09 Hz bins) scored by how far each harmonic stands out of its neighbourhood —
//! then tracked second by second (mains drifts by tenths of a hertz), and a narrow notch follows
//! each harmonic that is really there (or every harmonic asked for, when the frequency is given).

use std::f64::consts::PI;

use crate::fx::convolve::fft;
use crate::fx::eq::biquad;

const LONG: usize = 1 << 19;
const BLOCK_SECONDS: f64 = 1.0;

pub struct Hum {
    pub f0: f64,
    /// How far each harmonic (1, 2, …) stands out of the spectrum around it (dB).
    pub prominence: Vec<f64>,
    /// The hum's level (dBFS): the power in its harmonics.
    pub level_db: f64,
}

/// Finds mains hum near 50 or 60 Hz (or near `near` when given); None when nothing stands out by 6 dB.
pub fn detect(x: &[f32], sr: f64, near: Option<f64>, harmonics: usize) -> Option<Hum> {
    let len = x.len().min(LONG);
    if len < (sr * 0.5) as usize {
        return None;
    }
    let (mut re, mut im) = (vec![0.0; LONG], vec![0.0; LONG]);
    for i in 0..len {
        re[i] = x[i] as f64 * (0.5 - 0.5 * (2.0 * PI * i as f64 / len as f64).cos());
    }
    fft(&mut re, &mut im, false);
    let p: Vec<f64> = (0..LONG / 2).map(|k| re[k] * re[k] + im[k] * im[k]).collect();
    let bin = sr / LONG as f64;
    // The power within ±0.3 Hz of f, against what the same bins would hold at the level 2 … 8 Hz
    // either side (its median over ln 2: the mean of noise, robust to the voice's own peaks).
    let around = |f: f64| -> (f64, f64) {
        let k = (f / bin).round() as usize;
        let w = (0.3 / bin).ceil() as usize;
        let lobe: Vec<f64> = (k.saturating_sub(w)..=(k + w).min(p.len() - 1)).map(|i| p[i]).collect();
        let (a, b) = ((2.0 / bin) as usize, (8.0 / bin) as usize);
        let mut bg: Vec<f64> = (a..b).flat_map(|d| [k.saturating_sub(d), (k + d).min(p.len() - 1)]).map(|i| p[i]).collect();
        bg.sort_by(|x, y| x.total_cmp(y));
        (lobe.iter().sum(), (bg[bg.len() / 2] / std::f64::consts::LN_2 * lobe.len() as f64).max(1e-30))
    };
    let ranges: Vec<(f64, f64)> = match near {
        Some(f) => vec![(f - 1.5, f + 1.5)],
        None => vec![(48.0, 52.0), (58.0, 62.0)],
    };
    let mut best = (0.0, f64::MIN);
    for (lo, hi) in ranges {
        let mut f = lo;
        while f <= hi {
            let score: f64 = (1..=4).map(|h| (around(f * h as f64).0 / around(f * h as f64).1).log10().max(0.0)).sum();
            if score > best.1 {
                best = (f, score);
            }
            f += 0.02;
        }
    }
    // The coarse search ties within a lobe: the fundamental is the peak bin within ±1 Hz, interpolated.
    let k0 = (best.0 / bin).round() as usize;
    let span = (1.0 / bin) as usize;
    let k = (k0.saturating_sub(span)..=(k0 + span).min(p.len() - 2)).max_by(|a, b| p[*a].total_cmp(&p[*b])).unwrap_or(k0).max(1);
    let (a, b, c) = (p[k - 1].max(1e-30).ln(), p[k].max(1e-30).ln(), p[k + 1].max(1e-30).ln());
    let d = if (a - 2.0 * b + c).abs() > 1e-12 { 0.5 * (a - c) / (a - 2.0 * b + c) } else { 0.0 };
    let f0 = (k as f64 + d.clamp(-0.5, 0.5)) * bin;
    // How far each harmonic stands out where the voice does not cover it: the quiet spectrum (each
    // bin's 20th percentile over time, so the pauses), its line against the bins 4 … 10 away.
    let (q, n) = quiet_spectrum(x, sr);
    let qbin = sr / n as f64;
    let line = |h: usize| -> (f64, f64) {
        let k = (f0 * h as f64 / qbin).round() as usize;
        let pk: f64 = (k.saturating_sub(1)..=(k + 1).min(q.len() - 1)).map(|i| q[i]).sum();
        let mut bg: Vec<f64> = (4..=10).flat_map(|d| [k.saturating_sub(d), (k + d).min(q.len() - 1)]).map(|i| q[i]).collect();
        bg.sort_by(|a, b| a.total_cmp(b));
        (pk, bg[bg.len() / 2].max(1e-30))
    };
    let prominence: Vec<f64> = (1..=harmonics).map(|h| { let (pk, bg) = line(h); 10.0 * (pk / (3.0 * bg)).log10() }).collect();
    let strong = prominence.iter().take(5).filter(|p| **p >= 6.0).count();
    if strong < 2 && prominence[0] < 10.0 {
        return None;
    }
    // A sine of amplitude A puts A²·3n²/16 in its Hann lobe: the hum's mean square from its lines.
    let hum_ms: f64 = (1..=harmonics).filter(|h| prominence[h - 1] >= 6.0).map(|h| { let (pk, bg) = line(h); (pk - 3.0 * bg).max(0.0) * 16.0 / (3.0 * (n * n) as f64) }).sum();
    Some(Hum { f0, prominence, level_db: 10.0 * hum_ms.max(1e-12).log10() })
}

/// Each bin's 20th-percentile power over Hann frames (16384 samples, a quarter hop; 8192 for short clips).
fn quiet_spectrum(x: &[f32], sr: f64) -> (Vec<f64>, usize) {
    let n = if x.len() as f64 >= 3.0 * 16384.0 * sr / 48000.0 { 16384 } else { 8192 };
    let w: Vec<f64> = (0..n).map(|i| 0.5 - 0.5 * (2.0 * PI * i as f64 / n as f64).cos()).collect();
    let mut cols: Vec<Vec<f64>> = vec![vec![]; n / 2];
    let (mut re, mut im) = (vec![0.0; n], vec![0.0; n]);
    let mut s = 0;
    loop {
        for i in 0..n {
            re[i] = x.get(s + i).copied().unwrap_or(0.0) as f64 * w[i];
            im[i] = 0.0;
        }
        fft(&mut re, &mut im, false);
        for k in 0..n / 2 {
            cols[k].push(re[k] * re[k] + im[k] * im[k]);
        }
        s += n / 4;
        if s + n / 2 >= x.len() {
            break;
        }
    }
    let q = cols.into_iter().map(|mut c| { let i = c.len() / 5; *c.select_nth_unstable_by(i, |a, b| a.total_cmp(b)).1 }).collect();
    (q, n)
}

/// The fundamental in one block, within ±0.4 Hz of `f0` (Goertzel power).
fn track(x: &[f32], sr: f64, f0: f64) -> f64 {
    let power = |f: f64| -> f64 {
        let c = 2.0 * (2.0 * PI * f / sr).cos();
        let (mut s1, mut s2) = (0.0, 0.0);
        for v in x {
            let s = *v as f64 + c * s1 - s2;
            (s2, s1) = (s1, s);
        }
        s1 * s1 + s2 * s2 - c * s1 * s2
    };
    let mut best = (f0, 0.0);
    let mut f = f0 - 0.4;
    while f <= f0 + 0.4 {
        // The fundamental alone: it sits under the voice, its harmonics may not.
        let pw = power(f);
        if pw > best.1 {
            best = (f, pw);
        }
        f += 0.02;
    }
    best.0
}

/// Notches on `freq` (0: detected) and its harmonics, `width` Hz wide, following the drift.
/// Returns the hum it removed (None: no hum found, nothing changed).
pub fn dehum(l: &mut [f32], r: &mut [f32], sr: f64, freq: f64, harmonics: usize, width: f64) -> Option<Hum> {
    let mid: Vec<f32> = l.iter().zip(r.iter()).map(|(a, b)| (a + b) * 0.5).collect();
    let hum = detect(&mid, sr, (freq > 0.0).then_some(freq), harmonics)
        .or_else(|| (freq > 0.0).then(|| Hum { f0: freq, prominence: vec![99.0; harmonics], level_db: -120.0 }))?;
    let used: Vec<usize> = (1..=harmonics).filter(|&h| freq > 0.0 || hum.prominence[h - 1] >= 3.0).filter(|&h| hum.f0 * (h as f64) < sr * 0.45).collect();
    let block = (sr * BLOCK_SECONDS) as usize;
    let per_block: Vec<f64> = mid.chunks(block).map(|c| if c.len() > block / 2 { track(c, sr, hum.f0) } else { hum.f0 }).collect();
    let f_at = |i: usize| -> f64 {
        let pos = (i as f64 / block as f64 - 0.5).max(0.0);
        let (k, fr) = (pos.floor() as usize, pos.fract());
        let a = per_block[k.min(per_block.len() - 1)];
        let b = per_block[(k + 1).min(per_block.len() - 1)];
        a + (b - a) * fr
    };
    for &h in &used {
        let mut z = [[0.0f64; 2]; 2];
        let mut c = biquad("notch", hum.f0 * h as f64, 0.0, hum.f0 * h as f64 / width, sr);
        for i in 0..l.len() {
            if i % 32 == 0 {
                let f = f_at(i) * h as f64;
                c = biquad("notch", f, 0.0, f / width, sr);
            }
            l[i] = c.tick(&mut z[0], l[i] as f64) as f32;
            r[i] = c.tick(&mut z[1], r[i] as f64) as f32;
        }
    }
    Some(hum)
}
