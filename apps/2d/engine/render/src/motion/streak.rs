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
    /// Where its picture is: its padded boxes at the frame's time (page px).
    pub ink: [f64; 4],
    /// It blends with what is under it in a way an average of it doesn't give (a blend mode other than add, screen and
    /// multiply, frosted glass: still_runs.rs `keeps`), so it isn't laid on as one picture: it is painted at each of its
    /// moves, as laid out at the frame's time (blurred.rs).
    pub blends: bool,
    /// Its picture is laid on with a blend of its own (add, screen, multiply): a streak of its own, never one with its
    /// neighbours'.
    pub alone: bool,
    /// A group whose children each move their own way (bubbles rising in a group the frame pans past): each child's
    /// element id and moves (page px, as `moves`). The group is drawn as laid out at the frame's time, each child moved
    /// to each sub-frame, and averaged (blurred.rs): its sub-frames without a stage or layout of their own.
    pub parts: Vec<(String, Moves)>,
    /// Such a group laid on as one kept picture, each child's own streak over it (its moves and reach, page px): when
    /// no child's streak reads another's picture and none reads past the kept picture (blurred.rs `measured`). Empty:
    /// drawn at each move.
    pub subs: Vec<(Moves, [f64; 4])>,
    /// Such a group may be laid on as one kept picture (still_runs.rs `keeps`).
    pub keeps: bool,
}

/// For each stage piece of `centre` (piece 0 the background, then one per drawn top-level layer: stage.rs `parts`):
/// its moves when it only moves, None when it is the same in every sub-frame (it moves under HOLD_PX) or must be staged
/// per sub-frame. `items` are the sub-frames' evaluated comps; `streakable(p)` says piece p may be drawn as a kept
/// picture (`l` its layer: still_runs.rs `keeps`; else it `blends`); `spread(p)` how far piece p's blurs and shadows reach past its boxes (its own px: `pad`).
/// `shares(id)`: the sub-frames' layer `id` has `centre`'s own children, effects, masks and stops (eval.rs
/// `at_reusing`), so only its own fields are compared.
/// Also returns which pieces are staged per sub-frame. Empty when the sub-frames don't draw the same layers.
pub fn moves(centre: &Item, items: &[Item], streakable: impl Fn(usize, &Item) -> bool, spread: impl Fn(usize) -> f64, shares: impl Fn(&str) -> bool) -> (Vec<Option<Streak>>, Vec<bool>) {
    let rigid = |a: &Item, b: &Item| if shares(a.id) { same_own(a, b, true) } else { same_but_place(a, b, true) };
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
        let m = subs.iter().all(|s| rigid(l, s[k])).then(|| moved(cv.as_ref(), l, &views, |i| Some(subs[i][k]))).flatten();
        // Not one picture moved: a group whose children only move, each its own way, is drawn child by child.
        let parts = if m.is_none() && crate::scene::matte::of(l, centre).is_none() { split(cv.as_ref(), l, &views, |i| subs[i][k]) } else { None };
        if let Some(parts) = parts {
            let own = moved(cv.as_ref(), l, &views, |i| Some(subs[i][k]));
            let still = parts.iter().zip(&l.layers).all(|((_, pm), c)| part_still(c, cv.as_ref(), l, pm));
            match own {
                Some(own) if !still => {
                    let parts = parts.into_iter().map(|(id, pm)| (id, pm.iter().map(|a| [a.a, a.b, a.c, a.d, a.e, a.f]).collect())).collect();
                    let ink = [f64::MIN, f64::MIN, f64::MAX, f64::MAX];
                    out.push(Some(Streak { moves: own.iter().map(|a| [a.a, a.b, a.c, a.d, a.e, a.f]).collect(), reach: None, ink, blends: true, alone: true, parts, subs: vec![], keeps: streakable(k + 1, l) }));
                    staged.push(false);
                }
                Some(_) => {
                    out.push(None);
                    staged.push(false);
                }
                None => {
                    out.push(None);
                    staged.push(true);
                }
            }
            continue;
        }
        // A matted layer moves as one picture when its matte is the same picture moved alike (a frame's move over a title
        // and the water that reveals it); else it is staged.
        let m = match crate::scene::matte::of(l, centre) {
            None => m,
            Some(None) => None,
            Some(Some(mt)) => m.filter(|m| {
                let at = |i: usize| crate::scene::matte::of(subs[i][k], &items[i]).flatten();
                (0..items.len()).all(|i| at(i).is_some_and(|s| rigid(mt, s)))
                    && moved(cv.as_ref(), mt, &views, at).is_some_and(|mm| mm.iter().zip(m.iter()).all(|(a, b)| alike(a, b)))
            }),
        };
        match m {
            Some(m) if still(l, cv.as_ref(), &m) => {
                out.push(None);
                staged.push(false);
            }
            Some(m) => {
                let pad = grown(l, cv.as_ref(), spread(k + 1));
                let (reach, ink) = match reach(l, cv.as_ref(), &m, pad) {
                    Some((r, i)) => (Some(r), i),
                    None => (None, [f64::MIN, f64::MIN, f64::MAX, f64::MAX]),
                };
                out.push(Some(Streak { moves: m.iter().map(|a| [a.a, a.b, a.c, a.d, a.e, a.f]).collect(), reach, ink, blends: !streakable(k + 1, l), alone: l.props.get("blend").and_then(serde_json::Value::as_str).is_some_and(|b| b != "normal"), parts: vec![], subs: vec![], keeps: true }));
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

/// Where `l`, placed as at the frame's time (`cv` its frame), goes in each sub-frame (`views`, `at`: its frame and the
/// layer there): None when it isn't there or a place has no inverse.
fn moved<'i, 'a: 'i>(cv: Option<&View>, l: &Item, views: &[Option<View>], at: impl Fn(usize) -> Option<&'i Item<'a>>) -> Option<Vec<Aff>> {
    let from = placed(cv, l).inverse()?;
    views.iter().enumerate().map(|(i, v)| Some(placed(v.as_ref(), at(i)?) * from)).collect()
}

/// A group `l` (`at(i)`: it in sub-frame i) the same in every sub-frame but for its own place and its children's, each
/// child the same but for its own place: each child's id and where it goes in each sub-frame (page px, from its place at
/// the frame's time through the group's and the frame's). None for anything else.
fn split<'i, 'a: 'i>(cv: Option<&View>, l: &Item, views: &[Option<View>], at: impl Fn(usize) -> &'i Item<'a>) -> Option<Vec<(String, Vec<Aff>)>> {
    let all = |x: &[Item], y: &[Item], top: bool| x.len() == y.len() && x.iter().zip(y).all(|(p, q)| same_but_place(p, q, top));
    let alike = |b: &Item| same_own(l, b, true) && all(&l.effects, &b.effects, false) && all(&l.masks, &b.masks, false) && all(&l.stops, &b.stops, false) && all(&l.layers, &b.layers, true);
    if l.kind != "group" || l.layers.is_empty() || !(0..views.len()).all(|i| alike(at(i))) {
        return None;
    }
    let page = |v: Option<&View>, g: &Item, c: &Item| v.map_or(Aff::ID, |v| v.map(g)) * super::steps::local(g) * super::steps::local(c);
    l.layers.iter().enumerate().map(|(j, c)| {
        let from = page(cv, l, c).inverse()?;
        Some((c.id.to_string(), views.iter().enumerate().map(|(i, v)| page(v.as_ref(), at(i), &at(i).layers[j]) * from).collect()))
    }).collect()
}

/// Every corner of child `c` of group `g` (and its children) stays within HOLD_PX of its place under each of its moves.
fn part_still(c: &Item, view: Option<&View>, g: &Item, moves: &[Aff]) -> bool {
    let mut corners = std::collections::HashMap::new();
    super::steps::corners(c, view.map_or(Aff::ID, |v| v.map(g)) * super::steps::local(g), &mut corners);
    moves.iter().all(|m| corners.values().all(|&p| {
        let q = m.apply(p);
        (q.0 - p.0).hypot(q.1 - p.1) <= HOLD_PX
    }))
}

/// Two moves within a ten-thousandth in turn and scale and HOLD_PX in place: the same move.
fn alike(a: &Aff, b: &Aff) -> bool {
    [a.a - b.a, a.b - b.b, a.c - b.c, a.d - b.d].iter().all(|d| d.abs() <= 1e-4) && (a.e - b.e).abs() <= HOLD_PX && (a.f - b.f).abs() <= HOLD_PX
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

/// How far a piece's own blurs, shadows and strokes reach past its boxes (its own px, generously; `reach` scales it as the
/// layer is on screen): three times each blur and shadow number and each glow's radius, once each stroke or border
/// number, read from its markup.
pub fn pad(piece: &str) -> f64 {
    let mut pad = 0.0;
    // A glow drawn from the layer's own picture (stage.rs `data-glow="radius strength;…"`).
    for (at, _) in piece.match_indices("data-glow=\"") {
        let rest = &piece[at + 11..];
        let glows = &rest[..rest.find('"').unwrap_or(rest.len())];
        pad += 3.0 * glows.split(';').filter_map(|g| g.split_ascii_whitespace().next()?.parse::<f64>().ok()).map(f64::abs).sum::<f64>();
    }
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

/// `pad` (a piece's own px) as far as it reaches on screen (page px): times the most the layer or any of its children is
/// stretched there, and 2 px more.
fn grown(l: &Item, view: Option<&View>, pad: f64) -> f64 {
    pad * super::steps::widest(l, view.map_or(Aff::ID, |v| v.map(l))).max(1.0) + 2.0
}

/// The page px rectangles of the layer's picture under any of `moves` (its reach) and of the picture itself (its boxes'
/// corners, its own and its children's, as steps.rs measures them, `pad` page px further out: `grown`). None when a part
/// of it has no box (a path, a text, a picture without a size): blurred.rs measures those on the frame's layout.
fn reach(l: &Item, view: Option<&View>, moves: &[Aff], pad: f64) -> Option<([f64; 4], [f64; 4])> {
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
    swept([b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad], moves)
}

/// The page px rectangle a picture at `ink` (page px) covers under any of `moves`, and `ink`: a streak's (reach, ink).
/// None when not finite.
pub fn swept(ink: [f64; 4], moves: &[Aff]) -> Option<([f64; 4], [f64; 4])> {
    let [x0, y0, x1, y1] = ink;
    let corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)];
    let r = moves.iter().flat_map(|m| corners.map(|p| m.apply(p))).fold([f64::MAX, f64::MAX, f64::MIN, f64::MIN], |r, p| [r[0].min(p.0), r[1].min(p.1), r[2].max(p.0), r[3].max(p.1)]);
    (r.iter().chain(&ink).all(|v| v.is_finite()) && !moves.is_empty()).then_some((r, ink))
}

/// `b` is `a` but for its placing fields (`top`), its colours and fades (`TONE`) and numbers within HOLD_PX: the same
/// picture, moved. A turn or scale
/// change under a tilt or a smear (applied between them, stage.rs `transform`) isn't a move of the picture.
fn same_but_place(a: &Item, b: &Item, top: bool) -> bool {
    let all = |x: &[Item], y: &[Item]| x.len() == y.len() && x.iter().zip(y).all(|(p, q)| same_but_place(p, q, false));
    same_own(a, b, top) && all(&a.effects, &b.effects) && all(&a.masks, &b.masks) && all(&a.layers, &b.layers) && all(&a.stops, &b.stops)
}

/// `same_but_place` for `a` and `b` themselves, not what is in them (the same items when `b` is `at_reusing`'s: their
/// copies compare equal and carry no smear, which a frame that reuses them has none of).
fn same_own(a: &Item, b: &Item, top: bool) -> bool {
    if a.id != b.id || a.kind != b.kind || a.props.len() != b.props.len() {
        return false;
    }
    let warped = top && ["tiltX", "tiltY"].iter().any(|f| a.props.get(*f).and_then(serde_json::Value::as_f64).unwrap_or(0.0) != 0.0);
    // The scene's own fields, borrowed by both (eval.rs `props_at`: nothing keyed): the same, without a look at each.
    let props = std::ptr::eq(&*a.props, &*b.props) || a.props.iter().all(|(k, v)| {
        let Some(w) = b.props.get(k) else { return false };
        if top && PLACE.contains(&k.as_str()) && !(warped && k != "x" && k != "y") {
            return true;
        }
        v == w || TONE.contains(&k.as_str()) || colour(v) && colour(w) || matches!((v.as_f64(), w.as_f64()), (Some(x), Some(y)) if (x - y).abs() <= HOLD_PX)
    });
    props && !a.props.keys().any(|k| k == "~smear")
}

/// How many times a frame's layers are evaluated at to find its steps and its streaks (`probe_times`): a move over one
/// shutter opening (a 60th of a second at 30 fps) is close to straight between them, and each evaluation of a busy comp
/// costs a few ms.
const PROBES: usize = 5;

/// The times the layers are evaluated at, in order: the open shutter's start, its end and evenly between (the middle
/// one is the frame's own time, `t`, exactly). They don't depend on the step count, so the steps (steps.rs
/// `from_probes`) and the streaks are read off the same evaluations.
pub fn probe_times(t: f64, fps: f64, angle: f64) -> Vec<f64> {
    let open = angle / 360.0 / fps;
    (0..PROBES).map(|k| if 2 * k + 1 == PROBES { t } else { t + open * (k as f64 / (PROBES - 1) as f64 - 0.5) }).collect()
}

/// The moves at each of `n` sub-frames (shutter.rs `sample_times`: the middle of each of n equal slices of the open
/// shutter) from those at the probes (`moves[k]` at `probe_times`' k-th): each matrix entry straight between the
/// neighbouring probes.
pub fn spread(moves: &[[f64; 6]], n: usize) -> Moves {
    let last = moves.len() - 1;
    (0..n).map(|j| {
        let at = (j as f64 + 0.5) / n as f64 * last as f64;
        let i = (at.floor() as usize).min(last.saturating_sub(1));
        let f = at - i as f64;
        std::array::from_fn(|k| moves[i][k] + (moves[(i + 1).min(last)][k] - moves[i][k]) * f)
    }).collect()
}

/// How many of the `n` sub-frames the layers `ids` (staged per sub-frame) need: one per px the fastest of their corners
/// (and their mattes') travels over the probes (`at_probes`, in order), at least `least` (what moves inside a layer
/// isn't measured, as steps.rs). Their own steps, not the frame's: a still title under a fast pan needs the fewest.
pub fn own_steps(at_probes: &[Item], ids: &[String], least: usize, n: usize) -> usize {
    let places: Vec<_> = at_probes.iter().map(super::hold::places).collect();
    let path = ids.iter().map(|id| places.windows(2).map(|w| match (w[0].get(id.as_str()), w[1].get(id.as_str())) {
        (Some(a), Some(b)) if a.len() == b.len() => a.iter().zip(b).map(|(p, q)| (q.0 - p.0).hypot(q.1 - p.1)).fold(0.0, f64::max),
        _ => f64::INFINITY,
    }).sum::<f64>()).fold(0.0, f64::max);
    if !path.is_finite() {
        return n;
    }
    ((path / super::steps::GAP_PX - 1e-9).ceil() as usize).clamp(least.min(n), n)
}

/// `m` of `n` evenly spread sub-frames, by index (all of them when `m` ≥ `n`).
pub fn pick(m: usize, n: usize) -> Vec<usize> {
    if m >= n {
        return (0..n).collect();
    }
    (0..m).map(|i| (((i as f64 + 0.5) * n as f64 / m as f64) as usize).min(n - 1)).collect()
}

#[cfg(test)]
mod tests {
    #[test]
    fn moves_between_probes_are_read_off_them() {
        let p = super::probe_times(1.0, 30.0, 180.0);
        assert_eq!(p[2], 1.0, "the middle probe is the frame's own time");
        assert!((p[0] - (1.0 - 1.0 / 120.0)).abs() < 1e-12 && (p[4] - (1.0 + 1.0 / 120.0)).abs() < 1e-12, "{p:?}");
        let at = |x: f64| [1.0, 0.0, 0.0, 1.0, x, 0.0];
        // A straight move of 8 px over the open shutter: 4 sub-frames at the middle of each quarter.
        let m = super::spread(&[at(-4.0), at(-2.0), at(0.0), at(2.0), at(4.0)], 4);
        assert_eq!(m.iter().map(|m| m[4]).collect::<Vec<_>>(), vec![-3.0, -1.0, 1.0, 3.0]);
    }

    #[test]
    fn a_pieces_blurs_and_shadows_pad_its_reach() {
        let p = r#"<div style="filter:blur(4px);"><div style="box-shadow:2px -3px 5px rgba(0,0,0,0.5);stroke-width:6"></div></div>"#;
        assert_eq!(super::pad(p), 12.0 + 3.0 * (2.0 + 3.0 + 5.0 + 0.5) + 6.0);
        assert_eq!(super::pad(r#"<div data-glow="8 1;20 0.5" style=""></div>"#), 3.0 * 28.0, "a glow reaches three times its radius");
    }
}
