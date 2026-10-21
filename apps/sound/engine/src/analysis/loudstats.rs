//! The loudness figures a Broadcast WAV's bext chunk carries besides integrated loudness and true
//! peak (EBU Tech 3285 v2, EBU R128 / Tech 3342): the loudest momentary (400 ms) and short-term
//! (3 s) loudness, and the loudness range (LRA: the 10th to 95th percentile of the gated short-term
//! loudness, gated at −70 LUFS absolute and 20 LU under its own mean).

pub struct Stats {
    pub max_momentary: f64,
    pub max_short_term: f64,
    pub lra: f64,
    /// Short-term loudness (LUFS, 3 s window) at the end of each 100 ms hop from the first full window on (hop `k` ends
    /// at `(k + 30) / 10` s); a file under 3 s has its one window over everything there is.
    pub short_term: Vec<f64>,
    /// L/R correlation (Pearson, 400 ms windows, 100 ms hop; window `k` ends at `(k + 4) / 10` s) of the first two
    /// channels, None for a window under -70 dBFS or a mono file.
    pub correlation: Vec<Option<f64>>,
}

/// The correlation window: 4 hops of 100 ms.
pub const CORR_HOPS: usize = 4;

#[cfg(test)]
pub fn stats(l: &[f32], r: &[f32], sr: f64) -> Stats {
    stats_n(&[l, r], &[1.0, 1.0], sr)
}

/// The same over any bed, each channel's power times its BS.1770 weight (bed/).
pub fn stats_n(chs: &[&[f32]], weights: &[f64], sr: f64) -> Stats {
    let mut kw: Vec<[crate::analysis::loudness::Bq; 2]> = chs.iter().map(|_| crate::analysis::loudness::k_weighting(sr)).collect();
    let hop = (sr * 0.1).round() as usize;
    let mut tenths = vec![];
    let mut acc = 0.0;
    // Per hop: sum of L^2, R^2, L*R of the raw samples (the first two channels), for the correlation.
    let mut cross: Vec<[f64; 3]> = vec![];
    let mut cx = [0.0f64; 3];
    for i in 0..chs.iter().map(|c| c.len()).min().unwrap_or(0) {
        let mut s = 0.0;
        for (c, [shelf, hp]) in kw.iter_mut().enumerate() {
            let y = hp.run(shelf.run(chs[c][i] as f64));
            s += weights[c] * y * y;
        }
        acc += s;
        if chs.len() >= 2 {
            let (l, r) = (chs[0][i] as f64, chs[1][i] as f64);
            cx[0] += l * l;
            cx[1] += r * r;
            cx[2] += l * r;
        }
        if (i + 1) % hop == 0 {
            tenths.push(acc / hop as f64);
            cross.push(cx);
            acc = 0.0;
            cx = [0.0; 3];
        }
    }
    let lufs = |ms: f64| -0.691 + 10.0 * ms.max(1e-12).log10();
    let windows = |n: usize| -> Vec<f64> { tenths.windows(n).map(|w| lufs(w.iter().sum::<f64>() / n as f64)).collect() };
    let (momentary, short) = (windows(4), windows(30));
    let max = |v: &[f64]| v.iter().copied().fold(-70.0f64, f64::max);
    let gated: Vec<f64> = short.iter().copied().filter(|v| *v > -70.0).collect();
    let lra = if gated.is_empty() {
        0.0
    } else {
        let mean = lufs(gated.iter().map(|v| 10f64.powf((v + 0.691) / 10.0)).sum::<f64>() / gated.len() as f64);
        let mut kept: Vec<f64> = gated.into_iter().filter(|v| *v > mean - 20.0).collect();
        kept.sort_by(|a, b| a.total_cmp(b));
        let at = |q: f64| kept[((kept.len() - 1) as f64 * q).round() as usize];
        if kept.is_empty() { 0.0 } else { at(0.95) - at(0.10) }
    };
    let short_term = if short.is_empty() && !tenths.is_empty() { vec![lufs(tenths.iter().sum::<f64>() / tenths.len() as f64)] } else { short.clone() };
    let floor = 10f64.powf(-70.0 / 10.0);
    let correlation = if chs.len() < 2 {
        vec![]
    } else {
        cross
            .windows(CORR_HOPS)
            .map(|w| {
                let sum = w.iter().fold([0.0; 3], |a, c| [a[0] + c[0], a[1] + c[1], a[2] + c[2]]);
                let n = (CORR_HOPS * hop) as f64;
                (sum[0] / n > floor || sum[1] / n > floor).then(|| (sum[2] / (sum[0] * sum[1]).sqrt().max(1e-30)).clamp(-1.0, 1.0))
            })
            .collect()
    };
    Stats { max_momentary: max(&momentary), max_short_term: max(&short), lra, short_term, correlation }
}
