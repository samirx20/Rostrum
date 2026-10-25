//! The performance layer (Sam, 2026-10-15; the experiment's perform.ts): a track's notes and hits are played,
//! not just sequenced: micro-timing, a lean, swing, velocity variety, a dynamics curve, accents on the beat,
//! legato or staccato, vibrato on held notes, the pedal, strums that vary string to string. On by default
//! with the instrument family's values (names.rs PERFORM_DEFAULTS); a track's `perform` object merges over
//! them and `false` plays exactly as written. Seeded by the track id (and `seed`): the same every render.
//! It rewrites the voices the contract hands the engine, so the render and everything that plays it hear one thing.

use super::effects;
use super::error::Error;
use super::names::perform_defaults;
use super::read::Obj;
use super::time::Tempo;
use crate::instruments::expression::lane_at;
use serde_json::{json, Value};

const ARTICULATIONS: &[&str] = &["legato", "staccato", "normal"];

pub struct Perform {
    seed: f64,
    timing: f64,
    lean: f64,
    swing: f64,
    swing_grid: f64,
    velocity: f64,
    dynamics: Vec<[f64; 2]>,
    accent: f64,
    articulation: String,
    /// rate Hz, depth cents, delay s.
    vibrato: Option<[f64; 3]>,
    /// None: off; an empty list: the whole song; else [from, to] seconds.
    pedal: Option<Vec<[f64; 2]>>,
    pub strum: f64,
}

/// The track's `perform` over its family's defaults (`family` "": no instrument, nothing performed).
pub fn read(o: &mut Obj, family: &str, tempo: &Tempo) -> Result<Option<Perform>, Error> {
    let at = o.at("perform");
    let raw = o.raw("perform");
    let empty = json!({});
    let src = match raw {
        None | Some(Value::Bool(true)) => &empty,
        Some(Value::Bool(false)) => { o.put("perform", json!(false)); return Ok(None) }
        Some(v @ Value::Object(_)) => v,
        Some(v) => return Err(Error::bad(&at, v, "is not true, false or an object of performance fields", &["true", "false", "{\"timing\": 8, \"swing\": 0.3}"])),
    };
    let d = perform_defaults(family);
    let def = |k: &str| Some(d.get(k).and_then(Value::as_f64).unwrap_or(0.0));
    let mut p = Obj::new(src, at)?;
    let seed = p.num("seed", -1e9, 1e9, Some(0.0))?;
    let timing = p.num("timing", 0.0, 60.0, def("timing"))?;
    let lean = p.num("lean", -60.0, 60.0, Some(0.0))?;
    let swing = p.num("swing", 0.0, 1.0, Some(0.0))?;
    let swing_grid = p.num("swingGrid", 0.125, 1.0, Some(0.5))?;
    let velocity = p.num("velocity", 0.0, 0.5, def("velocity"))?;
    let accent = p.num("accent", 0.0, 0.5, def("accent"))?;
    let strum = p.num("strum", 0.0, 1.0, def("strum"))?;
    let articulation = p.name("articulation", ARTICULATIONS, Some(d.get("articulation").and_then(Value::as_str).unwrap_or("normal")))?;
    let dynamics = p.raw("dynamics").map(|v| effects::points(v, &p.at("dynamics"), 0.0, 2.0, tempo)).transpose()?.unwrap_or_default();
    p.put("dynamics", if dynamics.is_empty() { Value::Null } else { json!(dynamics) });
    let vibrato = match p.raw("vibrato") {
        None | Some(Value::Bool(false)) => { p.put("vibrato", json!(false)); None }
        Some(v) => {
            let mut vo = Obj::new(v, p.at("vibrato"))?;
            let x = [vo.num("rateHz", 0.1, 20.0, None)?, vo.num("depthCents", 0.0, 200.0, None)?, vo.num("delaySec", 0.0, 10.0, Some(0.2))?];
            p.put("vibrato", Value::Object(vo.done()?));
            Some(x)
        }
    };
    let pa = p.at("pedal");
    let pedal = match p.raw("pedal") {
        None | Some(Value::Bool(false)) => None,
        Some(Value::Bool(true)) => Some(vec![]),
        Some(v) => Some(ranges(v, &pa, tempo)?),
    };
    p.put("pedal", match &pedal { None => json!(false), Some(r) if r.is_empty() => json!(true), Some(r) => json!(r) });
    o.put("perform", Value::Object(p.done()?));
    Ok(if family.is_empty() { None } else { Some(Perform { seed, timing, lean, swing, swing_grid, velocity, dynamics, accent, articulation, vibrato, pedal, strum }) })
}

fn ranges(v: &Value, at: &str, tempo: &Tempo) -> Result<Vec<[f64; 2]>, Error> {
    let bad = || Error::bad(at, v, "is not true, false or a list of [from, to] times", &["true", "[[0, {\"beat\": 8}]]"]);
    let a = v.as_array().filter(|a| !a.is_empty()).ok_or_else(bad)?;
    a.iter().enumerate().map(|(i, r)| {
        let pair = r.as_array().filter(|p| p.len() == 2).ok_or_else(bad)?;
        let (from, to) = (tempo.time(&pair[0], &format!("{at}[{i}][0]"))?, tempo.time(&pair[1], &format!("{at}[{i}][1]"))?);
        if from >= to { return Err(Error::new("BAD_ARGUMENT", &format!("{at}[{i}]"), "this range", "ends before it starts")) }
        Ok([from, to])
    }).collect()
}

/// FNV-1a over the text (the experiment's hashSeed, so a seed means the same there and here).
fn hash(s: &str) -> u32 {
    s.encode_utf16().fold(0x811c9dc5u32, |h, c| (h ^ c as u32).wrapping_mul(0x01000193))
}

/// A number in −1 … 1 fixed by the seed and key.
fn jitter(seed: u32, key: &str) -> f64 {
    (hash(&format!("{seed}:{key}")) % 20001) as f64 / 10000.0 - 1.0
}

/// A chord's tones one after another (`ms` apart, low to high; negative: from the top), each held to the
/// chord's end; performed (`amount` > 0) each gap varies and each string is a little softer.
pub fn strum(voice: Value, ms: f64, amount: f64, key: &str, sr: f64) -> Vec<Value> {
    let mut freqs: Vec<f64> = voice["freqs"].as_array().map(|a| a.iter().filter_map(Value::as_f64).collect()).unwrap_or_default();
    if freqs.len() < 2 || ms == 0.0 {
        return vec![voice];
    }
    freqs.sort_by(|a, b| if ms > 0.0 { a.total_cmp(b) } else { b.total_cmp(a) });
    let (seed, spacing) = (hash(key), ms.abs() / 1000.0);
    let (start, dur, vel) = (voice["startIdx"].as_u64().unwrap_or(0), voice["duration"].as_f64().unwrap_or(0.0), voice["velocity"].as_f64().unwrap_or(0.8));
    let mut late = 0.0;
    let mut out = vec![];
    for (k, f) in freqs.into_iter().enumerate() {
        if k > 0 {
            late += if amount > 0.0 { spacing * (1.0 + amount * 0.45 * jitter(seed, &format!("s{k}"))) } else { spacing };
        }
        if late >= dur { break }
        let mut v = voice.clone();
        v["freqs"] = json!([f]);
        v["startIdx"] = json!(start + (late * sr).round() as u64);
        v["duration"] = json!(dur - late);
        if amount > 0.0 && k > 0 { v["velocity"] = json!(vel * (1.0 - 0.05 * amount).powi(k as i32)) }
        out.push(v);
    }
    out
}

/// Where the voices are played: the track id (the seed), the rate, the tempo, the song's end (seconds; the
/// pedal's `true`) and the last sample a voice may start on (None: no limit given).
pub struct Ctx<'a> {
    pub key: &'a str,
    pub sr: f64,
    pub tempo: &'a Tempo,
    pub end: f64,
    pub last: Option<u64>,
}

/// The voices as performed, in place. `own_art[i]`: voice i's note named its own articulation (the
/// performance's legato / staccato leave it alone).
pub fn apply(voices: &mut [Value], own_art: &[bool], p: &Perform, x: &Ctx) {
    let seed = hash(&format!("{}:{}", x.key, if p.seed.fract() == 0.0 { format!("{}", p.seed as i64) } else { p.seed.to_string() }));
    let mut starts: Vec<u64> = voices.iter().filter_map(|v| v["startIdx"].as_u64()).collect();
    starts.sort_unstable();
    starts.dedup();
    for (i, v) in voices.iter_mut().enumerate() {
        let start = v["startIdx"].as_u64().unwrap_or(0);
        let t = start as f64 / x.sr;
        let beat = x.tempo.beat(t);
        let spb = x.tempo.seconds(beat + 1.0) - x.tempo.seconds(beat);
        let mut shift = p.lean / 1000.0 + p.timing / 1000.0 * jitter(seed, &format!("{i}:t"));
        let cell = beat / p.swing_grid;
        if p.swing > 0.0 && (cell - cell.round()).abs() < 0.08 && (cell.round() as i64) % 2 != 0 {
            shift += p.swing * p.swing_grid / 3.0 * spb;
        }
        let mut vel = v["velocity"].as_f64().unwrap_or(0.8) * (1.0 + p.velocity * jitter(seed, &format!("{i}:v")));
        if !p.dynamics.is_empty() { vel *= lane_at(&p.dynamics, t) }
        if let (true, Some(down)) = (p.accent > 0.0, x.tempo.meter.accent(beat)) {
            vel *= 1.0 + if down { p.accent } else { p.accent / 2.0 };
        }
        if let Some(mut dur) = v["duration"].as_f64() {
            let art = if own_art.get(i).copied().unwrap_or(false) { "normal" } else { p.articulation.as_str() };
            let next = starts.iter().find(|&&s| s > start);
            if let (Some(&n), "legato") = (next, art) {
                let gap = (n - start) as f64 / x.sr;
                if gap - dur < 0.15 { dur = dur.max(gap + 0.03) }
            }
            if art == "staccato" { dur = (dur * 0.5).min(0.18) }
            let held = p.pedal.as_ref().and_then(|r| if r.is_empty() { Some([0.0, x.end]) } else { r.iter().copied().find(|[a, b]| t >= *a && t < *b) });
            if let Some([_, b]) = held.filter(|[a, b]| t >= *a && t < *b) { dur = dur.max(b - t) }
            vibrato(v, p, seed, i, dur);
            v["duration"] = json!(dur);
        }
        let moved = (start as f64 + (shift * x.sr).round()).max(0.0) as u64;
        v["startIdx"] = json!(x.last.map_or(moved, |l| moved.min(l)));
        v["velocity"] = json!(vel.clamp(0.02, 1.0));
    }
}

/// A player's vibrato on a held note (0.3 s or more) that has none of its own (nor a mod wheel); never on a plugin.
fn vibrato(v: &mut Value, p: &Perform, seed: u32, i: usize, dur: f64) {
    let Some([rate, depth, delay]) = p.vibrato else { return };
    let e = &v["expression"];
    if dur < 0.3 || v["instrument"] == "plugin" || !e["vibrato"].is_null() || !e["modulation"].is_null() {
        return;
    }
    let vib = json!({ "rate": rate * (1.0 + 0.04 * jitter(seed, &format!("{i}:r"))), "depth": depth * (1.0 + 0.15 * jitter(seed, &format!("{i}:d"))),
                      "delay": (delay * (1.0 + 0.2 * jitter(seed, &format!("{i}:o")))).min(dur * 0.5) });
    if v["expression"].is_object() { v["expression"]["vibrato"] = vib } else { v["expression"] = json!({ "vibrato": vib }) }
}
