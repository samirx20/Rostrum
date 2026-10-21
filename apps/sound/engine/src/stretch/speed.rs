//! A clip's speed: re-read along its rate (constant, a ramp from → to, or warp markers), on any number
//! of channels with one time map (a surround bed keeps its image). Stretched with its pitch kept
//! (stretch/mod.rs) or tape varispeed, where pitch follows speed (then shifted after, if asked).

use crate::mix::schedule::Rate;

fn clamp_rate(r: Option<f64>) -> f64 {
    let r = r.unwrap_or(1.0);
    (if r == 0.0 || r.is_nan() { 1.0 } else { r }).clamp(0.15, 4.0)
}

/// Re-reads the clip along its rate (constant, a ramp from -> to, or warp markers): stretched with its
/// pitch kept (and shifted by `semitones`, formants kept when asked; stretch/mod.rs) unless it is tape
/// varispeed, where pitch follows speed (then shifted after, if asked). `source` is media read at its
/// own length; without it the clip stretches its own signal, trimmed of trailing silence.
pub fn time_stretch(left: &mut [f32], right: &mut [f32], sr: f64, rate: &Rate, source: Option<(&[f32], &[f32])>) {
    let src = source.map(|(l, r)| [l, r]);
    time_stretch_n(&mut [left, right], sr, rate, src.as_ref().map(|s| &s[..]));
}

/// `time_stretch` over any number of channels.
pub fn time_stretch_n(chs: &mut [&mut [f32]], sr: f64, rate: &Rate, source: Option<&[&[f32]]>) {
    let len = chs.iter().map(|c| c.len()).min().unwrap_or(0);
    let r0 = clamp_rate(Some(rate.from));
    let r1 = clamp_rate(rate.to.or(Some(r0)));
    let shift = crate::stretch::Shift { ratio: 2f64.powf(rate.semitones / 12.0), formant: rate.formant.map(|st| 2f64.powf(st / 12.0)), voice: rate.content.as_deref().map(|c| c == "voice") };
    let shifted = (shift.ratio - 1.0).abs() > 1e-4 || shift.formant.is_some();
    let warp = rate.warp.as_ref().filter(|w| w.len() >= 2);
    if len < 32 || (source.is_none() && !shifted && warp.is_none() && (r0 - 1.0).abs() < 0.005 && (r1 - 1.0).abs() < 0.005) {
        return;
    }
    let own: Vec<Vec<f32>>;
    let src: Vec<&[f32]> = match source {
        Some(s) => s.to_vec(),
        None => {
            let mut active = len;
            while active > 64 && chs.iter().all(|c| c[active - 1].abs() < 0.001) {
                active -= 1;
            }
            active = len.min(active + (0.04 * sr).floor() as usize).max(64);
            own = chs.iter().map(|c| c[..active].to_vec()).collect();
            own.iter().map(|c| c.as_slice()).collect()
        }
    };
    let n = len as f64;
    let ramp = |k: f64| r0 * k + (r1 - r0) * k * k / (2.0 * n);
    let warped = warp.map(|w| warp_map(w, sr));
    let map: &dyn Fn(f64) -> f64 = match &warped {
        Some(f) => f,
        None => &ramp,
    };
    if rate.preserve_pitch || warp.is_some() {
        for (c, out) in chs.iter_mut().zip(crate::stretch::render_n(&src, len, map, &shift, sr)) {
            c[..len].copy_from_slice(&out);
        }
        return;
    }
    // Tape: read along the ramp, linear interpolation; silence past the source's end.
    let active = src.iter().map(|c| c.len()).min().unwrap_or(0);
    let mut tape = vec![vec![0f32; len]; src.len()];
    for i in 0..len {
        let pos = ramp(i as f64);
        let idx = pos.floor() as usize;
        if idx + 1 >= active {
            break;
        }
        let frac = (pos - idx as f64) as f32;
        for (t, s) in tape.iter_mut().zip(&src) {
            t[i] = s[idx] + (s[idx + 1] - s[idx]) * frac;
        }
    }
    if shifted {
        let refs: Vec<&[f32]> = tape.iter().map(|c| c.as_slice()).collect();
        tape = crate::stretch::render_n(&refs, len, &|k| k, &shift, sr);
    }
    for (c, t) in chs.iter_mut().zip(&tape) {
        c[..len].copy_from_slice(t);
    }
}

/// Warp markers [source s, clip s] (sorted by clip time) as a map from clip samples to source samples:
/// straight between markers, the end segments' rates beyond them.
fn warp_map(w: &[[f64; 2]], sr: f64) -> impl Fn(f64) -> f64 + '_ {
    move |k: f64| {
        let t = k / sr;
        let i = w.partition_point(|p| p[1] <= t).clamp(1, w.len() - 1);
        let ([s0, c0], [s1, c1]) = (w[i - 1], w[i]);
        (s0 + (t - c0) * (s1 - s0) / (c1 - c0).max(1e-6)) * sr
    }
}

#[cfg(test)]
mod tests {
    use crate::mix::schedule::Rate;

    #[test]
    fn a_bed_changes_speed_on_every_channel_by_one_map() {
        // 5.1: the same tone + hits on L and C (a phantom between them), noise on Ls, the rest silent.
        let sr = 48000.0;
        let n = 48000;
        let mut seed = 7u64;
        let mut noise = || {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            ((seed >> 40) as f32 / (1u64 << 24) as f32) * 2.0 - 1.0
        };
        let tone: Vec<f32> = (0..n).map(|i| (0.4 * (2.0 * std::f64::consts::PI * 440.0 * i as f64 / sr).sin()) as f32 + if i % 12000 == 0 { 0.5 } else { 0.0 }).collect();
        let ls: Vec<f32> = (0..n).map(|_| 0.2 * noise()).collect();
        let silent = vec![0.0f32; n];
        let src: Vec<&[f32]> = vec![&tone, &silent, &tone, &silent, &ls, &silent];
        for preserve_pitch in [true, false] {
            let rate = Rate { from: 0.5, to: None, preserve_pitch, warp: None, semitones: 0.0, formant: None, content: Some("music".into()) };
            let mut out = vec![vec![0.0f32; 2 * n]; 6];
            super::time_stretch_n(&mut out.iter_mut().map(|v| v.as_mut_slice()).collect::<Vec<_>>(), sr, &rate, Some(&src));
            let diff = out[0].iter().zip(&out[2]).fold(0.0f32, |m, (a, b)| m.max((a - b).abs()));
            assert!(diff < 1e-4, "one map: L and C stay one phantom (preserve pitch {preserve_pitch}: they differ by {diff})");
            for ch in [1, 3, 5] {
                assert!(out[ch].iter().all(|v| v.abs() < 1e-6), "a silent channel stays silent");
            }
            let rms = |v: &[f32]| (v.iter().map(|x| (*x as f64).powi(2)).sum::<f64>() / v.len() as f64).sqrt();
            // Half speed: the second half of the clip still sounds (the source is read to its end).
            assert!(rms(&out[0][n..2 * n - 4800]) > 0.1 && rms(&out[4][n..2 * n - 4800]) > 0.05);
        }
    }
}
