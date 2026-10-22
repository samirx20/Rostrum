//! The loudness measurements every mix reports and the mastering stage targets (fx/master.rs):
//! integrated loudness (ITU-R BS.1770-4 / EBU R128: K-weighting, 400 ms blocks, absolute and relative
//! gates) and true peak (4× oversampled peaks).

/// One biquad, direct form I, on one channel.
#[derive(Clone, Copy)]
pub(crate) struct Bq { b: [f64; 3], a: [f64; 2], x: [f64; 2], y: [f64; 2] }

impl Bq {
    pub(crate) fn run(&mut self, x: f64) -> f64 {
        let y = self.b[0] * x + self.b[1] * self.x[0] + self.b[2] * self.x[1] - self.a[0] * self.y[0] - self.a[1] * self.y[1];
        self.x = [x, self.x[0]];
        self.y = [y, self.y[0]];
        y
    }
}

/// The K-weighting filters at any sample rate (the BS.1770 analogue prototypes, as libebur128 derives them).
pub(crate) fn k_weighting(sr: f64) -> [Bq; 2] {
    let (f0, g, q) = (1681.974450955533, 3.999843853973347, 0.7071752369554196);
    let k = (std::f64::consts::PI * f0 / sr).tan();
    let vh = 10f64.powf(g / 20.0);
    let vb = vh.powf(0.4996667741545416);
    let a0 = 1.0 + k / q + k * k;
    let shelf = Bq { b: [(vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0], a: [2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0], x: [0.0; 2], y: [0.0; 2] };
    let (f0, q) = (38.13547087602444, 0.5003270373238773);
    let k = (std::f64::consts::PI * f0 / sr).tan();
    let a0 = 1.0 + k / q + k * k;
    let hp = Bq { b: [1.0, -2.0, 1.0], a: [2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0], x: [0.0; 2], y: [0.0; 2] };
    [shelf, hp]
}

/// Integrated loudness (LUFS) of a stereo signal; −70 for silence.
#[cfg(test)]
pub fn integrated_lufs(l: &[f32], r: &[f32], sr: f64) -> f64 {
    integrated_lufs_n(&[l, r], &[1.0, 1.0], sr)
}

/// Integrated loudness (LUFS) of any bed: each channel K-weighted, its power times its BS.1770 weight (bed/).
/// Measured by the `ebur128` crate (libebur128's port, MIT) with a channel map from the weights (0: unused,
/// 1.41: a surround, 1: a front); equal to our own `integrated_lufs_own` to 1e-9 LU on every clip tried
/// (loudness_parity.rs). A weight set it cannot map, or a rate it refuses, falls back to our own.
pub fn integrated_lufs_n(chs: &[&[f32]], weights: &[f64], sr: f64) -> f64 {
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let mut m = Lufs::new(chs.len(), weights, sr);
    m.push(&chs.iter().map(|c| &c[..n]).collect::<Vec<_>>());
    m.finish()
}

/// `integrated_lufs_n` fed block by block (the mix and the mastering stage read a song from disk): the same
/// figure, bit for bit, however the signal is cut into blocks.
pub struct Lufs {
    e: Option<ebur128::EbuR128>,
    own: Option<OwnLufs>,
    frames: usize,
}

impl Lufs {
    pub fn new(channels: usize, weights: &[f64], sr: f64) -> Lufs {
        use ebur128::{Channel, EbuR128, Mode};
        let map: Option<Vec<Channel>> = weights
            .iter()
            .enumerate()
            .map(|(i, w)| match *w {
                w if w == 0.0 => Some(Channel::Unused),
                w if (w - 1.41).abs() < 1e-9 => Some(if i % 2 == 0 { Channel::LeftSurround } else { Channel::RightSurround }),
                w if w == 1.0 => Some(match i { 0 => Channel::Left, 1 => Channel::Right, 2 => Channel::Center, _ => Channel::Left }),
                _ => None,
            })
            .collect();
        let e = (|| {
            let map = map?;
            if channels != map.len() || sr.fract() != 0.0 {
                return None;
            }
            let mut e = EbuR128::new(channels as u32, sr as u32, Mode::I).ok()?;
            e.set_channel_map(&map).ok()?;
            Some(e)
        })();
        // Our own runs beside it only where it cannot measure.
        let own = e.is_none().then(|| OwnLufs::new(channels, weights, sr));
        Lufs { e, own, frames: 0 }
    }

    /// The next frames (every channel the same length).
    pub fn push(&mut self, chs: &[&[f32]]) {
        let n = chs.first().map_or(0, |c| c.len());
        if n == 0 {
            return;
        }
        self.frames += n;
        if let Some(e) = &mut self.e {
            if e.add_frames_planar_f32(chs).is_err() {
                self.e = None; // a refused block: the figure reads −70, as a refused whole measure did
            }
        }
        if let Some(o) = &mut self.own {
            o.push(chs);
        }
    }

    pub fn finish(self) -> f64 {
        if let Some(o) = self.own {
            return o.finish();
        }
        match self.e.map(|e| e.loudness_global()) {
            Some(Ok(l)) if self.frames > 0 && l.is_finite() => l.max(-70.0),
            _ => -70.0,
        }
    }
}

/// Our own integrated loudness, block by block (the K-weighting above, 400 ms blocks, both gates).
struct OwnLufs {
    f: Vec<[Bq; 2]>,
    weights: Vec<f64>,
    hop: usize,
    at: usize,
    acc: f64,
    quarters: Vec<f64>,
}

impl OwnLufs {
    fn new(channels: usize, weights: &[f64], sr: f64) -> OwnLufs {
        OwnLufs { f: (0..channels).map(|_| k_weighting(sr)).collect(), weights: weights.to_vec(), hop: (sr * 0.1).round() as usize, at: 0, acc: 0.0, quarters: vec![] }
    }

    /// Mean square of the K-weighted signal per 100 ms; a block is four of them.
    fn push(&mut self, chs: &[&[f32]]) {
        for i in 0..chs.first().map_or(0, |c| c.len()) {
            let mut s = 0.0;
            for (c, [shelf, hp]) in self.f.iter_mut().enumerate() {
                let y = hp.run(shelf.run(chs[c][i] as f64));
                s += self.weights[c] * y * y;
            }
            self.acc += s;
            self.at += 1;
            if self.at % self.hop == 0 {
                self.quarters.push(self.acc / self.hop as f64);
                self.acc = 0.0;
            }
        }
    }

    fn finish(self) -> f64 {
        let blocks: Vec<f64> = self.quarters.windows(4).map(|w| w.iter().sum::<f64>() / 4.0).collect();
        let lufs = |ms: f64| -0.691 + 10.0 * ms.max(1e-12).log10();
        let gated = |min: f64| -> Option<f64> {
            let kept: Vec<f64> = blocks.iter().copied().filter(|&b| lufs(b) > min).collect();
            (!kept.is_empty()).then(|| kept.iter().sum::<f64>() / kept.len() as f64)
        };
        match gated(-70.0) {
            Some(m) => gated(lufs(m) - 10.0).map_or(-70.0, lufs),
            None => -70.0,
        }
    }
}

/// Our own integrated loudness (the K-weighting above, 400 ms blocks, both gates): the fallback and the reference.
#[cfg(test)]
pub fn integrated_lufs_own(chs: &[&[f32]], weights: &[f64], sr: f64) -> f64 {
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let mut o = OwnLufs::new(chs.len(), weights, sr);
    o.push(&chs.iter().map(|c| &c[..n]).collect::<Vec<_>>());
    o.finish()
}

/// The 4× interpolation filter: three fractional phases of a Kaiser-ish windowed sinc, 16 taps each.
fn phases() -> [[f64; 16]; 3] {
    let mut p = [[0.0; 16]; 3];
    for (ph, row) in p.iter_mut().enumerate() {
        let frac = (ph + 1) as f64 / 4.0;
        for (k, c) in row.iter_mut().enumerate() {
            let x = k as f64 - 7.0 - frac;
            let sinc = if x.abs() < 1e-9 { 1.0 } else { (std::f64::consts::PI * x).sin() / (std::f64::consts::PI * x) };
            let w = 0.5 + 0.5 * (std::f64::consts::PI * x / 8.5).cos();
            *c = sinc * w;
        }
    }
    p
}

/// The peak around each sample (it and the three interpolated points after it) over the channels given.
pub(crate) fn sample_peaks(chs: &[&[f32]]) -> Vec<f64> {
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let mut p = Peaks::new(chs.len());
    let mut out = p.push(&chs.iter().map(|c| &c[..n]).collect::<Vec<_>>());
    out.extend(p.finish());
    out
}

/// `sample_peaks` fed block by block: each sample's peak once the 8 samples after it are in (`finish`: past the
/// end reads 0, as the whole-signal measure does). The same values, bit for bit, however the signal is cut.
pub(crate) struct Peaks {
    p: [[f64; 16]; 3],
    /// Samples from frame `base` on: the 7 before the next to answer, and the ones not answered yet.
    buf: Vec<Vec<f32>>,
    base: usize,
    next: usize,
}

impl Peaks {
    pub fn new(channels: usize) -> Peaks {
        Peaks { p: phases(), buf: vec![vec![]; channels], base: 0, next: 0 }
    }

    /// The next frames in; the peaks of the frames that can be answered now, in order.
    pub fn push(&mut self, chs: &[&[f32]]) -> Vec<f64> {
        for (b, c) in self.buf.iter_mut().zip(chs) {
            b.extend_from_slice(c);
        }
        let have = self.base + self.buf.first().map_or(0, Vec::len);
        self.answer(have.saturating_sub(8), have)
    }

    /// The peaks of the frames left (the signal ends here).
    pub fn finish(&mut self) -> Vec<f64> {
        let have = self.base + self.buf.first().map_or(0, Vec::len);
        self.answer(have, have)
    }

    /// Peaks of frames `next .. upto`; frames from `end` on read 0 (past the signal).
    fn answer(&mut self, upto: usize, end: usize) -> Vec<f64> {
        if upto <= self.next {
            return vec![];
        }
        let (p, buf, base) = (&self.p, &self.buf, self.base);
        let at = |x: &[f32], j: isize| if j >= 0 && (j as usize) < end { x[j as usize - base] as f64 } else { 0.0 };
        // Each sample's peak depends only on its neighbours: computed in parts on all cores, joined in order.
        const PART: usize = 1 << 14;
        let parts: Vec<std::ops::Range<usize>> = (self.next..upto).step_by(PART).map(|s| s..(s + PART).min(upto)).collect();
        let out = crate::mix::par::map(parts, |range| {
            let mut acc = vec![0.0; buf.len()];
            range
                .map(|i| {
                    let mut m = buf.iter().fold(0.0f64, |m, c| m.max((c[i - base] as f64).abs()));
                    for row in p {
                        acc.iter_mut().for_each(|a| *a = 0.0);
                        for (k, c) in row.iter().enumerate() {
                            let j = i as isize + k as isize - 7;
                            for (a, x) in acc.iter_mut().zip(buf) {
                                *a += c * at(x, j);
                            }
                        }
                        m = acc.iter().fold(m, |m, a| m.max(a.abs()));
                    }
                    m
                })
                .collect::<Vec<f64>>()
        })
        .concat();
        self.next = upto;
        let keep_from = self.next.saturating_sub(7).max(self.base);
        for b in self.buf.iter_mut() {
            b.drain(..keep_from - self.base);
        }
        self.base = keep_from;
        out
    }
}

/// True peak (dBTP).
#[cfg(test)]
pub fn true_peak_db(l: &[f32], r: &[f32]) -> f64 {
    true_peak_db_n(&[l, r])
}

/// True peak (dBTP) over any set of channels.
pub fn true_peak_db_n(chs: &[&[f32]]) -> f64 {
    20.0 * sample_peaks(chs).into_iter().fold(1e-9, f64::max).log10()
}
