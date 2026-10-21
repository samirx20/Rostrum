//! The tone match (a clip's `matchEq`): an EQ curve ([Hz, dB] points, measured once on the host from
//! the two takes' long-term spectra and stored in the document) as an FIR filter, by frequency
//! sampling: linear phase (a symmetric, Hann-windowed impulse, its delay removed: no phase change)
//! or minimum phase (the same magnitude through the real cepstrum: no pre-ringing, no delay).

use std::f64::consts::PI;

use crate::fx::convolve::{convolve, fft};

/// The curve's gain (dB) at `hz`: straight lines on a log-frequency axis, held past the ends.
fn gain_at(curve: &[[f64; 2]], hz: f64) -> f64 {
    let (first, last) = (curve[0], curve[curve.len() - 1]);
    if hz <= first[0] {
        return first[1];
    }
    if hz >= last[0] {
        return last[1];
    }
    for w in curve.windows(2) {
        if hz <= w[1][0] {
            let t = (hz.ln() - w[0][0].ln()) / (w[1][0].ln() - w[0][0].ln());
            return w[0][1] + (w[1][1] - w[0][1]) * t;
        }
    }
    last[1]
}

/// The FIR taps (and the delay to remove: n/2 for linear phase, 0 for minimum phase).
pub fn design(curve: &[[f64; 2]], minimum: bool, sr: f64) -> (Vec<f64>, usize) {
    let n = if sr > 50000.0 { 8192 } else { 4096 };
    let mag: Vec<f64> = (0..n).map(|k| { let k = if k <= n / 2 { k } else { n - k }; 10f64.powf(gain_at(curve, (k as f64 * sr / n as f64).max(1.0)) / 20.0) }).collect();
    let (mut re, mut im) = (vec![0.0; n], vec![0.0; n]);
    if !minimum {
        re.copy_from_slice(&mag);
        fft(&mut re, &mut im, true);
        let taps: Vec<f64> = (0..n).map(|i| re[(i + n / 2) % n] * (0.5 - 0.5 * (2.0 * PI * i as f64 / n as f64).cos())).collect();
        return (taps, n / 2);
    }
    // Real cepstrum of the log magnitude, folded onto positive quefrencies: the minimum-phase spectrum.
    for k in 0..n {
        re[k] = mag[k].max(1e-6).ln();
    }
    fft(&mut re, &mut im, true);
    for i in 1..n / 2 {
        re[i] *= 2.0;
        im[i] = 0.0;
    }
    for i in n / 2 + 1..n {
        re[i] = 0.0;
        im[i] = 0.0;
    }
    fft(&mut re, &mut im, false);
    for k in 0..n {
        let (m, p) = (re[k].exp(), im[k]);
        (re[k], im[k]) = (m * p.cos(), m * p.sin());
    }
    fft(&mut re, &mut im, true);
    // Half the length, its last quarter faded out.
    let len = n / 2;
    let taps: Vec<f64> = (0..len).map(|i| { let fade = if i < len * 3 / 4 { 1.0 } else { 0.5 + 0.5 * (PI * (i - len * 3 / 4) as f64 / (len / 4) as f64).cos() }; re[i] * fade }).collect();
    (taps, 0)
}

/// Both channels through the curve.
pub fn apply(l: &mut [f32], r: &mut [f32], curve: &[[f64; 2]], phase: &str, sr: f64) {
    if curve.is_empty() {
        return;
    }
    let (taps, delay) = design(curve, phase == "minimum", sr);
    for ch in [l, r] {
        let mut x = ch.to_vec();
        x.extend(std::iter::repeat_n(0.0f32, delay));
        let y = convolve(&x, &taps);
        for (i, v) in ch.iter_mut().enumerate() {
            *v = y[i + delay] as f32;
        }
    }
}
