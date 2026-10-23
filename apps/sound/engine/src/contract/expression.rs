//! Note expression and the track's CC-style lanes (ENGINE_CONTRACT.md § Note, § Track expression), read
//! strictly and written as the engine's per-note Expression (instruments/expression.rs): a note's
//! `dynamics` is its shape, `vibrato` and `bend` its own; the track's `dynamics` lane becomes each note's
//! level lane, its `vibrato` lane the mod wheel and its `bend` lane the pitch wheel (× `bendRange` semitones,
//! added to the note's own bend), cut to the note (seconds into it). Its `sustain` lane is the pedal: a note
//! released while the pedal is down (0.5 or more) rings on until it lifts (`held`).

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
    sustain: Option<Vec<[f64; 2]>>,
    bend: Option<Vec<[f64; 2]>>,
    rate: f64,
    depth: f64,
    bend_range: f64,
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
    let sustain = lane(&mut e, "sustain", 1.0)?;
    let bend = e.raw("bend").map(|p| effects::points(p, &e.at("bend"), -1.0, 1.0, tempo)).transpose()?;
    e.put("bend", bend.as_ref().map_or(Value::Null, |p| json!(p)));
    let rate = e.num("vibratoRate", 0.1, 20.0, Some(5.5))?;
    let depth = e.num("vibratoDepth", 0.0, 200.0, Some(25.0))?;
    let bend_range = e.num("bendRange", 0.0, 24.0, Some(2.0))?;
    o.put("expression", Value::Object(e.done()?));
    Ok(Lanes { dynamics, vibrato, sustain, bend, rate, depth, bend_range })
}

/// How long a note sounds with the pedal: its own `dur`, or, when the pedal is down as it is released, until the
/// pedal next lifts (a pedal never lifted lets go at its lane's last point).
pub fn held(lanes: &Lanes, at: f64, dur: f64) -> f64 {
    let Some(p) = lanes.sustain.as_deref().filter(|p| !p.is_empty()) else { return dur };
    let end = at + dur;
    if lane_at(p, end) < 0.5 {
        return dur;
    }
    let mut prev = [end, lane_at(p, end)];
    for &q in p.iter().filter(|q| q[0] > end) {
        if q[1] < 0.5 {   // where the straight line between prev and q crosses 0.5
            let u = if prev[1] > q[1] { (prev[1] - 0.5) / (prev[1] - q[1]) } else { 1.0 };
            return prev[0] + (q[0] - prev[0]) * u - at;
        }
        prev = q;
    }
    prev[0].max(end) - at
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
    let span = dur + TAIL;
    let own = no.raw("bend").map(|b| pairs(b, &no.at("bend"), (0.0, 600.0), (-2400.0, 2400.0))).transpose()?;
    if let Some(pts) = &own {
        no.put("bend", json!(pts));
    }
    let wheel = lanes.bend.as_ref().map(|b| slice(b, at, span).iter().map(|p| [p[0], p[1] * lanes.bend_range * 100.0]).collect::<Vec<_>>());
    if let Some(b) = add(own, wheel) {
        x.insert("bend".into(), json!(b));
    }
    if let Some(d) = &lanes.dynamics {
        x.insert("level".into(), json!(slice(d, at, span)));
    }
    if let Some(v) = &lanes.vibrato {
        x.insert("modulation".into(), json!({ "rate": lanes.rate, "depth": lanes.depth, "points": slice(v, at, span) }));
    }
    Ok(if x.is_empty() { None } else { Some(Value::Object(x)) })
}

/// Two bends played together (both straight lines between points): their sum at every point of either.
fn add(a: Option<Vec<[f64; 2]>>, b: Option<Vec<[f64; 2]>>) -> Option<Vec<[f64; 2]>> {
    let (a, b) = match (a, b) {
        (Some(a), Some(b)) => (a, b),
        (a, b) => return a.or(b),
    };
    let mut xs: Vec<f64> = a.iter().chain(&b).map(|p| p[0]).collect();
    xs.sort_by(f64::total_cmp);
    xs.dedup();
    Some(xs.into_iter().map(|t| [t, lane_at(&a, t) + lane_at(&b, t)]).collect())
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

#[cfg(test)]
mod tests {
    use super::*;

    fn lanes(sustain: Option<Vec<[f64; 2]>>) -> Lanes {
        Lanes { dynamics: None, vibrato: None, sustain, bend: None, rate: 5.5, depth: 25.0, bend_range: 2.0 }
    }

    #[test]
    fn the_pedal_holds_a_released_note_and_an_old_song_plays_as_before() {
        assert_eq!(held(&lanes(None), 1.0, 0.5), 0.5);                       // no pedal lane: as written
        let pedal = vec![[0.0, 0.0], [1.2, 0.0], [1.2, 1.0], [3.0, 1.0], [3.0, 0.0]];
        assert_eq!(held(&lanes(Some(pedal.clone())), 0.0, 0.5), 0.5);        // released before the pedal goes down
        assert_eq!(held(&lanes(Some(pedal.clone())), 1.0, 0.5), 2.0);        // down at 1.5: rings to the lift at 3.0
        let never = vec![[0.0, 1.0], [4.0, 1.0]];
        assert_eq!(held(&lanes(Some(never)), 1.0, 0.5), 3.0);                // never lifted: lets go at its last point
    }

    #[test]
    fn a_bend_lane_adds_to_the_notes_own_bend() {
        let sum = add(Some(vec![[0.0, -100.0], [0.1, 0.0]]), Some(vec![[0.0, 0.0], [0.2, 200.0]])).unwrap();
        assert_eq!(sum, vec![[0.0, -100.0], [0.1, 100.0], [0.2, 200.0]]);
    }
}
