//! How many sub-frames a motion-blurred frame takes (MOTION.md › Motion blur › Steps follow the motion). The comp's
//! `shutterSamples` (Blur steps) is the fewest; a frame whose layers move further on screen while the shutter is open
//! gets more, so two neighbouring copies are at most GAP_PX apart (a smooth streak, not a ladder), up to MOST.
//! After Effects' adaptive sample limit works the same way.
//!
//! The move is measured on the evaluated comp (eval.rs `at`, read as a sub-frame of this frame: `shutter_at`, so a cut
//! is never counted as a move), at the edges of four equal slices of the open shutter (the probes streak.rs reads too): each layer's box corners
//! carried to the output through its own place, turn and scale, its groups' and the frame's (frame/mod.rs `map`).
//! The fastest slice of the fastest layer decides. What happens inside a layer (a path's shape, letters, a rig's
//! warp) is not measured: those keep the fewest steps.

use std::collections::HashMap;

use crate::frame::View;
use crate::rig::math::{Aff, Pt};
use crate::scene::eval::{self, Item};
use crate::scene::Node;

/// The farthest two neighbouring copies may be apart, in output px.
pub const GAP_PX: f64 = 1.0;
/// The most sub-frames a frame ever takes (After Effects' adaptive limit tops out at 256; 128 keeps a frame under
/// about 16 times its 8-step cost).
pub const MOST: usize = 128;

/// The sub-frames for the frame at `t`: at least `least`, more when something moves further than GAP_PX × `least`
/// on screen while the shutter (`angle` degrees at `fps`) is open.
#[cfg(test)]
pub fn steps(comp: &Node, t: f64, fps: f64, angle: f64, least: usize) -> usize {
    if least >= MOST {
        return least;
    }
    let probes: Vec<Item> = super::streak::probe_times(t, fps, angle)
        .into_iter()
        .filter_map(|at| eval::shutter_at(t, at, || eval::at(comp, at)))
        .collect();
    from_probes(&probes, least)
}

/// `steps` from the comp evaluated at the edges of equal slices of the open shutter, in order (streak.rs
/// `probe_times`: the frame's motion blur evaluates them once, for its steps and its streaks alike).
pub fn from_probes(probes: &[Item], least: usize) -> usize {
    if least >= MOST || probes.len() < 2 {
        return least;
    }
    let corners: Vec<HashMap<(&str, usize), Pt>> = probes.iter().map(on_screen).collect();
    // The most any corner moves across one slice (a layer showing on one side only has no move to measure).
    let mut fastest: f64 = 0.0;
    for pair in corners.windows(2) {
        for (key, p) in &pair[0] {
            if let Some(q) = pair[1].get(key) {
                fastest = fastest.max((q.0 - p.0).hypot(q.1 - p.1));
            }
        }
    }
    // px per slice × slices = px per shutter at that speed; one step per GAP_PX of it.
    let need = (fastest * (probes.len() - 1) as f64 / GAP_PX - 1e-9).ceil();
    if !need.is_finite() {
        return MOST;
    }
    (need as usize).clamp(least, MOST)
}

/// Every layer's box corners (its anchor alone when it has no box) in output px, by (layer id, corner).
fn on_screen<'a>(comp: &Item<'a>) -> HashMap<(&'a str, usize), Pt> {
    let view = View::of(comp).ok();
    let view = view.as_ref();
    let mut out = HashMap::new();
    for l in comp.layers.iter().filter(|l| l.kind != "camera") {
        let m = view.map_or(Aff::ID, |v| v.map(l));
        corners(l, m, &mut out);
    }
    out
}

pub(super) fn corners<'a>(it: &Item<'a>, parent: Aff, out: &mut HashMap<(&'a str, usize), Pt>) {
    let (m, (w, h)) = (parent * local(it), super::smear::size(it).unwrap_or((0.0, 0.0)));
    for (i, p) in [(0.0, 0.0), (w, 0.0), (0.0, h), (w, h)].into_iter().enumerate() {
        out.insert((it.id, i), m.apply(p));
    }
    for c in &it.layers {
        corners(c, m, out);
    }
}

/// The most the layer or any of its children is stretched on screen (`parent`: its frame's; the largest singular value
/// of each one's place, turn and scale, as `corners` carries them): how far its own blurs and shadows reach, scaled.
pub(super) fn widest(it: &Item, parent: Aff) -> f64 {
    let m = parent * local(it);
    let sum = m.a * m.a + m.b * m.b + m.c * m.c + m.d * m.d;
    let det = m.a * m.d - m.b * m.c;
    let own = ((sum + (sum * sum - 4.0 * det * det).max(0.0).sqrt()) / 2.0).sqrt();
    it.layers.iter().map(|c| widest(c, m)).fold(own, f64::max)
}

/// A layer's own place, turn and scale (stage.rs `layer`): the anchor point lands on (x, y); the layer turns and scales
/// about it.
pub(super) fn local(it: &Item) -> Aff {
    let n = |f: &str, d: f64| it.props.get(f).and_then(serde_json::Value::as_f64).unwrap_or(d);
    let (w, h) = super::smear::size(it).unwrap_or((0.0, 0.0));
    let (ax, ay) = (n("anchorX", 0.5) * w, n("anchorY", 0.5) * h);
    let s = n("scale", 1.0);
    Aff::translate(n("x", 0.0), n("y", 0.0)) * Aff::rotate(n("rotation", 0.0)) * Aff::scale(s * n("scaleX", 1.0), s * n("scaleY", 1.0)) * Aff::translate(-ax, -ay)
}
