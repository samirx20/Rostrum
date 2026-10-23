//! A track's designed sounds (`sounds`): each read through the design's field table (design/mod.rs), its
//! defaults filled, and written as one job clip of `designed` content.

use super::error::Error;
use super::read::Obj;
use super::time::Tempo;
use crate::design;
use serde_json::{json, Value};

/// (resolved, job clip, where it ends) for one designed sound.
pub fn read(v: &Value, at: &str, tempo: &Tempo, sr: u32) -> Result<(Value, Value, f64), Error> {
    let mut o = Obj::new(v, at)?;
    if let Some(old) = v.get("design").and_then(Value::as_str).filter(|d| design::RETIRED.contains(d)) {
        return Err(Error::new("BAD_ARGUMENT", &format!("{at}.design"), "this song", design::retired(old).trim_start_matches("this song ").to_string()));
    }
    let names = design::names();
    let name = o.name("design", &names, None)?;
    let t = tempo.time(o.required("at")?, &o.at("at"))?;
    o.put("at", json!(t));
    let own = design::fields(&name).expect("a design name read above");
    for f in design::COMMON.iter().chain(own) {
        let default = if f.3.is_nan() { None } else { Some(f.3) };
        o.num(f.0, f.1, f.2, default)?;
    }
    let resolved = o.done()?;
    let mut spec = resolved.clone();
    spec.remove("at");
    let secs = design::seconds(&spec);
    let samples = ((secs * sr as f64).ceil() as usize).max(16);
    let content = json!({ "kind": "designed", "spec": Value::Object(spec) });
    let job = super::track::clip_job(content, (t * sr as f64).round() as usize, samples, secs, 1.0, 0.0, 0.0, 0.0, vec![]);
    Ok((Value::Object(resolved), job, t + secs))
}

/// The field tables, as `describe` answers them.
pub fn describe() -> Value {
    let field = |f: &design::F| json!({ "name": f.0, "accepts": [f.1, f.2], "default": if f.3.is_nan() { Value::Null } else { json!(f.3) }, "help": f.4 });
    let common: Vec<Value> = design::COMMON.iter().map(field).collect();
    let designs: serde_json::Map<String, Value> = design::DESIGNS.iter().map(|(n, fs)| (n.to_string(), json!(fs.iter().map(field).collect::<Vec<_>>()))).collect();
    json!({ "common": common, "designs": designs, "lanes": {} })
}
