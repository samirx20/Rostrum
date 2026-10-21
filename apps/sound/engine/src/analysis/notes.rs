//! The notes of a single-line part (a bass or lead stem) for `analyze --notes`: YIN pitch, notes split
//! where the pitch changes or the level re-attacks.

/// The notes of a single-line part: YIN pitch every 256 samples, held for at least 60 ms.
pub fn notes(x: &[f32], sr: f64) -> Vec<(f64, f64, i64)> {
    let (w, hop) = (2048usize, 256usize);
    let max_lag = (sr / 40.0) as usize;
    let mut track: Vec<Option<i64>> = vec![];
    let mut level: Vec<f64> = vec![];
    let mut f = 0;
    while f + w + max_lag < x.len() {
        let s = &x[f..f + w + max_lag];
        // The level at the window's centre (512 samples): re-attacks of a repeated note show there.
        let mid = &s[w / 2 - 256..w / 2 + 256];
        let rms = (mid.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / mid.len() as f64).sqrt();
        let mut d = vec![0.0; max_lag];
        for tau in 1..max_lag {
            d[tau] = (0..w).map(|i| (s[i] - s[i + tau]) as f64).map(|v| v * v).sum();
        }
        // Cumulative mean normalised difference: the first dip under 0.2 is the period, else the
        // clearest dip if it is under 0.4 (a distorted or busy part never dips as far as a pure tone).
        let (mut cum, mut found, mut clearest) = (0.0, None, (0usize, f64::MAX));
        for tau in 1..max_lag {
            cum += d[tau];
            let dn = d[tau] * tau as f64 / cum.max(1e-12);
            if tau < (sr / 1000.0) as usize {
                continue;
            }
            if dn < clearest.1 {
                clearest = (tau, dn);
            }
            if dn < 0.2 {
                let mut t = tau;
                while t + 1 < max_lag && d[t + 1] < d[t] {
                    t += 1;
                }
                found = Some(t);
                break;
            }
        }
        let period = found.or(if clearest.1 < 0.4 { Some(clearest.0) } else { None });
        track.push(period.filter(|_| rms > 0.003).map(|t| (69.0 + 12.0 * ((sr / t as f64) / 440.0).log2()).round() as i64));
        level.push(rms);
        f += hop;
    }
    // A note runs while the pitch holds and the level does not jump (a jump of 1.6× within 2 frames re-strikes it).
    let attack = |k: usize| k >= 2 && level[k] > 1.6 * level[k - 2].max(1e-6) && level[k] > level[k - 1];
    let at = |k: usize| (k * hop + w / 2) as f64 / sr;
    let mut out = vec![];
    let mut i = 0;
    while i < track.len() {
        let Some(m) = track[i] else {
            i += 1;
            continue;
        };
        let mut j = i;
        while j + 1 < track.len() && track[j + 1] == Some(m) && !attack(j + 1) {
            j += 1;
        }
        let (start, end) = (at(i), at(j + 1));
        if end - start >= 0.06 {
            out.push((start, end - start, m));
        }
        i = j + 1;
    }
    out
}
