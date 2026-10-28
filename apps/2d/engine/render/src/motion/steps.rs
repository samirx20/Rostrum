//! How many sub-frames a motion-blurred frame takes (MOTION.md › Motion blur › Steps follow the motion). The comp's
//! `shutterSamples` (Blur steps) is the fewest; a frame whose layers move further on screen while the shutter is open
//! gets more, so two neighbouring copies are at most GAP_PX apart (a smooth streak, not a ladder), up to MOST.
//! After Effects' adaptive sample limit works the same way.
//!
//! The move is measured on the evaluated comp (eval.rs `at`, read as a sub-frame of this frame: `shutter_at`, so a cut
//! is never counted as a move), at the edges of `probes` equal slices of the open shutter: each layer's box corners
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
pub fn steps(comp: &Node, t: f64, fps: f64, angle: f64, least: usize) -> usize {
    measure(comp, t, fps, angle, least, false)
}

/// `steps` for the layers' own moves alone: every layer carried to the output through the frame as it stands at `t`
/// (the frame's own move left out). Sub-frames beyond these differ only in where the frame is (scene_serve.rs `buckets`).
pub fn own_steps(comp: &Node, t: f64, fps: f64, angle: f64, least: usize) -> usize {
    measure(comp, t, fps, angle, least, true)
}

fn measure(comp: &Node, t: f64, fps: f64, angle: f64, least: usize, own: bool) -> usize {
    if least >= MOST {
        return least;
    }
    let probes = least.clamp(2, 16);
    let open = angle / 360.0 / fps;
    let centre = if own { eval::shutter_at(t, t, || eval::at(comp, t)) } else { None };
    let still = centre.as_ref().and_then(|c| View::of(c).ok());
    let corners: Vec<HashMap<(&str, usize), Pt>> = (0..=probes)
        .map(|k| {
            let at = t + open * (k as f64 / probes as f64 - 0.5);
            eval::shutter_at(t, at, || eval::at(comp, at)).map_or_else(HashMap::new, |c| on_screen(&c, still.as_ref()))
        })
        .collect();
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
    let need = (fastest * probes as f64 / GAP_PX - 1e-9).ceil();
    if !need.is_finite() {
        return MOST;
    }
    (need as usize).clamp(least, MOST)
}

/// Every layer's box corners (its anchor alone when it has no box) in output px, by (layer id, corner).
/// `view`: the frame to carry them through (None: the comp's own at its time).
fn on_screen<'a>(comp: &Item<'a>, view: Option<&View>) -> HashMap<(&'a str, usize), Pt> {
    let own = if view.is_none() { View::of(comp).ok() } else { None };
    let view = view.or(own.as_ref());
    let mut out = HashMap::new();
    for l in comp.layers.iter().filter(|l| l.kind != "camera") {
        let m = view.map_or(Aff::ID, |v| v.map(l));
        corners(l, m, &mut out);
    }
    out
}

fn corners<'a>(it: &Item<'a>, parent: Aff, out: &mut HashMap<(&'a str, usize), Pt>) {
    let n = |f: &str, d: f64| it.props.get(f).and_then(serde_json::Value::as_f64).unwrap_or(d);
    let (w, h) = super::smear::size(it).unwrap_or((0.0, 0.0));
    let (ax, ay) = (n("anchorX", 0.5) * w, n("anchorY", 0.5) * h);
    // stage.rs `layer`: the anchor point lands on (x, y); the layer turns and scales about it.
    let s = n("scale", 1.0);
    let m = parent
        * Aff::translate(n("x", 0.0), n("y", 0.0))
        * Aff::rotate(n("rotation", 0.0))
        * Aff::scale(s * n("scaleX", 1.0), s * n("scaleY", 1.0))
        * Aff::translate(-ax, -ay);
    for (i, p) in [(0.0, 0.0), (w, 0.0), (0.0, h), (w, h)].into_iter().enumerate() {
        out.insert((it.id, i), m.apply(p));
    }
    for c in &it.layers {
        corners(c, m, out);
    }
}
