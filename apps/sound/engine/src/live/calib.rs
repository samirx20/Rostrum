//! Input latency calibration for overdubs. A microphone packet's time is when the device says it
//! captured it; what the device does before that (a mic array's processing) is not in it, and on
//! Sam's laptop it is a steady ~80 ms. `rostrum-sound play <silence> --calibrate` plays the
//! metronome, records it back through the microphone, and stores the median offset between each
//! click as played and as recorded, per (output, microphone) pair; every take afterwards is moved
//! earlier by it, so it lands where it was played.

use std::path::PathBuf;

fn file() -> Option<PathBuf> {
    std::env::var_os("LOCALAPPDATA").map(|d| PathBuf::from(d).join("rostrum").join("audio-calibration.json"))
}

fn key(output: &str, mic: &str) -> String {
    format!("{output} | {mic}")
}

/// The stored input offset (seconds) for this output and microphone, if they were calibrated.
pub fn offset(output: &str, mic: &str) -> Option<f64> {
    let v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(file()?).ok()?).ok()?;
    v[key(output, mic)]["offsetMs"].as_f64().map(|ms| ms / 1000.0)
}

pub fn store(output: &str, mic: &str, offset_ms: f64, jitter_ms: f64) -> Result<String, String> {
    let f = file().ok_or("no LOCALAPPDATA folder to keep the calibration in")?;
    let mut v: serde_json::Value = std::fs::read_to_string(&f).ok().and_then(|s| serde_json::from_str(&s).ok()).unwrap_or(serde_json::json!({}));
    v[key(output, mic)] = serde_json::json!({ "offsetMs": offset_ms, "jitterMs": jitter_ms });
    if let Some(d) = f.parent() {
        std::fs::create_dir_all(d).map_err(|e| format!("{}: {e}", d.display()))?;
    }
    std::fs::write(&f, serde_json::to_string_pretty(&v).unwrap()).map_err(|e| format!("{}: {e}", f.display()))?;
    Ok(f.to_string_lossy().into_owned())
}

/// Clicks found in a take (mono, `rate`, starting at mix time `start`) against a beat grid of
/// `beat` seconds: (median offset, spread) in milliseconds, or None with fewer than four clicks.
pub fn measure(take: &[f32], rate: f64, start: f64, beat: f64) -> Option<(f64, f64, usize)> {
    let frame = (rate / 1000.0).round().max(1.0) as usize;
    let env: Vec<f32> = take.chunks(frame).map(|c| c.iter().fold(0f32, |m, v| m.max(v.abs()))).collect();
    let mut sorted = env.clone();
    sorted.sort_by(f32::total_cmp);
    let floor = sorted.get(sorted.len() / 2).copied().unwrap_or(0.0);
    let threshold = (floor * 8.0).max(0.02);
    let (mut offs, mut last) = (vec![], None::<usize>);
    for (i, e) in env.iter().enumerate() {
        if *e > threshold && last.is_none_or(|l| i - l > (beat * 400.0) as usize) {
            let t = start + i as f64 / 1000.0;
            offs.push((t - (t / beat).round() * beat) * 1000.0);
            last = Some(i);
        }
    }
    if offs.len() < 4 {
        return None;
    }
    offs.sort_by(f64::total_cmp);
    Some((offs[offs.len() / 2], offs[offs.len() * 9 / 10] - offs[offs.len() / 10], offs.len()))
}

#[cfg(test)]
mod tests {
    #[test]
    fn finds_a_steady_offset_between_played_and_recorded_clicks() {
        // Clicks every 0.5 s, recorded 82 ms late, in a take that starts 0.19 s into the mix.
        let rate = 48000.0;
        let start = 0.19;
        let mut take = vec![0.001f32; (rate * 5.0) as usize];
        for b in 1..10 {
            let at = ((b as f64 * 0.5 + 0.082 - start) * rate) as usize;
            for k in 0..600 {
                take[at + k] = 0.3 * (k as f32 * 0.17).sin();
            }
        }
        let (median, spread, n) = super::measure(&take, rate, start, 0.5).unwrap();
        assert!((median - 82.0).abs() < 1.5 && spread < 2.0 && n == 9, "{median} {spread} {n}");
    }
}
