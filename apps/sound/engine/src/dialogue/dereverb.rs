//! The spectral dialogue repairs: late-reverb suppression (a roomy voiceover made drier) and
//! spectral repair (a cough, a siren, a chair squeak removed from a time–frequency region).
//!
//! Dereverb is statistical late-reverberation suppression (Lebart, Boucher & Denbigh 2001; Habets
//! 2007): the room's tail is modelled as an exponential decay, so the late reverb's power in a bin
//! now is the power some 50 ms ago scaled by e^(−2·δ·T) with δ = 3·ln 10 / RT60, and that much is
//! subtracted (a spectral gain, floored). The room's decay time is estimated blind from the clip
//! (rt60.rs: maximum-likelihood decay rates of its decaying stretches) unless given, so the strength
//! follows the room: a dry take keeps its sound, a long room loses more. No model: deterministic.
//!
//! Spectral repair attenuates each bin of the region down to the level the sound had around it
//! (the quieter of the frames just before and just after), keeping what was under it.

use crate::mix::schedule::Repair;
use crate::analysis::stft::{apply_mask, frame_time, Spec};

fn sizes(sr: f64) -> (usize, usize) {
    let n = if sr >= 32000.0 { 2048 } else { 1024 };
    (n, n / 4)
}

/// The room's decay time (RT60, s), estimated blind from the clip (rt60.rs). None: too few free decays.
pub fn decay_time(l: &[f32], r: &[f32], sr: f64) -> Option<f64> {
    crate::analysis::rt60::blind(l, r, sr)
}

/// The suppression gain per frame and bin: `amount` of the modelled late reverb taken out, never under `floor`.
pub fn late_gain(s: &Spec, rt60: f64, sr: f64, amount: f64, floor: f64) -> Vec<Vec<f64>> {
    let delay = ((0.05 * sr / s.hop as f64).round() as usize).max(1);
    let decay = (-2.0 * 3.0 * std::f64::consts::LN_10 / rt60 * delay as f64 * s.hop as f64 / sr).exp();
    let bins = s.n / 2 + 1;
    let mut smooth: Vec<Vec<f64>> = vec![vec![0.0; bins]; s.re.len()];
    let mut g = vec![vec![1.0; bins]; s.re.len()];
    let mut prev_g = vec![1.0; bins];
    for f in 0..s.re.len() {
        for k in 0..bins {
            let p = s.power(f, k);
            smooth[f][k] = if f > 0 { 0.6 * smooth[f - 1][k] + 0.4 * p } else { p };
            if f >= delay {
                let late = decay * smooth[f - delay][k];
                let raw = (1.0 - amount * late / smooth[f][k].max(1e-20)).max(floor * floor).sqrt();
                let v = 0.5 * prev_g[k] + 0.5 * raw;
                prev_g[k] = v;
                g[f][k] = v;
            }
        }
    }
    g
}

/// Dereverb: `amount` (0 … 1) of the modelled late reverb removed, at most `reduction` dB per bin;
/// `time` the room's RT60 in seconds (0: measured). Returns the RT60 used (None: none measured, unchanged).
pub fn dereverb(l: &mut [f32], r: &mut [f32], sr: f64, amount: f64, reduction: f64, time: f64) -> Option<f64> {
    let rt60 = if time > 0.0 { time } else { decay_time(l, r, sr)? };
    let (n, hop) = sizes(sr);
    let floor = 10f64.powf(-reduction / 20.0);
    apply_mask(l, r, n, hop, &|s| late_gain(s, rt60, sr, amount, floor));
    Some(rt60)
}

/// Spectral repair: each region's bins brought down to the level around it.
pub fn repair(l: &mut [f32], r: &mut [f32], sr: f64, regions: &[Repair]) {
    if regions.is_empty() {
        return;
    }
    let (n, hop) = sizes(sr);
    apply_mask(l, r, n, hop, &|s| {
        let bins = n / 2 + 1;
        let hz = sr / n as f64;
        let mut g = vec![vec![1.0f64; bins]; s.re.len()];
        let frames = s.re.len();
        let slack = hop as f64 / sr;
        for reg in regions {
            let inside: Vec<usize> = (0..frames).filter(|&f| { let t = frame_time(f, n, hop, sr); t >= reg.at - slack && t <= reg.at + reg.duration + slack }).collect();
            let (Some(&a), Some(&b)) = (inside.first(), inside.last()) else { continue };
            let before: Vec<usize> = (a.saturating_sub(4)..a.saturating_sub(1)).collect();
            let after: Vec<usize> = (b + 2..(b + 5).min(frames)).collect();
            let (k0, k1) = ((reg.low_hz / hz).floor() as usize, ((reg.high_hz / hz).ceil() as usize).min(bins - 1));
            for k in k0..=k1 {
                let mean = |fs: &[usize]| (!fs.is_empty()).then(|| (fs.iter().map(|&f| s.power(f, k)).sum::<f64>() / fs.len() as f64).max(1e-20).ln());
                let (pb, pa) = (mean(&before), mean(&after));
                let edge = if k == k0 || k == k1 { 0.5 } else { 1.0 };
                for &f in &inside {
                    // The quieter side where both are known: what is left once the noise is gone (the
                    // louder side may hold the end of a word, or the noise's own tail).
                    let reference = match (pb, pa) {
                        (Some(x), Some(y)) => x.min(y).exp(),
                        (Some(x), None) | (None, Some(x)) => x.exp(),
                        (None, None) => 0.0,
                    };
                    let gain = (reference / s.power(f, k).max(1e-20)).sqrt().min(1.0);
                    g[f][k] = g[f][k].min(gain.powf(edge));
                }
            }
        }
        g
    });
}
