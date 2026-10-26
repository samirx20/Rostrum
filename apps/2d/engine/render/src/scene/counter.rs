//! A text that counts (ENGINE_CONTRACT.md § 4 › Counter; fields.py `COUNTER`): with `counter` on, the text shown is
//! `countPrefix`, then `count` at this time (keyed like any number) written with `countDecimals` places, at least
//! `countDigits` digits (zeros in front) and the thousands mark `countSeparator`, then `countSuffix`; its `body` is not
//! shown. eval.rs writes the shown text into `body` for every reader of a text's fields (the stage, letter by letter,
//! `measure`, motion-blur sub-frames), so the canvas, the look tools and the export show the same number.

use serde_json::{Map, Value};

/// The thousands marks (fields.py `SEPARATORS`). The decimal mark is "." except with "period", where it is ",".
pub const SEPARATORS: &[&str] = &["comma", "period", "space", "none"];

/// The whole-number fields of a counter and their ranges (fields.py `countDecimals`, `countDigits`).
const WHOLE: [(&str, f64, f64); 2] = [("countDecimals", 0.0, 6.0), ("countDigits", 1.0, 15.0)];

/// Refuses, at load, a counting text whose decimals or digits the number can't be written with.
pub fn check(id: &str, props: &Map<String, Value>) -> Result<(), String> {
    if props.get("counter").and_then(Value::as_bool) != Some(true) {
        return Ok(());
    }
    for (f, lo, hi) in WHOLE {
        let d = props.get(f).and_then(Value::as_f64).unwrap_or(lo);
        if !(lo..=hi).contains(&d) || d.fract() != 0.0 {
            return Err(format!("{id}.{f}: {d} is not a whole number from {lo} to {hi}"));
        }
    }
    Ok(())
}

/// A counting text's fields with its shown text in `body`; any other text's are left as they are.
pub fn apply(props: &mut Map<String, Value>) {
    if props.get("counter").and_then(Value::as_bool) != Some(true) {
        return;
    }
    let s = |f: &str| props.get(f).and_then(Value::as_str).unwrap_or("").to_string();
    let n = props.get("count").and_then(Value::as_f64).unwrap_or(0.0);
    let whole = |f: &str, or: f64| props.get(f).and_then(Value::as_f64).unwrap_or(or) as usize;
    let written = number(n, whole("countDecimals", 0.0), whole("countDigits", 1.0), &s("countSeparator"));
    let shown = format!("{}{written}{}", s("countPrefix"), s("countSuffix"));
    props.insert("body".into(), Value::String(shown));
}

/// `n` rounded to `decimals` places, its whole part at least `digits` digits (zeros in front) and grouped by threes
/// with the thousands mark `sep` ("-1,284.50"; never "-0").
pub fn number(n: f64, decimals: usize, digits: usize, sep: &str) -> String {
    let (group, point) = match sep {
        "comma" => (",", "."),
        "period" => (".", ","),
        "space" => (" ", "."),
        _ => ("", "."),
    };
    let written = format!("{:.*}", decimals, n.abs());
    let (whole, frac) = written.split_once('.').unwrap_or((&written, ""));
    let whole = format!("{whole:0>digits$}");
    let mut out = String::new();
    for (i, c) in whole.chars().enumerate() {
        if i > 0 && (whole.len() - i) % 3 == 0 {
            out += group;
        }
        out.push(c);
    }
    if !frac.is_empty() {
        out = out + point + frac;
    }
    let zero = written.bytes().all(|b| b == b'0' || b == b'.');
    if n < 0.0 && !zero { format!("-{out}") } else { out }
}

#[cfg(test)]
mod tests {
    use super::number;

    #[test]
    fn numbers_are_written_with_their_marks() {
        assert_eq!(number(1284.0, 0, 1, "comma"), "1,284");
        assert_eq!(number(1234567.456, 2, 1, "period"), "1.234.567,46");
        assert_eq!(number(-0.004, 2, 1, "comma"), "0.00");
        assert_eq!(number(-12345.0, 0, 1, "space"), "-12 345");
        assert_eq!(number(999.6, 0, 1, "none"), "1000");
        assert_eq!(number(44.0, 0, 3, "comma"), "044");
    }
}
