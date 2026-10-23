//! What the mix reports: the file's figures and each track's as it reaches the mix (what an agent checks).

use crate::bed::Layout;
use crate::mix::duck;
use crate::mix::mastergain::MasterGain;
use crate::mix::tape::Tape;
use std::sync::Arc;

pub struct Mix {
    pub layout: Layout,
    /// The finished mix on disk (tape.rs), in the layout's file order: `frames` long. Read it in blocks
    /// (`read`), or whole where a caller needs it whole (`channels`: playback, a surround report).
    pub out: Option<Tape>,
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
    /// Tracks kept as stems (render_keep): each as it reaches the master, in the layout's channels, on disk (tape.rs);
    /// stems.rs writes them through the master's gain, block by block.
    pub stems: Vec<(String, Arc<Tape>)>,
    /// Each bus as it leaves (after its effects and fader), kept when any stem is: with the direct tracks' stems
    /// these add up to what reaches the master.
    pub bus_stems: Vec<(String, Arc<Tape>)>,
    /// The master's linear gain (fader, lane, fades, loudness gain): the one gain the stems carry (bus.rs sets it).
    pub gain: Option<MasterGain>,
    /// What the mastering stage did (fx/master.rs): its gain, and the largest reductions of its glue and limiter.
    pub master: crate::fx::master::MasterReport,
    /// Energy per band of the file (balance.rs BANDS, dB; a surround bed's stereo fold-down): its tonal balance.
    pub bands: [f64; 5],
    /// The file's peak and RMS (dB) per 1/30 s window: the master strip's live meter (levels.rs).
    pub levels: Vec<[f32; 2]>,
    /// The file's momentary / short-term loudness, loudness range and correlation (analysis/loudstats.rs).
    pub loud: Option<crate::analysis::loudstats::Stats>,
}

impl Mix {
    fn tape(&self) -> Result<&Tape, String> {
        self.out.as_ref().ok_or_else(|| "the mix was not rendered (an engine fault)".to_string())
    }

    /// Frames in the file.
    pub fn frames(&self) -> usize {
        self.gain.as_ref().map_or(0, |g| g.total)
    }

    /// Frames `at .. at + n` of every channel.
    pub fn read(&self, at: usize, n: usize) -> Result<Vec<Vec<f32>>, String> {
        self.tape()?.read(at, n)
    }

    /// The whole mix in memory, one buffer per channel.
    pub fn channels(&self) -> Result<Vec<Vec<f32>>, String> {
        self.tape()?.whole()
    }

    pub fn loud(&self) -> Result<&crate::analysis::loudstats::Stats, String> {
        self.loud.as_ref().ok_or_else(|| "the mix was not measured (an engine fault)".to_string())
    }
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
    /// Peak and RMS (dB) per 1/30 s window, song time: the Mixer's live meter (levels.rs).
    pub levels: Vec<[f32; 2]>,
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

/// A track's (or bus') figures over its first `total` frames, the whole signal in memory.
pub(crate) fn track_stats(name: &str, chs: &[Vec<f32>], total: usize, sr: f64, layout: Layout) -> TrackStats {
    let mut m = TrackMeter::new(name, chs.len(), total, sr, layout);
    m.push(chs);
    m.finish()
}

/// A track's figures measured as it comes, block by block (read from its tape): what `TrackStats` reports, the
/// same bit for bit however the track is cut into blocks. Frames past `total` (a loop's tail) are not measured.
pub(crate) struct TrackMeter {
    name: String,
    nch: usize,
    total: usize,
    sr: f64,
    at: usize,
    frame: usize,
    floor: f64,
    peak: f64,
    /// The 10 ms frame being summed: its power so far and its first sample.
    fs: f64,
    f0: usize,
    sum: f64,
    n: usize,
    first: Option<usize>,
    last: usize,
    levels: Vec<f64>,
    energy: Vec<f64>,
    lufs: crate::analysis::loudness::Lufs,
    balance: crate::analysis::balance::Balance,
    win: super::levels::Windows,
}

impl TrackMeter {
    pub fn new(name: &str, nch: usize, total: usize, sr: f64, layout: Layout) -> TrackMeter {
        let weights = if nch == layout.channels() { layout.weights() } else { vec![1.0; nch] };
        TrackMeter {
            name: name.into(), nch, total, sr, at: 0, frame: (sr * 0.01).round().max(1.0) as usize, floor: 10f64.powf(-50.0 / 20.0),
            peak: 0.0, fs: 0.0, f0: 0, sum: 0.0, n: 0, first: None, last: 0, levels: vec![], energy: vec![0.0; nch],
            lufs: crate::analysis::loudness::Lufs::new(nch, &weights, sr), balance: crate::analysis::balance::Balance::new(sr, true),
            win: super::levels::Windows::new(sr),
        }
    }

    /// The 10 ms frame ending at `end` closed: its level, and whether it sounds.
    fn close(&mut self, end: usize) {
        let rms = (self.fs / (end - self.f0) as f64).sqrt();
        self.levels.push(if rms > 0.0 { 20.0 * rms.log10() } else { -120.0 });
        if rms > self.floor {
            self.first.get_or_insert(self.f0);
            self.last = end;
            self.sum += self.fs;
            self.n += end - self.f0;
        }
        (self.fs, self.f0) = (0.0, end);
    }

    /// The next frames (every channel the same length); what falls past `total` is left out.
    pub fn push(&mut self, chs: &[Vec<f32>]) {
        let n = chs.first().map_or(0, Vec::len).min(self.total - self.at);
        if n == 0 {
            return;
        }
        let nch = self.nch as f64;
        let cut: Vec<&[f32]> = chs.iter().map(|c| &c[..n]).collect();
        let lufs = &mut self.lufs;
        let balance = &mut self.balance;
        // The loudness and the balance each on a core of their own, the levels here.
        std::thread::scope(|sc| {
            sc.spawn(|| lufs.push(&cut));
            sc.spawn(|| {
                // A stereo track is measured as it is; a bed track through its fold-down.
                if cut.len() == 2 {
                    balance.push(cut[0], cut[1]);
                } else {
                    let st = as_stereo(&cut.iter().map(|c| c.to_vec()).collect::<Vec<_>>());
                    balance.push(&st[0], &st[1]);
                }
            });
        });
        for i in 0..n {
            let (mut p, mut top) = (0.0, 0.0f64);
            for (c, e) in chs.iter().zip(self.energy.iter_mut()) {
                let a = c[i] as f64;
                top = top.max(a.abs());
                p += a * a;
                *e += a * a;
            }
            self.peak = self.peak.max(top);
            self.win.frame(top, p / nch);
            self.fs += p / nch;
            let k = self.at + i + 1;
            if k - self.f0 == self.frame || k == self.total {
                self.close(k);
            }
        }
        self.at += n;
    }

    pub fn finish(self) -> TrackStats {
        let (bands, speech) = self.balance.finish();
        let all: f64 = self.energy.iter().sum();
        TrackStats {
            rms: if self.n > 0 { (self.sum / self.n as f64).sqrt() } else { 0.0 },
            span: self.first.map(|f| (f as f64 / self.sr, self.last as f64 / self.sr)),
            onsets: onsets(&self.levels, self.frame as f64 / self.sr),
            lufs: self.lufs.finish(),
            bands,
            speech,
            shares: (self.nch > 2 && all > 0.0).then(|| self.energy.iter().map(|e| ((e / all) * 1000.0).round() / 1000.0).collect()),
            levels: self.win.finish(),
            name: self.name,
            peak: self.peak,
        }
    }
}
