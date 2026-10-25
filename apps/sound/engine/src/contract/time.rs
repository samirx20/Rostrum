//! Times in the contract: seconds, or beats through the tempo map. The engine's job works in samples;
//! this is the only place that turns one into the other.

use super::error::Error;
use super::read::number;
use serde_json::{json, Value};

/// Tempo segments, sorted by beat, the first at beat 0; constant tempo inside a segment, or (`"ramp": true`) a
/// glide to the next segment's bpm, even per beat: with k bpm per beat a beat lasts 60/bpm, so seconds =
/// 60/k·ln(bpm/bpm0) and beat = bpm0/k·(e^(k·seconds/60) − 1), exact (Python's `doc/tempo.py` agrees).
pub struct Tempo {
    /// (start beat, bpm, start seconds, bpm per beat)
    segs: Vec<(f64, f64, f64, f64)>,
    /// The bar map (schedule `meter`), for the performance's accents.
    pub meter: super::meter::Meter,
}

impl Tempo {
    pub fn read(v: Option<&Value>, at: &str) -> Result<(Tempo, Value), Error> {
        let raw: Vec<(f64, f64, bool)> = match v {
            None => vec![(0.0, 120.0, false)],
            Some(v) if v.is_number() => vec![(0.0, number(v, at, 10.0, 400.0)?, false)],
            Some(Value::Array(a)) => a.iter().enumerate().map(|(i, s)| {
                let p = format!("{at}[{i}]");
                let ramp = s.get("ramp").map(|r| r.as_bool().ok_or_else(|| Error::bad(&format!("{p}.ramp"), r, "is not true or false", &["true"]))).transpose()?.unwrap_or(false);
                let mut s = s.clone();
                if let Some(o) = s.as_object_mut() { o.remove("ramp"); }
                let mut o = super::read::Obj::new(&s, p)?;
                let beat = o.num("beat", 0.0, 1e6, None)?;
                let bpm = o.num("bpm", 10.0, 400.0, None)?;
                o.done()?;
                Ok((beat, bpm, ramp))
            }).collect::<Result<_, Error>>()?,
            Some(v) => return Err(Error::bad(at, v, "is not a bpm or a list of tempo segments", &["96", "[{\"beat\": 0, \"bpm\": 96}]"])),
        };
        if raw.first().map(|s| s.0) != Some(0.0) {
            return Err(Error::new("BAD_ARGUMENT", at, "the first segment", "must start at beat 0"));
        }
        if raw.windows(2).any(|w| w[1].0 <= w[0].0) {
            return Err(Error::new("BAD_ARGUMENT", at, "the segments", "must be in beat order"));
        }
        if raw.last().is_some_and(|s| s.2) {
            return Err(Error::new("BAD_ARGUMENT", at, "the last segment", "can't ramp: there is no next tempo to glide to"));
        }
        let mut segs: Vec<(f64, f64, f64, f64)> = vec![];
        for (i, &(beat, bpm, ramp)) in raw.iter().enumerate() {
            let secs = segs.last().map_or(0.0, |&s| Self::secs_in(s, beat));
            let k = if ramp { (raw[i + 1].1 - bpm) / (raw[i + 1].0 - beat) } else { 0.0 };
            segs.push((beat, bpm, secs, k));
        }
        let resolved = json!(raw.iter().map(|&(b, t, r)| if r { json!({ "beat": b, "bpm": t, "ramp": true }) } else { json!({ "beat": b, "bpm": t }) }).collect::<Vec<_>>());
        Ok((Tempo { segs, meter: Default::default() }, resolved))
    }

    fn secs_in((b0, bpm0, s0, k): (f64, f64, f64, f64), beat: f64) -> f64 {
        s0 + if k == 0.0 { (beat - b0) * 60.0 / bpm0 } else { 60.0 / k * (k * (beat - b0) / bpm0).ln_1p() }
    }

    /// Seconds at a beat.
    pub fn seconds(&self, beat: f64) -> f64 {
        Self::secs_in(*self.segs.iter().rev().find(|s| s.0 <= beat).unwrap_or(&self.segs[0]), beat)
    }

    /// The beat at a time (for a length in beats from a time in seconds).
    pub fn beat(&self, secs: f64) -> f64 {
        let &(b0, bpm0, s0, k) = self.segs.iter().rev().find(|s| s.2 <= secs).unwrap_or(&self.segs[0]);
        b0 + if k == 0.0 { (secs - s0) * bpm0 / 60.0 } else { bpm0 / k * (k * (secs - s0) / 60.0).exp_m1() }
    }

    /// A time: seconds, or `{"beat": n}`.
    pub fn time(&self, v: &Value, at: &str) -> Result<f64, Error> {
        self.parse(v, at, "beat", None)
    }

    /// A length from `start`: seconds, or `{"beats": n}`.
    pub fn length(&self, v: &Value, at: &str, start: f64) -> Result<f64, Error> {
        self.parse(v, at, "beats", Some(start))
    }

    fn parse(&self, v: &Value, at: &str, key: &str, from: Option<f64>) -> Result<f64, Error> {
        if v.is_number() {
            return number(v, at, 0.0, 86400.0);
        }
        let example = format!("{{\"{key}\": 4}}");
        let beats = match v.as_object() {
            Some(o) if o.len() == 1 && o.contains_key(key) => number(&o[key], &format!("{at}.{key}"), 0.0, 1e6)?,
            _ => return Err(Error::bad(at, v, &format!("is not seconds or {example}"), &["2.5", &example])),
        };
        Ok(match from {
            None => self.seconds(beats),
            Some(start) => self.seconds(self.beat(start) + beats) - start,
        })
    }
}
