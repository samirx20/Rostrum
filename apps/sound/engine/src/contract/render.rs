//! The `render` request: the schedule compiled, the mix rendered (tracks read back from the render cache
//! when unchanged), the mix and any stems written whole or not at all (`.partial`, then renamed), and the
//! meters answered in the same reply.

use super::error::Error;
use super::read::Obj;
use super::schedule::{compile, Compiled};
use crate::mix::{render, schedule::Schedule, wavio};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

pub struct Job {
    c: Compiled,
    out: PathBuf,
    stems: Vec<bool>,
    stems_dir: PathBuf,
}

/// Reads the request's fields (so an unknown one fails before any work).
pub fn read(o: &mut Obj) -> Result<Job, Error> {
    let mut c = compile(o.required("schedule")?, "schedule")?;
    let out = PathBuf::from(o.str("out", None)?);
    if !out.is_absolute() || out.extension().is_none_or(|e| !e.eq_ignore_ascii_case("wav")) {
        return Err(Error::new("BAD_ARGUMENT", "out", format!("\"{}\"", out.display()), "is not an absolute path to a .wav file"));
    }
    let stems: Vec<bool> = match o.raw("stems") {
        None => vec![false; c.ids.len()],
        Some(Value::String(s)) if s == "all" => vec![true; c.ids.len()],
        Some(Value::Array(a)) => {
            let mut keep = vec![false; c.ids.len()];
            for (i, v) in a.iter().enumerate() {
                let at = format!("stems[{i}]");
                let name = v.as_str().ok_or_else(|| Error::bad(&at, v, "is not a track id", &[]))?;
                let ids: Vec<&str> = c.ids.iter().map(String::as_str).collect();
                let k = ids.iter().position(|i| *i == name).ok_or_else(|| Error::unknown(&at, name, &ids))?;
                keep[k] = true;
            }
            keep
        }
        Some(v) => return Err(Error::bad("stems", v, "is not \"all\" or a list of track ids", &["\"all\"", "[\"strings\"]"])),
    };
    let default_dir = out.with_extension("stems");
    let stems_dir = PathBuf::from(o.str("stemsDir", Some(&default_dir.to_string_lossy()))?);
    if !o.bool("master", true)? {
        c.job["master"] = Value::Null;
    }
    Ok(Job { c, out, stems, stems_dir })
}

pub fn run(job: Job) -> Result<Value, Error> {
    let Job { c, out, stems, stems_dir } = job;
    let s = Schedule::parse(&c.job.to_string()).map_err(|e| Error::new("INTERNAL", "render", "the compiled job", e))?;
    let t0 = std::time::Instant::now();
    let cache = crate::mix::trackcache::TrackCache::default_dir();
    let mix = render::render_keep(&s, cache.as_ref(), &stems).map_err(Error::render)?;
    let took = t0.elapsed().as_secs_f64();
    let sr = s.sample_rate;
    write(&out, &wavio::write(&mix.channels, mix.layout, sr))?;
    let mut stem_files = serde_json::Map::new();
    if !mix.stems.is_empty() {
        std::fs::create_dir_all(&stems_dir).map_err(|e| Error::render(format!("{}: {e}", stems_dir.display())))?;
        for (id, chs) in &mix.stems {
            let f = stems_dir.join(format!("{id}.wav"));
            write(&f, &wavio::write(chs, mix.layout, sr))?;
            stem_files.insert(id.clone(), json!(f.to_string_lossy()));
        }
    }
    // Bus stems beside them, `<bus>.bus.wav`: with the stems of the tracks that play straight to the master they
    // add up to what reaches the master (`direct` lists those tracks).
    let mut bus_files = serde_json::Map::new();
    for (id, chs) in &mix.bus_stems {
        std::fs::create_dir_all(&stems_dir).map_err(|e| Error::render(format!("{}: {e}", stems_dir.display())))?;
        let f = stems_dir.join(format!("{id}.bus.wav"));
        write(&f, &wavio::write(chs, mix.layout, sr))?;
        bus_files.insert(id.clone(), json!(f.to_string_lossy()));
    }
    let direct: Vec<&str> = s.tracks.iter().filter(|t| t.into.is_none() && crate::mix::buses::direct(&s, t)).map(|t| t.name.as_str()).collect();
    let refs: Vec<&[f32]> = mix.channels.iter().map(|c| c.as_slice()).collect();
    let loud = crate::analysis::loudstats::stats_n(&refs, &mix.layout.weights(), sr as f64);
    let r2 = |v: f64| (v * 100.0).round() / 100.0;
    let tracks: Vec<Value> = mix.tracks.iter().map(|t| json!({ "id": t.name, "peak": t.peak, "rms": t.rms, "lufs": t.lufs,
        "span": t.span.map(|(a, b)| [a, b]), "onsets": t.onsets, "bands": t.bands })).collect();
    Ok(json!({
        "file": out.to_string_lossy(), "seconds": c.seconds, "renderSeconds": took, "sampleRate": sr,
        "lufs": mix.lufs, "truePeak": mix.true_peak, "peak": mix.peak, "lra": loud.lra, "clipped": mix.clipped, "bands": mix.bands,
        "series": { "hop": 0.1, "shortTermWindow": 3.0, "correlationWindow": 0.4, "momentaryWindow": 0.4,
            "momentary": loud.momentary.iter().map(|&v| (v * 1000.0).round() / 1000.0).collect::<Vec<_>>(),
            "shortTerm": loud.short_term.iter().map(|&v| r2(v)).collect::<Vec<_>>(),
            "truePeak": mix.true_peak_series.iter().map(|&v| r2(v)).collect::<Vec<_>>(),
            "correlation": loud.correlation.iter().map(|v| v.map(|c| (c * 1000.0).round() / 1000.0)).collect::<Vec<_>>() },
        "tracks": tracks, "stems": stem_files, "busStems": bus_files, "direct": direct,
        // What the stems took of the master: its linear gain (they carry it), and what they cannot carry.
        "master": { "gainDb": r2(mix.master.gain_db), "glueMaxReductionDb": r2(mix.master.glue_db),
                    "limiterMaxReductionDb": r2(mix.master.limiter_db),
                    "insertsOnMix": !s.effects.is_empty() || s.master_reverb != "dry" || !s.time_warps.is_empty() },
        "buses": mix.buses.iter().map(|t| json!({ "id": t.name, "peak": t.peak, "rms": t.rms, "lufs": t.lufs })).collect::<Vec<_>>(),
        "ducks": mix.ducks.iter().map(|(t, spans)| json!({ "track": t, "spans": spans.iter().map(|&(a, b, db)| [a, b, db]).collect::<Vec<_>>() })).collect::<Vec<_>>(),
    }))
}

/// Written to `<file>.partial`, checked, then renamed: a failed write leaves no file under the real name.
fn write(path: &Path, bytes: &[u8]) -> Result<(), Error> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| Error::render(format!("{}: {e}", dir.display())))?;
    }
    let partial = PathBuf::from(format!("{}.partial", path.display()));
    std::fs::write(&partial, bytes).map_err(|e| Error::render(format!("{}: {e}", partial.display())))?;
    if std::fs::metadata(&partial).map(|m| m.len()).unwrap_or(0) != bytes.len() as u64 {
        return Err(Error::render(format!("{} was not written whole; kept for inspection", partial.display())));
    }
    let _ = std::fs::remove_file(path);
    std::fs::rename(&partial, path).map_err(|e| Error::render(format!("{} → {}: {e}", partial.display(), path.display())))
}
