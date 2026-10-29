//! Near-still layers held through the shutter (MOTION.md › Motion blur). A motion-blurred frame draws every top-level
//! layer once per sub-frame; one that barely moves while the shutter is open (a slow drift, a background) gives the same
//! picture each time but for a fraction of a pixel, and paying for it every sub-frame was most of a busy export's
//! paint (a 140 px blur drawn 48 times a frame because a title flew past it). Such a layer's piece is written as at the
//! frame's own time in every sub-frame, so its pieces are the same and still_runs.rs paints it once.
//!
//! A piece is held only when both say it barely moves: every corner of the layer's box and of its children's boxes
//! (through its own place, turn and scale, its groups' and the frame's, as steps.rs measures, and its matte's) stays
//! within HOLD_PX of where it is at the frame's time, and its markup differs from the frame time's only in numbers that
//! each stay within HOLD_PX of their value then (path points, letter places, opacity, a blur's radius: what the corners
//! don't see). Anything else (a colour written in hex changing, a layer appearing within the shutter) is drawn every
//! sub-frame as before. Held, a layer's streak is at most HOLD_PX × 2 long: well under one pixel, so the picture differs
//! from the sub-frames' average by a level or two at the most, on hard edges only.

use std::collections::HashMap;

use crate::frame::View;
use crate::rig::math::{Aff, Pt};
use crate::scene::eval::Item;

/// The farthest a held layer's corners and numbers are from their place at the frame's time, in any sub-frame (px).
pub const HOLD_PX: f64 = 0.25;

/// `samples` (each sub-frame's stage pieces, `items` its evaluated comp) with every near-still layer's piece replaced
/// by `centre_pieces`' (the stage at the frame's own time, `centre` its comp). Returns how many pieces were held.
pub fn hold_still(centre: &Item, centre_pieces: &[String], items: &[Item], samples: &mut [Vec<String>]) -> usize {
    let ids_of = |c: &Item| -> Vec<String> { drawn(c).iter().map(|l| l.id.to_string()).collect() };
    let ids = ids_of(centre);
    // Piece 0 is the background; then one per drawn top-level layer (stage.rs `parts`), the same ones in every sub-frame.
    if centre_pieces.len() != ids.len() + 1 || samples.iter().any(|s| s.len() != centre_pieces.len()) || items.iter().any(|c| ids_of(c) != ids) {
        return 0;
    }
    let at_centre = places(centre);
    let moved: Vec<HashMap<&str, f64>> = items.iter().map(|c| farthest(&at_centre, &places(c))).collect();
    let mut held = 0;
    for (k, id) in ids.iter().enumerate() {
        let p = k + 1;
        if samples.iter().all(|s| s[p] == centre_pieces[p]) {
            continue; // the same already
        }
        let still = moved.iter().all(|m| m.get(id.as_str()).copied().unwrap_or(f64::INFINITY) <= HOLD_PX)
            && samples.iter().all(|s| numbers_near(&s[p], &centre_pieces[p]));
        if still {
            for s in samples.iter_mut() {
                s[p].clone_from(&centre_pieces[p]);
            }
            held += 1;
        }
    }
    held
}

/// The comp's top-level layers that are drawn as pieces of their own, in order (stage.rs `each_sibling`).
pub(super) fn drawn<'t, 'a>(comp: &'t Item<'a>) -> Vec<&'t Item<'a>> {
    comp.layers.iter().filter(|l| l.kind != "camera" && !crate::scene::matte::used(l, comp)).collect()
}

/// Every corner of each drawn top-level layer's piece (its own, its children's, its matte's) in output px, by layer id.
pub(super) fn places<'a>(comp: &Item<'a>) -> HashMap<&'a str, Vec<Pt>> {
    let view = View::of(comp).ok();
    let mut out = HashMap::new();
    for l in drawn(comp) {
        let mut pts = vec![];
        let mut add = |it: &Item<'a>| {
            let m = view.as_ref().map_or(Aff::ID, |v| v.map(it));
            let mut corners = HashMap::new();
            super::steps::corners(it, m, &mut corners);
            let mut keyed: Vec<_> = corners.into_iter().collect();
            keyed.sort_by(|a, b| a.0.cmp(&b.0));
            pts.extend(keyed.into_iter().map(|(_, p)| p));
        };
        add(l);
        if let Some(Some(m)) = crate::scene::matte::of(l, comp) {
            add(m);
        }
        out.insert(l.id, pts);
    }
    out
}

/// For each layer: the farthest any of its corners is from its place at the frame's time (infinite when they don't pair up).
fn farthest<'a>(centre: &HashMap<&'a str, Vec<Pt>>, sub: &HashMap<&'a str, Vec<Pt>>) -> HashMap<&'a str, f64> {
    centre
        .iter()
        .map(|(id, a)| {
            let d = match sub.get(id) {
                Some(b) if b.len() == a.len() => a.iter().zip(b).map(|(p, q)| (q.0 - p.0).hypot(q.1 - p.1)).fold(0.0, f64::max),
                _ => f64::INFINITY,
            };
            (*id, d)
        })
        .collect()
}

/// Whether `a` is `b` but for numbers, each within HOLD_PX of its counterpart (the same text between them).
pub fn numbers_near(a: &str, b: &str) -> bool {
    let (sa, na) = split(a);
    let (sb, nb) = split(b);
    sa == sb && na.len() == nb.len() && na.iter().zip(&nb).all(|(x, y)| (x - y).abs() <= HOLD_PX)
}

/// The text (bytes) with every decimal number taken out (a `#` marks where each was), and the numbers in order. A number is
/// digits with at most one point and an optional leading minus; one glued to letters or a `#` (an id, a hex colour)
/// is part of the text.
fn split(s: &str) -> (Vec<u8>, Vec<f64>) {
    let b = s.as_bytes();
    let (mut text, mut nums, mut i) = (Vec::with_capacity(s.len()), vec![], 0);
    let word = |c: u8| c.is_ascii_alphanumeric() || c == b'#' || c == b'_' || c == b'~';
    while i < b.len() {
        let c = b[i];
        let starts = (c.is_ascii_digit() || (c == b'-' || c == b'.') && b.get(i + 1).is_some_and(|d| d.is_ascii_digit() || *d == b'.'))
            && (i == 0 || !word(b[i - 1]));
        if starts {
            let mut j = i + usize::from(c == b'-');
            let mut dot = false;
            while j < b.len() && (b[j].is_ascii_digit() || b[j] == b'.' && !dot) {
                dot |= b[j] == b'.';
                j += 1;
            }
            // Glued to letters after it other than a unit (px, deg, %, e …): part of the text (a hex colour like 1fc59a).
            let unit_end = (j..b.len()).find(|&k| !b[k].is_ascii_alphabetic()).unwrap_or(b.len());
            let unit = &s[j..unit_end];
            let glued = !matches!(unit, "" | "px" | "deg" | "rad" | "turn" | "em" | "s" | "ms");
            if let (false, Ok(v)) = (glued, s[i..j].parse::<f64>()) {
                nums.push(v);
                text.push(b'#');
                i = j;
                continue;
            }
            text.extend_from_slice(&b[i..unit_end.max(j)]);
            i = unit_end.max(j);
            continue;
        }
        text.push(c);
        i += 1;
    }
    (text, nums)
}

#[cfg(test)]
mod tests {
    use super::numbers_near;

    #[test]
    fn numbers_within_a_quarter_pixel_are_near_and_anything_else_is_not() {
        let a = r#"<div id="blob0" style="left:300.10px;top:-12.5px;opacity:0.55;background:#1fc59a;filter:blur(140px)">é</div>"#;
        let b = r#"<div id="blob0" style="left:300.30px;top:-12.4px;opacity:0.56;background:#1fc59a;filter:blur(140px)">é</div>"#;
        assert!(numbers_near(a, b));
        assert!(!numbers_near(a, &b.replace("300.30", "300.40")), "0.3 px apart");
        assert!(!numbers_near(a, &b.replace("#1fc59a", "#1fc59b")), "a hex colour is text, not a number");
        assert!(!numbers_near(a, &b.replace("blob0", "blob1")), "an id is text");
        assert!(!numbers_near(a, &b.replace("px;top", "px;left")));
        assert!(!numbers_near("matrix(1, 0, 0, 1, 2, 3)", "matrix(1, 0, 0, 1, 2)"), "a number fewer");
    }
}
