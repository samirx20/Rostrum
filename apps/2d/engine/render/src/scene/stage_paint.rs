//! Paint on an element (ENGINE_CONTRACT.md § 2 `paint`; rostrum2d/paint_fields.py): the painting kit's picture of
//! the drawing showing now (eval.rs `paintSrc`), stretched over the element's own box and drawn over its own look,
//! inside the layer, so it moves, scales, turns and fades with it, and masks and effects see element and paint
//! together. Kept inside (`paintInside`): the painter draws it `SrcAtop` over the element
//! (`data-track-matte="atop"`, vendor/blitz-paint/src/track_matte.rs), so it shows only where the element itself is
//! drawn: one rule for a shape, a text's letters, a picture and a path.

use super::{percent, Item};

const FULL: &str = "position:absolute;left:0;top:0;width:100%;height:100%;";

/// The picture showing now, if any.
fn src<'a>(it: &'a Item) -> Option<&'a str> {
    it.props.get("paintSrc").and_then(|v| v.as_str()).filter(|s| !s.is_empty())
}

/// Whether the layer has paint showing now (its shadow then follows element and paint: stage.rs).
pub(super) fn shows(it: &Item) -> bool {
    src(it).is_some()
}

/// The element's own look (`own`: its content box markup) with its paint over it; `own` alone with no paint.
pub(super) fn over(it: &Item, own: String) -> String {
    let Some(src) = src(it) else { return own };
    let paint = format!("<div style=\"{FULL}\"><img src=\"/__local_asset?p={}\" style=\"width:100%;height:100%;object-fit:fill;\"></div>", percent(src));
    if it.on("paintInside") {
        format!("<div data-track-matte=\"atop\" style=\"{FULL}\">{paint}{own}</div>")
    } else {
        format!("<div style=\"{FULL}\">{own}{paint}</div>")
    }
}
