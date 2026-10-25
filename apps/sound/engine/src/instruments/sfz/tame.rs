//! An even kit (contract `{"kit": …, "even": true}`): each drum sample's transient held within `CREST_DB` of the hit's
//! own loudness, and each kit piece at its measured starting level (engine/data/kit_levels.json, by
//! devtools/kit_levels.py). Agent piece 5 (2026-10-25): one recorded kick's spike stood ~19 dB over its loudness and
//! pulled the whole master down 8 dB; mixed drums stand 12-15 dB over theirs. The sample is limited once, when it is
//! loaded (a 2 ms look-ahead, 40 ms recovery, so only the first milliseconds of a hit move), and kept: every hit plays
//! the same tamed sample, soft or loud, so a kit sounds as it did, with its spikes in reach.

use std::path::Path;
use std::sync::Arc;

use super::{onset, read_wav, Sample};

/// How far a hit's peak may stand over its loudness (dB: sample peak over its loudest 400 ms, K-weighted).
pub const CREST_DB: f64 = 15.0;
const LOOKAHEAD: f64 = 0.002;
const RECOVER: f64 = 0.040;

/// A sample with its transients held in reach (a cache entry of its own beside the sample as recorded).
pub struct Tamed(pub Arc<Sample>);

pub fn read(path: &Path) -> Result<Tamed, String> {
    let mut s = read_wav(path)?;
    tame(&mut s.frames, s.rate);
    let onset = onset::find(&s.frames, s.rate, 0);
    Ok(Tamed(Arc::new(Sample { onset, ..s })))
}

/// The loudest 400 ms of the sample (K-weighted, both channels' power summed: LUFS), as a linear amplitude.
fn loudness(frames: &[[f32; 2]], rate: f64) -> f64 {
    let mut k = [crate::analysis::loudness::k_weighting(rate), crate::analysis::loudness::k_weighting(rate)];
    let power: Vec<f64> = frames.iter().map(|f| (0..2).map(|c| { let y = k[c].iter_mut().fold(f[c] as f64, |x, b| b.run(x)); y * y }).sum()).collect();
    let w = ((0.4 * rate) as usize).min(power.len()).max(1);
    let mut sum = power[..w].iter().sum::<f64>();
    let mut top = sum;
    for i in w..power.len() {
        sum += power[i] - power[i - w];
        top = top.max(sum);
    }
    // LUFS = -0.691 + 10·log10(mean power): as an amplitude, 10^(LUFS / 20).
    10f64.powf((-0.691 + 10.0 * (top / w as f64).max(1e-20).log10()) / 20.0)
}

fn tame(frames: &mut [[f32; 2]], rate: f64) {
    if frames.is_empty() {
        return;
    }
    let ceiling = loudness(frames, rate) * 10f64.powf(CREST_DB / 20.0);
    let need: Vec<f64> = frames.iter().map(|f| { let a = f[0].abs().max(f[1].abs()) as f64; if a > ceiling { ceiling / a } else { 1.0 } }).collect();
    if need.iter().all(|&g| g >= 1.0) {
        return;
    }
    // Recovery forward (smooth, 40 ms), then the attack backward: a straight ramp down over the look-ahead into each
    // peak, so the gain never steps and every frame stays at or under the ceiling.
    let rc = 1.0 - (-1.0 / (RECOVER * rate)).exp();
    let mut g = need.clone();
    for i in 1..g.len() {
        g[i] = g[i].min(g[i - 1] + (1.0 - g[i - 1]) * rc);
    }
    let step = 1.0 / (LOOKAHEAD * rate).max(1.0);
    for i in (0..g.len() - 1).rev() {
        g[i] = g[i].min(g[i + 1] + step);
    }
    for (f, g) in frames.iter_mut().zip(&g) {
        *f = [(f[0] as f64 * g) as f32, (f[1] as f64 * g) as f32];
    }
}
