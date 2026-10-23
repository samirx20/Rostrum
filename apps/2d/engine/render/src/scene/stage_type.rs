//! A text layer's type in the stage (contract § 4 text): its OpenType features and variable axes as CSS
//! (type_font.rs), and text drawn letter by letter — on a path, or playing its keys letter by letter — as one
//! absolutely placed box per letter (letters.rs places them). Blitz's SVG `<text>` falls back to a serif, so
//! letters on a path are boxes turned to the path, not `<textPath>`.

use std::fmt::Write;

use serde_json::{Map, Value};

use super::eval::{self, Item};
use super::letters;
use super::stage::escape;
use super::type_font;

type R<T> = Result<T, String>;

/// `font-variation-settings` / `font-feature-settings` of a text layer.
pub fn font_css(it: &Item) -> R<String> {
    type_font::css(it)
}

/// Drawn letter by letter: on a path, or playing its keys letter by letter.
pub fn by_letter(it: &Item) -> bool {
    it.kind == "text" && (!it.str("path").is_empty() || animated(it))
}

/// Its keys play letter by letter (letterDelay ≠ 0).
pub fn animated(it: &Item) -> bool {
    it.kind == "text" && it.num("letterDelay") != 0.0
}

/// The transform fields a letter plays about its own centre, with the value that leaves it as it is.
const PLAYED: &[(&str, f64)] = &[("rotation", 0.0), ("scale", 1.0), ("scaleX", 1.0), ("scaleY", 1.0), ("opacity", 1.0), ("tiltX", 0.0), ("tiltY", 0.0)];

fn keyed(it: &Item, f: &str) -> bool {
    it.node.anim.iter().any(|(name, _)| name == f)
}

/// The layer's own box when its letters play its keys: keyed x / y hold their still values (the letters move
/// from there) and the other keyed transform fields their neutral ones (each letter plays them).
pub fn container<'a>(it: &Item<'a>) -> Item<'a> {
    let mut base = it.clone();
    // A text following a path layer takes its place and transform from the path (follow.rs); its own keys play per letter.
    let taken = |f: &str| super::follow::window(it).is_some() && super::follow::TAKEN.contains(&f);
    for f in ["x", "y"] {
        if keyed(it, f) && !taken(f) {
            base.props.insert(f.into(), it.node.props[f].clone());
        }
    }
    for (f, neutral) in PLAYED {
        if keyed(it, f) && !taken(f) {
            base.props.insert((*f).into(), Value::from(*neutral));
        }
    }
    base
}

fn num(p: &Map<String, Value>, f: &str) -> f64 {
    p[f].as_f64().unwrap_or(0.0)
}

/// (style, inner markup) of a text drawn letter by letter: `style` is the text's own (font, colour …), given
/// the box's size; each letter is a box placed on its baseline point and turned to its angle.
pub fn letters(it: &Item, mut style: String, gradient: Option<&str>, color: Option<&str>) -> R<(String, String)> {
    let placed = letters::place(it)?;
    let ranks = letters::ranks(it, &placed.letters);
    let (line, base) = (placed.line, placed.baseline);
    let _ = write!(style, "width:{:.3}px;height:{:.3}px;", placed.w, placed.h);
    // The layer's own colour and outline, which every letter inherits unless it plays its own (below).
    if color.is_none() && gradient.is_none() {
        let _ = write!(style, "color:{};", eval::faded(it.str("color"), eval::fill_opacity(&it.props)));
    }
    if it.on("stroke") {
        let _ = write!(style, "-webkit-text-stroke:{}px {};", it.num("strokeWidth"), it.str("strokeColor"));
    }
    let mut inner = String::new();
    for (l, rank) in placed.letters.iter().zip(ranks) {
        let (left, top) = (l.x - l.advance / 2.0, l.y - base);
        let mut s = format!("position:absolute;left:{left:.3}px;top:{top:.3}px;width:{:.3}px;height:{line:.3}px;line-height:{line:.3}px;text-align:left;transform-origin:{:.3}px {base:.3}px;", l.advance, l.advance / 2.0);
        let mut tf = vec![];
        let own = animated(it).then(|| eval::props_at(it.node, it.t - it.num("letterDelay") * rank));
        if let Some(p) = &own {
            let (dx, dy) = (num(p, "x") - num(&it.node.props, "x"), num(p, "y") - num(&it.node.props, "y"));
            if (dx, dy) != (0.0, 0.0) {
                tf.push(format!("translate({dx:.3}px, {dy:.3}px)"));
            }
        }
        if l.angle != 0.0 {
            tf.push(format!("rotate({:.4}deg)", l.angle));
        }
        if let Some(p) = &own {
            tf.push(played(it, p, line / 2.0 - base, &mut s));
            if it.on("stroke") {
                let _ = write!(s, "-webkit-text-stroke:{}px {};", num(p, "strokeWidth"), p["strokeColor"].as_str().unwrap_or("#ffffff"));
            }
        }
        if let Some(c) = color {
            let _ = write!(s, "color:{c};");
        } else if let Some(g) = gradient {
            // The layer's one gradient, each letter showing its part of it.
            let _ = write!(s, "background:{g};background-size:{:.3}px {:.3}px;background-position:{:.3}px {:.3}px;-webkit-background-clip:text;background-clip:text;color:transparent;", placed.w, placed.h, -left, -top);
        } else if let Some(p) = &own {
            let _ = write!(s, "color:{};", eval::faded(p["color"].as_str().unwrap_or("#ffffff"), eval::fill_opacity(p)));
        }
        if !tf.is_empty() {
            let _ = write!(s, "transform:{};", tf.join(" "));
        }
        let _ = write!(inner, "<div style=\"{s}\">{}</div>", escape(&l.ch.to_string()));
    }
    Ok((style, inner))
}

/// A letter's own keyed rotation, tilt, scale (about its centre, `c` below its baseline point) and opacity.
fn played(it: &Item, p: &Map<String, Value>, c: f64, s: &mut String) -> String {
    let get = |f: &str, neutral: f64| if keyed(it, f) { num(p, f) } else { neutral };
    let mut parts = vec![format!("translate(0px, {c:.3}px)")];
    let (tx, ty) = (get("tiltX", 0.0), get("tiltY", 0.0));
    if (tx, ty) != (0.0, 0.0) {
        parts.push(format!("perspective(1600px) rotateX({tx}deg) rotateY({ty}deg)"));
    }
    let r = get("rotation", 0.0);
    if r != 0.0 {
        parts.push(format!("rotate({r}deg)"));
    }
    let k = get("scale", 1.0);
    parts.push(format!("scale({:.5}, {:.5})", k * get("scaleX", 1.0), k * get("scaleY", 1.0)));
    parts.push(format!("translate(0px, {:.3}px)", -c));
    if keyed(it, "opacity") {
        let _ = write!(s, "opacity:{};", num(p, "opacity"));
    }
    parts.join(" ")
}
