//! The pitch of a single-line part (a bass, lead or voice stem) for `analyze --notes`: a YIN pitch track
//! every 256 samples (read between lags, so it has cents), and the notes it plays, split where the pitch
//! changes or the level re-attacks. The one pitch source: `look_pitch` reads it (ears/engine_ears.py).
//! YIN's difference function is d(τ) = E(0) + E(τ) − 2·r(τ), with r the window's correlation with the
//! signal ahead of it (one FFT a frame) and E the energies (running sums): a 20 s part reads in well
//! under a second, where the direct sum over every lag took 6–8 s.

/// The pitch track: frame k is at `first + k·hop` seconds (the window's centre); each frame's pitch in
/// MIDI notes (fractional: 69.25 is A4, 25 cents sharp), None where nothing is voiced.
pub struct Track {
    pub hop: f64,
    pub first: f64,
    pub midi: Vec<Option<f64>>,
}

/// A note: start (s), length (s), MIDI note, cents off it (the median over the note, + sharp).
pub type Note = (f64, f64, i64, f64);

const W: usize = 2048;
const HOP: usize = 256;

/// The pitch track between `lo` and `hi` Hz, and each frame's level.
pub fn track(x: &[f32], sr: f64, lo: f64, hi: f64) -> (Track, Vec<f64>) {
    let max_lag = ((sr / lo.max(20.0)) as usize).max(4);
    let min_lag = ((sr / hi.max(lo + 1.0)) as usize).max(2);
    let n = (W + max_lag).next_power_of_two();
    let (mut midi, mut level) = (vec![], vec![]);
    let (mut are, mut aim, mut bre, mut bim) = (vec![0.0; n], vec![0.0; n], vec![0.0; n], vec![0.0; n]);
    let (mut d, mut dn) = (vec![0.0; max_lag], vec![1.0; max_lag]);
    let mut f = 0;
    while f + W + max_lag < x.len() {
        let s = &x[f..f + W + max_lag];
        f += HOP;
        // The level at the window's centre (512 samples): re-attacks of a repeated note show there.
        let mid = &s[W / 2 - 256..W / 2 + 256];
        let rms = (mid.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / mid.len() as f64).sqrt();
        level.push(rms);
        if rms <= 0.003 {
            midi.push(None);
            continue;
        }
        // r(τ) = Σ_{i<W} s[i]·s[i+τ]: the window against the signal, through one spectrum each.
        for k in 0..n {
            are[k] = if k < W { s[k] as f64 } else { 0.0 };
            bre[k] = s.get(k).map_or(0.0, |v| *v as f64);
            aim[k] = 0.0;
            bim[k] = 0.0;
        }
        crate::fx::convolve::fft(&mut are, &mut aim, false);
        crate::fx::convolve::fft(&mut bre, &mut bim, false);
        for k in 0..n {
            let (re, im) = (are[k] * bre[k] + aim[k] * bim[k], are[k] * bim[k] - aim[k] * bre[k]);
            are[k] = re;
            aim[k] = im;
        }
        crate::fx::convolve::fft(&mut are, &mut aim, true);
        let e0: f64 = s[..W].iter().map(|v| (*v as f64).powi(2)).sum();
        let mut e = e0;
        for tau in 1..max_lag {
            e += (s[W + tau - 1] as f64).powi(2) - (s[tau - 1] as f64).powi(2);
            d[tau] = (e0 + e - 2.0 * are[tau]).max(0.0);
        }
        // Cumulative mean normalised difference: the first dip under 0.2 is the period, else the
        // clearest dip if it is under 0.4 (a distorted or busy part never dips as far as a pure tone).
        let (mut cum, mut found, mut clearest) = (0.0, None, (0usize, f64::MAX));
        for tau in 1..max_lag {
            cum += d[tau];
            dn[tau] = d[tau] * tau as f64 / cum.max(1e-12);
        }
        for tau in min_lag..max_lag {
            if dn[tau] < clearest.1 {
                clearest = (tau, dn[tau]);
            }
            if dn[tau] < 0.2 {
                let mut t = tau;
                while t + 1 < max_lag && dn[t + 1] < dn[t] {
                    t += 1;
                }
                found = Some(t);
                break;
            }
        }
        let period = found.or(if clearest.1 < 0.4 { Some(clearest.0) } else { None });
        midi.push(period.map(|t| {
            // Between lags: the parabola through the dip and its neighbours (this is where cents come from).
            let (a, b, c) = (dn[t - 1], dn[t], dn[(t + 1).min(max_lag - 1)]);
            let den = a - 2.0 * b + c;
            let lag = t as f64 + if den > 0.0 { (0.5 * (a - c) / den).clamp(-0.5, 0.5) } else { 0.0 };
            69.0 + 12.0 * ((sr / lag) / 440.0).log2()
        }));
    }
    (Track { hop: HOP as f64 / sr, first: (W / 2) as f64 / sr, midi }, level)
}

/// The notes of a single-line part, held for at least 60 ms, with their cents.
pub fn notes(x: &[f32], sr: f64, lo: f64, hi: f64) -> (Track, Vec<Note>) {
    let (tr, level) = track(x, sr, lo, hi);
    let near: Vec<Option<i64>> = tr.midi.iter().map(|m| m.map(|m| m.round() as i64)).collect();
    // A note runs while the pitch holds and the level does not jump (a jump of 1.6× within 2 frames re-strikes it).
    let attack = |k: usize| k >= 2 && level[k] > 1.6 * level[k - 2].max(1e-6) && level[k] > level[k - 1];
    let at = |k: usize| tr.first + k as f64 * tr.hop;
    let mut out = vec![];
    let mut i = 0;
    while i < near.len() {
        let Some(m) = near[i] else {
            i += 1;
            continue;
        };
        let mut j = i;
        while j + 1 < near.len() && near[j + 1] == Some(m) && !attack(j + 1) {
            j += 1;
        }
        let (start, end) = (at(i), at(j + 1));
        if end - start >= 0.06 {
            let mut cents: Vec<f64> = tr.midi[i..=j].iter().flatten().map(|v| (v - m as f64) * 100.0).collect();
            cents.sort_by(f64::total_cmp);
            out.push((start, end - start, m, cents[cents.len() / 2]));
        }
        i = j + 1;
    }
    (tr, out)
}

#[cfg(test)]
mod tests {
    #[test]
    fn reads_a_sharp_note_with_its_cents_and_its_start() {
        let sr = 44100.0;
        // A3 at +30 cents from 0.5 s to 1.5 s, then D4 (in tune) to 2.5 s.
        let f = |t: f64| if t < 1.5 { 220.0 * 2f64.powf(0.3 / 12.0) } else { 293.66 };
        let x: Vec<f32> = (0..(sr * 3.0) as usize).map(|i| i as f64 / sr).map(|t| if (0.5..2.5).contains(&t) { ((2.0 * std::f64::consts::PI * f(t) * t).sin() * 0.4) as f32 } else { 0.0 }).collect();
        let (_, notes) = super::notes(&x, sr, 40.0, 2000.0);
        let a = notes.iter().find(|n| n.2 == 57).unwrap_or_else(|| panic!("A3 not heard: {notes:?}"));
        assert!((a.3 - 30.0).abs() < 4.0, "cents {}", a.3);
        assert!((a.0 - 0.5).abs() < 0.03, "start {}", a.0);
        assert!(notes.iter().any(|n| n.2 == 62 && n.3.abs() < 4.0), "{notes:?}");
    }
}
