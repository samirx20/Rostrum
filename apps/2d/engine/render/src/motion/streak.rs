//! One streak per moving layer (MOTION.md › Motion blur › One streak per layer). A motion-blurred frame used to stage,
//! lay out and paint its page once per shutter sub-frame (up to 128). A top-level layer that is the same layer in every
//! sub-frame but for where it is placed (its x, y, turn and scale, and the frame's move, zoom and roll on it) is the same
//! picture moved: it is painted once, at the frame's own time, and drawn as the average of that picture under each
//! sub-frame's move in one GPU pass (blitz-paint `Run::Streak`, anyrender `draw_cached_streak`). The page is laid out
//! once. A layer whose look changes while the shutter is open (a path's shape, letters playing, a colour, a matte) or
//! that blends with what is under it is still staged per sub-frame (serve.rs `frame`).
//!
//! The streak is the layer's own motion blur composited over the layers under it, as After Effects blurs each layer on
//! its own: where two layers moving differently overlap, the sum of whole sub-frames differs from it slightly.

use crate::frame::View;
use crate::rig::math::{Aff, Pt};
use crate::scene::eval::Item;

use super::hold::HOLD_PX;

/// A layer's own placing fields: the only ones a streaked layer's sub-frames may differ in by more than HOLD_PX.
const PLACE: &[&str] = &["x", "y", "rotation", "scale", "scaleX", "scaleY"];

/// Fields that change how much a layer shows, not where: within one shutter opening their average is their value at the
/// frame's time (up to the curve of their ease over that instant), so a fade, like a colour change, doesn't stop a streak.
const TONE: &[&str] = &["opacity", "strength"];

/// A colour value (`#rrggbb[aa]`, `rgb(…)`, `rgba(…)`): taken at the frame's time, as `TONE`.
fn colour(v: &serde_json::Value) -> bool {
    v.as_str().is_some_and(|s| s.starts_with('#') || s.starts_with("rgb"))
}

/// One move per sub-frame (page px, as CSS `matrix(a, b, c, d, e, f)`): where the picture painted at the frame's own
/// time goes in that sub-frame.
pub type Moves = Vec<[f64; 6]>;

/// A layer drawn as one streak: its moves, and the page px rectangle its picture can reach under them (x0, y0, x1, y1;
/// None when its size isn't known before layout), so the streak is drawn over that part of the frame only.
#[derive(Clone, Debug)]
pub struct Streak {
    pub moves: Moves,
    pub reach: Option<[f64; 4]>,
    /// Where its picture is (its padded boxes at the frame's time) and every px its streak reads from (that picture
    /// carried back from anywhere it reaches): streaks whose reads miss each other's pictures can share one picture.
    pub ink: [f64; 4],
    pub reads: [f64; 4],
    /// It blends with what is under it (a blend mode, a glow, frosted glass: still_runs.rs `regroups`), so it isn't
    /// laid over as one picture: it is painted at each of its moves, as laid out at the frame's time (blurred.rs).
    pub blends: bool,
}

/// For each stage piece of `centre` (piece 0 the background, then one per drawn top-level layer: stage.rs `parts`):
/// its moves when it only moves, None when it is the same in every sub-frame (it moves under HOLD_PX) or must be staged
/// per sub-frame. `items` are the sub-frames' evaluated comps; `streakable(p)` says piece p may be drawn as a kept
/// picture (still_runs.rs `regroups`; else it `blends`); `spread(p)` how far piece p's blurs and shadows reach past its boxes (page px).
/// Also returns which pieces are staged per sub-frame. Empty when the sub-frames don't draw the same layers.
pub fn moves(centre: &Item, items: &[Item], streakable: impl Fn(usize) -> bool, spread: impl Fn(usize) -> f64) -> (Vec<Option<Streak>>, Vec<bool>) {
    let drawn = |c: &'_ Item| -> Vec<String> { super::hold::drawn(c).iter().map(|l| l.id.to_string()).collect() };
    let ids = drawn(centre);
    if items.iter().any(|c| drawn(c) != ids) {
        return (vec![], vec![]);
    }
    let view = |c: &Item| View::of(c).ok();
    let (cv, views): (Option<View>, Vec<Option<View>>) = (view(centre), items.iter().map(view).collect());
    let subs: Vec<Vec<&Item>> = items.iter().map(|c| super::hold::drawn(c)).collect();
    let mut out = vec![None];
    let mut staged = vec![false];
    for (k, l) in super::hold::drawn(centre).into_iter().enumerate() {
        let rigid = crate::scene::matte::of(l, centre).is_none() && subs.iter().all(|s| same_but_place(l, s[k], true));
        let m = rigid.then(|| {
            let from = placed(cv.as_ref(), l);
            subs.iter().zip(&views).map(|(s, v)| Some(placed(v.as_ref(), s[k]) * from.inverse()?)).collect::<Option<Vec<Aff>>>()
        }).flatten();
        match m {
            Some(m) if still(l, cv.as_ref(), &m) => {
                out.push(None);
                staged.push(false);
            }
            Some(m) => {
                let (reach, ink, reads) = match reach(l, cv.as_ref(), &m, spread(k + 1)) {
                    Some((r, i, d)) => (Some(r), i, d),
                    None => (None, [f64::MIN, f64::MIN, f64::MAX, f64::MAX], [f64::MIN, f64::MIN, f64::MAX, f64::MAX]),
                };
                out.push(Some(Streak { moves: m.iter().map(|a| [a.a, a.b, a.c, a.d, a.e, a.f]).collect(), reach, ink, reads, blends: !streakable(k + 1) }));
                staged.push(false);
            }
            _ => {
                out.push(None);
                staged.push(true);
            }
        }
    }
    (out, staged)
}

/// The layer's place, turn and scale, seen through the frame (stage.rs `layer`, frame/mod.rs `place`): its content's
/// px → page px, but for the content's own offset (the same in every sub-frame of a streaked layer).
fn placed(view: Option<&View>, l: &Item) -> Aff {
    let n = |f: &str, d: f64| l.props.get(f).and_then(serde_json::Value::as_f64).unwrap_or(d);
    let s = n("scale", 1.0);
    let own = Aff::translate(n("x", 0.0), n("y", 0.0)) * Aff::rotate(n("rotation", 0.0)) * Aff::scale(s * n("scaleX", 1.0), s * n("scaleY", 1.0));
    view.map_or(Aff::ID, |v| v.map(l)) * own
}

/// Every corner of the layer (and its children) stays within HOLD_PX of its place at the frame's time under each move.
fn still(l: &Item, view: Option<&View>, moves: &[Aff]) -> bool {
    let mut corners = std::collections::HashMap::new();
    super::steps::corners(l, view.map_or(Aff::ID, |v| v.map(l)), &mut corners);
    let pts: Vec<Pt> = corners.into_values().collect();
    moves.iter().all(|m| pts.iter().all(|&p| {
        let q = m.apply(p);
        (q.0 - p.0).hypot(q.1 - p.1) <= HOLD_PX
    }))
}

/// How far a piece's own blurs, shadows and strokes reach past its boxes (page px, generously): three times each blur and
/// shadow number, once each stroke or border number, read from its markup.
pub fn pad(piece: &str) -> f64 {
    let mut pad = 0.0;
    for (key, k) in [("blur(", 3.0), ("shadow(", 3.0), ("shadow:", 3.0), ("stroke-width", 1.0), ("border", 1.0)] {
        for (at, _) in piece.match_indices(key) {
            let rest = &piece[at + key.len()..];
            let decl = &rest[..rest.find([')', ';', '"']).unwrap_or(rest.len())];
            let nums = decl.split(|c: char| !(c.is_ascii_digit() || c == '.' || c == '-')).filter_map(|n| n.parse::<f64>().ok());
            pad += k * nums.map(f64::abs).sum::<f64>();
        }
    }
    pad
}

/// The page px rectangles of the layer's picture under any of `moves` (its reach), of the picture itself (its boxes'
/// corners, its own and its children's, as steps.rs measures them, `pad` further out) and of what its streak reads.
/// None when a part of it has no box (a path, a picture without a size).
fn reach(l: &Item, view: Option<&View>, moves: &[Aff], pad: f64) -> Option<([f64; 4], [f64; 4], [f64; 4])> {
    fn boxed(it: &Item) -> bool {
        (it.props.contains_key("w") || it.kind == "group") && it.kind != "path" && it.layers.iter().all(boxed)
    }
    if !boxed(l) {
        return None;
    }
    let mut corners = std::collections::HashMap::new();
    super::steps::corners(l, view.map_or(Aff::ID, |v| v.map(l)), &mut corners);
    let bound = |pts: &mut dyn Iterator<Item = Pt>| pts.fold([f64::MAX, f64::MAX, f64::MIN, f64::MIN], |r, p| [r[0].min(p.0), r[1].min(p.1), r[2].max(p.0), r[3].max(p.1)]);
    let b = bound(&mut corners.into_values());
    let pad = pad + 2.0;
    let (x0, y0, x1, y1) = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad);
    let ink = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)];
    let r = bound(&mut moves.iter().flat_map(|m| ink.map(|p| m.apply(p))));
    let back: Vec<Aff> = moves.iter().filter_map(Aff::inverse).collect();
    let reads = bound(&mut back.iter().flat_map(|b| moves.iter().flat_map(move |m| ink.map(|p| (*b * *m).apply(p)))));
    let all = [r, reads].iter().flatten().all(|v| v.is_finite());
    (all && back.len() == moves.len()).then_some((r, [x0, y0, x1, y1], reads))
}

/// `b` is `a` but for its placing fields (`top`), its colours and fades (`TONE`) and numbers within HOLD_PX: the same
/// picture, moved. A turn or scale
/// change under a tilt or a smear (applied between them, stage.rs `transform`) isn't a move of the picture.
fn same_but_place(a: &Item, b: &Item, top: bool) -> bool {
    if a.id != b.id || a.kind != b.kind || a.props.len() != b.props.len() {
        return false;
    }
    let warped = top && ["tiltX", "tiltY"].iter().any(|f| a.props.get(*f).and_then(serde_json::Value::as_f64).unwrap_or(0.0) != 0.0);
    let props = a.props.iter().all(|(k, v)| {
        let Some(w) = b.props.get(k) else { return false };
        if top && PLACE.contains(&k.as_str()) && !(warped && k != "x" && k != "y") {
            return true;
        }
        v == w || TONE.contains(&k.as_str()) || colour(v) && colour(w) || matches!((v.as_f64(), w.as_f64()), (Some(x), Some(y)) if (x - y).abs() <= HOLD_PX)
    });
    let all = |x: &[Item], y: &[Item]| x.len() == y.len() && x.iter().zip(y).all(|(p, q)| same_but_place(p, q, false));
    props && !a.props.keys().any(|k| k == "~smear") && all(&a.effects, &b.effects) && all(&a.masks, &b.masks) && all(&a.layers, &b.layers) && all(&a.stops, &b.stops)
}

/// How many sub-frames a frame's layers are evaluated at to find their streaks (`probes`): a move over one shutter
/// opening (a 60th of a second at 30 fps) is close to straight between them, and each evaluation of a busy comp costs
/// about 10-25 ms.
const PROBES: usize = 5;

/// The sub-frames (of `n`) the layers are evaluated at: the first, the last and evenly between (all when `n` is few).
pub fn probes(n: usize) -> Vec<usize> {
    if n <= PROBES {
        return (0..n).collect();
    }
    (0..PROBES).map(|i| ((i * (n - 1)) as f64 / (PROBES - 1) as f64).round() as usize).collect()
}

/// The moves at all `n` sub-frames from those at `probes` (`moves[i]` at sub-frame `probes[i]`): each matrix entry
/// straight between its neighbouring probes.
pub fn spread(moves: &[[f64; 6]], probes: &[usize], n: usize) -> Moves {
    if probes.len() == n {
        return moves.to_vec();
    }
    (0..n).map(|j| {
        let i = probes.windows(2).position(|w| j <= w[1]).unwrap_or(probes.len() - 2);
        let (a, b) = (probes[i], probes[i + 1]);
        let f = (j as f64 - a as f64) / (b - a).max(1) as f64;
        std::array::from_fn(|k| moves[i][k] + (moves[i + 1][k] - moves[i][k]) * f)
    }).collect()
}

#[cfg(test)]
mod tests {
    #[test]
    fn moves_between_probes_are_read_off_them() {
        let p = super::probes(9);
        assert_eq!(p, vec![0, 2, 4, 6, 8]);
        let at = |x: f64| [1.0, 0.0, 0.0, 1.0, x, 0.0];
        let m = super::spread(&[at(-4.0), at(-2.0), at(0.0), at(2.0), at(4.0)], &p, 9);
        assert_eq!(m.iter().map(|m| m[4]).collect::<Vec<_>>(), vec![-4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0]);
        assert_eq!(super::probes(3), vec![0, 1, 2]);
    }

    #[test]
    fn a_pieces_blurs_and_shadows_pad_its_reach() {
        let p = r#"<div style="filter:blur(4px);"><div style="box-shadow:2px -3px 5px rgba(0,0,0,0.5);stroke-width:6"></div></div>"#;
        assert_eq!(super::pad(p), 12.0 + 3.0 * (2.0 + 3.0 + 5.0 + 0.5) + 6.0);
    }
}
