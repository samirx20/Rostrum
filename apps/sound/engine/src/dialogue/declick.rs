//! De-click: where the clicks are (AR-residual impulses that stand out of the voice's own pulses),
//! filled by the AR interpolation of lsar.rs.

use crate::dialogue::lsar::{fill, model, ORDER};

/// Clicks: AR-residual impulses up to `max_len` samples that stand out of both the block's typical
/// residual (`3 + (10 − sensitivity)` robust deviations) and every other peak around them (±21 ms:
/// `1.5 + 0.3·(10 − sensitivity)` times the largest), so a voice's own glottal pulses — impulsive in
/// the residual too, but alike from period to period — are never taken for clicks. Returns the clicks removed.
pub fn declick(x: &mut [f32], sensitivity: f64, max_len: usize) -> usize {
    let gaps = clicks(x, sensitivity, max_len);
    fill(x, &gaps, None)
}

/// Where the clicks are: [from, to) samples.
pub fn clicks(x: &[f32], sensitivity: f64, max_len: usize) -> Vec<(usize, usize)> {
    let (k, k_peak) = (3.0 + (10.0 - sensitivity), 1.5 + 0.3 * (10.0 - sensitivity));
    let block = 4096;
    let mut res = vec![0.0f64; x.len()];
    let mut sigma = vec![0.0f64; x.len().div_ceil(block)];
    for (b, s) in (0..x.len()).step_by(block).enumerate() {
        let e = (s + block).min(x.len());
        let w: Vec<f64> = x[s.saturating_sub(ORDER)..e].iter().map(|v| *v as f64).collect();
        let off = s - s.saturating_sub(ORDER);
        let a = model(&w, &vec![true; w.len()], ORDER);
        for t in off.max(ORDER)..w.len() {
            res[s + t - off] = (0..=ORDER).map(|j| a[j] * w[t - j]).sum();
        }
        let mut mags: Vec<f64> = res[s..e].iter().map(|v| v.abs()).collect();
        mags.sort_by(|a, b| a.total_cmp(b));
        sigma[b] = 1.4826 * mags[mags.len() / 2];
    }
    let reach = 1024;
    let mut gaps: Vec<(usize, usize)> = vec![];
    let mut t = ORDER;
    while t < res.len() {
        let v = res[t].abs();
        if v <= k * sigma[t / block] || v == 0.0 {
            t += 1;
            continue;
        }
        // Where the residual settles after it (the click and the model's ringing).
        let mut end = t + 1;
        while end < res.len() && end < t + max_len + ORDER && res[end].abs() > 0.25 * v {
            end += 1;
        }
        let around = (t.saturating_sub(reach)..(t + reach).min(res.len())).filter(|&i| i + 2 < t || i > end + ORDER).map(|i| res[i].abs()).fold(0.0, f64::max);
        if v > k_peak * around && end - t <= max_len {
            gaps.push((t.saturating_sub(2), (end + 2).min(x.len())));
        }
        t = end + 1;
    }
    gaps
}
