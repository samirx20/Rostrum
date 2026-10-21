//! Insert effects: read against names.rs EFFECTS (closed list of types and fields, defaults filled), written
//! as the engine's job form (schedule/effect.rs). Envelope times go through the tempo map.

use super::error::Error;
use super::names::{self, Def, Field, Kind};
use super::read::{number, one_of, Obj};
use super::time::Tempo;
use serde_json::{json, Map, Value};

/// A list of effects at `at`; each comes back with every default filled (it is also the job's form).
pub fn list(v: Option<&Value>, at: &str, tempo: &Tempo) -> Result<Vec<Value>, Error> {
    match v {
        None => Ok(vec![]),
        Some(Value::Array(a)) => a.iter().enumerate().map(|(i, e)| effect(e, &format!("{at}[{i}]"), tempo)).collect(),
        Some(v) => Err(Error::bad(at, v, "is not a list of effects", &["[{\"type\": \"eq\", …}]"])),
    }
}

fn effect(v: &Value, at: &str, tempo: &Tempo) -> Result<Value, Error> {
    let mut o = Obj::new(v, at)?;
    let kind = o.name("type", &names::effect_names(), None)?;
    let fields = names::EFFECTS.iter().find(|(n, _)| *n == kind).map(|(_, f)| *f).unwrap_or(&[]);
    if kind == "eq" {
        let tempo_ref = tempo;
        let bands = o.list("bands", |b, p| fields_of(b, &p, names::EQ_BAND, tempo_ref).map(Value::Object))?;
        if bands.is_empty() {
            return Err(Error::new("BAD_ARGUMENT", &o.at("bands"), "bands", "needs at least one band"));
        }
        o.put("bands", Value::Array(bands));
    } else {
        for f in fields {
            let x = field(&mut o, f, tempo)?;
            o.put(f.0, x);
        }
    }
    let out = o.done()?;
    if kind == "reverb" && !out["space"].as_str().unwrap_or("").starts_with("freeverb.") {
        if let Some(k) = ["decay", "damping", "size"].into_iter().find(|k| !out[*k].is_null()) {
            return Err(Error::new("BAD_ARGUMENT", &format!("{at}.{k}"), k, "only applies to the freeverb.* spaces").hint("Use space \"freeverb.hall\" (or room / cathedral), or leave it out."));
        }
    }
    Ok(Value::Object(out))
}

/// An object made only of `fields` (an EQ band).
fn fields_of(v: &Value, at: &str, fields: &[Field], tempo: &Tempo) -> Result<Map<String, Value>, Error> {
    let mut o = Obj::new(v, at)?;
    for f in fields {
        let x = field(&mut o, f, tempo)?;
        o.put(f.0, x);
    }
    o.done()
}

fn field(o: &mut Obj, f: &Field, tempo: &Tempo) -> Result<Value, Error> {
    let at = o.at(f.0);
    let Some(v) = o.raw(f.0) else {
        return match f.2 {
            Def::N(x) if matches!(f.1, Kind::Int(..)) => Ok(json!(x as i64)),
            Def::N(x) => Ok(json!(x)),
            Def::B(b) => Ok(json!(b)),
            Def::S(s) => Ok(json!(s)),
            Def::None if matches!(f.1, Kind::OptNum(..)) => Ok(Value::Null),
            Def::None => Err(Error::missing(&at)),
        };
    };
    match f.1 {
        Kind::Num(lo, hi) | Kind::OptNum(lo, hi) => Ok(json!(number(v, &at, lo, hi)?)),
        Kind::Int(lo, hi) => {
            let x = number(v, &at, lo, hi)?;
            if x.fract() != 0.0 {
                return Err(Error::bad(&at, v, "is not a whole number", &[]));
            }
            Ok(json!(x as i64))
        }
        Kind::Bool => v.as_bool().map(Value::from).ok_or_else(|| Error::bad(&at, v, "is not true or false", &["true", "false"])),
        Kind::Name(names) => {
            let s = v.as_str().ok_or_else(|| Error::bad(&at, v, "is not text", names))?;
            one_of(s, &at, names)?;
            Ok(json!(s))
        }
        Kind::Env(lo, hi) => envelope(v, &at, lo, hi, tempo),
    }
}

/// A number, or [[time, value], …] in time order.
pub fn envelope(v: &Value, at: &str, lo: f64, hi: f64, tempo: &Tempo) -> Result<Value, Error> {
    if v.is_number() {
        return Ok(json!(number(v, at, lo, hi)?));
    }
    let pts = points(v, at, lo, hi, tempo)?;
    Ok(json!(pts))
}

/// Points [[time, value], …], times through the tempo map, in time order.
pub fn points(v: &Value, at: &str, lo: f64, hi: f64, tempo: &Tempo) -> Result<Vec<[f64; 2]>, Error> {
    let Some(a) = v.as_array().filter(|a| !a.is_empty()) else {
        return Err(Error::bad(at, v, "is not a number or a list of [time, value] points", &["0.5", "[[0, 0.2], [4, 0.8]]"]));
    };
    let mut out = Vec::with_capacity(a.len());
    for (i, p) in a.iter().enumerate() {
        let pa = format!("{at}[{i}]");
        let pair = p.as_array().filter(|p| p.len() == 2).ok_or_else(|| Error::bad(&pa, p, "is not a [time, value] pair", &["[2.0, 0.5]"]))?;
        let t = tempo.time(&pair[0], &format!("{pa}[0]"))?;
        let x = number(&pair[1], &format!("{pa}[1]"), lo, hi)?;
        if out.last().is_some_and(|l: &[f64; 2]| l[0] > t) {
            return Err(Error::new("BAD_ARGUMENT", &pa, "this point", "is earlier than the one before; points must be in time order"));
        }
        out.push([t, x]);
    }
    Ok(out)
}
