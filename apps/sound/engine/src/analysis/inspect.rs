//! `rostrum-sound inspect <clip.wav> [--png <out.png>]`: what is wrong with a recording, as numbers
//! (and a spectrogram) an agent can act on — clipped runs, clicks, mains hum, the room's decay and
//! late-reverb share, sibilance, the long-term spectrum (1/3 octave, what a tone match compares)
//! and transient noises (a cough, a knock, a click: when, how long, which band, how loud). The
//! detectors are the repairs' own (lsar.rs, dehum.rs, dereverb.rs), so what is reported is what the
//! repair will act on. The host renders the clip (src/engine/sound/render/clipInspect.ts) and caches this.

use serde_json::{json, Value};

use crate::analysis::balance::db;
use crate::analysis::stft::{forward, frame_time, Spec};

const N: usize = 1024;
const HOP: usize = 256;

/// Mean power per bin over the given frames.
fn mean_power(s: &Spec, frames: &[usize]) -> Vec<f64> {
    (0..=s.n / 2).map(|k| frames.iter().map(|&f| s.power(f, k)).sum::<f64>() / frames.len().max(1) as f64).collect()
}

/// Third-octave long-term spectrum (dB) over the active frames, centres 25 Hz … Nyquist.
fn ltas(s: &Spec, active: &[usize], sr: f64) -> Vec<[f64; 2]> {
    let p = mean_power(s, active);
    let hz = sr / s.n as f64;
    // Power normalised so a full-scale sine reads about 0 dB in its band (sqrt-Hann window sum n/2·…).
    let norm = 4.0 / (s.n as f64 * s.n as f64 * 0.5);
    (0..31).map(|i| 25.0 * 2f64.powf(i as f64 / 3.0)).filter(|c| *c * 2f64.powf(1.0 / 6.0) < sr / 2.0).map(|c| {
        let (k0, k1) = (((c / 2f64.powf(1.0 / 6.0)) / hz).round() as usize, ((c * 2f64.powf(1.0 / 6.0)) / hz).round() as usize);
        [(c * 10.0).round() / 10.0, db(norm * (k0..=k1.max(k0)).map(|k| p[k]).sum::<f64>())]
    }).collect()
}

/// Transient noises: frames 12 dB over the clip's floor and no more than 10 dB under the sound
/// around them (±0.5 s: not a phrase's tail) that are not periodic (no voice in them) and not a
/// sibilant (a twentieth of their power between 300 Hz and 2 kHz), grouped, 40 ms or longer; the band
/// holding 90 % of their excess power over the surroundings; their peak against the speech level.
fn noises(s: &Spec, x: &[f32], sr: f64) -> Vec<Value> {
    let hz = sr / s.n as f64;
    let bin = |f: f64| ((f / hz) as usize).min(s.n / 2);
    let frames = s.re.len();
    let level: Vec<f64> = (0..frames).map(|f| 10.0 * (bin(100.0)..=s.n / 2).map(|k| s.power(f, k)).sum::<f64>().max(1e-14).log10()).collect();
    let span = (0.5 * sr / s.hop as f64) as usize;
    let mut sorted = level.clone();
    sorted.sort_by(|a, b| a.total_cmp(b));
    let floor = sorted.get(sorted.len() / 10).copied().unwrap_or(-120.0);
    let speech = sorted.get(sorted.len() * 3 / 4).copied().unwrap_or(-120.0);
    // Periodicity: the autocorrelation of 43 ms of the signal around the frame, peak at 2.5 … 14 ms
    // lags with the window's own taper divided out (a voice is periodic, a cough is not).
    const W: usize = 2048;
    let hann: Vec<f64> = (0..W).map(|i| 0.5 - 0.5 * (2.0 * std::f64::consts::PI * i as f64 / W as f64).cos()).collect();
    let autocorr = |seg: &dyn Fn(usize) -> f64| -> Vec<f64> {
        let (mut re, mut im) = (vec![0.0; 2 * W], vec![0.0; 2 * W]);
        for i in 0..W {
            re[i] = seg(i) * hann[i];
        }
        crate::fx::convolve::fft(&mut re, &mut im, false);
        for k in 0..2 * W {
            (re[k], im[k]) = (re[k] * re[k] + im[k] * im[k], 0.0);
        }
        crate::fx::convolve::fft(&mut re, &mut im, true);
        re
    };
    let taper = autocorr(&|_| 1.0);
    let (la, lb) = ((0.0025 * sr) as usize, ((0.014 * sr) as usize).min(W / 2));
    let periodic = |f: usize| -> f64 {
        let c = frame_time(f, s.n, s.hop, sr) * sr;
        let r = autocorr(&|i| x.get((c as isize + i as isize - (W / 2) as isize).max(0) as usize).copied().unwrap_or(0.0) as f64);
        (la..lb).map(|l| r[l] / r[0].max(1e-30) * taper[0] / taper[l]).fold(0.0, f64::max)
    };
    let cand: Vec<bool> = (0..frames).map(|f| {
        let mut around: Vec<f64> = level[f.saturating_sub(span)..(f + span).min(frames)].to_vec();
        around.sort_by(|a, b| a.total_cmp(b));
        let low: f64 = (bin(300.0)..bin(2000.0)).map(|k| s.power(f, k)).sum::<f64>();
        let all: f64 = (bin(100.0)..=s.n / 2).map(|k| s.power(f, k)).sum::<f64>().max(1e-20);
        level[f] > floor + 12.0 && level[f] > around[around.len() / 2] - 10.0 && low / all > 0.05 && periodic(f) < 0.5
    }).collect();
    let mut out = vec![];
    let mut f = 0;
    while f < frames {
        if !cand[f] {
            f += 1;
            continue;
        }
        let a = f;
        while f + 1 < frames && (cand[f + 1] || (f + 2 < frames && cand[f + 2])) {
            f += 1;
        }
        let group: Vec<usize> = (a..=f).collect();
        let ctx: Vec<usize> = (a.saturating_sub(span)..(f + span).min(frames)).filter(|g| !cand[*g]).collect();
        let (pg, pb) = (mean_power(s, &group), mean_power(s, &ctx));
        let excess: Vec<f64> = pg.iter().zip(&pb).map(|(g, b)| (g - b).max(0.0)).collect();
        let total: f64 = excess.iter().sum::<f64>().max(1e-20);
        let (mut acc, mut lo, mut hi) = (0.0, 0, s.n / 2);
        for (k, e) in excess.iter().enumerate() {
            acc += e;
            if acc < 0.05 * total { lo = k + 1 }
            if acc <= 0.95 * total { hi = k + 1 }
        }
        let peak = group.iter().map(|&g| level[g]).fold(f64::MIN, f64::max) - speech;
        let (t0, t1) = (frame_time(a, s.n, s.hop, sr) - s.hop as f64 / sr, frame_time(f, s.n, s.hop, sr) + s.hop as f64 / sr);
        let r = |v: f64| (v * 1000.0).round() / 1000.0;
        // Shorter is a plosive or a click (clicks are counted on their own).
        if t1 - t0 >= 0.04 {
            out.push(json!({ "at": r(t0.max(0.0)), "duration": r(t1 - t0.max(0.0)), "lowHz": (lo as f64 * hz).round(), "highHz": (hi.min(s.n / 2) as f64 * hz).round(), "vsSpeechDb": (peak * 10.0).round() / 10.0 }));
        }
        f += 1;
    }
    out.sort_by(|a, b| b["vsSpeechDb"].as_f64().unwrap_or(0.0).total_cmp(&a["vsSpeechDb"].as_f64().unwrap_or(0.0)));
    out.truncate(20);
    out
}

pub fn inspect(l: &[f32], r: &[f32], sr: f64, png: Option<&str>) -> Result<Value, String> {
    let mid: Vec<f32> = l.iter().zip(r).map(|(a, b)| (a + b) * 0.5).collect();
    let seconds = l.len() as f64 / sr;
    let s = forward(&mid, N, HOP);
    let fl: Vec<f64> = (0..s.re.len()).map(|f| (0..=N / 2).map(|k| s.power(f, k)).sum::<f64>()).collect();
    let top = fl.iter().fold(0.0f64, |m, v| m.max(*v));
    let active: Vec<usize> = (0..fl.len()).filter(|&f| fl[f] > top * 1e-3).collect();
    let peak = l.iter().chain(r).fold(0.0f32, |m, v| m.max(v.abs())) as f64;
    let ms = l.iter().chain(r).map(|v| (*v as f64).powi(2)).sum::<f64>() / (2 * l.len()).max(1) as f64;
    // Clipping: runs of 2+ samples at 99.9 % of the peak (what declip at its default would redraw).
    let runs = |x: &[f32]| { let mut c = x.to_vec(); crate::dialogue::lsar::declip(&mut c, 0.999) };
    // Clicks: where declick (at its defaults) would act, on the louder channel's count.
    let max_len = (sr * 0.0015) as usize;
    let (cl, cr) = (crate::dialogue::declick::clicks(l, 5.0, max_len), crate::dialogue::declick::clicks(r, 5.0, max_len));
    let clicks: Vec<f64> = if cl.len() >= cr.len() { cl } else { cr }.iter().map(|g| (g.0 as f64 / sr * 1000.0).round() / 1000.0).collect();
    let hum = crate::dialogue::dehum::detect(&mid, sr, None, 8).map(|h| json!({ "hz": (h.f0 * 100.0).round() / 100.0, "levelDb": (h.level_db * 10.0).round() / 10.0, "harmonicsDb": h.prominence.iter().map(|p| (p * 10.0).round() / 10.0).collect::<Vec<_>>() }));
    let reverb = crate::dialogue::dereverb::decay_time(l, r, sr).map(|rt| {
        let big = forward(&mid, 2048, 512);
        let g = crate::dialogue::dereverb::late_gain(&big, rt, sr, 1.0, 0.0);
        let (mut late, mut all) = (0.0, 0.0);
        for f in 0..big.re.len() {
            for k in 0..=1024 {
                let p = big.power(f, k);
                all += p;
                late += p * (1.0 - g[f][k] * g[f][k]);
            }
        }
        json!({ "rt60": (rt * 100.0).round() / 100.0, "lateDb": db(late / all.max(1e-20)) })
    });
    // Sibilance: the 4–10 kHz band against the voice band (300 Hz–3.4 kHz) over the speech frames:
    // their medians, and their loudest 5 % (the sibilants' peaks against the vowels').
    let hz = sr / N as f64;
    let band = |a: f64, b: f64| -> Vec<f64> {
        let mut v: Vec<f64> = active.iter().map(|&f| ((a / hz) as usize..((b / hz) as usize).min(N / 2)).map(|k| s.power(f, k)).sum::<f64>().max(1e-20)).collect();
        v.sort_by(|x, y| x.total_cmp(y));
        v
    };
    let (sib, voice) = (band(4000.0, 10000.0f64.min(sr * 0.49)), band(300.0, 3400.0));
    let pick = |q: f64| -> Option<f64> {
        let i = ((sib.len() as f64 - 1.0) * q) as usize;
        Some((10.0 * (sib.get(i)? / voice.get(i)?).log10() * 10.0).round() / 10.0)
    };
    let found = noises(&s, &mid, sr);
    let spectrogram = match png {
        Some(path) => {
            let boxes: Vec<(f64, f64, f64, f64)> = found.iter().map(|n| { let a = n["at"].as_f64().unwrap_or(0.0); (a, a + n["duration"].as_f64().unwrap_or(0.0), n["lowHz"].as_f64().unwrap_or(0.0), n["highHz"].as_f64().unwrap_or(0.0)) }).collect();
            let (w, h) = crate::analysis::spectrogram::write(path, &s, sr, seconds, &boxes)?;
            json!({ "file": path, "width": w, "height": h, "seconds": seconds, "minHz": crate::analysis::spectrogram::MIN_HZ, "maxHz": sr / 2.0 })
        }
        None => Value::Null,
    };
    Ok(json!({
        "seconds": seconds, "sampleRate": sr, "peakDb": db(peak * peak), "rmsDb": db(ms),
        "clipping": { "runs": runs(l).max(runs(r)), "atFullScale": peak >= 0.999 },
        "clicks": clicks.len(), "clickTimes": clicks.iter().take(20).collect::<Vec<_>>(), "hum": hum, "reverb": reverb,
        "sibilance": { "medianDb": pick(0.5), "loudestDb": pick(0.95) },
        "ltas": ltas(&s, &active, sr), "noises": found, "spectrogram": spectrogram,
    }))
}
