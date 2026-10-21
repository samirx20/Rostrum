//! Transients kept sharp through a stretch. A phase vocoder spreads a hit over its analysis window
//! (a soft attack, a pre-echo before it); a DAW's stretch keeps hits as they were. So the source's
//! onsets are found (a jump in its high band), and around each one the output plays the source
//! itself, at its own speed (read at the shift's ratio for pitch), cross-faded in and out of the
//! stretched signal: from 45 ms before the hit (the stretcher's pre-echo reaches that far) to 45 ms after it.

use crate::stretch::Shift;

/// Where the source's hits start (samples): a 1 ms frame of the high band (first difference) 10 dB
/// over the loudest of the 30 ms before it and within 40 dB of the clip's loudest, 60 ms apart at least.
pub fn onsets(src: &[&[f32]], sr: f64) -> Vec<usize> {
    let n = src.iter().map(|c| c.len()).min().unwrap_or(0);
    let k = src.len() as f64;
    let frame = ((sr / 1000.0) as usize).max(1);
    let mut prev = 0.0f64;
    let mut db = vec![];
    for f in (0..n).step_by(frame) {
        let mut e = 0.0;
        for i in f..(f + frame).min(n) {
            let m = src.iter().map(|c| c[i] as f64).sum::<f64>() / k;
            e += (m - prev) * (m - prev);
            prev = m;
        }
        db.push(10.0 * (e / frame as f64 + 1e-20).log10());
    }
    let top = db.iter().cloned().fold(-200.0, f64::max);
    let mut out: Vec<usize> = vec![];
    for f in 30..db.len() {
        let before = db[f - 30..f - 2].iter().cloned().fold(-200.0, f64::max);
        if db[f] > top - 40.0 && db[f] - before > 10.0 && out.last().map_or(true, |&o| f * frame - o >= 60 * frame) {
            out.push((f - 1) * frame);
        }
    }
    out
}

/// Plays the source over the stretched output around each of its hits. Not on a pitched voice (PSOLA
/// keeps its consonants as they were, and the source read at another speed would carry its formants
/// with it) nor on anything pitched with its formants kept.
pub fn splice(out: &mut [Vec<f32>], src: &[&[f32]], map: &dyn Fn(f64) -> f64, shift: &Shift, sr: f64) {
    if (shift.formant.is_some() || shift.voice == Some(true)) && (shift.ratio - 1.0).abs() > 1e-3 {
        return;
    }
    let len = out[0].len();
    let ms = |x: f64| x * sr / 1000.0;
    let (a, b, c, d) = (ms(-45.0), ms(-30.0), ms(25.0), ms(45.0));
    // Raised-cosine weight of the source at m samples from the hit.
    let weight = |m: f64| {
        let ramp = |u: f64| 0.5 - 0.5 * (std::f64::consts::PI * u.clamp(0.0, 1.0)).cos();
        if m < b { ramp((m - a) / (b - a)) } else if m < c { 1.0 } else { 1.0 - ramp((m - c) / (d - c)) }
    };
    for o in onsets(src, sr) {
        // The output sample the hit lands on: the map's inverse, by bisection (it is monotone).
        let (mut lo, mut hi) = (0usize, len);
        while lo < hi {
            let mid = (lo + hi) / 2;
            if map(mid as f64) < o as f64 { lo = mid + 1 } else { hi = mid }
        }
        if lo >= len || (map(lo as f64) - o as f64).abs() > ms(5.0) {
            continue; // the hit is outside what this clip plays
        }
        let k = lo as i64;
        for m in a as i64..d as i64 {
            let i = k + m;
            if i < 0 || i as usize >= len {
                continue;
            }
            let pos = o as f64 + m as f64 * shift.ratio;
            let j = pos.floor();
            if j < 0.0 || j as usize + 1 >= src.iter().map(|c| c.len()).min().unwrap_or(0) {
                continue;
            }
            let (j, f, w) = (j as usize, (pos - j) as f32, weight(m as f64) as f32);
            for ch in 0..src.len() {
                let s = src[ch][j] + (src[ch][j + 1] - src[ch][j]) * f;
                out[ch][i as usize] = out[ch][i as usize] * (1.0 - w) + s * w;
            }
        }
    }
}
