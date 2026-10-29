//! Styled runs inside one text layer (the Python layer's text_runs.py): up to `COUNT` stretches of its `body`, each
//! `run<n>From` ≤ letter < `run<n>To` (letters counted in `body`, line breaks included), with its own colour, weight,
//! scale and opacity, every one keyable. A run is used while its To > From. Drawn as spans inside the text's one box
//! (stage.rs), or per letter when the text is drawn letter by letter (stage_type.rs, letters.rs): one layer, the
//! words flow as one line, nothing placed by hand.

use std::fmt::Write;

use serde_json::{Map, Value};

use super::eval;
use super::fields::{Field, Kind};
use super::stage::escape;

pub const COUNT: usize = 4;

/// The run fields in the table's order (fields.py: text_runs.FIELDS).
pub const FIELDS: &[Field] = &[
    ("run1From", Kind::Number), ("run1To", Kind::Number), ("run1Color", Kind::Color), ("run1Weight", Kind::Number), ("run1Scale", Kind::Number), ("run1Opacity", Kind::Number),
    ("run2From", Kind::Number), ("run2To", Kind::Number), ("run2Color", Kind::Color), ("run2Weight", Kind::Number), ("run2Scale", Kind::Number), ("run2Opacity", Kind::Number),
    ("run3From", Kind::Number), ("run3To", Kind::Number), ("run3Color", Kind::Color), ("run3Weight", Kind::Number), ("run3Scale", Kind::Number), ("run3Opacity", Kind::Number),
    ("run4From", Kind::Number), ("run4To", Kind::Number), ("run4Color", Kind::Color), ("run4Weight", Kind::Number), ("run4Scale", Kind::Number), ("run4Opacity", Kind::Number),
];

/// One used run at one time.
#[derive(Clone, Debug, PartialEq)]
pub struct Run {
    pub from: usize,
    pub to: usize,
    pub color: String,
    pub weight: f64,
    pub scale: f64,
    pub opacity: f64,
}

fn num(p: &Map<String, Value>, f: &str, or: f64) -> f64 {
    p.get(f).and_then(Value::as_f64).unwrap_or(or)
}

/// The used runs in `p` (a text's field values at one time), in run order.
pub fn read(p: &Map<String, Value>) -> Vec<Run> {
    (1..=COUNT)
        .filter_map(|n| {
            let (from, to) = (num(p, &format!("run{n}From"), 0.0).max(0.0) as usize, num(p, &format!("run{n}To"), 0.0).max(0.0) as usize);
            (to > from).then(|| Run {
                from,
                to,
                color: p.get(&format!("run{n}Color")).and_then(Value::as_str).unwrap_or("").to_string(),
                weight: num(p, &format!("run{n}Weight"), 0.0),
                scale: num(p, &format!("run{n}Scale"), 1.0),
                opacity: num(p, &format!("run{n}Opacity"), 1.0),
            })
        })
        .collect()
}

/// The run letter `i` of the body is in (the last listed wins where two overlap).
pub fn at(runs: &[Run], i: usize) -> Option<&Run> {
    runs.iter().rev().find(|r| (r.from..r.to).contains(&i))
}

/// A run is scaled (its scale keyed, or not 1) on a one-line text: the text is then drawn letter by letter
/// (stage_type.rs `by_letter`), each letter of the run scaled about the run's centre; a wrapped text keeps scale 1.
pub fn scaled(it: &super::eval::Item) -> bool {
    it.kind == "text" && it.num("boxWidth") == 0.0 && !it.on("counter")
        && (1..=COUNT).any(|n| {
            let f = format!("run{n}Scale");
            num(&it.props, &format!("run{n}To"), 0.0) > num(&it.props, &format!("run{n}From"), 0.0)
                && (num(&it.props, &f, 1.0) != 1.0 || it.node.anim.iter().any(|(name, _)| *name == f))
        })
}

/// A run's own CSS: its colour (faded by its opacity and the text's fill opacity) unless the layer's look sets one
/// colour for all (`keep_colour`) and its weight (0 = the text's). Its scale is drawn per letter (stage_type.rs).
pub fn css(r: &Run, fill_opacity: f64, keep_colour: bool) -> String {
    let mut s = String::new();
    if !keep_colour && !r.color.is_empty() {
        let _ = write!(s, "color:{};", eval::faded(&r.color, r.opacity * fill_opacity));
    } else if r.opacity != 1.0 {
        let _ = write!(s, "opacity:{};", r.opacity);
    }
    if r.weight > 0.0 {
        let _ = write!(s, "font-weight:{:.0};", r.weight);
    }
    s
}

/// The body's markup: plain letters escaped, each run's letters in a span with its style.
pub fn markup(body: &str, runs: &[Run], fill_opacity: f64, keep_colour: bool) -> String {
    if runs.is_empty() {
        return escape(body);
    }
    let mut out = String::new();
    let mut open: Option<&Run> = None;
    let mut chunk = String::new();
    let flush = |out: &mut String, chunk: &mut String, run: Option<&Run>| {
        if chunk.is_empty() {
            return;
        }
        match run {
            Some(r) => {
                let _ = write!(out, "<span style=\"{}\">{}</span>", css(r, fill_opacity, keep_colour), escape(chunk));
            }
            None => *out += &escape(chunk),
        }
        chunk.clear();
    };
    for (i, ch) in body.chars().enumerate() {
        let run = at(runs, i);
        if run != open {
            flush(&mut out, &mut chunk, open);
            open = run;
        }
        chunk.push(ch);
    }
    flush(&mut out, &mut chunk, open);
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn a_run_styles_only_its_letters() {
        let p = json!({"run1From": 8, "run1To": 12, "run1Color": "#ff0000", "run1Weight": 800, "run1Scale": 1, "run1Opacity": 1,
                       "run2From": 0, "run2To": 0}).as_object().unwrap().clone();
        let runs = read(&p);
        assert_eq!(runs.len(), 1);
        let m = markup("Make it move on cue", &runs, 1.0, false);
        assert!(m.starts_with("Make it <span style=\"color:"), "{m}");
        assert!(m.contains("font-weight:800;\">move</span> on cue"), "{m}");
    }

    /// The width of `body` as measured (the box the stage lays it out in), with run 1 on `word` styled by `run`.
    fn width(body: &str, word: &str, run: serde_json::Value, by_letter: bool) -> f64 {
        let from = body.find(word).unwrap();
        let mut t = json!({ "id": "t", "body": body, "font": "Roboto Flex", "size": 80, "weight": 400, "stretch": 100,
                            "tracking": 0.0, "lineHeight": 1.2, "align": "left", "boxWidth": 0,
                            "letterDelay": if by_letter { 0.05 } else { 0.0 },
                            "run1From": from, "run1To": from + word.len(), "run1Color": "#ff0000" });
        t.as_object_mut().unwrap().extend(run.as_object().unwrap().clone());
        let got = super::super::measure::measure(&json!({ "items": [t] }), None).unwrap();
        got["sizes"]["t"][0].as_f64().unwrap()
    }

    /// Span and letter-by-letter drawing place a run and the words after it alike: the line up to the run's end and
    /// the whole line measure the same both ways (a heavier run's advances are used, spaces kept); a scaled run
    /// (drawn letter by letter) widens the line by its own extra width, so the words after it move along.
    #[test]
    fn spans_and_letters_lay_a_run_out_alike() {
        let heavy = json!({ "run1Weight": 900, "run1Scale": 1.0, "run1Opacity": 1.0 });
        for body in ["Make it move", "Make it move on cue"] {
            let (span, letters) = (width(body, "move", heavy.clone(), false), width(body, "move", heavy.clone(), true));
            assert!((span - letters).abs() < 1.0, "{body:?}: spans {span:.1} px, letter by letter {letters:.1} px");
        }
        let plain = width("Make it move on cue", "move", json!({ "run1Weight": 0, "run1Scale": 1.0, "run1Opacity": 1.0 }), true);
        let heavy_w = width("Make it move on cue", "move", heavy, true);
        assert!(heavy_w > plain + 4.0, "a heavier run widens the line: {plain:.1} → {heavy_w:.1}");
        let word = width("move", "move", json!({ "run1Weight": 0, "run1Scale": 1.0, "run1Opacity": 1.0 }), true);
        let big = width("Make it move on cue", "move", json!({ "run1Weight": 0, "run1Scale": 1.5, "run1Opacity": 1.0 }), false);
        assert!((big - (plain + 0.5 * word)).abs() < 1.0, "a 1.5× run widens the line by half its width: {plain:.1} + {:.1} ≠ {big:.1}", 0.5 * word);
    }
}
