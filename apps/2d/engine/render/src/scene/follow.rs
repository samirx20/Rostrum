//! A text that follows a path layer (`pathLayer`, contract § 4 text): the one place the reference is resolved, per
//! frame. The text keeps only the path layer's id; at every time `t` it takes that layer's shape (`d`), its box and
//! its transform as they are then, and its trim window, so a reshaped, moved, turned or drawn-on path carries the
//! letters with it. A text and the path it follows sit side by side (same parent); anything else is refused at load.

use serde_json::Value;

use super::eval::{props_at, Item};
use super::Node;

type R<T> = Result<T, String>;

/// The path layer's fields a following text takes as its own: its place, box anchor, turn, scale and tilt.
pub const TAKEN: &[&str] = &["x", "y", "anchorX", "anchorY", "rotation", "scale", "scaleX", "scaleY", "tiltX", "tiltY"];

/// The path layer a text follows: its sibling named by `pathLayer`, or a message naming what is wrong.
fn target<'a>(text: &Node, siblings: &'a [Node]) -> R<&'a Node> {
    let want = text.props["pathLayer"].as_str().unwrap_or("");
    match siblings.iter().find(|n| n.id == want) {
        Some(n) if n.kind == "path" => Ok(n),
        Some(n) => Err(format!("{}.pathLayer: follows \"{want}\", which is a {} layer, not a path", text.id, n.kind)),
        None => Err(format!(
            "{}.pathLayer: follows the path layer \"{want}\", which is not beside it (deleted, or in another group): pick a path layer in the same group, or clear pathLayer",
            text.id
        )),
    }
}

fn follows(n: &Node) -> bool {
    n.kind == "text" && n.props.get("pathLayer").and_then(Value::as_str).is_some_and(|s| !s.is_empty())
}

/// Refuse a following text whose path layer is missing, isn't a path, or that also has its own `path`.
pub fn check(parent: &Node) -> R<()> {
    for l in &parent.layers {
        if follows(l) {
            target(l, &parent.layers)?;
            if !l.props["path"].as_str().unwrap_or("").is_empty() {
                return Err(format!("{}.path: a text that follows a path layer (pathLayer) has no path data of its own; clear one of them", l.id));
            }
        }
        check(l)?;
    }
    Ok(())
}

/// Give each following text among `layers` (the children of `parent`, evaluated at `t`) its path layer's shape,
/// box, transform and trim window at `t` (checked at load, so the target is there).
pub fn resolve(parent: &Node, layers: &mut [Item], t: f64) {
    for it in layers.iter_mut().filter(|it| follows(it.node)) {
        let Ok(path) = target(it.node, &parent.layers) else { continue };
        let p = props_at(path, t);
        for f in TAKEN {
            it.props.insert((*f).into(), p[*f].clone());
        }
        it.props.insert("path".into(), p["d"].clone());
        for (to, from) in [("followW", "w"), ("followH", "h"), ("followFrom", "trimStart"), ("followTo", "trimEnd")] {
            it.props.insert(to.into(), p[from].clone());
        }
    }
}

/// The trim window (fractions of the path's length) and the box (w, h) of a following text; None otherwise.
pub fn window(it: &Item) -> Option<((f64, f64), (f64, f64))> {
    let n = |f: &str| it.props.get(f).and_then(Value::as_f64);
    Some(((n("followFrom")?.clamp(0.0, 1.0), n("followTo")?.clamp(0.0, 1.0)), (n("followW")?, n("followH")?)))
}
