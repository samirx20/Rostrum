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
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let measured = (|| {
        let map = map?;
        if chs.len() != map.len() || sr.fract() != 0.0 || n == 0 {
            return None;
        }
        let mut e = EbuR128::new(chs.len() as u32, sr as u32, Mode::I).ok()?;
        e.set_channel_map(&map).ok()?;
        let cut: Vec<&[f32]> = chs.iter().map(|c| &c[..n]).collect();
        e.add_frames_planar_f32(&cut).ok()?;
        e.loudness_global().ok()
    })();
    match measured {
        Some(l) if l.is_finite() => l.max(-70.0),
        Some(_) => -70.0,
        None => integrated_lufs_own(chs, weights, sr),
    }
}

/// Our own integrated loudness (the K-weighting above, 400 ms blocks, both gates): the fallback and the reference.
pub fn integrated_lufs_own(chs: &[&[f32]], weights: &[f64], sr: f64) -> f64 {
    let mut f: Vec<[Bq; 2]> = chs.iter().map(|_| k_weighting(sr)).collect();
    let hop = (sr * 0.1).round() as usize;
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    // Mean square of the K-weighted signal per 100 ms; a block is four of them.
    let mut quarters = vec![];
    let mut acc = 0.0;
    for i in 0..n {
        let mut s = 0.0;
        for (c, [shelf, hp]) in f.iter_mut().enumerate() {
            let y = hp.run(shelf.run(chs[c][i] as f64));
            s += weights[c] * y * y;
        }
        acc += s;
        if (i + 1) % hop == 0 {
            quarters.push(acc / hop as f64);
            acc = 0.0;
        }
    }
    let blocks: Vec<f64> = quarters.windows(4).map(|w| w.iter().sum::<f64>() / 4.0).collect();
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

/// The peak around each sample (it and the three interpolated points after it) over the channels
/// given, or of each channel alone (`per_channel`: one list per channel).
pub(crate) fn sample_peaks(chs: &[&[f32]]) -> Vec<f64> {
    let p = phases();
    let n = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let at = |x: &[f32], i: isize| if i >= 0 && (i as usize) < n { x[i as usize] as f64 } else { 0.0 };
    // Each sample's peak depends only on its neighbours: computed in blocks on all cores, joined in order.
    const BLOCK: usize = 1 << 16;
    let blocks: Vec<std::ops::Range<usize>> = (0..n).step_by(BLOCK).map(|s| s..(s + BLOCK).min(n)).collect();
    crate::mix::par::map(blocks, |range| {
        let mut acc = vec![0.0; chs.len()];
        range
            .map(|i| {
                let mut m = chs.iter().fold(0.0f64, |m, c| m.max((c[i] as f64).abs()));
                for row in &p {
                    acc.iter_mut().for_each(|a| *a = 0.0);
                    for (k, c) in row.iter().enumerate() {
                        let j = i as isize + k as isize - 7;
                        for (a, x) in acc.iter_mut().zip(chs) {
                            *a += c * at(x, j);
                        }
                    }
                    m = acc.iter().fold(m, |m, a| m.max(a.abs()));
                }
                m
            })
            .collect::<Vec<f64>>()
    })
    .concat()
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
