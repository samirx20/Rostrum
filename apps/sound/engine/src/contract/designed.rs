//! A track's designed sounds (`sounds`): each read through the design's field table (design/mod.rs), its
//! defaults filled, and written as one job clip of `designed` content.

use super::error::Error;
use super::read::{number, Obj};
use super::time::Tempo;
use crate::design;
use serde_json::{json, Value};

/// (resolved, job clip, where it ends) for one designed sound.
pub fn read(v: &Value, at: &str, tempo: &Tempo, sr: u32) -> Result<(Value, Value, f64), Error> {
    let mut o = Obj::new(v, at)?;
    let names = design::names();
    let name = o.name("design", &names, None)?;
    let t = tempo.time(o.required("at")?, &o.at("at"))?;
    o.put("at", json!(t));
    let own = design::fields(&name).expect("a design name read above");
    for f in design::COMMON.iter().chain(own) {
        let default = if f.3.is_nan() { None } else { Some(f.3) };
        o.num(f.0, f.1, f.2, default)?;
    }
    if name == "whoosh" {
        for (key, lo, hi) in [("speed", 0.0, 1.0), ("panPath", -1.0, 1.0)] {
            if let Some(l) = o.raw(key) {
                let pts = lane(l, &o.at(key), lo, hi)?;
                o.put(key, json!(pts));
            }
        }
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

/// `[[fraction 0 … 1, value], …]`, fractions rising.
fn lane(v: &Value, at: &str, lo: f64, hi: f64) -> Result<Vec<[f64; 2]>, Error> {
    let a = v.as_array().ok_or_else(|| Error::bad(at, v, "is not a list of [fraction, value] points", &["[[0, 0], [0.5, 1], [1, 0]]"]))?;
    let mut out: Vec<[f64; 2]> = vec![];
    for (i, p) in a.iter().enumerate() {
        let pa = format!("{at}[{i}]");
        let pair = p.as_array().filter(|x| x.len() == 2).ok_or_else(|| Error::bad(&pa, p, "is not a [fraction, value] point", &["[0.5, 1]"]))?;
        let u = number(&pair[0], &format!("{pa}[0]"), 0.0, 1.0)?;
        let x = number(&pair[1], &format!("{pa}[1]"), lo, hi)?;
        if out.last().is_some_and(|q| q[0] > u) {
            return Err(Error::new("BAD_ARGUMENT", &pa, format!("{u}"), "comes before the point ahead of it (fractions must rise)"));
        }
        out.push([u, x]);
    }
    Ok(out)
}

/// The field tables, as `describe` answers them.
pub fn describe() -> Value {
    let field = |f: &design::F| json!({ "name": f.0, "accepts": [f.1, f.2], "default": if f.3.is_nan() { Value::Null } else { json!(f.3) }, "help": f.4 });
    let common: Vec<Value> = design::COMMON.iter().map(field).collect();
    let designs: serde_json::Map<String, Value> = design::DESIGNS.iter().map(|(n, fs)| (n.to_string(), json!(fs.iter().map(field).collect::<Vec<_>>()))).collect();
    json!({ "common": common, "designs": designs, "lanes": { "whoosh": ["speed", "panPath"] } })
}
