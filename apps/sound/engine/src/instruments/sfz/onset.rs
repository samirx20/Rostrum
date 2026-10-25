//! When a sample is heard: its attack, measured once from the sample itself (a slow bow, a horn's breath, a harp
//! string's pluck noise), so a note can start that much early and be heard on its beat (finding 4 of the
//! 2026-10-25 agent pieces: sampled brass, horn and harp read 40-60 ms late).
//!
//! The definition (one, used by the score and by `range`): the first moment the sample's 10 ms RMS envelope comes
//! within 12 dB of the loudest it gets in its first half second, measured from where the region starts playing it.
//! A note leads by that (and the region's `ampeg_delay`), at most `MAX_LEAD`: a swell longer than that is the
//! sound's shape, not its lateness.

/// The most a note starts early (seconds).
pub const MAX_LEAD: f64 = 0.15;
const WINDOW: f64 = 0.010;
const HOP: f64 = 0.001;
const SPAN: f64 = 0.5;
const WITHIN_DB: f64 = -12.0;

/// Frames from `from` to where the sample is heard (0 for silence).
pub fn find(frames: &[[f32; 2]], rate: f64, from: usize) -> usize {
    let end = frames.len().min(from + (SPAN * rate) as usize);
    if end <= from {
        return 0;
    }
    let mut sums = Vec::with_capacity(end - from + 1);
    let mut acc = 0.0f64;
    sums.push(0.0);
    for f in &frames[from..end] {
        let m = 0.5 * (f[0] as f64 + f[1] as f64);
        acc += m * m;
        sums.push(acc);
    }
    let (win, hop) = (((WINDOW * rate) as usize).max(1), ((HOP * rate) as usize).max(1));
    let n = end - from;
    if n <= win {
        return 0;
    }
    let env: Vec<f64> = (0..=(n - win)).step_by(hop).map(|k| sums[k + win] - sums[k]).collect();
    let top = env.iter().cloned().fold(0.0, f64::max);
    if top <= 1e-14 {
        return 0;
    }
    let at = top * 10f64.powf(WITHIN_DB / 10.0); // window energies: 12 dB under in RMS is 10^-1.2 of the energy
    let k = env.iter().position(|&e| e >= at).unwrap_or(0);
    k * hop + win / 2
}

/// How early an instrument file's notes start, in ms: the median and the most over one note per sample it plays at
/// a forte-ish velocity (what `range` answers as `attackMs`; the score leads each note by its own region's).
pub fn typical_ms(file: &str) -> Result<Option<(f64, f64)>, String> {
    const SR: f64 = 48000.0;
    let regions = super::instrument(file)?;
    let mut seen = std::collections::HashSet::new();
    let mut ms = vec![];
    for key in 0..=127u8 {
        for r in super::select(&regions, key, 100, 0, 0.0) {
            if seen.insert(r.sample.clone()) {
                let v = super::SfzVoice::new(r, super::cached(&r.sample, super::read_wav)?, key as f64, 0.8, 0.0, false, false, 1.0, None, SR);
                ms.push(v.lead() as f64 / SR * 1000.0);
            }
        }
    }
    if ms.is_empty() {
        return Ok(None);
    }
    ms.sort_by(f64::total_cmp);
    Ok(Some((ms[ms.len() / 2], ms[ms.len() - 1])))
}
