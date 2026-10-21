//! Note names: "C4" = MIDI 60, "F#3", "Bb2", "C#-1", or a MIDI number; a list is a chord.

use super::error::Error;
use super::read::number;
use serde_json::Value;

const STEPS: [(char, i32); 7] = [('C', 0), ('D', 2), ('E', 4), ('F', 5), ('G', 7), ('A', 9), ('B', 11)];

pub fn freq(key: f64) -> f64 {
    440.0 * 2f64.powf((key - 69.0) / 12.0)
}

/// MIDI keys of one pitch or a chord.
pub fn keys(v: &Value, at: &str) -> Result<Vec<f64>, Error> {
    match v {
        Value::Array(a) if !a.is_empty() => a.iter().enumerate().map(|(i, p)| key(p, &format!("{at}[{i}]"))).collect(),
        v => Ok(vec![key(v, at)?]),
    }
}

pub fn key(v: &Value, at: &str) -> Result<f64, Error> {
    if v.is_number() {
        return number(v, at, 0.0, 127.0);
    }
    let bad = || Error::bad(at, v, "is not a note name or MIDI number", &["\"D3\"", "\"F#4\"", "\"Bb2\"", "62"]);
    let s = v.as_str().ok_or_else(bad)?.trim();
    let mut chars = s.chars();
    let letter = chars.next().map(|c| c.to_ascii_uppercase()).ok_or_else(bad)?;
    let step = STEPS.iter().find(|(c, _)| *c == letter).map(|(_, n)| *n).ok_or_else(bad)?;
    let rest: String = chars.collect();
    let acc_len = rest.chars().take_while(|c| *c == '#' || *c == 'b').count();
    let (acc, octave) = rest.split_at(acc_len);
    let octave: i32 = octave.parse().map_err(|_| bad())?;
    let shift = acc.matches('#').count() as i32 - acc.matches('b').count() as i32;
    let k = (octave + 1) * 12 + step + shift;
    if !(0..=127).contains(&k) {
        return Err(Error::bad(at, v, "is outside MIDI 0 … 127 (C-1 … G9)", &[]));
    }
    Ok(k as f64)
}

pub fn name(key: u8) -> String {
    const N: [&str; 12] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
    format!("{}{}", N[key as usize % 12], key as i32 / 12 - 1)
}
