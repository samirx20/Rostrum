//! The strict reader every part of the contract reads through: each object is read field by field,
//! each value checked (type, range, accepted names), its default written into the resolved copy, and
//! any field left unread is an error. So "unknown names fail loudly" and "defaults are filled by the
//! engine" live in one place, and `check` returns exactly what the engine will do.

use super::error::Error;
use serde_json::{Map, Value};

/// One JSON object being read at `path` (e.g. `tracks[2].notes[5]`).
pub struct Obj<'a> {
    pub path: String,
    src: &'a Map<String, Value>,
    seen: Vec<&'static str>,
    /// What was read, with defaults filled in.
    pub out: Map<String, Value>,
}

impl<'a> Obj<'a> {
    pub fn new(v: &'a Value, path: impl Into<String>) -> Result<Obj<'a>, Error> {
        let path = path.into();
        match v.as_object() {
            Some(src) => Ok(Obj { path, src, seen: vec![], out: Map::new() }),
            None => Err(Error::bad(&path, v, "is not an object", &["{ … }"])),
        }
    }

    pub fn at(&self, key: &str) -> String {
        if self.path.is_empty() { key.to_string() } else { format!("{}.{key}", self.path) }
    }

    /// The raw value of `key`, marking it read (None when absent or null).
    pub fn raw(&mut self, key: &'static str) -> Option<&'a Value> {
        self.seen.push(key);
        self.src.get(key).filter(|v| !v.is_null())
    }

    pub fn has(&self, key: &str) -> bool {
        self.src.get(key).is_some_and(|v| !v.is_null())
    }

    fn need(&mut self, key: &'static str) -> Result<&'a Value, Error> {
        let at = self.at(key);
        self.raw(key).ok_or_else(|| Error::missing(&at))
    }

    pub fn put(&mut self, key: &str, v: Value) {
        self.out.insert(key.to_string(), v);
    }

    /// A number in `lo ..= hi` (out of range is an error, never a clamp), `default` when absent.
    pub fn num(&mut self, key: &'static str, lo: f64, hi: f64, default: Option<f64>) -> Result<f64, Error> {
        let at = self.at(key);
        let x = match (self.raw(key), default) {
            (None, Some(d)) => d,
            (None, None) => return Err(Error::missing(&at)),
            (Some(v), _) => number(v, &at, lo, hi)?,
        };
        self.put(key, x.into());
        Ok(x)
    }

    pub fn opt_num(&mut self, key: &'static str, lo: f64, hi: f64) -> Result<Option<f64>, Error> {
        let at = self.at(key);
        let x = self.raw(key).map(|v| number(v, &at, lo, hi)).transpose()?;
        self.put(key, x.map_or(Value::Null, Value::from));
        Ok(x)
    }

    pub fn bool(&mut self, key: &'static str, default: bool) -> Result<bool, Error> {
        let at = self.at(key);
        let b = match self.raw(key) {
            None => default,
            Some(Value::Bool(b)) => *b,
            Some(v) => return Err(Error::bad(&at, v, "is not true or false", &["true", "false"])),
        };
        self.put(key, b.into());
        Ok(b)
    }

    pub fn str(&mut self, key: &'static str, default: Option<&str>) -> Result<String, Error> {
        let at = self.at(key);
        let s = match (self.raw(key), default) {
            (None, Some(d)) => d.to_string(),
            (None, None) => return Err(Error::missing(&at)),
            (Some(Value::String(s)), _) => s.clone(),
            (Some(v), _) => return Err(Error::bad(&at, v, "is not text", &[])),
        };
        self.put(key, s.clone().into());
        Ok(s)
    }

    /// One of `names` (a closed list).
    pub fn name(&mut self, key: &'static str, names: &[&str], default: Option<&str>) -> Result<String, Error> {
        let s = self.str(key, default)?;
        one_of(&s, &self.at(key), names)?;
        Ok(s)
    }

    /// A list (absent: empty), each element read by `each` at `key[i]`.
    pub fn list<T>(&mut self, key: &'static str, mut each: impl FnMut(&'a Value, String) -> Result<T, Error>) -> Result<Vec<T>, Error> {
        let at = self.at(key);
        match self.raw(key) {
            None => Ok(vec![]),
            Some(Value::Array(a)) => a.iter().enumerate().map(|(i, v)| each(v, format!("{at}[{i}]"))).collect(),
            Some(v) => Err(Error::bad(&at, v, "is not a list", &["[ … ]"])),
        }
    }

    pub fn required(&mut self, key: &'static str) -> Result<&'a Value, Error> {
        self.need(key)
    }

    /// Ends the read: a field nobody asked for is an unknown name.
    pub fn done(self) -> Result<Map<String, Value>, Error> {
        if let Some(k) = self.src.keys().find(|k| !self.seen.contains(&k.as_str())) {
            let mut known: Vec<&str> = self.seen.clone();
            known.sort();
            known.dedup();
            return Err(Error::unknown(&self.at(k), k, &known));
        }
        Ok(self.out)
    }
}

pub fn number(v: &Value, at: &str, lo: f64, hi: f64) -> Result<f64, Error> {
    let Some(x) = v.as_f64() else {
        return Err(Error::bad(at, v, "is not a number", &[]));
    };
    if !(lo..=hi).contains(&x) {
        return Err(Error::bad(at, v, &format!("is outside {lo} … {hi}"), &[]));
    }
    Ok(x)
}

pub fn one_of(s: &str, at: &str, names: &[&str]) -> Result<(), Error> {
    if names.contains(&s) { Ok(()) } else { Err(Error::unknown(at, s, names)) }
}
