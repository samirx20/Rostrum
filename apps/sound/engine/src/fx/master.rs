//! The mastering stage (a mix's `master`, decided by TypeScript): a glue compressor linked across the bed,
//! the mix normalised to an integrated loudness target (ITU-R BS.1770-4 / EBU R128: K-weighting,
//! 400 ms blocks, absolute and relative gates) and a look-ahead true-peak limiter (4× oversampled
//! peaks), so a social-media mix lands at −14 LUFS with no inter-sample peak over −1 dBTP.
//! The measurements are analysis/loudness.rs.

use serde::Deserialize;

use crate::analysis::loudness::{integrated_lufs_n, sample_peaks};

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct MasterSpec {
    /// Integrated loudness target (LUFS), or none: the level is left as mixed (still limited).
    pub loudness: Option<f64>,
    /// True-peak ceiling (dBTP).
    pub true_peak: f64,
    /// Glue compression 0 (none) … 1 (firm): ratio 1 + 3·glue over the program's own loudness.
    pub glue: f64,
}

/// A look-ahead limiter on true peaks, linked across the channels: the gain reaches what each peak
/// needs by the time it plays (a held minimum smoothed over the look-ahead, which never overshoots),
/// then recovers over `release`.
fn limit(chs: &mut [Vec<f32>], ceiling: f64, sr: f64) {
    let peaks = sample_peaks(&chs.iter().map(|c| c.as_slice()).collect::<Vec<_>>());
    let n = peaks.len();
    let la = (sr * 0.0015).round() as usize;
    let need: Vec<f64> = peaks.iter().map(|&p| if p > ceiling { ceiling / p } else { 1.0 }).collect();
    // Minimum over [i, i + la], then an exponential recovery.
    let mut held = vec![1.0; n];
    let mut dq: std::collections::VecDeque<usize> = Default::default();
    for j in (0..n).rev() {
        while dq.back().is_some_and(|&k| need[k] >= need[j]) {
            dq.pop_back();
        }
        dq.push_back(j);
        while dq.front().is_some_and(|&k| k > j + la) {
            dq.pop_front();
        }
        held[j] = need[*dq.front().unwrap()];
    }
    let rel = 1.0 - (-1.0 / (0.08 * sr)).exp();
    let mut g = 1.0f64;
    for h in held.iter_mut() {
        g = if *h < g { *h } else { g + (1.0 - g) * rel };
        g = g.min(*h);
        *h = g;
    }
    // A moving average over the look-ahead: every gain in the window is already at most the peak's need.
    let mut sum = 0.0;
    for i in 0..n {
        sum += held[i];
        if i > la {
            sum -= held[i - la - 1];
        }
        let g = sum / (i.min(la) + 1) as f64;
        for c in chs.iter_mut() {
            c[i] = (c[i] as f64 * g) as f32;
        }
    }
}

/// Feed-forward compression linked across the channels, over the program's own loudness (soft
/// knee, 6 dB); the detector is the BS.1770-weighted mean power (the LFE does not drive it).
fn glue(chs: &mut [Vec<f32>], weights: &[f64], amount: f64, program: f64, sr: f64) {
    if amount <= 0.0 {
        return;
    }
    let ratio = 1.0 + 3.0 * amount;
    let threshold = program + 3.0;
    let (att, rel) = (1.0 - (-1.0 / (0.025 * sr)).exp(), 1.0 - (-1.0 / (0.18 * sr)).exp());
    let det = 1.0 - (-1.0 / (0.01 * sr)).exp();
    let wsum: f64 = weights.iter().sum::<f64>().max(1e-9);
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let (mut ms, mut gr) = (0.0f64, 0.0f64);
    for i in 0..n {
        let mut p = 0.0;
        for (c, w) in chs.iter().zip(weights) {
            let x = c[i] as f64;
            p += w * x * x;
        }
        ms += det * (p / wsum - ms);
        let lvl = 10.0 * ms.max(1e-12).log10();
        let over = lvl - threshold;
        let want = if over <= -3.0 { 0.0 } else if over < 3.0 { (1.0 / ratio - 1.0) * (over + 3.0).powi(2) / 12.0 } else { (1.0 / ratio - 1.0) * over };
        gr += (if want < gr { att } else { rel }) * (want - gr);
        let g = 10f64.powf(gr / 20.0);
        for c in chs.iter_mut() {
            c[i] = (c[i] as f64 * g) as f32;
        }
    }
}

/// Masters a bed in place: glue, then gain to the target (BS.1770 with the layout's channel weights),
/// then the true-peak limiter (linked: every channel under the ceiling); the gain is corrected and
/// the chain re-run (from the glued signal) until the result is within 0.2 LU.
pub fn master_n(chs: &mut [Vec<f32>], weights: &[f64], spec: &MasterSpec, sr: f64) {
    let lufs = |chs: &[Vec<f32>]| integrated_lufs_n(&chs.iter().map(|c| c.as_slice()).collect::<Vec<_>>(), weights, sr);
    let program = lufs(chs);
    // A little under the ceiling: encoders (mp3, aac) and other meters read inter-sample peaks a few tenths higher.
    let ceiling = 10f64.powf((spec.true_peak - 0.3) / 20.0);
    if program <= -69.0 {
        // No integrated loudness to read (silence, or under the 400 ms gate: a UI click): the ceiling still holds.
        limit(chs, ceiling, sr);
        return;
    }
    glue(chs, weights, spec.glue, program, sr);
    let src: Vec<Vec<f32>> = chs.to_vec();
    let mut gain_db = spec.loudness.map_or(0.0, |t| t - lufs(chs));
    for pass in 0..4 {
        let g = 10f64.powf(gain_db / 20.0) as f32;
        for (c, s) in chs.iter_mut().zip(&src) {
            for i in 0..c.len() {
                c[i] = s[i] * g;
            }
        }
        limit(chs, ceiling, sr);
        let Some(target) = spec.loudness else { break };
        let got = lufs(chs);
        if (got - target).abs() <= 0.2 || pass == 3 {
            break;
        }
        gain_db += target - got;
    }
}

#[cfg(test)]
#[path = "master_tests.rs"]
mod tests;
