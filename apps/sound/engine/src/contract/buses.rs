//! Buses and sends (added 2026-10-21, P5): the schedule's `buses` (a fader, pan, inserts and lanes on the
//! sum of what feeds it, out to the master or a parent bus) and a track's routing (`output`, `sends`),
//! written as the engine's job buses (mix/buses.rs), which name buses by index.

use super::error::Error;
use super::read::Obj;
use super::time::Tempo;
use super::{effects, track};
use serde_json::{json, Value};

/// Every bus id, checked (pattern, unique, not a track's id), before anything is read.
pub fn ids(v: Option<&Value>, at: &str, tracks: &[String]) -> Result<Vec<String>, Error> {
    let Some(v) = v else { return Ok(vec![]) };
    let out = track::ids(v, at, "bus")?;
    if let Some((i, id)) = out.iter().enumerate().find(|(_, id)| tracks.contains(id)) {
        return Err(Error::new("BAD_ARGUMENT", &format!("{at}[{i}].id"), format!("\"{id}\""), "is a track's id too; buses and tracks need different ids"));
    }
    Ok(out)
}

/// The buses: (resolved, job), every `output` checked to name a bus and never loop back.
pub fn read(o: &mut Obj, tempo: &Tempo, ids: &[String]) -> Result<(Vec<Value>, Vec<Value>), Error> {
    let mut outputs: Vec<Option<usize>> = vec![];
    let read: Vec<(Value, Value)> = o.list("buses", |b, p| {
        let mut bo = Obj::new(b, p)?;
        let id = bo.str("id", None)?;
        let volume = bo.num("volume", 0.0, 4.0, Some(1.0))?;
        let pan = bo.num("pan", -1.0, 1.0, Some(0.0))?;
        let mute = bo.bool("mute", false)?;
        let fx_at = bo.at("effects");
        let fx = effects::list(bo.raw("effects"), &fx_at, tempo)?;
        bo.put("effects", json!(fx));
        let auto = track::automation(&mut bo, tempo, true)?;
        let output = output(&mut bo, ids)?;
        outputs.push(output);
        let job = json!({ "name": id, "volume": volume, "pan": pan, "effects": effects::job(&fx, 0.0), "automation": auto, "output": output, "muted": mute });
        Ok((Value::Object(bo.done()?), job))
    })?;
    for start in 0..outputs.len() {
        let (mut at, mut path) = (start, vec![start]);
        while let Some(next) = outputs[at] {
            path.push(next);
            if next == start {
                let names: Vec<&str> = path.iter().map(|&k| ids[k].as_str()).collect();
                return Err(Error::new("BAD_ARGUMENT", &format!("{}[{start}].output", o.at("buses")), format!("\"{}\"", ids[start]), format!("routes back into itself: {}", names.join(" → "))));
            }
            if path.len() > outputs.len() + 1 {
                break; // a loop further on; reported when its own bus is the start
            }
            at = next;
        }
    }
    Ok(read.into_iter().unzip())
}

/// `output`: a bus id (its index), absent = the master.
fn output(o: &mut Obj, ids: &[String]) -> Result<Option<usize>, Error> {
    let at = o.at("output");
    let Some(v) = o.raw("output") else { return Ok(None) };
    let k = bus(v, &at, ids)?;
    o.put("output", json!(ids[k]));
    Ok(Some(k))
}

fn bus(v: &Value, at: &str, ids: &[String]) -> Result<usize, Error> {
    let name = v.as_str().ok_or_else(|| Error::bad(at, v, "is not a bus id", &[]))?;
    if ids.is_empty() {
        return Err(Error::new("BAD_ARGUMENT", at, format!("\"{name}\""), "names a bus, but the schedule has no buses").hint("Add it to the schedule's \"buses\"."));
    }
    ids.iter().position(|i| i == name).ok_or_else(|| Error::unknown(at, name, &ids.iter().map(String::as_str).collect::<Vec<_>>()))
}

/// A track's routing: its `output` (bus index) and `sends` (job form: bus index, level number or lane, pre).
pub fn route(o: &mut Obj, tempo: &Tempo, ids: &[String]) -> Result<(Option<usize>, Vec<Value>), Error> {
    let out = output(o, ids)?;
    let sends = o.list("sends", |s, p| {
        let mut so = Obj::new(s, p)?;
        let ba = so.at("bus");
        let k = bus(so.required("bus")?, &ba, ids)?;
        so.put("bus", json!(ids[k]));
        let la = so.at("level");
        let level = match so.raw("level") {
            None => json!(1.0),
            Some(v) if v.is_number() => json!(super::read::number(v, &la, 0.0, 4.0)?),
            Some(v) => json!(effects::points(v, &la, 0.0, 4.0, tempo)?),
        };
        so.put("level", level.clone());
        let pre = so.bool("pre", false)?;
        if out == Some(k) {
            return Err(Error::new("BAD_ARGUMENT", &so.at("bus"), format!("\"{}\"", ids[k]), "is already this track's output; a send to it would play the track twice"));
        }
        Ok((Value::Object(so.done()?), json!({ "bus": k, "level": level, "pre": pre })))
    })?;
    let (resolved, job): (Vec<Value>, Vec<Value>) = sends.into_iter().unzip();
    o.put("sends", json!(resolved));
    Ok((out, job))
}
