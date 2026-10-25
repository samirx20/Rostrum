//! The bar map the performance accents by (doc/meter.py sends it): stretches of one time signature, each
//! {at: its first beat, bar: a bar's length in beats, beat: a main beat's length in beats} (4/4: bar 4, beat 1;
//! 6/8: bar 3, beat 1.5). Absent: 4/4 throughout.

use super::error::Error;
use super::read::Obj;
use serde_json::{json, Value};

#[derive(Clone, Debug)]
pub struct Meter(Vec<[f64; 3]>);

impl Default for Meter {
    fn default() -> Self { Meter(vec![[0.0, 4.0, 1.0]]) }
}

impl Meter {
    pub fn read(v: Option<&Value>, at: &str) -> Result<(Meter, Value), Error> {
        let Some(v) = v else { return Ok((Meter::default(), json!([{ "at": 0.0, "bar": 4.0, "beat": 1.0 }]))) };
        let a = v.as_array().filter(|a| !a.is_empty()).ok_or_else(|| Error::bad(at, v, "is not a list of time signature stretches", &["[{\"at\": 0, \"bar\": 3, \"beat\": 1}]"]))?;
        let mut segs = vec![];
        for (i, s) in a.iter().enumerate() {
            let mut o = Obj::new(s, format!("{at}[{i}]"))?;
            segs.push([o.num("at", 0.0, 1e6, None)?, o.num("bar", 0.25, 64.0, None)?, o.num("beat", 0.125, 16.0, Some(1.0))?]);
            o.done()?;
        }
        if segs[0][0] != 0.0 || segs.windows(2).any(|w| w[1][0] <= w[0][0]) {
            return Err(Error::new("BAD_ARGUMENT", at, "the stretches", "must start at beat 0 and be in beat order"));
        }
        let resolved = json!(segs.iter().map(|s| json!({ "at": s[0], "bar": s[1], "beat": s[2] })).collect::<Vec<_>>());
        Ok((Meter(segs), resolved))
    }

    /// Some(true) on a bar's downbeat, Some(false) on its other main beats, None between them.
    pub fn accent(&self, beat: f64) -> Option<bool> {
        let [at, bar, main] = *self.0.iter().rev().find(|s| s[0] <= beat + 1e-9).unwrap_or(&self.0[0]);
        let pos = (beat - at).rem_euclid(bar);
        let near = |x: f64, step: f64| { let c = x / step; (c - c.round()).abs() * step < 0.06 };
        if near(pos, bar) { Some(true) } else if near(pos, main) { Some(false) } else { None }
    }
}
