//! Track mattes (ENGINE_CONTRACT.md § 4 matte): a layer whose `matte` names a sibling layer is seen through that
//! layer's drawing at the same frame: by its alpha or its luma (`matteMode`), or the inverse. The matte layer is
//! drawn only as the matte, never on its own; it animates as usual.
//!
//! The painter draws it (vendor/blitz-paint/src/track_matte.rs): a `data-track-matte` box whose first child holds
//! the matte layer's own markup (stage.rs's one layer drawing, so any layer type is a matte) and whose second holds
//! the matted layer's. A matte outside its times leaves the first child empty: the layer is hidden, or whole when
//! inverted.

use super::eval::Item;
use super::stage::escape;
use super::Node;

#[cfg(test)]
#[path = "matte_tests.rs"]
mod tests;

type R<T> = Result<T, String>;

pub const MODES: &[&str] = &["alpha", "alphaInverted", "luma", "lumaInverted"];

fn matte_of(n: &Node) -> &str {
    n.props.get("matte").and_then(|v| v.as_str()).unwrap_or("")
}

/// Checked when the scene loads and after every edit: each `matte` names another layer beside it (same group or
/// comp), and a matte layer has no matte of its own (so mattes never go round in a loop).
pub fn check(n: &Node) -> R<()> {
    for l in &n.layers {
        let name = matte_of(l);
        if name.is_empty() {
            continue;
        }
        if name == l.id {
            return Err(format!("{}.matte: a layer can't be its own matte", l.id));
        }
        let m = n.layers.iter().find(|s| s.id == name).ok_or_else(|| {
            let beside: Vec<&str> = n.layers.iter().filter(|s| s.id != l.id && s.kind != "camera").map(|s| s.id.as_str()).collect();
            format!("{}.matte: no layer \"{name}\" beside it (a matte is a layer in the same group or comp; beside it: {})", l.id, beside.join(", "))
        })?;
        if m.kind == "camera" {
            return Err(format!("{}.matte: the camera \"{name}\" can't be a matte", l.id));
        }
        if !matte_of(m).is_empty() {
            return Err(format!("{}.matte: \"{name}\" has a matte of its own; a matte layer can't have one", l.id));
        }
    }
    n.layers.iter().try_for_each(check)
}

/// Whether this layer is some sibling's matte (then it isn't drawn on its own). Asked of the scene, not the frame:
/// a matte stays hidden while the layer it shapes is outside its own times.
pub fn used(l: &Item, parent: &Item) -> bool {
    parent.node.layers.iter().any(|s| matte_of(s) == l.id)
}

/// The matte layer `l` names among its parent's layers now (None: outside its times), or no matte at all.
pub fn of<'p, 'a>(l: &Item, parent: &'p Item<'a>) -> Option<Option<&'p Item<'a>>> {
    let name = l.props.get("matte").and_then(|v| v.as_str()).unwrap_or("");
    (!name.is_empty()).then(|| parent.layers.iter().find(|s| s.id == name))
}

/// The matted layer's placed markup seen through the matte's placed markup ("" outside its times). The box holds
/// the layer apart from what is under it, so it carries the layer's blend.
pub fn wrap(l: &Item, matte: &str, layer: String) -> String {
    let blend = super::blends::style(l.str("blend"));
    let full = "position:absolute;left:0;top:0;width:100%;height:100%;";
    format!(
        "<div data-matte=\"{}\" data-track-matte=\"{}\" style=\"{full}{blend}\"><div style=\"{full}\">{matte}</div><div style=\"{full}\">{layer}</div></div>",
        escape(l.str("matte")), l.str("matteMode")
    )
}
