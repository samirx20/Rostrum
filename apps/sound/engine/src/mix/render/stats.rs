//! What the mix reports: the file's figures and each track's as it reaches the mix (what an agent checks).

use crate::bed::Layout;
use crate::mix::duck;

pub struct Mix {
    pub layout: Layout,
    /// One buffer per channel, in the layout's file order.
    pub channels: Vec<Vec<f32>>,
    pub peak: f64,
    pub sum_sq: f64,
    /// Each channel's sample sum (DC offset).
    pub sums: Vec<f64>,
    pub clipped: usize,
    /// Integrated loudness (LUFS, BS.1770 channel weights) and true peak (dBTP) of the file.
    pub lufs: f64,
    pub true_peak: f64,
    /// True peak (dBTP) of each 100 ms hop of the file (analysis/loudness.rs sample_peaks), the series behind `true_peak`.
    pub true_peak_series: Vec<f64>,
    pub ducks: Vec<(String, Vec<duck::DuckSpan>)>,
    pub tracks: Vec<TrackStats>,
    /// Each bus as it leaves (buses.rs), in schedule order; empty without buses.
    pub buses: Vec<TrackStats>,
    /// Energy per band of the file (balance.rs BANDS, dB; a surround bed's stereo fold-down): its tonal balance.
    pub bands: [f64; 5],
}

/// One track as it reaches the mix (after its effects, fader and ducking): what an agent checks.
pub struct TrackStats {
    pub name: String,
    pub peak: f64,
    /// RMS over the 10 ms frames where it sounds (above −50 dBFS).
    pub rms: f64,
    /// When it first and last sounds (seconds), or None if never.
    pub span: Option<(f64, f64)>,
    /// Where its sounds start (seconds): read on the track alone, so a pad under it hides nothing.
    pub onsets: Vec<f64>,
    /// Integrated loudness (LUFS) of the track alone, as it reaches the mix.
    pub lufs: f64,
    /// Energy per band where it sounds (balance.rs BANDS, dB).
    pub bands: [f64; 5],
    /// Its level in the speech band every 100 ms (dB): what masks a voice, and what a voice is.
    pub speech: Vec<f64>,
    /// In a surround bed: each channel's share of the track's energy (0 … 1, the layout's order).
    pub shares: Option<Vec<f64>>,
}

/// Onsets in 10 ms frame levels (dBFS): a frame above −50 dBFS that is 12 dB over the loudest of
/// the previous 50 ms (short enough to part 16ths), at least 80 ms after the previous onset. The mix readout uses the same rule.
pub fn onsets(frames: &[f64], frame_secs: f64) -> Vec<f64> {
    let mut out: Vec<f64> = vec![];
    for f in 0..frames.len() {
        if frames[f] < -50.0 {
            continue;
        }
        let before = frames[f.saturating_sub(5)..f].iter().cloned().fold(-120.0, f64::max);
        let t = f as f64 * frame_secs;
        if frames[f] - before >= 12.0 && out.last().map_or(true, |&p| t - p >= 0.08) {
            out.push((t * 100.0).round() / 100.0);
        }
    }
    out
}

/// A bed's channels as stereo for the stereo-only measures (balance.rs): the fold-down (bed/).
pub fn as_stereo(chs: &[Vec<f32>]) -> Vec<Vec<f32>> {
    match Layout::of_channels(chs.len()) {
        Ok(l) if l != Layout::Stereo => crate::bed::apply(&crate::bed::downmix(l, Layout::Stereo).expect("a surround bed folds to stereo"), chs),
        _ => chs.to_vec(),
    }
}

pub(crate) fn track_stats(name: &str, chs: &[Vec<f32>], total: usize, sr: f64, layout: Layout) -> TrackStats {
    let frame = (sr * 0.01).round().max(1.0) as usize;
    let floor = 10f64.powf(-50.0 / 20.0);
    let nch = chs.len() as f64;
    let (mut peak, mut sum, mut n, mut first, mut last) = (0.0f64, 0.0f64, 0usize, None, 0usize);
    let mut levels = vec![];
    for f in (0..total).step_by(frame) {
        let end = (f + frame).min(total);
        let mut s = 0.0;
        for i in f..end {
            let mut p = 0.0;
            for c in chs {
                let a = c[i] as f64;
                peak = peak.max(a.abs());
                p += a * a;
            }
            s += p / nch;
        }
        let rms = (s / (end - f) as f64).sqrt();
        levels.push(if rms > 0.0 { 20.0 * rms.log10() } else { -120.0 });
        if rms > floor {
            first.get_or_insert(f);
            last = end;
            sum += s;
            n += end - f;
        }
    }
    let weights = if chs.len() == layout.channels() { layout.weights() } else { vec![1.0; chs.len()] };
    let cut: Vec<&[f32]> = chs.iter().map(|c| &c[..total.min(c.len())]).collect();
    // A stereo track is measured as it is; a bed track through its fold-down.
    let folded;
    let st: &[Vec<f32>] = if chs.len() == 2 { chs } else { folded = as_stereo(chs); &folded };
    let (bands, speech) = crate::analysis::balance::bands_and_speech(&st[0], &st[1], total, sr);
    let energy: Vec<f64> = chs.iter().map(|c| c[..total.min(c.len())].iter().map(|v| (*v as f64).powi(2)).sum()).collect();
    let all: f64 = energy.iter().sum();
    TrackStats {
        name: name.into(),
        peak,
        rms: if n > 0 { (sum / n as f64).sqrt() } else { 0.0 },
        span: first.map(|f| (f as f64 / sr, last as f64 / sr)),
        onsets: onsets(&levels, frame as f64 / sr),
        lufs: crate::analysis::loudness::integrated_lufs_n(&cut, &weights, sr),
        bands,
        speech,
        shares: (chs.len() > 2 && all > 0.0).then(|| energy.iter().map(|e| ((e / all) * 1000.0).round() / 1000.0).collect()),
    }
}
