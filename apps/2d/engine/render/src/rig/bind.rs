//! Binds (RIG.md › Evaluation 4–5): a rigid bind moves, turns and scales its layer by its bone's delta; a bend bind
//! gives its layer a warp mesh skinned to two bones, which the stage writes as the renderer's `<fewarp>` filter
//! primitive (vendor/blitz-paint/src/warp.rs: a grid over the rest rect and each point's deformed place, layer px).

use std::fmt::Write;

use serde_json::{json, Value};

use super::math::{layer_map, Aff, Pt};
use super::pose::{num, text, Pose};
use crate::scene::eval::{props_at, Item};
use crate::scene::Node;

/// The mesh reaches this far past the layer's box (of its longer side), so strokes and shadows travel with it.
const MARGIN: f64 = 0.15;

/// The rig's binds applied to its showing layers (a layer that isn't showing is skipped).
pub fn apply(pose: &Pose, rig: &Node, t: f64, layers: &mut [Item]) {
    for bind in rig.rig.iter().filter(|p| p.kind == "bind") {
        let p = props_at(bind, t);
        let Some(layer) = layers.iter_mut().find(|l| l.id == text(&p, "layer")) else { continue };
        let Some(b1) = pose.index(text(&p, "bone")) else { continue };
        match pose.index(text(&p, "bone2")) {
            None => rigid(layer, pose.delta(b1)),
            Some(b2) => bend(layer, pose, b1, b2, num(&p, "grid").round() as usize, num(&p, "soft")),
        }
    }
}

/// The layer's anchor point (x, y) → D·(x, y); its rotation turns and its scale grows with D.
fn rigid(layer: &mut Item, d: Aff) {
    let (x, y) = d.apply((layer.num("x"), layer.num("y")));
    let (rotation, scale) = (layer.num("rotation") + d.turn(), layer.num("scale") * d.uniform_scale());
    for (f, v) in [("x", x), ("y", y), ("rotation", rotation), ("scale", scale)] {
        layer.props.insert(f.into(), Value::from(v));
    }
}

/// bone2's share of a rig point at signed distance `s` past bone2's pivot: smoothstep over ±soft (a step at 0).
fn weight2(s: f64, soft: f64) -> f64 {
    if soft <= 0.0 {
        return if s >= 0.0 { 1.0 } else { 0.0 };
    }
    let u = ((s + soft) / (2.0 * soft)).clamp(0.0, 1.0);
    u * u * (3.0 - 2.0 * u)
}

/// A `grid × grid` mesh over the layer's box: each point taken to rig px by the layer's transform, moved by
/// w·D_bone + (1−w)·D_bone2, and taken back. Stored as the layer's `warp` (the stage writes it); a layer with no
/// size or a squashed-flat transform gets none (nothing to see).
fn bend(layer: &mut Item, pose: &Pose, b1: usize, b2: usize, grid: usize, soft: f64) {
    let (w, h) = (layer.num("w"), layer.num("h"));
    let m = layer_map(&layer.props);
    let Some(back) = m.inverse() else { return };
    if !(w > 0.0 && h > 0.0) {
        return;
    }
    let (d1, d2) = (pose.delta(b1), pose.delta(b2));
    let joint = pose.rest[b2].origin();
    // "Along the bones": the mean of the two bones' rest directions (the first's alone if they cancel).
    let (r1, r2) = (pose.rest[b1], pose.rest[b2]);
    let (ax, ay) = (r1.a + r2.a, r1.b + r2.b);
    let len = ax.hypot(ay);
    let axis = if len > 1e-9 { (ax / len, ay / len) } else { (r1.a, r1.b) };
    let pad = MARGIN * w.max(h);
    let (rx, ry, rw, rh) = (-pad, -pad, w + 2.0 * pad, h + 2.0 * pad);
    let n = grid.clamp(1, 64);
    let mut pts = String::new();
    for j in 0..=n {
        for i in 0..=n {
            let q = m.apply((rx + rw * i as f64 / n as f64, ry + rh * j as f64 / n as f64));
            let w2 = weight2((q.0 - joint.0) * axis.0 + (q.1 - joint.1) * axis.1, soft);
            let (p1, p2): (Pt, Pt) = (d1.apply(q), d2.apply(q));
            let moved = back.apply((p1.0 + (p2.0 - p1.0) * w2, p1.1 + (p2.1 - p1.1) * w2));
            let _ = write!(pts, "{}{:.3} {:.3}", if pts.is_empty() { "" } else { " " }, moved.0, moved.1);
        }
    }
    layer.props.insert("warp".into(), json!({ "x": rx, "y": ry, "w": rw, "h": rh, "cols": n, "rows": n, "pts": pts }));
}

/// The stage's part of a bent layer: (style for its outer box, the filter's markup), both empty without a warp.
/// The warp is the only primitive of its own filter on the layer's outer box; the layer's blur, glow and shadow
/// are CSS on the boxes inside it, so they are drawn first and bend with it.
pub fn warp_markup(it: &Item) -> (String, String) {
    let Some(w) = it.props.get("warp") else { return (String::new(), String::new()) };
    let id: String = format!("rw-{}", it.id.chars().map(|c| if c.is_ascii_alphanumeric() || c == '_' { c.to_string() } else { format!("-{:x}-", c as u32) }).collect::<String>());
    let n = |f: &str| w[f].as_f64().unwrap_or(0.0);
    let defs = format!(
        "<svg width=\"0\" height=\"0\" style=\"position:absolute;left:0;top:0;\"><defs><filter id=\"{id}\"><fewarp x=\"{:.3}\" y=\"{:.3}\" w=\"{:.3}\" h=\"{:.3}\" cols=\"{}\" rows=\"{}\" pts=\"{}\"/></filter></defs></svg>",
        n("x"), n("y"), n("w"), n("h"), n("cols"), n("rows"), w["pts"].as_str().unwrap_or("")
    );
    (format!("filter:url(#{id});"), defs)
}
