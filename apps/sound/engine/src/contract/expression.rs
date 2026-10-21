//! Note expression and the track's CC-style lanes (ENGINE_CONTRACT.md § Note, § Track expression), read
//! strictly and written as the engine's per-note Expression (instruments/expression.rs): a note's
//! `dynamics` is its shape, `vibrato` and `bend` its own; the track's `dynamics` lane becomes each note's
//! level lane and its `vibrato` lane the mod wheel, cut to the note (seconds into it).

use super::effects;
use super::error::Error;
use super::read::{number, Obj};
use super::time::Tempo;
use crate::instruments::expression::lane_at;
use serde_json::{json, Map, Value};

/// How long after a note's end the lanes still shape it (its release).
const TAIL: f64 = 4.0;

pub struct Lanes {
    dynamics: Option<Vec<[f64; 2]>>,
    vibrato: Option<Vec<[f64; 2]>>,
    rate: f64,
    depth: f64,
}

/// The track's `expression`: lanes in seconds (through the tempo map), rate and depth of the wheel's vibrato.
pub fn lanes(o: &mut Obj, tempo: &Tempo) -> Result<Lanes, Error> {
    let at = o.at("expression");
    let empty = json!({});
    let v = o.raw("expression").unwrap_or(&empty);
    let mut e = Obj::new(v, &at)?;
    let lane = |e: &mut Obj, key: &'static str, hi: f64| -> Result<Option<Vec<[f64; 2]>>, Error> {
        let p = e.raw(key).map(|p| effects::points(p, &e.at(key), 0.0, hi, tempo)).transpose()?;
        e.put(key, p.as_ref().map_or(Value::Null, |p| json!(p)));
        Ok(p)
    };
    let dynamics = lane(&mut e, "dynamics", 2.0)?;
    let vibrato = lane(&mut e, "vibrato", 1.0)?;
    let rate = e.num("vibratoRate", 0.1, 20.0, Some(5.5))?;
    let depth = e.num("vibratoDepth", 0.0, 200.0, Some(25.0))?;
    o.put("expression", Value::Object(e.done()?));
    Ok(Lanes { dynamics, vibrato, rate, depth })
}

/// A note's own expression plus the track's lanes under it; None when it has none.
pub fn note(no: &mut Obj, lanes: &Lanes, at: f64, dur: f64) -> Result<Option<Value>, Error> {
    let mut x = Map::new();
    if let Some(d) = no.raw("dynamics") {
        let pts = pairs(d, &no.at("dynamics"), (0.0, 1.0), (0.0, 2.0))?;
        x.insert("shape".into(), json!(pts));
        no.put("dynamics", json!(pts));
    }
    if let Some(v) = no.raw("vibrato") {
        let mut vo = Obj::new(v, no.at("vibrato"))?;
        let (rate, depth, delay) = (vo.num("rate", 0.1, 20.0, Some(5.5))?, vo.num("depth", 0.0, 200.0, Some(20.0))?, vo.num("delay", 0.0, 10.0, Some(0.2))?);
        no.put("vibrato", Value::Object(vo.done()?));
        x.insert("vibrato".into(), json!({ "rate": rate, "depth": depth, "delay": delay }));
    }
    if let Some(b) = no.raw("bend") {
        let pts = pairs(b, &no.at("bend"), (0.0, 600.0), (-2400.0, 2400.0))?;
        x.insert("bend".into(), json!(pts));
        no.put("bend", json!(pts));
    }
    let span = dur + TAIL;
    if let Some(d) = &lanes.dynamics {
        x.insert("level".into(), json!(slice(d, at, span)));
    }
    if let Some(v) = &lanes.vibrato {
        x.insert("modulation".into(), json!({ "rate": lanes.rate, "depth": lanes.depth, "points": slice(v, at, span) }));
    }
    Ok(if x.is_empty() { None } else { Some(Value::Object(x)) })
}

/// A lane cut to [at, at + span], in seconds from `at` (its value at both ends, its points between).
fn slice(pts: &[[f64; 2]], at: f64, span: f64) -> Vec<[f64; 2]> {
    let mut out = vec![[0.0, lane_at(pts, at)]];
    out.extend(pts.iter().filter(|p| p[0] > at && p[0] < at + span).map(|p| [p[0] - at, p[1]]));
    out.push([span, lane_at(pts, at + span)]);
    out
}

/// `[[x, value], …]`, x ascending inside `xs`, each value inside `vs`.
fn pairs(v: &Value, at: &str, xs: (f64, f64), vs: (f64, f64)) -> Result<Vec<[f64; 2]>, Error> {
    let a = v.as_array().ok_or_else(|| Error::bad(at, v, "is not a list of points", &["[[0, 0.6], [1, 1.0]]"]))?;
    let mut out: Vec<[f64; 2]> = vec![];
    for (i, p) in a.iter().enumerate() {
        let pa = format!("{at}[{i}]");
        let pair = p.as_array().filter(|q| q.len() == 2).ok_or_else(|| Error::bad(&pa, p, "is not a point", &["[x, value]"]))?;
        let (x, y) = (number(&pair[0], &pa, xs.0, xs.1)?, number(&pair[1], &pa, vs.0, vs.1)?);
        if out.last().is_some_and(|l| x < l[0]) {
            return Err(Error::new("BAD_ARGUMENT", &pa, "a point", "is earlier than the one before it (points go in order)"));
        }
        out.push([x, y]);
    }
    Ok(out)
}
