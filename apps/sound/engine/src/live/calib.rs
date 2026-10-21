//! Input latency calibration for overdubs. A microphone packet's time is when the device says it
//! captured it; what the device does before that (a mic array's processing) is not in it, and on
//! Sam's laptop it is a steady ~80 ms. `rostrum-sound play <silence> --calibrate` plays a loud sweep
//! on every beat (instead of the metronome click, which a laptop microphone barely hears), records it
//! back through the microphone (opened raw, so it doesn't turn itself down: record.rs), finds each
//! sweep by its shape and stores the median offset between played and recorded, per (output,
//! microphone, raw) set; every take afterwards is moved earlier by it, so it lands where it was played.

use std::path::PathBuf;

fn file() -> Option<PathBuf> {
    std::env::var_os("LOCALAPPDATA").map(|d| PathBuf::from(d).join("rostrum").join("audio-calibration.json"))
}

fn key(output: &str, mic: &str, raw: bool) -> String {
    format!("{output} | {mic}{}", if raw { " | raw" } else { "" })
}

/// The stored input offset (seconds) for this output and microphone, if they were calibrated.
pub fn offset(output: &str, mic: &str, raw: bool) -> Option<f64> {
    let v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(file()?).ok()?).ok()?;
    v[key(output, mic, raw)]["offsetMs"].as_f64().map(|ms| ms / 1000.0)
}

pub fn store(output: &str, mic: &str, raw: bool, offset_ms: f64, jitter_ms: f64) -> Result<String, String> {
    let f = file().ok_or("no LOCALAPPDATA folder to keep the calibration in")?;
    let mut v: serde_json::Value = std::fs::read_to_string(&f).ok().and_then(|s| serde_json::from_str(&s).ok()).unwrap_or(serde_json::json!({}));
    v[key(output, mic, raw)] = serde_json::json!({ "offsetMs": offset_ms, "jitterMs": jitter_ms });
    if let Some(d) = f.parent() {
        std::fs::create_dir_all(d).map_err(|e| format!("{}: {e}", d.display()))?;
    }
    std::fs::write(&f, serde_json::to_string_pretty(&v).unwrap()).map_err(|e| format!("{}: {e}", f.display()))?;
    Ok(f.to_string_lossy().into_owned())
}

/// The calibration signal the transport plays on each beat instead of the click: a loud, short sweep
/// (600 Hz → 7 kHz, where laptop speakers and microphones both work). A sweep is found by matching its
/// shape (cross-correlation), so it is found even when quiet, under room noise, or turned down by the mic.
pub const CHIRP: f64 = 0.08;

pub fn chirp(t: f64) -> f32 {
    if !(0.0..CHIRP).contains(&t) {
        return 0.0;
    }
    let (f0, f1) = (600.0f64, 7000.0f64);
    let k = (f1 / f0).ln() / CHIRP;
    let phase = 2.0 * std::f64::consts::PI * f0 * ((k * t).exp() - 1.0) / k;
    let fade = (t / 0.004).min(1.0) * ((CHIRP - t) / 0.004).min(1.0);
    (phase.sin() * fade * 0.7) as f32
}

/// The sweeps found in a take (mono, `rate`, starting at mix time `start`), one per beat of `beat`
/// seconds: (median offset, spread from the 10th to the 90th percentile, sweeps found) in milliseconds,
/// or None with fewer than four. The first beat is left out (a device settling in). A beat counts only
/// when its best match stands clear of the rest of its window (12× the window's RMS; noise alone
/// peaks near 4–5×).
pub fn measure(take: &[f32], rate: f64, start: f64, beat: f64) -> Option<(f64, f64, usize)> {
    let template: Vec<f32> = (0..(CHIRP * rate) as usize).map(|i| chirp(i as f64 / rate)).collect();
    let corr = correlate(take, &template);
    let end = start + take.len() as f64 / rate;
    let mut offs = vec![];
    let mut b = (start / beat).ceil() + 1.0;
    while (b * beat + 0.45 + CHIRP) < end {
        let (lo, hi) = (((b * beat - 0.02 - start) * rate).max(0.0) as usize, ((b * beat + 0.45 - start) * rate) as usize);
        let w = &corr[lo..hi.min(corr.len())];
        let (i, peak) = w.iter().enumerate().fold((0, 0f32), |m, (i, v)| if v.abs() > m.1 { (i, v.abs()) } else { m });
        let rms = (w.iter().map(|v| (v * v) as f64).sum::<f64>() / w.len().max(1) as f64).sqrt() as f32;
        if peak > 12.0 * rms && peak > 1e-4 {
            offs.push((start + (lo + i) as f64 / rate - b * beat) * 1000.0);
        }
        b += 1.0;
    }
    if offs.len() < 4 {
        return None;
    }
    offs.sort_by(f64::total_cmp);
    Some((offs[offs.len() / 2], offs[offs.len() * 9 / 10] - offs[offs.len() / 10], offs.len()))
}

/// corr[i] = Σ x[i + j]·t[j], by FFT.
fn correlate(x: &[f32], t: &[f32]) -> Vec<f32> {
    let n = (x.len() + t.len()).next_power_of_two();
    let mut planner = realfft::RealFftPlanner::<f32>::new();
    let (fwd, inv) = (planner.plan_fft_forward(n), planner.plan_fft_inverse(n));
    let spectrum = |v: &[f32]| {
        let mut buf = vec![0f32; n];
        buf[..v.len()].copy_from_slice(v);
        let mut out = fwd.make_output_vec();
        fwd.process(&mut buf, &mut out).unwrap();
        out
    };
    let (xs, ts) = (spectrum(x), spectrum(t));
    let mut prod: Vec<_> = xs.iter().zip(&ts).map(|(a, b)| a * b.conj()).collect();
    let mut out = vec![0f32; n];
    inv.process(&mut prod, &mut out).unwrap();
    out.truncate(x.len());
    out
}

#[cfg(test)]
mod tests {
    #[test]
    fn finds_a_steady_offset_between_played_and_recorded_sweeps() {
        // Sweeps every 0.5 s, recorded 184 ms late, quiet (−30 dB) under noise, in a take starting 0.19 s into the mix.
        let rate = 48000.0;
        let start = 0.19;
        let mut seed = 1u32;
        let mut take: Vec<f32> = (0..(rate * 6.0) as usize).map(|_| { seed = seed.wrapping_mul(1664525).wrapping_add(1013904223); (seed >> 8) as f32 / 16777216.0 * 0.02 - 0.01 }).collect();
        for b in 1..11 {
            let at = ((b as f64 * 0.5 + 0.184 - start) * rate) as usize;
            for k in 0..(super::CHIRP * rate) as usize {
                take[at + k] += 0.03 * super::chirp(k as f64 / rate);
            }
        }
        let (median, spread, n) = super::measure(&take, rate, start, 0.5).unwrap();
        assert!((median - 184.0).abs() < 0.5 && spread < 1.0 && n >= 8, "{median} {spread} {n}");
    }
}
