//! The `render` request: the schedule compiled, the mix rendered (tracks read back from the render cache
//! when unchanged), the mix and any stems written block by block, whole or not at all (`.partial`, then
//! renamed), the strips' live meters beside it (`<mix>.levels.json`, levels.rs), and the meters answered in the same reply.

use super::error::Error;
use super::read::Obj;
use super::schedule::{compile, Compiled};
use crate::mix::{render, schedule::Schedule};
use serde_json::{json, Value};
use std::path::PathBuf;

pub struct Job {
    c: Compiled,
    out: PathBuf,
    stems: Vec<bool>,
    stems_dir: PathBuf,
    /// A stretch of the song, seconds (`from` / `to`; both or neither).
    range: Option<(f64, f64)>,
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
    let range = match (o.opt_num("from", 0.0, 1e7)?, o.opt_num("to", 0.0, 1e7)?) {
        (None, None) => None,
        (Some(a), Some(b)) if a < b => Some((a, b)),
        (a, b) => return Err(Error::new("BAD_ARGUMENT", "from", format!("from {a:?} to {b:?}"), "is not a stretch of the song: give both `from` and `to` in seconds, 0 ≤ from < to")),
    };
    Ok(Job { c, out, stems, stems_dir, range })
}

pub fn run(job: Job) -> Result<Value, Error> {
    let Job { c, out, stems, stems_dir, range } = job;
    let mut s = Schedule::parse(&c.job.to_string()).map_err(|e| Error::new("INTERNAL", "render", "the compiled job", e))?;
    if let Some((a, b)) = range {
        let (sr, total) = (s.sample_rate as f64, s.total_samples);
        let (from, to) = ((a * sr).round() as usize, ((b * sr).round() as usize).min(total));
        if from >= to {
            return Err(Error::new("BAD_ARGUMENT", "from", format!("{a} s"), format!("starts after the song ends ({:.1} s)", total as f64 / sr)));
        }
        s.range = Some((from, to));
    }
    let t0 = std::time::Instant::now();
    let cache = crate::mix::trackcache::TrackCache::default_dir();
    let mix = render::render_keep(&s, cache.as_ref(), &stems).map_err(Error::render)?;
    let took = t0.elapsed().as_secs_f64();
    let sr = s.sample_rate;
    crate::mix::wavwriter::write_mix(&out, &mix, sr).map_err(Error::render)?;
    // The stems, `<track>.wav`, and the bus stems beside them, `<bus>.bus.wav`: with the stems of the tracks that play
    // straight to the master the bus stems add up to what reaches the master (`direct` lists those tracks).
    let named = |list: &[(String, std::sync::Arc<crate::mix::tape::Tape>)], ext: &str| -> Vec<(String, PathBuf)> { list.iter().map(|(id, _)| (id.clone(), stems_dir.join(format!("{id}{ext}")))).collect() };
    let (stem_paths, bus_paths) = (named(&mix.stems, ".wav"), named(&mix.bus_stems, ".bus.wav"));
    let files: Vec<(&crate::mix::tape::Tape, PathBuf)> = mix.stems.iter().chain(&mix.bus_stems).zip(stem_paths.iter().chain(&bus_paths)).map(|((_, t), (_, p))| (&**t, p.clone())).collect();
    render::stems::write(&mix, &files, sr).map_err(Error::render)?;
    // The strips' live meters beside the mix (levels.rs): what `rostrum-sound play` shows while it plays this file.
    render::levels::Levels::of(&mix, sr as f64, s.range.map_or(0, |r| r.0)).write(&out).map_err(Error::render)?;
    let as_map = |paths: &[(String, PathBuf)]| -> serde_json::Map<String, Value> { paths.iter().map(|(id, p)| (id.clone(), json!(p.to_string_lossy()))).collect() };
    let (stem_files, bus_files) = (as_map(&stem_paths), as_map(&bus_paths));
    let direct: Vec<&str> = s.tracks.iter().filter(|t| t.into.is_none() && crate::mix::buses::direct(&s, t)).map(|t| t.name.as_str()).collect();
    let loud = mix.loud().map_err(Error::render)?;
    let r2 = |v: f64| (v * 100.0).round() / 100.0;
    let tracks: Vec<Value> = mix.tracks.iter().map(|t| json!({ "id": t.name, "peak": t.peak, "rms": t.rms, "lufs": t.lufs,
        "span": t.span.map(|(a, b)| [a, b]), "onsets": t.onsets, "bands": t.bands })).collect();
    Ok(json!({
        "file": out.to_string_lossy(), "seconds": c.seconds,
        "range": s.range.map(|(a, b)| [a as f64 / sr as f64, b as f64 / sr as f64]), "renderSeconds": took, "sampleRate": sr,
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
