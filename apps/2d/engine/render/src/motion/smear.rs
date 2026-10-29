//! Smears (MOTION.md § Smear): a layer stretched along its velocity, an animator's smear frame. The velocity is the
//! layer's own move over the last frame, in its parent's px (x, y after rig binds): (position now − position one
//! frame ago). The stretch k = clamp(1 + amount · max(0, speed − minSpeed) / length, 1, max), where length is the
//! layer's (scaled, turned) box measured along the motion. stage.rs `transform` puts `smear_css` right after the
//! anchor translate, so it acts in the parent's space about the anchor point.

use serde_json::{json, Value};

use crate::scene::eval::Item;

/// The private key the post-pass leaves the measured smear under (read only by `smear_css`).
const KEY: &str = "~smear";

/// Every smearing layer in `it` measured against the same comp one frame earlier (`prev`).
pub(super) fn measure(it: &mut Item, prev: &Item) {
    let me = &*it;
    let measured = me.effects.iter().find(|e| e.kind == "smear").and_then(|s| {
        let p = super::find(prev, me.id)?;
        stretch(me, s, (me.num("x") - p.num("x"), me.num("y") - p.num("y")))
    });
    if let Some(v) = measured {
        it.props.to_mut().insert(KEY.into(), v);
    }
    for l in &mut it.layers {
        measure(l, prev);
    }
}

/// The layer's own box in its px (before its scale): w × h, or a text's estimated from its size and letters
/// (the laid-out box isn't known before layout; `amount` is the control that tunes it). steps.rs measures it too.
pub(super) fn size(it: &Item) -> Option<(f64, f64)> {
    if it.props.contains_key("w") {
        return Some((it.num("w"), it.num("h")));
    }
    if it.kind != "text" {
        return None;
    }
    let body = it.str("body");
    let lines = body.lines().count().max(1) as f64;
    let longest = body.lines().map(|l| l.chars().count()).max().unwrap_or(0) as f64;
    let w = if it.num("boxWidth") > 0.0 { it.num("boxWidth") } else { 0.6 * it.num("size") * longest };
    Some((w, it.num("size") * it.num("lineHeight") * lines))
}

/// The smear for a move `d` (px this frame), or None when it doesn't stretch.
fn stretch(it: &Item, s: &Item, d: (f64, f64)) -> Option<Value> {
    let speed = d.0.hypot(d.1);
    let over = speed - s.num("minSpeed");
    if over <= 0.0 || s.num("amount") <= 0.0 {
        return None;
    }
    let u = (d.0 / speed, d.1 / speed);
    let (w, h) = size(it)?;
    let (sx, sy) = (it.num("scale") * it.num("scaleX"), it.num("scale") * it.num("scaleY"));
    let (ax, ay) = (it.num("anchorX"), it.num("anchorY"));
    let (sin, cos) = it.num("rotation").to_radians().sin_cos();
    // The box's corners about the anchor, scaled and turned as the layer is, measured along the motion.
    let (mut front, mut back) = (f64::MIN, f64::MAX);
    for lx in [-ax * w, (1.0 - ax) * w] {
        for ly in [-ay * h, (1.0 - ay) * h] {
            let (px, py) = (lx * sx, ly * sy);
            let along = (cos * px - sin * py) * u.0 + (sin * px + cos * py) * u.1;
            (front, back) = (front.max(along), back.min(along));
        }
    }
    let length = front - back;
    if length <= 1e-9 {
        return None;
    }
    let k = (1.0 + s.num("amount") * over / length).clamp(1.0, s.num("max").max(1.0));
    if k <= 1.0 + 1e-6 {
        return None;
    }
    let across = if s.on("keepArea") { 1.0 / k } else { 1.0 };
    // Behind: the leading edge stays where it is and the stretch goes back along the path.
    let shift = if s.str("stretch") == "behind" { -(k - 1.0) * front } else { 0.0 };
    Some(json!({ "angle": u.1.atan2(u.0).to_degrees(), "k": k, "across": across, "dx": shift * u.0, "dy": shift * u.1 }))
}

/// The smear's CSS transform for a layer at its time, if it has a smear that stretches it now: along the motion
/// by k (and across by 1/k when it keeps its area), about the anchor, shifted so a trailing smear's front stays.
pub fn smear_css(it: &Item) -> Option<String> {
    let m = it.props.get(KEY)?;
    let n = |f: &str| m[f].as_f64().unwrap_or(0.0);
    let a = n("angle");
    Some(format!("translate({:.3}px, {:.3}px) rotate({a:.4}deg) scale({:.5}, {:.5}) rotate({:.4}deg)", n("dx"), n("dy"), n("k"), n("across"), -a))
}
