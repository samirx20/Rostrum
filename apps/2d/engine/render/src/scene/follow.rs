//! A text that follows a path layer (`pathLayer`, contract § 4 text), and any layer that rides one (`ridePath`,
//! contract § 4 every layer): the one place a path-layer reference is resolved, per frame. The layer keeps only the
//! path layer's id; at every time `t` it takes that layer's shape (`d`), its box, its transform and its trim window
//! as they are then, so a reshaped, moved, turned or drawn-on path carries the letters, or the rider, with it. A
//! layer and the path it follows sit side by side (same parent); anything else is refused at load.

use serde_json::{Map, Value};

use super::eval::{props_at, Item};
use super::letters::Along;
use super::Node;

type R<T> = Result<T, String>;

/// The path layer's fields a following text takes as its own: its place, box anchor, turn, scale and tilt.
pub const TAKEN: &[&str] = &["x", "y", "anchorX", "anchorY", "rotation", "scale", "scaleX", "scaleY", "tiltX", "tiltY"];

/// The path layer named by `field` (`pathLayer` or `ridePath`): a sibling of `layer`, or a message naming what is wrong.
fn target<'a>(layer: &Node, field: &str, siblings: &'a [Node]) -> R<&'a Node> {
    let want = layer.props[field].as_str().unwrap_or("");
    match siblings.iter().find(|n| n.id == want) {
        Some(n) if n.kind == "path" => Ok(n),
        Some(n) => Err(format!("{}.{field}: follows \"{want}\", which is a {} layer, not a path", layer.id, n.kind)),
        None => Err(format!(
            "{}.{field}: follows the path layer \"{want}\", which is not beside it (deleted, or in another group): pick a path layer in the same group, or clear {field}",
            layer.id
        )),
    }
}

fn names(n: &Node, field: &str) -> bool {
    n.props.get(field).and_then(Value::as_str).is_some_and(|s| !s.is_empty())
}

fn follows(n: &Node) -> bool {
    n.kind == "text" && names(n, "pathLayer")
}

/// A layer riding a path layer: its anchor sits on that path, its own x, y an offset from there.
fn rides(n: &Node) -> bool {
    names(n, "ridePath")
}

/// Refuse a following text whose path layer is missing, isn't a path, or that also has its own `path`; and a rider
/// whose path is missing, isn't a path or itself rides one (no chains), or a text that both follows and rides.
pub fn check(parent: &Node) -> R<()> {
    for l in &parent.layers {
        if rides(l) {
            let path = target(l, "ridePath", &parent.layers)?;
            if rides(path) {
                return Err(format!("{}.ridePath: rides \"{}\", which itself rides a path; a path that is ridden can't ride one", l.id, path.id));
            }
            if follows(l) {
                return Err(format!("{}.ridePath: a text that follows a path layer (pathLayer) already sits on it; clear one of them", l.id));
            }
        }
        if follows(l) {
            target(l, "pathLayer", &parent.layers)?;
            if !l.props["path"].as_str().unwrap_or("").is_empty() {
                return Err(format!("{}.path: a text that follows a path layer (pathLayer) has no path data of its own; clear one of them", l.id));
            }
        }
        check(l)?;
    }
    Ok(())
}

/// Give each following text among `layers` (the children of `parent`, evaluated at `t`) its path layer's shape,
/// box, transform and trim window at `t`, and put each rider on its path layer (checked at load, so the target is there).
pub fn resolve(parent: &Node, layers: &mut [Item], t: f64) {
    for it in layers.iter_mut().filter(|it| rides(it.node)) {
        let Ok(path) = target(it.node, "ridePath", &parent.layers) else { continue };
        let Some((x, y, angle)) = ride(&path.id, &props_at(path, t), it.str("rideAt"), it.num("rideAlong")) else { continue };
        let turn = if it.on("rideTurn") { angle } else { 0.0 };
        for (f, v) in [("x", x), ("y", y), ("rotation", turn)] {
            let own = it.num(f);
            it.props.to_mut().insert(f.into(), Value::from(own + v));
        }
    }
    for it in layers.iter_mut().filter(|it| follows(it.node)) {
        let Ok(path) = target(it.node, "pathLayer", &parent.layers) else { continue };
        let p = props_at(path, t);
        for f in TAKEN {
            it.props.to_mut().insert((*f).into(), p[*f].clone());
        }
        it.props.to_mut().insert("path".into(), p["d"].clone());
        for (to, from) in [("followW", "w"), ("followH", "h"), ("followFrom", "trimStart"), ("followTo", "trimEnd")] {
            it.props.to_mut().insert(to.into(), p[from].clone());
        }
    }
}

/// The trim window (fractions of the path's length) and the box (w, h) of a following text; None otherwise.
pub fn window(it: &Item) -> Option<((f64, f64), (f64, f64))> {
    let n = |f: &str| it.props.get(f).and_then(Value::as_f64);
    Some(((n("followFrom")?.clamp(0.0, 1.0), n("followTo")?.clamp(0.0, 1.0)), (n("followW")?, n("followH")?)))
}

/// Where a rider sits on a path layer whose fields at this time are `p`: the point (in the path's parent, the space
/// x, y are in) and the path's direction there (degrees, in that space). `at`: "end" = the drawn-on tip (trimEnd),
/// "start" = trimStart, "along" = `along` (0..1) of the whole length. The path's box goes to its parent as
/// stage.rs `transform` draws it: anchor, rotation, scale and stretch (tilt and smear are left out). None for a
/// path with no length (nothing to ride: the rider stays at its own x, y).
fn ride(id: &str, p: &Map<String, Value>, at: &str, along: f64) -> Option<(f64, f64, f64)> {
    let n = |f: &str| p.get(f).and_then(Value::as_f64).unwrap_or(0.0);
    let path = Along::new(id, p.get("d")?.as_str()?).ok()?;
    let (s, e) = (n("trimStart").clamp(0.0, 1.0), n("trimEnd").clamp(0.0, 1.0));
    let frac = match at { "start" => s, "along" => along.clamp(0.0, 1.0), _ => e.max(s) };
    let (q, dir) = path.at(frac * path.total);
    let (sx, sy, r) = (n("scale") * n("scaleX"), n("scale") * n("scaleY"), n("rotation").to_radians());
    let place = |vx: f64, vy: f64| {
        let (vx, vy) = (vx * sx, vy * sy);
        (vx * r.cos() - vy * r.sin(), vx * r.sin() + vy * r.cos())
    };
    let (dx, dy) = place(q.x - n("anchorX") * n("w"), q.y - n("anchorY") * n("h"));
    let (tx, ty) = place(dir.to_radians().cos(), dir.to_radians().sin());
    Some((n("x") + dx, n("y") + dy, ty.atan2(tx).to_degrees()))
}
