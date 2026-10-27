//! The `measure` request: one or more versions of a song mixed and mastered exactly as `render` does, and only their
//! numbers answered — no file is written. For a search over trials (the host's loudness fit: a compressor's threshold,
//! a fader, the master's limit): each trial's instruments and the measures of its unchanged tracks come from the run's
//! memory (mix/held.rs), the trials of one request run side by side, and the mastering stays in memory on a short
//! song. Any other request ends the run and lets that memory go.

use super::error::Error;
use super::read::Obj;
use super::schedule::{compile, Compiled};
use crate::mix::schedule::Schedule;
use serde_json::{json, Value};

/// Trials of one request mixed at once (each mix already uses every core for its tracks; its master is one thread).
const SIDE_BY_SIDE: usize = 4;

pub struct Job {
    trials: Vec<Compiled>,
}

/// `schedules` (a list: several trials, answered in order) or `schedule` (one); `master` (true; false: no mastering).
pub fn read(o: &mut Obj) -> Result<Job, Error> {
    let mut trials = if o.has("schedules") { o.list("schedules", |v, at| compile(v, &at))? } else { vec![compile(o.required("schedule")?, "schedule")?] };
    if trials.is_empty() {
        return Err(Error::new("BAD_ARGUMENT", "schedules", "[]", "holds no schedule to measure"));
    }
    if !o.bool("master", true)? {
        for c in &mut trials {
            c.job["master"] = Value::Null;
        }
    }
    Ok(Job { trials })
}

pub fn run(job: Job) -> Result<Value, Error> {
    let t0 = std::time::Instant::now();
    let answers = crate::mix::par::map_n(job.trials, SIDE_BY_SIDE, one);
    let results = answers.into_iter().collect::<Result<Vec<Value>, Error>>()?;
    Ok(json!({ "results": results, "renderSeconds": t0.elapsed().as_secs_f64() }))
}

/// One trial's numbers, named as `render` names them.
fn one(c: Compiled) -> Result<Value, Error> {
    let s = Schedule::parse(&c.job.to_string()).map_err(|e| Error::new("INTERNAL", "measure", "the compiled job", e))?;
    let t0 = std::time::Instant::now();
    let cache = crate::mix::trackcache::TrackCache::default_dir();
    let mix = crate::mix::render::render_held(&s, cache.as_ref()).map_err(Error::render)?;
    let r2 = |v: f64| (v * 100.0).round() / 100.0;
    Ok(json!({
        "renderSeconds": t0.elapsed().as_secs_f64(), "lufs": mix.lufs, "truePeak": mix.true_peak, "peak": mix.peak,
        "master": { "gainDb": r2(mix.master.gain_db), "glueMaxReductionDb": r2(mix.master.glue_db),
                    "limiterMaxReductionDb": r2(mix.master.limiter_db), "heldDb": r2(mix.master.held_db) },
        "tracks": mix.tracks.iter().map(|t| json!({ "id": t.name, "peak": t.peak, "rms": t.rms, "lufs": t.lufs })).collect::<Vec<_>>(),
        "buses": mix.buses.iter().map(|t| json!({ "id": t.name, "peak": t.peak, "rms": t.rms, "lufs": t.lufs })).collect::<Vec<_>>(),
    }))
}
