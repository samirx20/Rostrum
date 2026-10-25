//! Listening for agents (`rostrum-sound analyze <mono.f32> <rate> [--notes]`): what a recording holds,
//! as numbers an agent can read — tempo and beat grid, key, chords over time, the notes of a
//! single-line part (a bass or lead stem), and timbre over time (brightness, energy per band,
//! noisiness). Classic signal processing, no model: an STFT (rustfft, through fx/convolve.rs), spectral flux
//! for onsets, autocorrelation for tempo, a pitch-class profile (chroma) for key and chords, YIN for
//! pitch. TypeScript decodes the file and caches the answer (src/engine/sound/listen/listen.ts).

use std::f64::consts::PI;

use crate::analysis::keyfind::NAMES;
use crate::analysis::notes::notes;
use crate::analysis::tempo::{tempo, Tempo};

/// Magnitude spectra of Hann-windowed frames of `n` samples every `hop`.
fn stft(x: &[f32], n: usize, hop: usize) -> Vec<Vec<f64>> {
    let win: Vec<f64> = (0..n).map(|i| 0.5 - 0.5 * (2.0 * PI * i as f64 / n as f64).cos()).collect();
    (0..x.len().saturating_sub(n) / hop + 1)
        .map(|f| {
            let mut re: Vec<f64> = (0..n).map(|i| x.get(f * hop + i).copied().unwrap_or(0.0) as f64 * win[i]).collect();
            let mut im = vec![0.0; n];
            crate::fx::convolve::fft(&mut re, &mut im, false);
            (0..n / 2).map(|k| re[k].hypot(im[k])).collect()
        })
        .collect()
}

/// A frame's pitch-class profile (C … B), from 65 Hz to 2 kHz, normalised to sum 1.
fn chroma(mag: &[f64], sr: f64, n: usize) -> [f64; 12] {
    chroma_in(mag, sr, n, 65.0, 2000.0)
}

/// The pitch-class profile of the frequencies `lo` … `hi` (the bass: 30 … 250 Hz), normalised to sum 1.
fn chroma_in(mag: &[f64], sr: f64, n: usize, lo: f64, hi: f64) -> [f64; 12] {
    let mut c = [0.0; 12];
    for (k, &m) in mag.iter().enumerate().skip(1) {
        let f = k as f64 * sr / n as f64;
        if !(lo..=hi).contains(&f) {
            continue;
        }
        let midi = 69.0 + 12.0 * (f / 440.0).log2();
        c[(midi.round() as i64).rem_euclid(12) as usize] += m * m;
    }
    let s: f64 = c.iter().sum();
    if s > 0.0 {
        c.iter_mut().for_each(|v| *v /= s);
    }
    c
}

/// What `analyze` is asked for: the notes and pitch track of a single-line part (between `range` Hz),
/// only those (`pitch_only`: no tempo, key or timbre), and the beats in a bar (for the downbeats).
pub struct Ask {
    pub notes: bool,
    pub pitch_only: bool,
    pub range: (f64, f64),
    pub per_bar: usize,
    /// The tempo the score says (`--expect-bpm`), weighed against what the sound repeats at (tempo.rs 3b).
    pub expect: Option<f64>,
}

impl Ask {
    pub fn from_args(args: &[String]) -> Result<Ask, String> {
        let num = |name: &str, k: usize| -> Result<Option<f64>, String> {
            match args.iter().position(|a| a == name) {
                None => Ok(None),
                Some(i) => args.get(i + 1 + k).ok_or(format!("{name} takes a value"))?.parse().map(Some).map_err(|_| format!("{name}: not a number")),
            }
        };
        let flag = |n: &str| args.iter().any(|a| a == n);
        Ok(Ask {
            notes: flag("--notes") || flag("--pitch-only"),
            pitch_only: flag("--pitch-only"),
            range: (num("--range", 0)?.unwrap_or(40.0), num("--range", 1)?.unwrap_or(2000.0)),
            per_bar: num("--beats-per-bar", 0)?.unwrap_or(4.0).max(1.0) as usize,
            expect: num("--expect-bpm", 0)?,
        })
    }
}

/// The notes of a single-line part and its pitch track, as JSON (`notes`: [start, length, midi, name, cents]).
fn pitch_json(x: &[f32], sr: f64, range: (f64, f64)) -> (serde_json::Value, serde_json::Value) {
    let r = |v: f64, d: i32| (v * 10f64.powi(d)).round() / 10f64.powi(d);
    let (tr, found) = notes(x, sr, range.0, range.1);
    let list = found.iter().map(|(s, d, m, c)| serde_json::json!([r(*s, 3), r(*d, 3), m, format!("{}{}", NAMES[m.rem_euclid(12) as usize], m.div_euclid(12) - 1), r(*c, 1)])).collect();
    let track = serde_json::json!({ "hop": tr.hop, "first": tr.first, "midi": tr.midi.iter().map(|m| m.map(|m| r(m, 3))).collect::<Vec<_>>() });
    (list, track)
}

/// The whole analysis with the defaults (the tests' way in).
#[cfg(test)]
pub fn analyze(x: &[f32], sr: f64, with_notes: bool) -> serde_json::Value {
    analyze_asked(x, sr, &Ask { notes: with_notes, pitch_only: false, range: (40.0, 2000.0), per_bar: 4, expect: None })
}

pub fn analyze_asked(x: &[f32], sr: f64, ask: &Ask) -> serde_json::Value {
    let r = |v: f64, d: i32| (v * 10f64.powi(d)).round() / 10f64.powi(d);
    if ask.pitch_only {
        let (notes, pitch) = pitch_json(x, sr, ask.range);
        return serde_json::json!({ "seconds": r(x.len() as f64 / sr, 2), "notes": notes, "pitch": pitch });
    }
    // Fine frames (2048 / 512) for onsets and timbre; long ones (8192 / 2048) for pitch classes.
    let (n1, h1, n2, h2) = (2048, 512, 8192, 2048);
    let fine = stft(x, n1, h1);
    let long = stft(x, n2, h2);
    // Onsets on frames that end where they start: a sharp onset's flux peaks when it is about 1.2 hops
    // into a frame's tail, so the signal is led by a frame less that much and frame k's time is k hops
    // (measured on a click train: beats read 63 ms early without it).
    let lead = n1 - (1.2 * h1 as f64) as usize;
    let led: Vec<f32> = std::iter::repeat(0.0).take(lead).chain(x.iter().cloned()).collect();
    let Tempo { bpm, first, clarity, beats, alternatives, unsure, downbeat, heard, expected } = tempo(&stft(&led, n1, h1), sr / h1 as f64, sr / n1 as f64, ask.per_bar, ask.expect);
    let chromas: Vec<[f64; 12]> = long.iter().map(|m| chroma(m, sr, n2)).collect();
    // Chords from the register they are voiced in (from A2 up): a loud bass note would read a triad as its root and fifth.
    let voiced: Vec<[f64; 12]> = long.iter().map(|m| chroma_in(m, sr, n2, 110.0, 2000.0)).collect();
    let energy: Vec<f64> = long.iter().map(|m| m.iter().map(|v| v * v).sum::<f64>()).collect();
    let loudest = energy.iter().cloned().fold(0.0, f64::max).max(1e-12);
    let mut total = [0.0; 12];
    for (c, e) in chromas.iter().zip(&energy) {
        (0..12).for_each(|i| total[i] += c[i] * e);
    }
    // The bass: each frame's lowest note under 160 Hz (its overtones are not bass notes: a low C's
    // third harmonic is a G).
    let mut bass = [0.0; 12];
    for (m, e) in long.iter().zip(&energy) {
        if let Some(pc) = crate::analysis::keyfind::bass_note(m, sr / n2 as f64) {
            bass[pc] += e;
        }
    }
    // Chords per beat (the long frames that fall in it), merged while unchanged.
    let mut chords: Vec<(f64, f64, String)> = vec![];
    for w in beats.windows(2) {
        let frames: Vec<usize> = (0..long.len()).filter(|&f| { let t = (f * h2 + n2 / 2) as f64 / sr; t >= w[0] && t < w[1] }).collect();
        let quiet = frames.iter().all(|&f| energy[f] < loudest * 1e-3);
        let mut c = [0.0; 12];
        for &f in &frames {
            (0..12).for_each(|i| c[i] += voiced[f][i] / frames.len() as f64);
        }
        let name = if quiet || frames.is_empty() { "N".to_string() } else { crate::analysis::keyfind::chord(&c).unwrap_or_else(|| "N".into()) };
        match chords.last_mut() {
            Some(last) if last.2 == name => last.1 = w[1],
            _ => chords.push((w[0], w[1], name)),
        }
    }
    let mut melody = [0.0; 12];
    for (m, e) in long.iter().zip(&energy) {
        let b = chroma_in(m, sr, n2, 250.0, 2000.0);
        (0..12).for_each(|i| melody[i] += b[i] * e);
    }
    let (key_name, key_margin, key_rival) = crate::analysis::keyfind::key(&total, &bass, &melody, &chords);
    // Timbre every second: brightness (spectral centroid), energy per band (dB), noisiness (spectral flatness).
    let bands = [("sub", 20.0, 60.0), ("bass", 60.0, 250.0), ("lowMid", 250.0, 1000.0), ("mid", 1000.0, 4000.0), ("high", 4000.0, 10000.0)];
    let per = (sr / h1 as f64).round() as usize;
    let timbre: Vec<serde_json::Value> = fine
        .chunks(per.max(1))
        .enumerate()
        .map(|(s, frames)| {
            let mut sum = vec![0.0; n1 / 2];
            for m in frames {
                for (k, v) in m.iter().enumerate() {
                    sum[k] += v * v;
                }
            }
            let hz = |k: usize| k as f64 * sr / n1 as f64;
            let total: f64 = sum.iter().sum::<f64>().max(1e-20);
            let centroid = sum.iter().enumerate().map(|(k, p)| hz(k) * p).sum::<f64>() / total;
            let geo = (sum.iter().skip(1).map(|p| (p + 1e-20).ln()).sum::<f64>() / (sum.len() - 1) as f64).exp();
            let flat = geo / (total / sum.len() as f64);
            let level = |lo: f64, hi: f64| r(10.0 * (sum.iter().enumerate().filter(|(k, _)| hz(*k) >= lo && hz(*k) < hi).map(|(_, p)| p).sum::<f64>() / frames.len() as f64 + 1e-12).log10(), 0);
            serde_json::json!({ "t": s, "centroid": r(centroid, 0), "flatness": r(flat, 3), "bands": bands.iter().map(|(_, lo, hi)| level(*lo, *hi)).collect::<Vec<_>>() })
        })
        .collect();
    // Speech: alone (the stretcher's own test: PSOLA), or mixed with music (a hint: a pitched voice over a bed).
    let speech_alone = crate::stretch::psola::is_speech([x, x], sr);
    let speech_in_mix = !speech_alone && crate::stretch::psola::speech_in_mix(&crate::stretch::psola::speech_features([x, x], sr));
    let mut out = serde_json::json!({
        "seconds": r(x.len() as f64 / sr, 2),
        "tempo": { "bpm": r(bpm, 1), "firstBeat": r(first, 2), "clarity": r(clarity, 2), "halfAndDouble": [r(bpm / 2.0, 1), r(bpm * 2.0, 1)], "alternatives": alternatives.iter().map(|(b, s)| serde_json::json!([r(*b, 1), r(*s, 2)])).collect::<Vec<_>>(), "unsure": unsure.map(|u| r(u, 1)), "heard": r(heard, 1),
                   "expected": expected.map(|(b, fit)| serde_json::json!({ "bpm": r(b, 1), "support": r(fit, 2), "fits": fit >= crate::analysis::meter::FIT })) },
        "beats": beats.iter().map(|b| r(*b, 3)).collect::<Vec<_>>(),
        "downbeats": beats.iter().skip(downbeat.0).step_by(ask.per_bar).map(|b| r(*b, 3)).collect::<Vec<_>>(),
        "downbeatConfidence": r(downbeat.1, 2),
        "key": { "name": key_name, "margin": r(key_margin, 3), "alternative": key_rival, "unsure": key_margin < 0.1 || x.len() as f64 / sr < 4.0 },
        "chords": chords.iter().map(|(a, b, c)| serde_json::json!([r(*a, 2), r(*b, 2), c])).collect::<Vec<_>>(),
        "speech": { "alone": speech_alone, "inMix": speech_in_mix },
        "bandNames": bands.iter().map(|b| b.0).collect::<Vec<_>>(),
        "timbre": timbre,
    });
    if ask.notes {
        let (notes, pitch) = pitch_json(x, sr, ask.range);
        out["notes"] = notes;
        out["pitch"] = pitch;
    }
    out
}

#[cfg(test)]
#[path = "analyze_tests.rs"]
mod tests;
