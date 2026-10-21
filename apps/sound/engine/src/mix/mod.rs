//! The offline mix (`rostrum-sound render`): the job TypeScript hands over (schedule/), every clip,
//! track and the master bus rendered (render/, bus.rs), the whole-clip effects and ducking
//! (effects.rs), each track kept in the render cache (trackcache.rs, cache.rs), the bed written as a
//! float WAV (wavio.rs). Clips and tracks render on all cores (par.rs), the result the same every run.

pub mod bus;
pub mod buses;
#[cfg(test)]
mod buses_tests;
pub mod cache;
pub mod clipshape;
pub mod duck;
pub mod effects;
pub mod par;
pub mod render;
pub mod schedule;
pub mod trackcache;
#[cfg(test)]
mod trackcache_tests;
pub mod wavio;

pub fn load(path: &str) -> Result<schedule::Schedule, String> {
    schedule::Schedule::parse(&std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?)
}

/// `rostrum-sound render <schedule.json> <out.wav>`: the mix written, its stats on stdout (JSON).
pub fn render_cmd(args: &[String]) -> Result<(), String> {
    use std::time::Instant;
    let s = load(&args[1])?;
    let t0 = Instant::now();
    let mix = render::render(&s)?;
    let took = t0.elapsed().as_secs_f64();
    std::fs::write(&args[2], wavio::write(&mix.channels, mix.layout, s.sample_rate)).map_err(|e| format!("{}: {e}", args[2]))?;
    let ducks: Vec<serde_json::Value> = mix.ducks.iter().map(|(t, spans)| serde_json::json!({ "track": t, "spans": spans.iter().map(|&(a, b, db)| [a, b, db]).collect::<Vec<_>>() })).collect();
    let secs = mix.channels[0].len() as f64 / s.sample_rate as f64;
    let refs: Vec<&[f32]> = mix.channels.iter().map(|c| c.as_slice()).collect();
    let t1 = Instant::now();
    let loud = crate::analysis::loudstats::stats_n(&refs, &mix.layout.weights(), s.sample_rate as f64);
    render::prof("loudness stats", t1);
    let r2 = |v: f64| (v * 100.0).round() / 100.0;
    // The meters' own series, one value per 100 ms hop (analysis/loudstats.rs): `shortTerm[k]` is the 3 s window ending
    // at (k + 30) / 10 s, `truePeak[k]` the 4x true peak (dBTP) of hop k, `correlation[k]` the L/R correlation of the
    // 400 ms window ending at (k + 4) / 10 s (null where it is below -70 dBFS).
    let series = serde_json::json!({
        "hop": 0.1, "shortTermWindow": 3.0, "correlationWindow": 0.4,
        "shortTerm": loud.short_term.iter().map(|&v| r2(v)).collect::<Vec<_>>(),
        "truePeak": mix.true_peak_series.iter().map(|&v| r2(v)).collect::<Vec<_>>(),
        "correlation": loud.correlation.iter().map(|v| v.map(|c| (c * 1000.0).round() / 1000.0)).collect::<Vec<_>>(),
    });
    let stat = |t: &render::stats::TrackStats| serde_json::json!({ "name": t.name, "peak": t.peak, "rms": t.rms, "lufs": t.lufs, "span": t.span.map(|(a, b)| [a, b]), "onsets": t.onsets, "bands": t.bands, "speech": t.speech, "shares": t.shares });
    let mut out = serde_json::json!({
        "seconds": secs, "renderSeconds": took, "realtimeFactor": secs / took.max(1e-9), "layout": mix.layout.name(), "channels": mix.channels.len(),
        "peak": mix.peak, "lufs": mix.lufs, "truePeak": mix.true_peak,
        "maxMomentary": loud.max_momentary, "maxShortTerm": loud.max_short_term, "lra": loud.lra, "sumSq": mix.sum_sq, "sums": mix.sums, "sumL": mix.sums[0], "sumR": mix.sums[1], "clipped": mix.clipped, "ducks": ducks, "bands": mix.bands, "series": series,
        "tracks": mix.tracks.iter().map(stat).collect::<Vec<_>>(),
        "surround": bus::surround_report(&mix, s.sample_rate as f64),
    });
    if !mix.buses.is_empty() {
        out["buses"] = mix.buses.iter().map(stat).collect();
    }
    println!("{out}");
    Ok(())
}
