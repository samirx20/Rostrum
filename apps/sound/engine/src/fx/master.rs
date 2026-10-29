//! The mastering stage (a mix's `master`, decided by TypeScript): a glue compressor linked across the bed,
//! the mix normalised to an integrated loudness target (ITU-R BS.1770-4 / EBU R128: K-weighting,
//! 400 ms blocks, absolute and relative gates) and a look-ahead true-peak limiter (4× oversampled
//! peaks), so a social-media mix lands at −14 LUFS with no inter-sample peak over −1 dBTP.
//! The measurements are analysis/loudness.rs.

use serde::Deserialize;

use std::collections::VecDeque;

use crate::analysis::loudness::{Lufs, Peaks};
use crate::mix::spool::Spool;
use crate::mix::spool::CHUNK as BLOCK;

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct MasterSpec {
    /// Integrated loudness target (LUFS), or none: the level is left as mixed (still limited).
    pub loudness: Option<f64>,
    /// True-peak ceiling (dBTP).
    pub true_peak: f64,
    /// Glue compression 0 (none) … 1 (firm): ratio 1 + 3·glue over the program's own loudness.
    pub glue: f64,
    /// The most the limiter may pull (dB), or none: a mix that would need more is turned down as a whole instead
    /// (one gain for the song, so the balance is untouched), landing under its loudness target.
    #[serde(default)]
    pub max_limit: Option<f64>,
}

/// What the mastering stage did: `gain_db` is the gain to the loudness target (the same on every sample);
/// `glue_db` and `limiter_db` are the largest gain reductions (≥ 0 dB) of the glue and the limiter; `held_db` (≥ 0 dB)
/// how far the whole mix was turned down under its target (or fader) so the limiter keeps within `max_limit`.
#[derive(Clone, Copy, Debug, Default)]
pub struct MasterReport {
    /// The program's own integrated loudness before the stage (LUFS; -70 and under: none to read): the glue's level.
    pub program: f64,
    pub gain_db: f64,
    pub glue_db: f64,
    pub limiter_db: f64,
    pub held_db: f64,
}

/// The mastering stage's gain at every frame, as it was applied to the mix (one channel each, spooled like the mix):
/// the glue's (None without glue) and the limiter pass's (the gain to the target times the limiter's own). Both are
/// linked across the channels, so the same gain on every stem keeps the stems adding up to the mix (render/stems.rs).
pub struct Dynamics {
    pub glue: Option<Spool>,
    pub limiter: Spool,
}

impl Dynamics {
    /// The whole gain (glue × target gain × limiter) at frames `at .. at + n`.
    pub fn read(&self, at: usize, n: usize) -> Result<Vec<f64>, String> {
        let mut g: Vec<f64> = self.limiter.read(at, n)?.swap_remove(0).into_iter().map(f64::from).collect();
        if let Some(glue) = &self.glue {
            g.iter_mut().zip(glue.read(at, n)?.swap_remove(0)).for_each(|(g, x)| *g *= x as f64);
        }
        Ok(g)
    }
}

/// A look-ahead limiter on true peaks, linked across the channels: the gain reaches what each peak
/// needs by the time it plays (a held minimum smoothed over the look-ahead, which never overshoots),
/// then recovers over `release`. Fed block by block, it answers each frame once the look-ahead after it is in
/// (`finish`: the rest); `deepest` is its largest gain reduction (dB, ≥ 0).
pub(super) struct Limiter {
    ceiling: f64,
    la: usize,
    rel: f64,
    peaks: Peaks,
    /// The frames' needs not yet past the window: (frame, need), needs rising from front to back.
    window: VecDeque<(usize, f64)>,
    needs: usize,
    held: usize,
    g: f64,
    /// The last `la + 1` recovered gains, and their sum (the moving average).
    recent: VecDeque<f64>,
    sum: f64,
    lowest: f64,
    /// The frames waiting for their gain.
    wait: Vec<VecDeque<f32>>,
    /// The gain each released frame got, until `limited` takes them (Dynamics).
    given: Vec<f32>,
}

impl Limiter {
    fn new(nch: usize, ceiling: f64, sr: f64) -> Limiter {
        let la = (sr * 0.0015).round() as usize;
        Limiter { ceiling, la, rel: 1.0 - (-1.0 / (0.08 * sr)).exp(), peaks: Peaks::new(nch), window: VecDeque::new(), needs: 0, held: 0, g: 1.0, recent: VecDeque::new(), sum: 0.0, lowest: 1.0, wait: vec![VecDeque::new(); nch], given: vec![] }
    }

    fn push(&mut self, block: &[Vec<f32>]) -> Vec<Vec<f32>> {
        for (w, c) in self.wait.iter_mut().zip(block) {
            w.extend(c.iter().copied());
        }
        let peaks = self.peaks.push(&block.iter().map(|c| c.as_slice()).collect::<Vec<_>>());
        self.needs_in(&peaks, false)
    }

    fn finish(&mut self) -> Vec<Vec<f32>> {
        let peaks = self.peaks.finish();
        self.needs_in(&peaks, true)
    }

    /// Each peak's need into the window; then every frame whose window is whole (`ended`: every frame left) out.
    fn needs_in(&mut self, peaks: &[f64], ended: bool) -> Vec<Vec<f32>> {
        let mut out = vec![vec![]; self.wait.len()];
        for &p in peaks {
            let need = if p > self.ceiling { self.ceiling / p } else { 1.0 };
            while self.window.back().is_some_and(|&(_, v)| v >= need) {
                self.window.pop_back();
            }
            self.window.push_back((self.needs, need));
            self.needs += 1;
            // Frame j's hold: the least need over [j, j + la].
            if self.needs > self.la {
                self.release(self.needs - 1 - self.la, &mut out);
            }
        }
        if ended {
            while self.held < self.needs {
                self.release(self.held, &mut out);
            }
        }
        out
    }

    /// Frame `j` (the next one) gets its gain: the held minimum, the recovery, the moving average over the look-ahead.
    fn release(&mut self, j: usize, out: &mut [Vec<f32>]) {
        while self.window.front().is_some_and(|&(k, _)| k < j) {
            self.window.pop_front();
        }
        let h = self.window.front().expect("the window holds frame j").1;
        let mut g = self.g;
        g = if h < g { h } else { g + (1.0 - g) * self.rel };
        g = g.min(h);
        self.g = g;
        self.sum += g;
        self.recent.push_back(g);
        if j > self.la {
            self.sum -= self.recent.pop_front().expect("la + 2 gains");
        }
        let gain = self.sum / (j.min(self.la) + 1) as f64;
        self.lowest = self.lowest.min(gain);
        self.given.push(gain as f32);
        for (o, w) in out.iter_mut().zip(self.wait.iter_mut()) {
            let x = w.pop_front().expect("a frame per need");
            o.push((x as f64 * gain) as f32);
        }
        self.held += 1;
    }

    fn deepest(&self) -> f64 {
        -20.0 * self.lowest.max(1e-9).log10()
    }
}

/// Feed-forward compression linked across the channels, over the program's own loudness (soft
/// knee, 6 dB); the detector is the BS.1770-weighted mean power (the LFE does not drive it). Block by block;
/// `deepest` is its largest gain reduction (dB, ≥ 0).
pub(super) struct Glue {
    weights: Vec<f64>,
    wsum: f64,
    ratio: f64,
    threshold: f64,
    att: f64,
    rel: f64,
    det: f64,
    ms: f64,
    gr: f64,
    deepest: f64,
    /// The gain each frame got (Dynamics).
    given: Vec<f32>,
}

impl Glue {
    pub(super) fn new(weights: &[f64], amount: f64, program: f64, sr: f64) -> Glue {
        Glue {
            weights: weights.to_vec(), wsum: weights.iter().sum::<f64>().max(1e-9), ratio: 1.0 + 3.0 * amount, threshold: program + 3.0,
            att: 1.0 - (-1.0 / (0.025 * sr)).exp(), rel: 1.0 - (-1.0 / (0.18 * sr)).exp(), det: 1.0 - (-1.0 / (0.01 * sr)).exp(), ms: 0.0, gr: 0.0, deepest: 0.0, given: vec![],
        }
    }

    fn block(&mut self, chs: &mut [Vec<f32>]) {
        let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
        for i in 0..n {
            let mut p = 0.0;
            for (c, w) in chs.iter().zip(&self.weights) {
                let x = c[i] as f64;
                p += w * x * x;
            }
            self.ms += self.det * (p / self.wsum - self.ms);
            let lvl = 10.0 * self.ms.max(1e-12).log10();
            let over = lvl - self.threshold;
            let r = self.ratio;
            let want = if over <= -3.0 { 0.0 } else if over < 3.0 { (1.0 / r - 1.0) * (over + 3.0).powi(2) / 12.0 } else { (1.0 / r - 1.0) * over };
            self.gr += (if want < self.gr { self.att } else { self.rel }) * (want - self.gr);
            self.deepest = self.deepest.min(self.gr);
            let g = 10f64.powf(self.gr / 20.0);
            self.given.push(g as f32);
            for c in chs.iter_mut() {
                c[i] = (c[i] as f64 * g) as f32;
            }
        }
    }
}

/// A signal the mastering stage reads block by block, as often as it needs (the same frames every time).
pub type Source<'a> = &'a dyn Fn(usize, usize) -> Result<Vec<Vec<f32>>, String>;

/// The source's integrated loudness, read through once.
fn lufs_of(read: Source, nch: usize, total: usize, weights: &[f64], sr: f64) -> Result<f64, String> {
    let mut m = Lufs::new(nch, weights, sr);
    for at in (0..total).step_by(BLOCK) {
        let b = read(at, BLOCK.min(total - at))?;
        m.push(&b.iter().map(|c| c.as_slice()).collect::<Vec<_>>());
    }
    Ok(m.finish())
}

/// One limiter pass: the result, its gain at every frame (the target gain times the limiter's: Dynamics), its deepest
/// reduction (dB) and, with `measure`, the result's loudness.
pub(super) struct Pass {
    pub(super) out: Spool,
    pub(super) gains: Spool,
    pub(super) deepest: f64,
    lufs: Option<f64>,
}

/// The source through `gain` and the limiter into a new spool, with the gain each frame got.
pub(super) fn limited(read: Source, nch: usize, total: usize, gain: Option<f32>, ceiling: f64, sr: f64, on_disk: bool, measure: Option<&[f64]>) -> Result<Pass, String> {
    let mut lim = Limiter::new(nch, ceiling, sr);
    let mut out = Spool::new(nch, total, on_disk)?;
    let mut gains = Spool::new(1, total, on_disk)?;
    let mut meter = measure.map(|w| Lufs::new(nch, w, sr));
    let g = gain.unwrap_or(1.0);
    let mut emit = |b: Vec<Vec<f32>>, given: &mut Vec<f32>, out: &mut Spool, gains: &mut Spool| -> Result<(), String> {
        if b.first().is_some_and(|c| !c.is_empty()) {
            if let Some(m) = &mut meter {
                m.push(&b.iter().map(|c| c.as_slice()).collect::<Vec<_>>());
            }
            out.push(&b)?;
            gains.push(&[given.drain(..).map(|x| x * g).collect()])?;
        }
        Ok(())
    };
    for at in (0..total).step_by(BLOCK) {
        let mut b = read(at, BLOCK.min(total - at))?;
        if gain.is_some() {
            b.iter_mut().for_each(|c| c.iter_mut().for_each(|v| *v *= g));
        }
        let o = lim.push(&b);
        emit(o, &mut lim.given, &mut out, &mut gains)?;
    }
    let o = lim.finish();
    emit(o, &mut lim.given, &mut out, &mut gains)?;
    Ok(Pass { out: out.done()?, gains: gains.done()?, deepest: lim.deepest(), lufs: meter.map(Lufs::finish) })
}

/// The source through the glue (threshold over `program`) into a spool, with the gain each frame got, its deepest
/// reduction (dB, ≥ 0) and, with `measure`, the glued signal's loudness.
#[allow(clippy::too_many_arguments)]
pub(super) fn glue_pass(read: Source, nch: usize, total: usize, weights: &[f64], amount: f64, program: f64, sr: f64, on_disk: bool, measure: bool) -> Result<Pass, String> {
    let mut g = Glue::new(weights, amount, program, sr);
    let mut sp = Spool::new(nch, total, on_disk)?;
    let mut gains = Spool::new(1, total, on_disk)?;
    let mut m = measure.then(|| Lufs::new(nch, weights, sr));
    for at in (0..total).step_by(BLOCK) {
        let mut b = read(at, BLOCK.min(total - at))?;
        g.block(&mut b);
        gains.push(&[std::mem::take(&mut g.given)])?;
        if let Some(m) = &mut m {
            m.push(&b.iter().map(|c| c.as_slice()).collect::<Vec<_>>());
        }
        sp.push(&b)?;
    }
    Ok(Pass { out: sp.done()?, gains: gains.done()?, deepest: -g.deepest, lufs: m.map(Lufs::finish) })
}

/// Masters a signal of `total` frames: glue, then gain to the target (BS.1770 with the layout's channel weights),
/// then the true-peak limiter (linked: every channel under the ceiling); the gain is corrected and the chain re-run
/// (from the glued signal) until the result is within 0.2 LU. Block by block: the glued signal and each pass's result
/// are spooled (`on_disk`: on disk), so a whole song is never in memory. The mastered signal, what it did (MasterReport)
/// and its gain at every frame (Dynamics: what the stems carry).
pub fn master_blocks(read: Source, nch: usize, total: usize, weights: &[f64], spec: &MasterSpec, sr: f64, on_disk: bool) -> Result<(Spool, MasterReport, Dynamics), String> {
    let program = lufs_of(read, nch, total, weights, sr)?;
    // A little under the ceiling: encoders (mp3, aac) and other meters read inter-sample peaks a few tenths higher.
    let ceiling = 10f64.powf((spec.true_peak - 0.3) / 20.0);
    if program <= -69.0 {
        // No integrated loudness to read (silence, or under the 400 ms gate: a UI click): the ceiling still holds.
        let p = limited(read, nch, total, None, ceiling, sr, on_disk, None)?;
        return Ok((p.out, MasterReport { program, limiter_db: p.deepest, ..Default::default() }, Dynamics { glue: None, limiter: p.gains }));
    }
    // The glued signal, spooled (with no glue: the source itself), and its loudness on the way.
    let (glued, glue_gains, glue_db, glued_lufs) = match spec.glue > 0.0 {
        true => {
            let g = glue_pass(read, nch, total, weights, spec.glue, program, sr, on_disk, spec.loudness.is_some())?;
            (Some(g.out), Some(g.gains), g.deepest, g.lufs)
        }
        false => (None, None, 0.0, None),
    };
    let from_glued = |at: usize, n: usize| glued.as_ref().expect("glued").read(at, n);
    let src: Source = if glued.is_some() { &from_glued } else { read };
    let mut gain_db = match (spec.loudness, glued_lufs) {
        (None, _) => 0.0,
        (Some(t), Some(l)) => t - l,
        (Some(t), None) => t - lufs_of(src, nch, total, weights, sr)?,
    };
    let mut report = MasterReport { program, glue_db, ..Default::default() };
    let mut pass = 0;
    loop {
        let g = 10f64.powf(gain_db / 20.0) as f32;
        let p = limited(src, nch, total, Some(g), ceiling, sr, on_disk, spec.loudness.map(|_| weights))?;
        (report.gain_db, report.limiter_db) = (gain_db, p.deepest);
        // Over the most limiting: the whole mix down by what is over (the limiter's need falls dB for dB), and the
        // target no longer pulls it back up.
        let over = spec.max_limit.map_or(0.0, |m| p.deepest - m);
        if over > 0.05 && pass < 6 {
            gain_db -= over + 0.02;
            report.held_db += over + 0.02;
        } else {
            match (spec.loudness, p.lufs) {
                (Some(target), Some(got)) if report.held_db == 0.0 && (got - target).abs() > 0.2 && pass < 3 => gain_db += target - got,
                _ => return Ok((p.out, report, Dynamics { glue: glue_gains, limiter: p.gains })),
            }
        }
        pass += 1;
    }
}

/// Masters a bed in memory, in place (bed/ fold-downs, tests): `master_blocks` over it.
pub fn master_n(chs: &mut [Vec<f32>], weights: &[f64], spec: &MasterSpec, sr: f64) -> MasterReport {
    let total = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let src: &[Vec<f32>] = chs;
    let read = |at: usize, n: usize| Ok(src.iter().map(|c| c[at..at + n].to_vec()).collect());
    let (out, report, _) = master_blocks(&read, chs.len(), total, weights, spec, sr, false).expect("mastering in memory cannot fail");
    for (c, o) in chs.iter_mut().zip(out.into_whole().expect("in memory")) {
        c[..total].copy_from_slice(&o);
    }
    report
}

#[path = "master_window.rs"]
pub mod window;

#[cfg(test)]
#[path = "master_tests.rs"]
mod tests;
