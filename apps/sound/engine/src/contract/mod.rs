//! The engine contract (apps/sound/ENGINE_CONTRACT.md): requests in, answers out. The schedule is read
//! strictly (read.rs, names.rs) and compiled to the engine's internal job (schedule.rs, track.rs), which
//! the renderer reads; requests come one per line (`serve`) or one per run (`request`, `render`). Plugins
//! (plugin.rs) are listed and opened for a person by plugin_requests.rs.

mod buses;
mod channel;
mod clip;
mod effects;
mod ending;
mod error;
mod expression;
mod hit;
mod instrument;
mod measure;
pub(crate) mod media;
pub mod names;
mod names_instruments;
mod perform;
mod plain;
mod pitch;
mod plugin;
mod plugin_requests;
mod range;
mod read;
mod render;
mod schedule;
pub mod serve;
mod meter;
mod time;
mod track;
#[cfg(test)]
mod tests;

pub use error::Error;
use serde_json::{json, Value};

/// One request answered: `{"id", "ok": true, "result"}` or `{"id", "ok": false, "error"}`.
pub fn answer(req: &Value) -> Value {
    let id = req.get("id").cloned().unwrap_or(Value::Null);
    match handle(req) {
        Ok(result) => json!({ "id": id, "ok": true, "result": result }),
        Err(e) => json!({ "id": id, "ok": false, "error": e.to_json() }),
    }
}

/// Every request this engine answers (`describe` lists them, so a host can tell what an older engine lacks).
const REQUESTS: &[&str] = &["describe", "check", "render", "measure", "range", "plugins", "pluginWindow", "quit"];

fn handle(req: &Value) -> Result<Value, Error> {
    let mut o = read::Obj::new(req, "")?;
    let _ = o.raw("id");
    let what = o.name("do", REQUESTS, None)?;
    if what != "measure" {
        crate::mix::held::clear();             // a run of `measure` requests ends: what it held is let go
    }
    // Every field is read (and unknown ones refused) before anything is rendered, scanned or opened.
    let job = if what == "render" { Some(render::read(&mut o)?) } else { None };
    let trials = if what == "measure" { Some(measure::read(&mut o)?) } else { None };
    let scan = if what == "plugins" { Some(plugin_requests::read_paths(&mut o)?) } else { None };
    let window = if what == "pluginWindow" { Some(plugin_requests::read_window(&mut o)?) } else { None };
    let result = match what.as_str() {
        "describe" => {
            let mut d = names::describe();
            d["contract"] = json!(schedule::CONTRACT);
            d["engine"] = json!(env!("CARGO_PKG_VERSION"));
            d["requests"] = json!(REQUESTS);
            d
        }
        "check" => {
            let c = schedule::compile(o.required("schedule")?, "schedule")?;
            json!({ "resolved": c.resolved, "length": c.seconds, "tracks": c.ids.len(), "credits": c.credits })
        }
        "range" => range::range(o.required("instrument")?, "instrument")?,
        "render" | "measure" | "plugins" | "pluginWindow" => json!(null),
        _ => json!({ "bye": true }),
    };
    o.done()?;
    if let Some(paths) = scan {
        return Ok(plugin_requests::list(&paths));
    }
    if let Some(p) = window {
        return plugin_requests::open(p);
    }
    if let Some(t) = trials {
        return measure::run(t);
    }
    match job {
        Some(job) => render::run(job),
        None => Ok(result),
    }
}
